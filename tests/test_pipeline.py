import pytest

from shorts_printer import config, jobs, pipeline, video, worker
from shorts_printer.jobs import STEPS, Job, atomic_write_json, read_json


def stub_steps(monkeypatch, fail=None):
    ran = []

    def make(name):
        def step(job):
            ran.append(name)
            if name == fail:
                raise RuntimeError("일부러 sk-ant-SECRET 실패")
            return f"{name}-engine"
        return step

    monkeypatch.setattr(pipeline, "RUN", {s: make(s) for s in STEPS})
    return ran


def test_failure_is_recorded_redacted_then_retry_resumes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    job = Job.create("주제", "ko-KR-SunHiNeural")
    ran = stub_steps(monkeypatch, fail="voice")
    with pytest.raises(RuntimeError):
        pipeline.run(job)
    d = job.data
    assert d["status"] == "failed" and d["error"]["step"] == "voice"
    assert "SECRET" not in d["error"]["message"] and "SECRET" not in (job.dir / "log.txt").read_text()
    assert [d["steps"][s]["status"] for s in STEPS] == ["done", "failed", "pending", "pending", "pending", "pending"]

    ran = stub_steps(monkeypatch)
    pipeline.run(job)
    assert ran == ["voice", "subtitles", "footage", "thumbnail", "render"]   # 끝난 단계는 건너뛴다
    d = job.data
    assert d["status"] == "done" and d["error"] is None and d["steps"]["render"]["engine"] == "render-engine"


def scene_job(*done):
    """문장 2개짜리 대본·음성 시각이 있는 작업."""
    job = Job.create("주제", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", {"sentences": ["하나", "둘"], "prompts": ["p1", "p2"],
                                                "search_terms": ["cat", "dog"]})
    atomic_write_json(job.dir / "timing.json", [{"start": 0, "end": 1.2}, {"start": 1.3, "end": 2.5}])
    for s in done:
        job.step(s, status="done")
    return job


def test_footage_waits_for_clips_then_resumes(monkeypatch):
    monkeypatch.setattr(config, "VIDEO", "flow")   # .env의 SP_VIDEO와 상관없이
    job = scene_job("script", "voice", "subtitles")
    ran = stub_steps(monkeypatch)
    monkeypatch.setitem(pipeline.RUN, "footage", pipeline.step_footage)
    pipeline.run(job)
    d = job.data
    assert d["status"] == "waiting" and d["steps"]["footage"]["status"] == "pending" and ran == [] and d["error"] is None
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    pipeline.run(job)
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"


def test_sensitive_script_waits_for_confirm_before_footage(monkeypatch):
    monkeypatch.setattr(config, "VIDEO", "flow")
    job = scene_job("script", "voice", "subtitles")
    atomic_write_json(job.dir / "script.json", read_json(job.dir / "script.json") | {"sensitive": "건강·의료"})
    for i in (0, 1):
        (job.dir / "clips").mkdir(exist_ok=True)
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    ran = stub_steps(monkeypatch)
    monkeypatch.setitem(pipeline.RUN, "footage", pipeline.step_footage)
    pipeline.run(job)
    assert job.data["status"] == "waiting" and ran == [] and "민감 분야(건강·의료)" in (job.dir / "log.txt").read_text()
    job.update(confirmed=True)
    pipeline.run(job)
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"
    assert read_json(job.dir / "clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"},
                                                 {"file": "clip1.mp4", "source": "직접 올림"}]


def test_auto_provider_fills_what_it_can_then_waits(monkeypatch):
    class Fake:
        label, hint = "Fake", ""

        def __init__(self):
            self.calls = []

        def ready(self):
            return True

        def make(self, scenes, out, log):
            self.calls.append([s["i"] for s in scenes])
            if scenes and scenes[0]["i"] == 0:
                (out / "clip0.mp4").write_bytes(b"x")
                yield {"file": "clip0.mp4", "source": "Fake", "sec": scenes[0]["sec"]}

    fake = Fake()
    monkeypatch.setitem(video.VIDEO, "fake", fake)
    monkeypatch.setattr(config, "VIDEO", "fake")
    job = scene_job("script", "voice", "subtitles")
    with pytest.raises(pipeline.Wait):
        pipeline.step_footage(job)
    assert read_json(job.dir / "clips.json") == [{"file": "clip0.mp4", "source": "Fake", "sec": pytest.approx(1.3, abs=0.04)}]
    (job.dir / "clips" / "clip1.mp4").write_bytes(b"x")
    video.set_clip(job.dir, {"file": "clip1.mp4", "source": "직접 올림"})
    assert pipeline.step_footage(job) == "Fake 2개"
    assert fake.calls == [[0, 1], []]   # 있는 장면은 다시 안 만든다
    assert [c["source"] for c in read_json(job.dir / "clips.json")] == ["Fake", "직접 올림"]


def test_default_video_falls_back_to_flow(monkeypatch):
    monkeypatch.setattr(config, "VIDEO", "stock")
    assert video.default() == "flow"
    monkeypatch.setattr(config, "VIDEO", "nope")
    assert video.default() == "flow"
    monkeypatch.setattr(config, "VIDEO", "flow-auto")   # Chrome이 없는 기계면 Flow(직접 올림)
    monkeypatch.setattr(video.flow_auto, "CHROME", "/nope")
    assert video.default() == "flow"


def test_redact_hides_any_api_key_by_suffix(monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "sd-SECRET-123")
    assert jobs.redact("x sd-SECRET-123 y") == "x *** y"
    monkeypatch.setenv("SHORT_API_KEY", "ab")
    assert "ab" in jobs.redact("ab")   # 짧은 값은 가리지 않는다


def test_redo_steps():
    job = scene_job(*STEPS)
    job.update(status="failed")
    assert worker.redo(job.id, ("render",))
    d = Job.load(job.id).data
    assert d["status"] == "queued" and d["steps"]["render"]["status"] == "pending" and d["steps"]["thumbnail"]["status"] == "done"
    assert worker._q.get_nowait() == ("run", job.id)


def test_script_step_passes_brief_from_trend_pick(monkeypatch):
    job = Job.create("주제", "ko-KR-SunHiNeural", brief="질문으로 시작", source={"trend": "t1", "pick": 0})
    assert job.data["brief"] == "질문으로 시작" and job.data["source"] == {"trend": "t1", "pick": 0}
    seen = []

    def write(topic, brief=None, recent=()):
        seen.append((topic, brief, recent))
        raise RuntimeError("여기까지만")
    monkeypatch.setattr(pipeline.script, "write", write)
    with pytest.raises(RuntimeError):
        pipeline.step_script(job)
    other = Job.create("예전", "ko-KR-SunHiNeural")
    atomic_write_json(other.dir / "script.json", {"title": "라면의 진짜 이유", "sentences": ["x"]})
    with pytest.raises(RuntimeError):
        pipeline.step_script(job)
    assert seen == [("주제", "질문으로 시작", []), ("주제", "질문으로 시작", ["라면의 진짜 이유"])]


def test_script_step_revises_when_note(monkeypatch):
    job = scene_job(*STEPS)
    job.update(script_note="더 짧게", usage={"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01})
    monkeypatch.setattr(pipeline.script, "write", lambda *a: pytest.fail("새로 쓰면 장면이 바뀐다"))
    monkeypatch.setattr(pipeline.script, "revise", lambda s, note: (
        s | {"sentences": ["짧게", "둘"]}, {"model": "m", "input_tokens": 2, "output_tokens": 2, "cost_usd": 0.02}))
    assert pipeline.step_script(job) == "m"
    assert read_json(job.dir / "script.json")["prompts"] == ["p1", "p2"] and job.data["usage"]["cost_usd"] == 0.03


def test_flow_auto_retries_failed_scene_once_after_delay(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    import playwright.sync_api

    fa = video.flow_auto
    monkeypatch.setattr(fa, "open_chrome", lambda: None)
    monkeypatch.setattr(fa, "_settings", lambda page: None)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", MagicMock())
    slept = []
    monkeypatch.setattr(fa.time, "sleep", slept.append)
    tries = []

    def gen(page, prompt, path):   # 장면 a는 계속, b는 처음 한 번만 실패
        tries.append(prompt)
        if prompt == "a" or (prompt == "b" and tries.count("b") == 1):
            raise RuntimeError("화면이 바뀜")

    monkeypatch.setattr(fa, "_generate", gen)
    scenes = [{"i": i, "prompt": p, "file": f"{p}.mp4"} for i, p in enumerate("abc")]
    logs = []
    got = [c["file"] for c in fa.FlowAuto().make(scenes, tmp_path, logs.append)]
    assert tries == ["a", "b", "c", "a", "b"]   # 실패한 장면만 딱 한 번 더
    assert got == ["c.mp4", "b.mp4"] and len(slept) == 2 and 0 < slept[0] <= fa.RETRY_AFTER
    assert "직접 올려 주세요" in logs[-2] and "다시 시도해 완료" in logs[-1]

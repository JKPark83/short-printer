from dataclasses import replace
from types import SimpleNamespace

import pytest

from shorts_printer import registry
from shorts_printer.adapters import flow_auto
from shorts_printer.adapters.flow import Flow
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.core import channel, pipeline, scenes, trends
from shorts_printer.core.pipeline import STEPS, Job
from shorts_printer.core.services import Services
from shorts_printer.infra import store
from shorts_printer.infra.worker import LocalQueue

CH = "ko-40sec-facts"


class Publisher:
    label, hint = "가짜올림", ""

    def __init__(self, fail_thumb=False):
        self.sent, self.thumbs, self.fail_thumb = [], [], fail_thumb

    def ready(self):
        return True

    def upload(self, path, meta, log):
        self.sent.append((path.name, meta))
        return "VID"

    def set_thumbnail(self, video_id, path):
        if self.fail_thumb:
            raise RuntimeError("forbidden")
        self.thumbs.append((video_id, path.name))


def services(**kw) -> Services:
    """작은 가짜로 묶은 Services. 쓰지 않는 공급자는 None."""
    return Services(**{"channel": channel.load(CH), "llm": None, "tts": None, "video": Flow(),
                       "publisher": Publisher(), "splitter": Korean()} | kw)


def stub_steps(monkeypatch, fail=None):
    ran = []

    def make(name):
        def step(job, sv):
            ran.append(name)
            if name == fail:
                raise RuntimeError("일부러 sk-ant-SECRET 실패")
            return f"{name}-engine"
        return step

    monkeypatch.setattr(pipeline, "RUN", {s: make(s) for s in STEPS})
    return ran


def test_failure_is_recorded_redacted_then_retry_resumes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    job = Job.create(CH, "주제", "ko-KR-SunHiNeural")
    assert job.data["channel"] == CH
    ran = stub_steps(monkeypatch, fail="voice")
    with pytest.raises(RuntimeError):
        pipeline.run(job, services())
    d = job.data
    assert d["status"] == "failed" and d["error"]["step"] == "voice"
    assert "SECRET" not in d["error"]["message"] and "SECRET" not in "\n".join(job.tail())
    assert [d["steps"][s]["status"] for s in STEPS] == ["done", "failed", "pending", "pending", "pending", "pending"]

    ran = stub_steps(monkeypatch)
    pipeline.run(job, services())
    assert ran == ["voice", "subtitles", "footage", "thumbnail", "render"]   # 끝난 단계는 건너뛴다
    d = job.data
    assert d["status"] == "done" and d["error"] is None and d["steps"]["render"]["engine"] == "render-engine"


def scene_job(*done, ch=CH):
    """문장 2개짜리 대본·음성 시각이 있는 작업."""
    job = Job.create(ch, "주제", "ko-KR-SunHiNeural")
    job.put("script.json", {"sentences": ["하나", "둘"], "prompts": ["p1", "p2"],
                                                "search_terms": ["cat", "dog"]})
    job.put("timing.json", [{"start": 0, "end": 1.2}, {"start": 1.3, "end": 2.5}])
    for s in done:
        job.step(s, status="done")
    return job


def test_review_job_waits_for_confirmed_script():
    job = Job.create(CH, "주제", "ko-KR-SunHiNeural", review=True)
    job.step("script", status="done")
    with pytest.raises(pipeline.Wait):   # 확정 전엔 음성(크레딧)부터 멈춘다
        pipeline.step_voice(job, services())
    job.update(status="waiting")
    assert pipeline.in_review(job.data)
    job.update(confirmed=True)
    assert not pipeline.in_review(job.data)
    assert not pipeline.in_review(Job.create(CH, "주제", "v").data | {"status": "waiting"})   # 스케줄·CLI는 안 멈춘다


def footage_only(monkeypatch):
    ran = stub_steps(monkeypatch)
    monkeypatch.setitem(pipeline.RUN, "footage", pipeline.step_footage)
    return ran


def test_footage_waits_for_clips_then_resumes(monkeypatch):
    job = scene_job("script", "voice", "subtitles")
    ran = footage_only(monkeypatch)
    pipeline.run(job, services())
    d = job.data
    assert d["status"] == "waiting" and d["steps"]["footage"]["status"] == "pending"
    assert ran == [] and d["error"] is None
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    pipeline.run(job, services())
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"


def sensitive_job():
    job = scene_job("script", "voice", "subtitles")
    job.put("script.json", job.doc("script.json") | {"sensitive": "건강·의료"})
    (job.dir / "clips").mkdir()
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    return job


def test_sensitive_script_waits_for_confirm_before_footage(monkeypatch):
    job = sensitive_job()
    ran = footage_only(monkeypatch)
    pipeline.run(job, services())
    assert job.data["status"] == "waiting" and ran == [] and "민감 분야(건강·의료)" in "\n".join(job.tail())
    job.update(confirmed=True)
    pipeline.run(job, services())
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"
    assert job.doc("clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"},
                                                 {"file": "clip1.mp4", "source": "직접 올림"}]


def test_sensitive_gate_off_skips_the_wait(monkeypatch):
    job = sensitive_job()
    ran = footage_only(monkeypatch)
    pipeline.run(job, services(channel=channel.load(CH).model_copy(update={"sensitive_gate": False})))
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"


def test_auto_provider_fills_what_it_can_then_waits():
    class Fake:
        label, hint = "Fake", ""

        def __init__(self):
            self.calls = []

        def ready(self):
            return True

        def make(self, todo, out, log):
            self.calls.append([s["i"] for s in todo])
            if todo and todo[0]["i"] == 0:
                (out / "clip0.mp4").write_bytes(b"x")
                yield {"file": "clip0.mp4", "source": "Fake", "sec": todo[0]["sec"]}

    fake = Fake()
    sv = services(video=fake)
    job = scene_job("script", "voice", "subtitles")
    with pytest.raises(pipeline.Wait):
        pipeline.step_footage(job, sv)
    sec = pytest.approx(1.3, abs=0.04)
    assert job.doc("clips.json") == [{"file": "clip0.mp4", "source": "Fake", "sec": sec}]
    (job.dir / "clips" / "clip1.mp4").write_bytes(b"x")
    scenes.set_clip(job, {"file": "clip1.mp4", "source": "직접 올림"})
    assert pipeline.step_footage(job, sv) == "Fake 2개"
    assert fake.calls == [[0, 1], []]   # 있는 장면은 다시 안 만든다
    assert [c["source"] for c in job.doc("clips.json")] == ["Fake", "직접 올림"]


def test_flow_auto_without_chrome_falls_back_to_flow(monkeypatch):
    ch = channel.load(CH)
    ch = ch.model_copy(update={"video": ch.video.model_copy(update={"provider": "flow-auto"})})
    monkeypatch.setattr(flow_auto, "CHROME", "/nope")   # Chrome이 없는 기계면 Flow(직접 올림)
    assert registry.video(ch)[0] == "flow"


def test_redact_hides_any_api_key_by_suffix(monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "sd-SECRET-123")
    assert store.redact("x sd-SECRET-123 y") == "x *** y"
    monkeypatch.setenv("SHORT_API_KEY", "ab")
    assert "ab" in store.redact("ab")   # 짧은 값은 가리지 않는다


def test_redo_steps():
    q = LocalQueue(lambda cid: pytest.fail("넣기만 하면 Services를 찾지 않는다"))
    job = scene_job(*STEPS)
    job.update(status="failed")
    assert q.redo(job.id, ("render",))
    d = Job.load(job.id).data
    assert d["status"] == "queued" and d["steps"]["render"]["status"] == "pending"
    assert d["steps"]["thumbnail"]["status"] == "done"
    assert q._q.get_nowait() == ("run", job.id)


def test_queue_resolves_services_by_job_channel(monkeypatch):
    seen, got = [], []
    q = LocalQueue(lambda cid: seen.append(cid) or SimpleNamespace(cid=cid))
    monkeypatch.setattr(pipeline, "run", lambda job, sv: got.append(("run", job.id, sv.cid)))
    monkeypatch.setattr(pipeline, "publish", lambda job, sv: got.append(("upload", job.id, sv.cid)))
    monkeypatch.setattr(trends, "run", lambda t, sv: got.append(("trend", t.id, sv.cid)))
    a, b, t = Job.create("ch-a", "주제", "v"), Job.create("ch-b", "주제", "v"), trends.Trend.create("ch-c")
    q.run_one(a.id)
    q.run_one(b.id, "upload")
    q.run_one(t.id, "trend")
    assert seen == ["ch-a", "ch-b", "ch-c"]
    assert got == [("run", a.id, "ch-a"), ("upload", b.id, "ch-b"), ("trend", t.id, "ch-c")]


def test_queue_marks_failed_when_channel_cannot_resolve():
    def resolve(cid):
        raise KeyError("채널이 없어요")
    q = LocalQueue(resolve)
    a, b, t = Job.create("gone", "주제", "v"), Job.create("gone", "주제", "v"), trends.Trend.create("gone")
    q.run_one(a.id)
    q.run_one(b.id, "upload")
    q.run_one(t.id, "trend")
    assert Job.load(a.id).data["status"] == "failed" and "채널이 없어요" in Job.load(a.id).data["error"]["message"]
    assert Job.load(b.id).data["upload"]["status"] == "failed"
    assert trends.Trend.load(t.id).data["status"] == "failed"
    assert q.enqueue(a.id) and q.enqueue_trend(t.id)   # queued에 갇히지 않아 다시 넣을 수 있다


def test_script_step_passes_brief_and_recent_titles_of_same_channel(monkeypatch):
    job = Job.create(CH, "주제", "ko-KR-SunHiNeural", brief="질문으로 시작", source={"trend": "t1", "pick": 0})
    assert job.data["brief"] == "질문으로 시작" and job.data["source"] == {"trend": "t1", "pick": 0}
    seen = []

    def write(llm, ch, topic, brief=None, recent=()):
        seen.append((ch.id, topic, brief, recent))
        raise RuntimeError("여기까지만")
    monkeypatch.setattr(pipeline.script, "write", write)
    with pytest.raises(RuntimeError):
        pipeline.step_script(job, services())
    for cid, title in ((CH, "라면의 진짜 이유"), ("en-other", "Other channel title")):
        other = Job.create(cid, "예전", "v")
        other.put("script.json", {"title": title, "sentences": ["x"]})
    with pytest.raises(RuntimeError):
        pipeline.step_script(job, services())
    assert seen == [(CH, "주제", "질문으로 시작", []), (CH, "주제", "질문으로 시작", ["라면의 진짜 이유"])]


def test_script_step_revises_when_note(monkeypatch):
    job = scene_job(*STEPS)
    job.update(script_note="더 짧게", usage={"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01})
    monkeypatch.setattr(pipeline.script, "write", lambda *a: pytest.fail("새로 쓰면 장면이 바뀐다"))
    monkeypatch.setattr(pipeline.script, "revise", lambda llm, ch, s, note, **kw: (
        s | {"sentences": ["짧게", "둘"]}, {"model": "m", "input_tokens": 2, "output_tokens": 2, "cost_usd": 0.02}))
    assert pipeline.step_script(job, services()) == "m"
    assert job.doc("script.json")["prompts"] == ["p1", "p2"] and job.data["usage"]["cost_usd"] == 0.03


def test_publish_uses_channel_publisher():
    job = scene_job(*STEPS)
    meta = {"title": "제목", "description": "설명", "tags": ["a"]}
    job.put("script.json", meta | {"sentences": ["x"]})
    (job.dir / "thumbnail.jpg").write_bytes(b"JPG")
    sv = services()
    pipeline.publish(job, sv)
    assert sv.publisher.sent == [("final.mp4", meta)]
    assert sv.publisher.thumbs == [("VID", "thumbnail.jpg")]
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and up["note"] is None
    assert "가짜올림 업로드 완료: VID (비공개)" in "\n".join(job.tail())

    sv = replace(sv, publisher=Publisher(fail_thumb=True))   # 썸네일 실패는 업로드를 실패로 두지 않는다
    pipeline.publish(job, sv)
    up = job.data["upload"]
    assert up["status"] == "done" and "forbidden" in up["note"] and "가짜올림에서" in up["note"]


def test_publish_appends_channel_footer_to_description():
    job = scene_job(*STEPS)
    s = {"title": "제목", "description": "설명\n", "tags": [], "sentences": ["x"]}
    job.put("script.json", s)
    ch = channel.load(CH)
    sv = services(channel=ch.model_copy(update={"publish": ch.publish.model_copy(update={"footer": "※AI 이미지"})}))
    pipeline.publish(job, sv)
    assert sv.publisher.sent[0][1]["description"] == "설명\n\n※AI 이미지"


def test_flow_auto_retries_failed_scene_once_after_delay(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    import playwright.sync_api

    fa = flow_auto
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
    todo = [{"i": i, "prompt": p, "file": f"{p}.mp4"} for i, p in enumerate("abc")]
    logs = []
    got = [c["file"] for c in fa.FlowAuto().make(todo, tmp_path, logs.append)]
    assert tries == ["a", "b", "c", "a", "b"]   # 실패한 장면만 딱 한 번 더
    assert got == ["c.mp4", "b.mp4"] and len(slept) == 2 and 0 < slept[0] <= fa.RETRY_AFTER
    assert "직접 올려 주세요" in logs[-2] and "다시 시도해 완료" in logs[-1]

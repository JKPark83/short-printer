import pytest

from shorts_printer import pipeline
from shorts_printer.jobs import STEPS, Job


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
    assert [d["steps"][s]["status"] for s in STEPS] == ["done", "done", "failed", "pending", "pending", "pending"]

    ran = stub_steps(monkeypatch)
    pipeline.run(job)
    assert ran == ["voice", "subtitles", "thumbnail", "render"]   # 끝난 단계는 건너뛴다
    d = job.data
    assert d["status"] == "done" and d["error"] is None and d["steps"]["render"]["engine"] == "render-engine"


def test_footage_without_keys_adds_notice_once(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    job = Job.create("주제", "ko-KR-SunHiNeural")
    assert pipeline.step_footage(job) == "그라데이션"
    pipeline.step_footage(job)
    assert len(job.data["notices"]) == 1 and (job.dir / "clips.json").read_text() == "[]"


def test_script_step_passes_brief_from_trend_pick(monkeypatch):
    job = Job.create("주제", "ko-KR-SunHiNeural", brief="질문으로 시작", source={"trend": "t1", "pick": 0})
    assert job.data["brief"] == "질문으로 시작" and job.data["source"] == {"trend": "t1", "pick": 0}
    seen = []

    def write(topic, brief=None):
        seen.append((topic, brief))
        raise RuntimeError("여기까지만")
    monkeypatch.setattr(pipeline.script, "write", write)
    with pytest.raises(RuntimeError):
        pipeline.step_script(job)
    assert seen == [("주제", "질문으로 시작")]

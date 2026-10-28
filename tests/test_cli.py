"""cli: approve가 취소를 풀고 승인하는지, 취소로 멈추면 완성이라 하지 않는지, 공급자 오류는 작업 없이 바로 끝나는지,
upload가 완성 작업만 화면과 같은 길로 올리는지."""
import sys

import pytest
from test_pipeline import CH, services

from shorts_printer import cli, registry
from shorts_printer.core import pipeline
from shorts_printer.core.pipeline import Job


def sp(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["sp", *args])
    cli.main()


def test_approve_clears_cancel_and_interrupted_run_exits(monkeypatch, capsys):
    job = Job.create(CH, "주제", "v", long=True)
    job.update(status="interrupted", cancel=True)
    seen = []

    def run(j, sv):
        seen.append((j.data["cancel"], j.data["script_ok"]))
        j.update(status="interrupted")
    monkeypatch.setattr(registry, "services", lambda cid: services())
    monkeypatch.setattr(pipeline, "run", run)
    with pytest.raises(SystemExit, match="취소돼 멈췄어요"):
        sp(monkeypatch, "approve", job.id, "script")
    assert seen == [(None, True)] and "완성" not in capsys.readouterr().out


def test_bad_provider_exits_before_job(monkeypatch):
    def boom(cid):
        raise RuntimeError("모르는 영상 공급자예요: x (가능: flow)")
    monkeypatch.setattr(registry, "services", boom)
    monkeypatch.setattr(Job, "create", lambda *a, **k: pytest.fail("작업을 만들면 안 된다"))
    with pytest.raises(SystemExit, match="모르는 영상 공급자예요"):
        sp(monkeypatch, "run", "주제", "--channel", CH)


def test_upload_only_done_jobs_through_queue_path(monkeypatch, capsys):
    sv = services()
    monkeypatch.setattr(registry, "services", lambda cid: sv)
    monkeypatch.setattr(registry, "notify", lambda text: [])
    job = Job.create(CH, "주제", "v", long=True)
    job.put("script.json", {"title": "제목", "description": "설명", "tags": ["a"], "sentences": ["x"]})
    job.update(status="waiting")
    with pytest.raises(SystemExit, match="완성된 영상만 올릴 수 있어요"):   # 최종 검수 전에는 못 올린다
        sp(monkeypatch, "upload", job.id)
    assert sv.publisher.sent == []

    job.update(status="done")
    sp(monkeypatch, "upload", job.id)
    assert [name for name, _ in sv.publisher.sent] == ["final.mp4"]
    assert job.data["upload"]["status"] == "done" and "업로드 완료: https://v/VID" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="이미 올렸어요"):
        sp(monkeypatch, "upload", job.id)
    assert len(sv.publisher.sent) == 1


def test_upload_failure_exits_with_error(monkeypatch):
    sv = services()

    def boom(path, meta, log):
        raise RuntimeError("quotaExceeded")
    sv.publisher.upload = boom
    monkeypatch.setattr(registry, "services", lambda cid: sv)
    monkeypatch.setattr(registry, "notify", lambda text: [])
    job = Job.create(CH, "주제", "v")
    job.put("script.json", {"title": "제목", "description": "설명", "tags": [], "sentences": ["x"]})
    job.update(status="done")
    with pytest.raises(SystemExit, match="업로드 실패: quotaExceeded"):
        sp(monkeypatch, "upload", job.id)
    assert job.data["upload"]["status"] == "failed"

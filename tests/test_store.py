import threading

import pytest

from shorts_printer import config
from shorts_printer.core.pipeline import Job
from shorts_printer.core.schedule import Schedule
from shorts_printer.core.trends import Trend
from shorts_printer.infra import store
from shorts_printer.infra.sqlite import SQLiteStore
from shorts_printer.infra.store import atomic_write_json, migrate


def test_sqlite_docs_logs_ids_delete(db):
    assert db.get("job", "a") is None and db.get("job", "a", "script.json", []) == []
    db.put("job", "b", {"id": "b", "t": "한글"})
    db.put("job", "a", {"id": "a"})
    db.put("job", "a", {"title": "제목"}, "script.json")
    db.put("job", "c", [1], "script.json")   # 상태 문서 없는 id는 ids에 안 나온다
    db.put("trend", "z", {})
    assert db.ids("job") == ["a", "b"] and db.ids("trend") == ["z"]
    assert db.get("job", "a", "script.json") == {"title": "제목"} and db.get("job", "b")["t"] == "한글"
    for i in range(5):
        db.log("job", "a", f"줄{i}")
    db.log("job", "b", "다른 작업")
    assert db.tail("job", "a", 3) == ["줄2", "줄3", "줄4"] and db.tail("job", "a") == [f"줄{i}" for i in range(5)]
    db.delete("job", "a")
    assert db.ids("job") == ["b"] and db.get("job", "a", "script.json") is None and db.tail("job", "a") == []
    assert db.tail("job", "b") == ["다른 작업"]


def test_sqlite_edit_rolls_back_on_error(db):
    db.put("job", "a", {"n": 1})
    with pytest.raises(KeyError):
        db.edit("job", "a", lambda d: d["없음"])
    assert db.edit("job", "a", lambda d: d | {"n": 2}) == {"n": 2} and db.get("job", "a") == {"n": 2}


def test_edit_loses_nothing_across_threads_and_connections(db, tmp_path):
    """웹·작업 스레드(같은 연결)와 다른 프로세스(다른 연결)가 같이 고쳐도 잃지 않는다."""
    other = SQLiteStore(config.DB)   # 다른 프로세스 대신
    db.put("job", "a", {"n": 0})

    def bump(s):
        for _ in range(50):
            s.edit("job", "a", lambda d: d | {"n": d["n"] + 1})

    ts = [threading.Thread(target=bump, args=(s,)) for s in (db, db, db, other, other)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    other.close()
    assert db.get("job", "a")["n"] == 250


def test_store_must_be_attached(monkeypatch):
    monkeypatch.setattr(store, "_STORE", None)
    with pytest.raises(RuntimeError, match="저장소"):
        Job.all()


def test_record_over_store(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "secret-key-123")
    a = Job.create("ch", "주제", "v")
    b = Job.create("ch", "둘째", "v")
    assert [j.id for j in Job.all()] == sorted([a.id, b.id]) and Trend.all() == [] and Schedule.all() == []
    assert not (config.JOBS_DIR / a.id).exists()   # 미디어 폴더는 쓸 때 만든다
    assert a.dir.is_dir() and a.data["status"] == "draft" and a.data["steps"]["thumbnail"]["status"] == "pending"
    a.update(status="running")
    a.step("script", status="done", sec=1.5)
    assert a.data["status"] == "running" and a.data["steps"]["script"] == {"status": "done", "engine": None, "sec": 1.5}
    a.put("script.json", {"title": "제목"})
    assert a.doc("script.json") == {"title": "제목"} and a.doc("cues.json", []) == []
    a.log("키 secret-key-123 실패")
    line = a.tail()[-1]
    assert line.endswith("키 *** 실패") and line[2] == ":" and "secret" not in line
    with pytest.raises(FileNotFoundError, match="작업이 없어요: 없음"):
        Job.load("없음")
    with pytest.raises(FileNotFoundError, match="스케줄이 없어요"):
        Schedule.load(a.id)   # 종류가 다르면 없는 것
    a.delete()
    assert not a.dir.exists() and [j.id for j in Job.all()] == [b.id] and a.tail() == []
    with pytest.raises(FileNotFoundError):
        Job.load(a.id)


def _old(root, rec_id, kind, files, log=None):
    d = root / rec_id
    d.mkdir(parents=True)
    atomic_write_json(d / f"{kind}.json", {"id": rec_id, "status": "done", "steps": {"render": {"status": "done"}}})
    for name, value in files.items():
        (d / name).parent.mkdir(exist_ok=True)
        atomic_write_json(d / name, value)
    if log:
        (d / "log.txt").write_text("".join(f"{x}\n" for x in log), encoding="utf-8")
    return d


def test_migrate_imports_once_and_keeps_originals(db):
    files = {"script.json": {"title": "옛 제목"}, "before-chunks/cues.json": []}
    j = _old(config.JOBS_DIR, "20260101-000000-aaaa", "job", files, ["10:00:00 시작", "10:01:00 끝"])
    (j / "voice.wav").write_bytes(b"RIFF")
    _old(config.TRENDS_DIR, "20260101-000001-bbbb", "trend", {"picks.json": {"picks": []}})
    _old(config.SCHEDULES_DIR, "20260101-000002-cccc", "schedule", {})
    (config.JOBS_DIR / ".cache").mkdir()
    atomic_write_json(config.JOBS_DIR / ".cache" / "x.json", {})   # 기록이 아닌 폴더는 건너뛴다
    db.log("job", "20260101-000000-aaaa", "반쯤 옮긴 줄")   # 지난번에 멈춘 흔적은 지우고 다시 옮긴다

    assert migrate() == {"job": 1, "trend": 1, "schedule": 1}
    job = Job.load("20260101-000000-aaaa")
    assert job.data["status"] == "done" and job.doc("script.json") == {"title": "옛 제목"}
    assert job.tail() == ["10:00:00 시작", "10:01:00 끝"] and job.doc("before-chunks/cues.json") is None
    assert Trend.load("20260101-000001-bbbb").doc("picks.json") == {"picks": []}
    assert Schedule.all()[0].id == "20260101-000002-cccc"
    assert (j / "job.json").exists() and (j / "log.txt").exists() and (j / "script.json").exists()   # 원본은 백업

    job.update(status="failed")
    assert migrate() == {"job": 0, "trend": 0, "schedule": 0}   # 이미 있는 id는 건너뛴다(고친 값을 덮지 않는다)
    assert job.data["status"] == "failed" and len(job.tail()) == 2

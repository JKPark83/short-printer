import io
import json

from fastapi.testclient import TestClient

from shorts_printer import footage, thumbnail, worker
from shorts_printer.jobs import Job, atomic_write_json
from shorts_printer.web import app as web

SCRIPT = {"title": "라면 물 양의 비밀", "sentences": ["물은 550ml", "면은 나중에"]}
USAGE = {"model": "claude-opus-5-5", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}


class Done(io.BytesIO):
    length = None


def hit(i):
    return {"id": i, "pageURL": f"page{i}", "user": "kim", "user_id": 3, "webformatURL": f"w{i}.jpg", "largeImageURL": f"L{i}.jpg"}


def fake(monkeypatch, pick=1):
    calls, seen = [], []

    def ask(system, content, fmt, refusal, what):
        calls.append((system, content))
        if fmt is thumbnail.Plan:
            return thumbnail.Plan(lines=["물 이렇게 끓이면", "라면 망함"], accent="망함", queries=["shocked woman", "ramen"]), USAGE
        return thumbnail.Choice(pick=pick, position="bottom", reason="놀란 표정"), USAGE

    def open_(url, **h):
        seen.append(url)
        return Done(json.dumps({"hits": [hit(1), hit(2)]}).encode() if url.startswith(thumbnail.PHOTOS) else b"jpg")

    monkeypatch.setattr(thumbnail, "ask", ask)
    monkeypatch.setattr(footage, "_open", open_)
    monkeypatch.setenv("PIXABAY_API_KEY", "k")
    return calls, seen


def test_rules_come_from_skill_without_front_matter():
    r = thumbnail.rules()
    assert not r.startswith("---") and "name:" not in r.splitlines()[0] and "한눈에" in r


def test_make_picks_photo_and_avoids_it_next_time(monkeypatch, tmp_path):
    calls, seen = fake(monkeypatch)
    t = thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert calls[0][0].startswith(thumbnail.rules()[:20])   # 스킬 본문이 지시문
    assert t["photo"]["id"] == 2 and "L2.jpg" in seen and (tmp_path / "thumb_photo.jpg").read_bytes() == b"jpg"
    assert t["position"] == "bottom" and t["accent"] == "망함" and t["usage"]["cost_usd"] == 0.02
    atomic_write_json(tmp_path / "thumb.json", t)

    calls, seen = fake(monkeypatch, pick=0)
    t2 = thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert "이전에 쓴 문구" in calls[0][1]
    assert t2["photo"]["id"] == 1 and t2["used"] == [2, 1]   # 2번은 후보에서 빠진다
    assert not any(c.get("text", "").startswith("1번") for c in calls[1][1])


def test_make_without_match_or_bad_accent(monkeypatch, tmp_path):
    fake(monkeypatch, pick=-1)
    t = thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert t["photo"] is None and not (tmp_path / "thumb_photo.jpg").exists()
    monkeypatch.delenv("PIXABAY_API_KEY")
    monkeypatch.setattr(thumbnail, "ask", lambda *a: (thumbnail.Plan(lines=["  ", "라면"], accent="없는말", queries=[]), USAGE))
    t = thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert t["lines"] == ["라면"] and t["accent"] == "" and t["photo"] is None


def test_old_job_gets_thumbnail_step_and_rethumb_rules():
    job = Job.create("주제", "ko-KR-SunHiNeural")
    d = json.loads((job.dir / "job.json").read_text())
    del d["steps"]["thumbnail"]
    d["status"], d["steps"]["render"]["status"] = "done", "done"
    (job.dir / "job.json").write_text(json.dumps(d))
    assert job.data["steps"]["thumbnail"]["status"] == "done"   # 예전 작업

    client = TestClient(web.app, base_url="http://127.0.0.1")
    put = []
    worker._q.put = put.append
    try:
        assert client.post(f"/api/jobs/{job.id}/thumbnail").json() == {"ok": True}
        assert put == [("run", job.id)] and job.data["status"] == "queued"
        assert {job.data["steps"][s]["status"] for s in ("thumbnail", "render")} == {"pending"}
        assert client.post(f"/api/jobs/{job.id}/thumbnail").status_code == 409   # 만드는 중
        job.update(status="done", upload={"status": "done", "video_id": "v"})
        assert "스튜디오" in client.post(f"/api/jobs/{job.id}/thumbnail").json()["detail"]
    finally:
        del worker._q.put


def test_job_cost_adds_thumbnail():
    assert web.job_cost({"usage": USAGE, "thumb_usage": USAGE}) == 0.02
    assert web.job_cost({"usage": None}) is None


def test_step_thumbnail_skips_photos_other_jobs_used(monkeypatch):
    from shorts_printer import pipeline, render
    a, b = Job.create("가", "v"), Job.create("나", "v")
    atomic_write_json(a.dir / "thumb.json", {"photo": {"id": 7}})
    atomic_write_json(b.dir / "script.json", SCRIPT)
    atomic_write_json(b.dir / "thumb.json", {"photo": {"id": 8}})   # 다시 만들기: 자기 사진은 make가 used로 피한다
    got = []
    monkeypatch.setattr(thumbnail, "make", lambda *a: got.append(a[-1]) or {
        "lines": ["라면"], "accent": "", "position": "top", "photo": {"id": 8}, "usage": USAGE})
    monkeypatch.setattr(render, "thumbnail", lambda *a: "사진")
    pipeline.step_thumbnail(b)
    assert got == [{7}]   # 다른 작업 사진만

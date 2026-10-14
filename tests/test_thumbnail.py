import json

from fastapi.testclient import TestClient

from shorts_printer import thumbnail, worker
from shorts_printer.jobs import Job, atomic_write_json
from shorts_printer.web import app as web

SCRIPT = {"title": "라면 물 양의 비밀", "sentences": ["물은 550ml", "면은 나중에"]}
USAGE = {"model": "claude-opus-5-5", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}


def test_rules_come_from_skill_without_front_matter():
    r = thumbnail.rules()
    assert not r.startswith("---") and "name:" not in r.splitlines()[0] and "한눈에" in r


def test_make_plans_text_only(monkeypatch, tmp_path):
    calls = []

    def ask(system, content, fmt, refusal, what):
        calls.append((system, content))
        return thumbnail.Plan(lines=["  ", "라면"], accent="없는말"), USAGE
    monkeypatch.setattr(thumbnail, "ask", ask)
    t = thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert t["lines"] == ["라면"] and t["accent"] == "" and t["position"] == "top" and "photo" not in t
    assert calls[0][0].startswith(thumbnail.rules())   # 스킬 본문이 지시문
    atomic_write_json(tmp_path / "thumb.json", t)
    thumbnail.make(tmp_path, SCRIPT, "라면", print)
    assert "이전에 쓴 문구" in calls[1][1]
    atomic_write_json(tmp_path / "thumb.json", t)
    t = thumbnail.make(tmp_path, SCRIPT, "라면", print, note="숫자를 넣어 줘")
    assert "지금 문구: 라면" in calls[2][1] and "수정 요청(규칙보다 우선): 숫자를 넣어 줘" in calls[2][1]
    assert "이전에 쓴 문구" not in calls[2][1] and t["note"] == "숫자를 넣어 줘"


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
        assert client.post(f"/api/jobs/{job.id}/thumbnail", data={"note": "x" * 301}).status_code == 400
        assert client.post(f"/api/jobs/{job.id}/thumbnail", data={"note": " 숫자 넣기 "}).json()["ok"]
        assert put == [("run", job.id)] and job.data["status"] == "queued" and job.data["thumb_note"] == "숫자 넣기"
        assert {job.data["steps"][s]["status"] for s in ("thumbnail", "render")} == {"pending"}
        assert client.post(f"/api/jobs/{job.id}/thumbnail").status_code == 409   # 만드는 중
        job.update(status="done", upload={"status": "done", "video_id": "v"})
        assert "스튜디오" in client.post(f"/api/jobs/{job.id}/thumbnail").json()["detail"]
    finally:
        del worker._q.put


def test_job_cost_adds_thumbnail():
    assert web.job_cost({"usage": USAGE, "thumb_usage": USAGE}) == 0.02
    assert web.job_cost({"usage": None}) is None

from fastapi.testclient import TestClient

from shorts_printer import registry
from shorts_printer.core import channel, thumbnail
from shorts_printer.core.pipeline import Job
from shorts_printer.infra import store
from shorts_printer.web import app as web

SCRIPT = {"title": "라면 물 양의 비밀", "sentences": ["물은 550ml", "면은 나중에"]}
USAGE = {"model": "claude-opus-5-5", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}
CH = channel.load("ko-40sec-facts")


class LLM:
    label = "가짜"

    def __init__(self):
        self.calls = []

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append((system, text))
        return schema(lines=["  ", "라면"], accent="없는말"), USAGE


def test_system_has_channel_rules_without_front_matter_plus_limits():
    r = thumbnail.system(CH)
    assert not r.startswith("---") and "name:" not in r.splitlines()[0] and "한눈에" in r
    assert "문구는 한국어로 1~2줄, 줄마다 12자 이내, 합쳐 22자 이내." in r   # channel.toml [thumbnail]


def test_make_plans_text_only():
    llm = LLM()
    t = thumbnail.make(llm, CH, [], SCRIPT, "라면", print)
    assert t["lines"] == ["라면"] and t["accent"] == "" and t["position"] == "top" and "photo" not in t
    assert llm.calls[0][0].startswith(thumbnail.system(CH))   # 채널 규칙이 지시문
    thumbnail.make(llm, CH, t["texts"], SCRIPT, "라면", print)
    assert "이전에 쓴 문구" in llm.calls[1][1]
    t = thumbnail.make(llm, CH, t["texts"], SCRIPT, "라면", print, note="숫자를 넣어 줘")
    assert "지금 문구: 라면" in llm.calls[2][1] and "수정 요청(규칙보다 우선): 숫자를 넣어 줘" in llm.calls[2][1]
    assert "이전에 쓴 문구" not in llm.calls[2][1] and t["note"] == "숫자를 넣어 줘"


def test_old_job_gets_thumbnail_step_and_rethumb_rules(monkeypatch):
    job = Job.create(CH.id, "주제", "ko-KR-SunHiNeural")
    d = store.store().get("job", job.id)
    del d["steps"]["thumbnail"]
    d["status"], d["steps"]["render"]["status"] = "done", "done"
    store.store().put("job", job.id, d)
    assert job.data["steps"]["thumbnail"]["status"] == "done"   # 예전 작업

    client = TestClient(web.app, base_url="http://127.0.0.1")
    put = []
    monkeypatch.setattr(registry.queue()._q, "put", put.append)
    assert client.post(f"/api/jobs/{job.id}/thumbnail", data={"note": "x" * 301}).status_code == 400
    assert client.post(f"/api/jobs/{job.id}/thumbnail", data={"note": " 숫자 넣기 "}).json()["ok"]
    assert put == [("run", job.id)] and job.data["status"] == "queued" and job.data["thumb_note"] == "숫자 넣기"
    assert {job.data["steps"][s]["status"] for s in ("thumbnail", "render")} == {"pending"}
    assert client.post(f"/api/jobs/{job.id}/thumbnail").status_code == 409   # 만드는 중
    job.update(status="done", upload={"status": "running", "video_id": None})
    assert "올리는 중" in client.post(f"/api/jobs/{job.id}/thumbnail").json()["detail"]


def test_job_cost_adds_thumbnail():
    assert web.job_cost({"usage": USAGE, "thumb_usage": USAGE}) == 0.02
    assert web.job_cost({"usage": None}) is None

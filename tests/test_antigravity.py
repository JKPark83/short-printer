import json
import subprocess

import pytest
from pydantic import BaseModel

from shorts_printer import config, registry
from shorts_printer.adapters import antigravity
from shorts_printer.adapters.antigravity import Antigravity, AntigravityResearch


class Out(BaseModel):
    answer: int


USAGE = {"input_tokens": 100, "cache_read_tokens": 20, "output_tokens": 5, "thinking_tokens": 7}


def fake_run(monkeypatch, result: dict, seen: dict, head: str = "", stderr: str = ""):
    def run(cmd, *, cwd, timeout, **kw):
        seen.update(cmd=cmd, cwd=cwd, timeout=timeout, prompt=next(a for a in cmd if a.startswith("-p="))[3:])
        return subprocess.CompletedProcess(cmd, 0, stdout=head + json.dumps(result) + "\n", stderr=stderr)
    monkeypatch.setattr(antigravity.subprocess, "run", run)


def test_ask_parses_structured_output_and_usage(monkeypatch):
    monkeypatch.setattr(config, "ANTIGRAVITY_MODEL", "gemini-4-argon-high")
    monkeypatch.setattr(config, "ANTIGRAVITY_EFFORT", None)
    seen = {}
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": {"answer": 5}, "usage": USAGE}, seen)
    out, usage = Antigravity().ask("짧게", "2+3은", Out, refusal="거절", what="답")
    assert out.answer == 5
    assert usage == {"model": "gemini-4-argon-high", "input_tokens": 120, "output_tokens": 12, "cost_usd": 0.0}
    cmd = seen["cmd"]
    assert cmd[cmd.index("--model") + 1] == "gemini-4-argon-high" and "--effort" not in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == Out.model_json_schema()
    assert seen["prompt"].startswith("[지시문]\n짧게") and seen["prompt"].endswith("2+3은")
    assert antigravity.NO_WEB in seen["prompt"]
    assert "shorts-printer" not in seen["cwd"]   # 프로젝트의 GEMINI.md·AGENTS.md를 읽지 않게


def test_ask_skips_warning_line_before_json(monkeypatch):
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": {"answer": 1}}, {},
             head="jetski: no output produced — something\n")
    assert Antigravity().ask("s", "t", Out, refusal="거절", what="답")[0].answer == 1


@pytest.mark.parametrize("result, msg", [
    ({"status": "SUCCESS", "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}, "RunCommand"),
    ({"status": "ERROR", "error": "not logged in"}, "Antigravity 오류: not logged in"),
    ({"status": "SUCCESS", "response": ""}, "답을 받지 못했어요"),
    ({"status": "SUCCESS", "response": "{\"picks\""}, "답을 받지 못했어요"),
    ({"status": "SUCCESS", "structured_output": {"wrong": 1}}, "답 모양이 틀렸어요"),
])
def test_ask_errors_in_korean(monkeypatch, result, msg):
    fake_run(monkeypatch, result, {})
    with pytest.raises(RuntimeError, match=msg):
        Antigravity().ask("s", "t", Out, refusal="거절", what="답")


def test_ask_web_sites_go_into_prompt(monkeypatch):
    seen = {}
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": {"answer": 1}}, seen)
    Antigravity().ask("s", "t", Out, refusal="거절", what="답", web=["kdca.go.kr", "nih.gov"])
    assert "kdca.go.kr, nih.gov" in seen["prompt"] and antigravity.NO_WEB not in seen["prompt"]
    assert "웹 검색은 5번까지만" in seen["prompt"]


def test_ask_web_true_caps_searches(monkeypatch):
    seen = {}
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": {"answer": 1}}, seen)
    Antigravity().ask("s", "t", Out, refusal="거절", what="답", web=True)
    assert "웹 검색은 5번까지만" in seen["prompt"]   # Claude max_uses=5와 같게, 없으면 31번 돌다 시간이 다 됐다


@pytest.mark.parametrize("result", [
    {"status": "ERROR", "response": "The stream was interrupted. Please continue the task you were working on."},
    {"status": "SUCCESS", "response": ""},
    {"status": "SUCCESS", "response": '{"picks":[{"angle":"귤'},
])
def test_print_timeout_is_korean(monkeypatch, result):
    fake_run(monkeypatch, result, {},
             stderr="[agy] print timeout after 20m0s with turn in progress; returning partial output\n")
    with pytest.raises(RuntimeError, match="20분 안에 답하지 않았어요"):
        Antigravity().ask("s", "t", Out, refusal="거절", what="추천 주제")
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": {"answer": 3}}, {},
             stderr="[agy] print timeout after 20m0s")
    assert Antigravity().ask("s", "t", Out, refusal="거절", what="답")[0].answer == 3   # 다 된 답은 버리지 않는다


def test_empty_answer_particle(monkeypatch):
    fake_run(monkeypatch, {"status": "SUCCESS", "response": ""}, {})
    with pytest.raises(RuntimeError, match="추천 주제를 받지"):
        Antigravity().ask("s", "t", Out, refusal="거절", what="추천 주제")
    assert [antigravity._obj(w) for w in ["검수 결과", "목차", "2장 장면", "썸네일 문구", "AI"]] == [
        "를", "를", "을", "를", "를"]


def test_run_errors_are_korean(monkeypatch):
    def run(*a, **kw):
        raise ValueError("embedded null byte")
    monkeypatch.setattr(antigravity.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="실행하지 못했어요: ValueError"):
        Antigravity().ask("s", "t\0", Out, refusal="거절", what="답")


def test_resolve_does_not_remember_failures(monkeypatch):
    calls = []
    def open_(self, req, timeout):
        calls.append(req.full_url)
        raise OSError("끊김")
    monkeypatch.setattr(antigravity.urllib.request.OpenerDirector, "open", open_)
    url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/Y"
    assert antigravity._resolve(url) == url and antigravity._resolve(url) == url
    assert len(calls) == 2   # 실패를 기억하면 서버를 다시 켤 때까지 그 사실이 범위 밖으로 버려진다


def test_ask_rejects_images_and_long_prompt(monkeypatch):
    with pytest.raises(RuntimeError, match="그림"):
        Antigravity().ask("s", "t", Out, refusal="거절", what="답", images=[b"jpg"])
    with pytest.raises(RuntimeError, match="너무 길어요"):
        Antigravity().ask("s", "가" * 400_000, Out, refusal="거절", what="답")


def test_gather_drops_out_of_scope_sources(monkeypatch):
    seen = {}
    found = {"facts": [
        {"text": "물은 100도에서 끓는다.", "url": "https://www.kdca.go.kr/a", "title": "A", "published": "2025-01-02"},
        {"text": "피부염은 방치하면 번진다.", "url": "https://sub.nih.gov/b", "title": "B", "quote": "It spreads"},
        {"text": "블로그 주장", "url": "https://blog.example.com/c"},
        {"text": "리다이렉트로 온 사실", "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/X"},
        {"text": "확인 못 함: 달은 치즈다", "url": ""},
    ], "notes": ["검색 '물' 0건"]}
    fake_run(monkeypatch, {"status": "SUCCESS", "structured_output": found, "usage": USAGE}, seen)
    real = {"https://vertexaisearch.cloud.google.com/grounding-api-redirect/X": "https://medlineplus.gov/d"}
    monkeypatch.setattr(antigravity, "_resolve", lambda u: real.get(u, u))
    facts, usage = AntigravityResearch().gather("지시", "주제: 물", queries=3, max_pages=4,
                                                domains=["kdca.go.kr", "nih.gov", "medlineplus.gov"])
    assert [f["text"] for f in facts] == [
        "Antigravity 조사: 출처 있는 사실 3개, 범위 밖 출처 1건 뺌", "검색 '물' 0건", "확인 못 함: 달은 치즈다",
        "물은 100도에서 끓는다.", "피부염은 방치하면 번진다.", "리다이렉트로 온 사실"]
    assert all(not f["url"] for f in facts[:3])
    assert facts[3]["published"] == "2025-01-02" and facts[3]["retrieved_at"] and "quote" not in facts[3]
    assert "quote" not in facts[4] and facts[5]["url"] == "https://medlineplus.gov/d"   # 검색 요약을 원문인 척 안 낸다
    assert "kdca.go.kr, nih.gov" in seen["prompt"] and "검색은 3번까지만" in seen["prompt"]
    assert "web_fetch" in seen["prompt"] and "quote는 적지 않는다" in seen["prompt"]
    assert seen["timeout"] == antigravity.RESEARCH_TIMEOUT + 60
    assert usage["cost_usd"] == 0.0


def test_registry_has_antigravity():
    assert isinstance(registry.LLMS["antigravity"], Antigravity)
    assert isinstance(registry.RESEARCHERS["antigravity"], AntigravityResearch)


@pytest.mark.live
def test_live_ask():
    out, usage = Antigravity().ask("짧게 답한다.", "2+3은?", Out, refusal="거절", what="답")
    assert out.answer == 5 and usage["input_tokens"] > 0

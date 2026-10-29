import json
import subprocess

import pytest
from pydantic import BaseModel

from shorts_printer import config, registry
from shorts_printer.adapters import claude_code
from shorts_printer.adapters.claude_code import ClaudeCode


class Out(BaseModel):
    answer: str


def fake_run(monkeypatch, result: dict, seen: dict):
    def run(cmd, *, input, env, **kw):
        seen.update(cmd=cmd, input=input, env=env)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(result), stderr="")
    monkeypatch.setattr(claude_code.subprocess, "run", run)


def test_ask_uses_subscription_model_and_effort(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    monkeypatch.setattr(config, "CLAUDE_CODE_EFFORT", "max")
    seen = {}
    fake_run(monkeypatch, {"is_error": False, "stop_reason": "tool_use", "structured_output": {"answer": "짜다"},
                           "usage": {"input_tokens": 2, "cache_creation_input_tokens": 10, "output_tokens": 5}}, seen)
    out, usage = ClaudeCode().ask("짧게", "바다는 왜 짤까", Out, refusal="거절", what="답")
    assert out.answer == "짜다"
    assert usage == {"model": "claude-opus-5-5", "input_tokens": 12, "output_tokens": 5, "cost_usd": 0.0}
    cmd = seen["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5" and cmd[cmd.index("--effort") + 1] == "max"
    assert seen["input"] == "바다는 왜 짤까"
    assert "ANTHROPIC_API_KEY" not in seen["env"]   # 있으면 구독 대신 API로 과금된다


@pytest.mark.parametrize("result, msg", [
    ({"is_error": True, "result": "usage limit reached"}, "Claude Code 오류: usage limit"),
    ({"is_error": False, "stop_reason": "refusal"}, "거절"),
    ({"is_error": False, "stop_reason": "end_turn"}, "답을 받지 못했어요"),
    ({"is_error": False, "structured_output": {"wrong": 1}}, "답 모양이 틀렸어요"),
])
def test_ask_errors_in_korean(monkeypatch, result, msg):
    fake_run(monkeypatch, result, {})
    with pytest.raises(RuntimeError, match=msg):
        ClaudeCode().ask("s", "t", Out, refusal="거절", what="답")


def test_script_llm_follows_channel_script_llm():
    sv = registry.services("momjob")
    assert sv.script_llm is registry.LLMS[sv.channel.script.llm or sv.channel.llm]


def test_ask_turns_on_only_web_search_and_names_allowed_sites(monkeypatch):
    seen, ok, run = {}, {"is_error": False, "structured_output": {"answer": "짜다"}}, subprocess.run
    fake_run(monkeypatch, ok, seen)
    ClaudeCode().ask("짧게", "t", Out, refusal="거절", what="답")
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and "--allowedTools" not in cmd   # 검색이 없으면 도구도 없다
    ClaudeCode().ask("짧게", "t", Out, refusal="거절", what="답", web=["kdca.go.kr", "who.int"])
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "WebSearch" and cmd[cmd.index("--allowedTools") + 1] == "WebSearch"
    system = cmd[cmd.index("--system-prompt") + 1]
    assert system.startswith("짧게") and "5번까지" in system and "kdca.go.kr, who.int" in system
    # 모델이 다른 사이트를 넣어도 훅이 허용 사이트로 덮어쓴다
    hook = json.loads(cmd[cmd.index("--settings") + 1])["hooks"]["PreToolUse"][0]
    call = {"tool_input": {"query": "독감", "allowed_domains": ["wikipedia.org"], "blocked_domains": ["x.com"]}}
    r = run(hook["hooks"][0]["command"], shell=True, input=json.dumps(call), capture_output=True, text=True)
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert hook["matcher"] == "WebSearch" and out["permissionDecision"] == "allow"
    assert out["updatedInput"] == {"query": "독감", "allowed_domains": ["kdca.go.kr", "who.int"]}
    with pytest.raises(RuntimeError, match="그림을 못 받아요"):
        ClaudeCode().ask("s", "t", Out, refusal="거절", what="답", images=[b"png"])


def test_trends_llm_follows_channel_trends_llm():
    sv = registry.services("momjob")
    assert sv.trends_llm is registry.LLMS[sv.channel.trends.llm or sv.channel.llm]

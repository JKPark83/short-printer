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
    sv = registry.services("ko-40sec-facts")
    assert sv.script_llm is registry.LLMS[sv.channel.script.llm or sv.channel.llm]

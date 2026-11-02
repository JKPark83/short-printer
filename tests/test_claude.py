from types import SimpleNamespace

import pydantic

from shorts_printer.adapters import claude, claude_research
from shorts_printer.ports.llm import Cached


class Out(pydantic.BaseModel):
    text: str


def reply(stop="end_turn", inp=100, written=0, read=0, content=()):
    usage = SimpleNamespace(input_tokens=inp, output_tokens=50, cache_creation_input_tokens=written,
                            cache_read_input_tokens=read, server_tool_use=None)
    return SimpleNamespace(usage=usage, stop_reason=stop, parsed_output=Out(text="ok"), model="claude-opus-5-5",
                           content=list(content))


def test_one_off_system_is_not_cached_but_shared_head_is(monkeypatch):
    seen = []
    monkeypatch.setattr(claude, "stream", lambda **kw: (seen.append(kw), reply(read=2000))[1])
    out, usage = claude.Claude().ask("규칙", "질문", Out, refusal="거절", what="답")
    assert out.text == "ok" and seen[0]["system"] == [{"type": "text", "text": "규칙"}]   # 쓰기 1.25배만 내지 않게
    assert "cache_control" not in seen[0]
    # 입력 100·출력 50·캐시 읽기 2000 → (100*4 + 2000*0.2 + 50*20) / 1e6
    assert usage["input_tokens"] == 2100 and usage["cost_usd"] == round((400 + 400 + 1000) / 1e6, 4)
    claude.Claude().ask(Cached("장면 규칙", "고쳐 쓰기 규칙"), "질문", Out, refusal="거절", what="답")
    assert seen[1]["system"] == [{"type": "text", "text": "장면 규칙", "cache_control": {"type": "ephemeral"}},
                                 {"type": "text", "text": "고쳐 쓰기 규칙"}]   # 공통 앞부분 끝에만 캐시 위치
    assert Cached("장면 규칙", "고쳐 쓰기 규칙") == "장면 규칙\n\n고쳐 쓰기 규칙"   # 다른 공급자에겐 그냥 문자열


def test_pause_turn_caches_the_growing_conversation_only_when_continuing(monkeypatch):
    seen, replies = [], [reply("pause_turn", content=["검색 결과"]), reply(read=900, written=300)]
    monkeypatch.setattr(claude, "stream", lambda **kw: (seen.append(kw), replies.pop(0))[1])
    _, usage = claude.Claude().ask("규칙", "질문", Out, refusal="거절", what="답", web=True)
    assert "cache_control" not in seen[0] and seen[1]["cache_control"] == {"type": "ephemeral"}
    assert seen[1]["messages"][-1] == {"role": "assistant", "content": ["검색 결과"]}
    assert usage["input_tokens"] == 100 + 100 + 300 + 900


def test_research_shares_the_loop_and_counts_cache_tokens(monkeypatch):
    seen, replies = [], [reply("pause_turn"), reply(read=5000)]
    monkeypatch.setattr(claude_research, "stream", lambda **kw: (seen.append(kw), replies.pop(0))[1])
    _, usage = claude_research.ClaudeResearch().gather("조사 규칙", "주제", domains=[], queries=3, max_pages=2)
    assert seen[0]["system"] == [{"type": "text", "text": "조사 규칙"}] and seen[1]["cache_control"]
    assert usage["input_tokens"] == 5200 and usage["cost_usd"] == round((800 + 5000 * 0.2 + 100 * 20) / 1e6, 4)


def test_cost_counts_cache_writes_at_one_and_a_quarter():
    assert claude.cost("claude-opus-5-5", 0, 0, written=1_000_000) == 5.0
    assert claude.cost("unknown-model", 1, 1) is None

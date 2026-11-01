from types import SimpleNamespace

import pydantic

from shorts_printer.adapters import claude


class Out(pydantic.BaseModel):
    text: str


def test_ask_caches_the_system_prompt_and_prices_cache_tokens(monkeypatch):
    seen = {}

    def fake_stream(**kw):
        seen.update(kw)
        usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0,
                                cache_read_input_tokens=2000, server_tool_use=None)
        return SimpleNamespace(usage=usage, stop_reason="end_turn", parsed_output=Out(text="ok"),
                               model="claude-opus-5-5", content=[])
    monkeypatch.setattr(claude, "stream", fake_stream)
    out, usage = claude.Claude().ask("규칙", "질문", Out, refusal="거절", what="답")
    assert out.text == "ok"
    assert seen["system"] == [{"type": "text", "text": "규칙", "cache_control": {"type": "ephemeral"}}]
    # 입력 100·출력 50·캐시 읽기 2000 → (100*4 + 2000*0.2 + 50*20) / 1e6
    assert usage["input_tokens"] == 2100 and usage["cost_usd"] == round((400 + 400 + 1000) / 1e6, 4)


def test_cost_counts_cache_writes_at_one_and_a_quarter():
    assert claude.cost("claude-opus-5-5", 0, 0, written=1_000_000) == 5.0
    assert claude.cost("unknown-model", 1, 1) is None

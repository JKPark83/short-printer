from types import SimpleNamespace

import anthropic
import pytest

from shorts_printer import script

OK = script.Script(title="t", description="d", tags=["a"], sensitive="", scenes=[script.Scene(sentence="하나", prompt="p1", term="coffee"),
                                                                 script.Scene(sentence="둘", prompt="p2", term="cup")])


def fake_client(monkeypatch, resp=None, exc=None):
    calls = []

    def parse(**kw):
        calls.append(kw)
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(anthropic, "Anthropic", lambda: SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse))))
    return calls


def resp(**kw):
    base = dict(stop_reason="end_turn", parsed_output=OK, model="claude-opus-5-5",
                usage=SimpleNamespace(input_tokens=1000, output_tokens=2000))
    return SimpleNamespace(**base | kw)


def test_write_returns_script_and_cost(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    s, usage = script.write("커피")
    assert s == OK
    assert usage == {"model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.044}
    assert calls[0]["output_format"] is script.Script and calls[0]["fallbacks"] == "default"


def test_haiku_skips_fallback(monkeypatch):
    monkeypatch.setattr(script.config, "CLAUDE_MODEL", "claude-haiku-4-5")
    calls = fake_client(monkeypatch, resp(model="claude-haiku-4-5"))
    script.write("커피")
    assert "fallbacks" not in calls[0] and "betas" not in calls[0]


def test_refusal_and_missing_key_become_korean_errors(monkeypatch):
    fake_client(monkeypatch, resp(stop_reason="refusal", parsed_output=None))
    with pytest.raises(RuntimeError, match="주제를 바꿔"):
        script.write("x")
    fake_client(monkeypatch, exc=TypeError('Could not resolve authentication method. Expected api_key'))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        script.write("x")


def test_flat_keeps_parallel_lists():
    f = OK.flat()
    assert f["sentences"] == ["하나", "둘"] and f["prompts"] == ["p1", "p2"] and f["search_terms"] == ["coffee", "cup"]
    assert "scenes" not in f and f["title"] == "t"


def test_cost_unknown_model_is_none():
    assert script.cost("claude-sonnet-5-5-20260901", 1_000_000, 0) == 2
    assert script.cost("mystery", 1, 1) is None


@pytest.mark.live
def test_live_claude_writes_korean_script():
    if not script.config.secret("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY 없음")
    s, usage = script.write("커피를 처음 마신 사람들")
    assert 6 <= len(s.scenes) <= 7 and all("No on-screen text" in x.prompt and x.term for x in s.scenes) and usage["output_tokens"] > 0


def test_brief_is_appended(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    script.write("커피", "첫 문장은 질문으로")
    assert calls[0]["messages"][0]["content"] == "주제: 커피\n\n참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:\n첫 문장은 질문으로"
    script.write("커피")
    assert calls[1]["messages"][0]["content"] == "주제: 커피"


def test_channel_and_recent_titles_are_appended(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    monkeypatch.setattr(script.config, "CHANNEL", "생활 속 과학")
    script.write("커피", recent=["라면이 꼬불꼬불한 진짜 이유"])
    text = calls[0]["messages"][0]["content"]
    assert "채널 분야: 생활 속 과학" in text and "최근 제목(이 틀을 피한다):\n- 라면이 꼬불꼬불한 진짜 이유" in text


def test_revise_keeps_scene_count_and_prompts(monkeypatch):
    s = OK.flat()
    calls = fake_client(monkeypatch, resp(parsed_output=script.Revision(title="새 제목", description="d", tags=["a"],
                                                                         sentences=[" 하나! ", "둘!"])))
    new, usage = script.revise(s, "느낌표를 붙여 줘")
    assert new["sentences"] == ["하나!", "둘!"] and new["prompts"] == ["p1", "p2"] and new["title"] == "새 제목"
    assert "(화면: p1)" in calls[0]["messages"][0]["content"] and "느낌표를 붙여 줘" in calls[0]["messages"][0]["content"]
    fake_client(monkeypatch, resp(parsed_output=script.Revision(title="t", description="d", tags=[], sentences=["하나"])))
    with pytest.raises(RuntimeError, match="장면 수"):
        script.revise(s, "줄여 줘")

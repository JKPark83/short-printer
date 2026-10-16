from types import SimpleNamespace

import anthropic
import pytest

from shorts_printer import config
from shorts_printer.adapters import claude
from shorts_printer.core import channel, prompts, script

OK = script.Script(title="t", description="d", tags=["a"], sensitive="",
                   scenes=[script.Scene(sentence="하나", prompt="p1"), script.Scene(sentence="둘", prompt="p2")])
USAGE = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": None}


class FakeLLM:
    """llm.ask 호출을 기록하고 정해진 답을 준다(네트워크 없음)."""
    label = "Claude"

    def __init__(self, out=OK):
        self.out, self.calls = out, []

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append(dict(system=system, text=text, schema=schema, refusal=refusal, what=what))
        return self.out, USAGE


@pytest.fixture
def ko():
    return channel.load("ko-40sec-facts")


def make_channel(tmp_path, **kw) -> channel.Channel:
    for name in channel.TEXTS:
        (tmp_path / name).write_text(f"---\nx: 1\n---\n{name} 본문", encoding="utf-8")
    base = dict(id="en-test", dir=tmp_path, name="n", description="d", concept="space facts", language="en",
                tts={"voices": {"v": "V"}, "sample": "Hi"}, trends={"production": "p"})
    return channel.Channel(**base | kw)


def test_write_prefixes_channel_style_and_returns_usage(ko):
    llm = FakeLLM()
    s, usage = script.write(llm, ko, "커피")
    assert [x.prompt for x in s.scenes] == [f"{ko.video.style} p1", f"{ko.video.style} p2"] and usage == USAGE
    assert llm.calls[0]["schema"] is script.Script and llm.calls[0]["system"] == script.system(ko)
    assert "주제를 바꿔" in llm.calls[0]["refusal"]


def test_write_without_style_keeps_prompt(tmp_path):
    s, _ = script.write(FakeLLM(), make_channel(tmp_path), "Mars")
    assert [x.prompt for x in s.scenes] == ["p1", "p2"]


def test_ko_system_keeps_every_old_rule(ko):
    sys = script.system(ko)
    for rule in ["52~56초", "정확히 7개", "62~68자", "68자를 넘지", "이모지·해시태그·괄호", "60~90단어", "photoreal",
                 "주인공·장소·시대·옷차림", "앞 5초", "No on-screen text, no numbers, no logos.", "실존 인물의 얼굴",
                 "No dialogue, no voices, no music.",
                 "훅", "존댓말", "널리 확인된", "여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?", "질문형",
                 "3D 애니메이션", "단면도", "한국어"]:
        assert rule in sys, rule


def test_words_unit_english_system(tmp_path):
    ch = make_channel(tmp_path, script={"scenes": 5, "sentence": [12, 16], "unit": "words", "duration": "30초"})
    sys = script.system(ch)
    assert "영어" in sys and "12~16단어" in sys and "정확히 5개" in sys and "자(" not in sys
    assert "## 채널 대본 규칙\nscript.md 본문" in sys and "## 채널 장면 영상 규칙\nvideo_style.md 본문" in sys


def test_brief_channel_and_recent_titles_are_appended(ko):
    llm = FakeLLM()
    script.write(llm, ko, "커피", "첫 문장은 질문으로", recent=["라면이 꼬불꼬불한 진짜 이유"])
    text = llm.calls[0]["text"]
    assert text.startswith("주제: 커피\n\n참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:"
                           "\n첫 문장은 질문으로")
    assert f"채널 분야: {ko.concept}" in text and "최근 제목(이 틀을 피한다):\n- 라면이 꼬불꼬불한 진짜 이유" in text


def test_flat_keeps_parallel_lists():
    f = OK.flat()
    assert f["sentences"] == ["하나", "둘"] and f["prompts"] == ["p1", "p2"]
    assert "scenes" not in f and f["title"] == "t"


def test_revise_keeps_scene_count_and_prompts(ko):
    s = OK.flat()
    llm = FakeLLM(script.Revision(title="새 제목", description="d", tags=["a"], sentences=[" 하나! ", "둘!"]))
    new, _ = script.revise(llm, ko, s, "느낌표를 붙여 줘")
    assert new["sentences"] == ["하나!", "둘!"] and new["prompts"] == ["p1", "p2"] and new["title"] == "새 제목"
    assert "(화면: p1)" in llm.calls[0]["text"] and "느낌표를 붙여 줘" in llm.calls[0]["text"]
    assert llm.calls[0]["system"] == script.system(ko) + "\n\n" + prompts.render("script_revise")
    with pytest.raises(RuntimeError, match="장면 수"):
        script.revise(FakeLLM(script.Revision(title="t", description="d", tags=[], sentences=["하나"])),
                      ko, s, "줄여 줘")


def test_draft_revise_rewrites_prompts_too(ko):
    s = OK.flat()
    out = script.Draft(title="t", description="d", tags=[], sentences=["하나", "셋"], prompts=[" p1 ", "p3"])
    llm = FakeLLM(out)
    new, _ = script.revise(llm, ko, s, "둘을 셋으로", draft=True)
    assert new["sentences"] == ["하나", "셋"] and new["prompts"] == ["p1", "p3"]
    assert llm.calls[0]["system"].endswith(prompts.render("script_revise_draft"))
    with pytest.raises(RuntimeError, match="장면 수"):
        script.revise(FakeLLM(out.model_copy(update={"prompts": ["p1"]})), ko, s, "줄여 줘", draft=True)


def test_translate_sends_script_and_thumb_and_keeps_source(ko):
    s = OK.flat()
    out = script.Translation(title="제목", description="d", tags=["a"], sentences=["하나", "둘"], thumb=["줄"],
                             cues=[], notes=[])
    llm = FakeLLM(out)
    got, _ = script.translate(llm, ko, s, {"lines": ["ライン"], "accent": 0})
    assert got["ko"]["sentences"] == ["하나", "둘"] and got["src"] == script.ko_source(s, {"lines": ["ライン"]})
    assert "썸네일 문구 1줄:\nライン" in llm.calls[0]["text"] and "2. " in llm.calls[0]["text"]
    with pytest.raises(RuntimeError, match="문장 수"):
        script.translate(FakeLLM(out.model_copy(update={"sentences": ["하나"]})), ko, s, None)
    with pytest.raises(RuntimeError, match="자막 줄 수"):
        script.translate(llm, ko, s, None, ["両替は"])


# Claude 어댑터

def fake_client(monkeypatch, resp=None, exc=None):
    calls, resps = [], resp if isinstance(resp, list) else [resp]

    def parse(**kw):
        calls.append(kw | {"messages": list(kw["messages"])})
        if exc:
            raise exc
        return resps.pop(0) if len(resps) > 1 else resps[0]

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    return calls


def resp(**kw):
    base = dict(stop_reason="end_turn", parsed_output=OK, model="claude-opus-5-5",
                usage=SimpleNamespace(input_tokens=1000, output_tokens=2000, server_tool_use=None))
    return SimpleNamespace(**base | kw)


def ask(**kw):
    return claude.Claude().ask("sys", "글", script.Script, refusal="주제를 바꿔 보세요", what="대본", **kw)


def test_claude_returns_result_and_cost(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    out, usage = ask()
    assert out is OK
    assert usage == {"model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.044}
    assert calls[0]["output_format"] is script.Script and calls[0]["fallbacks"] == "default"
    assert calls[0]["messages"][0]["content"] == "글" and calls[0]["system"] == "sys" and "tools" not in calls[0]


def test_claude_web_search_resumes_pause_and_adds_search_cost(monkeypatch):
    searched = SimpleNamespace(input_tokens=1000, output_tokens=2000,
                               server_tool_use=SimpleNamespace(web_search_requests=3))
    calls = fake_client(monkeypatch, [resp(stop_reason="pause_turn", parsed_output=None, content=["검색 중"],
                                           usage=searched), resp(usage=searched)])
    out, usage = ask(web=True)
    assert out is OK and len(calls) == 2
    assert calls[0]["tools"] == [claude.WEB_SEARCH] and len(calls[0]["messages"]) == 1
    assert calls[1]["messages"][1] == {"role": "assistant", "content": ["검색 중"]}
    assert usage["input_tokens"] == 2000 and usage["cost_usd"] == round(0.088 + 6 * claude.SEARCH_USD, 4)


def test_claude_puts_images_before_text(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    ask(images=[b"\xff\xd8", "https://i.ytimg.com/x.jpg"])
    content = calls[0]["messages"][0]["content"]
    assert [c["type"] for c in content] == ["image", "image", "text"] and content[2]["text"] == "글"
    assert content[0]["source"] == {"type": "base64", "media_type": "image/jpeg", "data": "/9g="}
    assert content[1]["source"] == {"type": "url", "url": "https://i.ytimg.com/x.jpg"}


def test_haiku_skips_fallback(monkeypatch):
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-haiku-4-5")
    calls = fake_client(monkeypatch, resp(model="claude-haiku-4-5"))
    ask()
    assert calls[0]["model"] == "claude-haiku-4-5" and "fallbacks" not in calls[0] and "betas" not in calls[0]


def test_refusal_and_missing_key_become_korean_errors(monkeypatch):
    fake_client(monkeypatch, resp(stop_reason="refusal", parsed_output=None))
    with pytest.raises(RuntimeError, match="주제를 바꿔"):
        ask()
    fake_client(monkeypatch, resp(parsed_output=None, stop_reason="max_tokens"))
    with pytest.raises(RuntimeError, match="대본을 받지 못했어요"):
        ask()
    fake_client(monkeypatch, exc=TypeError('Could not resolve authentication method. Expected api_key'))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ask()


def test_claude_ready_hint_and_cost(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    c = claude.Claude()
    assert not c.ready() and "ANTHROPIC_API_KEY" in c.hint
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "x")
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-sonnet-5-5-20260901")
    assert c.ready() and c.hint == c.model == "claude-sonnet-5-5-20260901" and c.cost(1_000_000, 0) == 2
    assert claude.cost("mystery", 1, 1) is None


@pytest.mark.live
def test_live_claude_writes_korean_script(ko):
    if not config.secret("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY 없음")
    s, usage = script.write(claude.Claude(), ko, "커피를 처음 마신 사람들")
    assert 6 <= len(s.scenes) <= 7 and all("No on-screen text" in x.prompt for x in s.scenes)
    assert usage["output_tokens"] > 0

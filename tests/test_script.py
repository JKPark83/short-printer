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
    for rule in ["100~110초", "정확히 13개", "52~58자", "58자를 넘지", "이모지·해시태그·괄호", "80~110단어",
                 "photoreal", "주인공·장소·시대·옷차림", "앞 5초", "No on-screen text, no numbers, no logos.",
                 "실존 인물의 얼굴", "No dialogue, no voices, no music.",
                 "훅", "존댓말", "사실 시트", "fact_ids", "prompt_ko",
                 "여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?", "질문형",
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


FACTS = [{"id": "F1", "text": "물은 100도에서 끓는다", "url": "https://a.go.kr/1", "kind": "official"},
         {"id": "F2", "text": "가격이 올랐다", "url": "https://news.kr/2", "kind": "news"}]


def test_write_and_revise_append_fact_sheet_only_when_facts(ko):
    llm = FakeLLM()
    script.write(llm, ko, "커피", facts=FACTS)
    script.write(llm, ko, "커피")
    assert llm.calls[0]["text"].endswith(
        "\n\n사실 시트(이것만 사실로 쓴다):\nF1. 물은 100도에서 끓는다\nF2. 가격이 올랐다 (보도)")
    assert "사실 시트" not in llm.calls[1]["text"] and script.sheet_block([]) == ""
    rev = FakeLLM(script.Revision(title="t", description="d", tags=[], sentences=["하나", "둘"]))
    s = OK.flat() | {"fact_ids": [["F1"], []]}
    new, _ = script.revise(rev, ko, s, "짧게", facts=FACTS)
    text = rev.calls[0]["text"]
    assert "사실 시트" in text and "F1." in text and "(근거: F1)" in text
    assert new["fact_ids"] == [["F1"], []]   # 문장만 바뀌어 근거는 그대로
    new, _ = script.revise(rev, ko, OK.flat() | {"fact_ids": [["F1"]]}, "짧게")   # 장면 수가 다른 예전 값은 비운다
    assert new["fact_ids"] == [[], []] and "사실 시트" not in rev.calls[1]["text"]


def test_flat_and_draft_carry_fact_ids_and_prompts_ko(ko):
    sc = script.Script(title="t", description="d", tags=[], sensitive="",
                       scenes=[script.Scene(sentence="하나", prompt="p", fact_ids=["F1"], prompt_ko="장면")])
    f = sc.flat()
    assert f["fact_ids"] == [["F1"]] and f["prompts_ko"] == ["장면"]
    out = script.Draft(title="t", description="d", tags=[], sentences=["하나", "둘"], prompts=["p1", "p3"],
                       fact_ids=[["F2"], []], prompts_ko=["가"])   # prompts_ko 개수가 틀리면 예전 풀이를 잇는다
    s = OK.flat() | {"fact_ids": [["F1"], ["F2"]], "prompts_ko": ["일", "이"]}
    new, _ = script.revise(FakeLLM(out), ko, s, "고쳐", draft=True)
    assert new["fact_ids"] == [["F2"], []] and new["prompts_ko"] == ["일", ""]   # p2→p3로 바뀐 장면의 풀이는 비운다
    # 모델이 fact_ids·prompts_ko를 빼먹으면 안 바꾼 장면의 근거가 지워지지 않는다
    bare = script.Draft(title="t", description="d", tags=[], sentences=["하나", "둘 2개"], prompts=["p1", "p2"])
    new, _ = script.revise(FakeLLM(bare), ko, s, "고쳐", draft=True)
    assert new["fact_ids"] == [["F1"], ["F2"]] and new["prompts_ko"] == ["일", "이"]
    assert script.unverified(new, FACTS) == []


def test_unverified_flags_number_sentences_without_known_facts():
    s = {"sentences": ["물은 100도에서 끓는다", "3월에 올랐다", "숫자 없음", "２배다", "1분이면 된다"],
         "fact_ids": [["F1"], ["F9"], [], [], ["F1", "F2"]]}
    assert script.unverified(s, FACTS) == [1, 3]
    assert script.unverified({"sentences": ["7가지"]}, FACTS) == [0]   # fact_ids 없는 예전 대본


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


def test_claude_web_search_limited_to_sites(monkeypatch):
    calls = fake_client(monkeypatch, resp())
    ask(web=["kma.go.kr", "yna.co.kr"])
    assert calls[0]["tools"] == [claude.WEB_SEARCH | {"allowed_domains": ["kma.go.kr", "yna.co.kr"]}]


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

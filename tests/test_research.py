import contextlib
from types import SimpleNamespace as NS

import anthropic
import pytest

from shorts_printer import config
from shorts_printer.adapters.claude_research import ClaudeResearch
from shorts_printer.core import channel, research
from shorts_printer.core.channel import ResearchCfg

CH = "ko-40sec-facts"


def _usage(inp, out, searches):
    return NS(input_tokens=inp, output_tokens=out, server_tool_use=NS(web_search_requests=searches))


def _cite(**kw):
    return NS(**kw)


def _client(create):
    """messages.stream(...)을 with로 열면 get_final_message가 create(**kw) 결과를 돌려주는 가짜."""
    def stream(**kw):
        return contextlib.nullcontext(NS(get_final_message=lambda: create(**kw)))
    return NS(beta=NS(messages=NS(stream=stream)))


def test_claude_research_collects_cited_sentences_over_pause_turn(monkeypatch):
    first = NS(stop_reason="pause_turn", model="claude-opus-5-5", usage=_usage(1000, 100, 2), content=[
        NS(type="server_tool_use", id="s1", input={"query": "물 끓는점"}),
        NS(type="web_search_tool_result", tool_use_id="s1", content=[]),
        NS(type="text", text=" 물은 100도에서 끓는다. ", citations=[
            _cite(type="web_search_result_location", url="https://a.go.kr/x", title="A")]),
    ])
    page = NS(type="web_fetch_result", url="https://b.go.kr/y", retrieved_at="2026-10-16T00:00:00Z",
              content=NS(title="B 문서"))
    second = NS(stop_reason="end_turn", model="claude-opus-5-5", usage=_usage(2000, 200, 1), content=[
        NS(type="web_fetch_tool_result", content=page),
        NS(type="text", text="얼음은 0도에서 녹는다.", citations=[_cite(type="char_location", document_index=0)]),
        NS(type="text", text="\n확인 못 함: 달은 치즈다", citations=None),   # 실제 응답처럼 줄바꿈으로 나뉜다
    ])
    calls, resps = [], [first, second]

    def create(**kw):
        calls.append(kw | {"messages": list(kw["messages"])})
        return resps.pop(0)

    client = _client(create)
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-opus-5-5")
    facts, usage = ClaudeResearch().gather("지시", "주제: 물", domains=["a.go.kr", "b.go.kr"], queries=3, max_pages=4)

    assert facts == [
        {"text": "도구: 검색 1번, 열람 1쪽", "url": "", "title": "", "published": "", "retrieved_at": ""},
        {"text": "검색 '물 끓는점': 0건", "url": "", "title": "", "published": "", "retrieved_at": ""},
        {"text": "물은 100도에서 끓는다.", "url": "https://a.go.kr/x", "title": "A", "published": "",
         "retrieved_at": ""},
        {"text": "얼음은 0도에서 녹는다.", "url": "https://b.go.kr/y", "title": "B 문서", "published": "",
         "retrieved_at": "2026-10-16T00:00:00Z"},
        {"text": "확인 못 함: 달은 치즈다", "url": "", "title": "", "published": "", "retrieved_at": ""},
    ]
    # 토큰 3000·300 → 3000*4/1e6 + 300*20/1e6 = 0.018, 검색 3번 0.03
    assert usage == {"model": "claude-opus-5-5", "input_tokens": 3000, "output_tokens": 300, "cost_usd": 0.048}
    search, fetch = calls[0]["tools"]
    assert search["allowed_domains"] == fetch["allowed_domains"] == ["a.go.kr", "b.go.kr"]
    assert search["max_uses"] == 3 and fetch["max_uses"] == 4 and fetch["citations"] == {"enabled": True}
    assert calls[0]["max_tokens"] == 128000 and calls[0]["fallbacks"] == "default"
    assert "output_format" not in calls[0] and len(calls[1]["messages"]) == 2   # pause_turn이면 이어 부른다


def test_claude_research_refusal(monkeypatch):
    resp = NS(stop_reason="refusal", model="claude-opus-5-5", usage=_usage(1, 1, 0), content=[])
    monkeypatch.setattr(anthropic, "Anthropic", lambda: _client(lambda **kw: resp))
    with pytest.raises(RuntimeError, match="거절"):
        ClaudeResearch().gather("s", "t", domains=["a.kr"], queries=1, max_pages=1)


def test_claude_research_without_domains_has_no_allowed_domains(monkeypatch):
    calls = []
    resp = NS(stop_reason="end_turn", model="m", usage=_usage(1, 1, 0), content=[
        NS(type="server_tool_use", id="u1", input={"url": "https://a.kr/p"}),
        NS(type="web_fetch_tool_result", tool_use_id="u1",
           content=NS(type="web_fetch_tool_result_error", error_code="url_not_accessible")),
    ])
    monkeypatch.setattr(anthropic, "Anthropic",
                        lambda: _client(lambda **kw: calls.append(kw) or resp))
    facts, _ = ClaudeResearch().gather("s", "t", domains=[], queries=1, max_pages=1)
    assert all("allowed_domains" not in t for t in calls[0]["tools"])
    # 도구 오류가 메모로 남아 못 찾은 이유를 알 수 있다
    assert [f["text"] for f in facts] == ["도구: 검색 0번, 열람 1쪽",
                                          "열람 'https://a.kr/p' 오류: url_not_accessible"]


def test_parse_joins_split_citation_blocks_into_one_fact_per_line():
    """인용 경계로 쪼개진 줄(afe1 F1 모양): 한국어 문장 + 꼬리표가 사실, 원문 조각은 quote로."""
    from shorts_printer.adapters.claude_research import parse
    en = ("congenitally blind speakers gesture despite their lack of a visual model, "
          "even when they speak to a blind listener")
    hit = NS(type="web_search_result_location", url="https://nature.com/a", title="Nature",
             cited_text=f"We show that {en}.")
    ko = NS(type="web_search_result_location", url="https://ncbi.nlm.nih.gov/b", title="StatPearls",
            cited_text="Normal urine odor is described as urinoid.")
    facts = parse([[
        NS(type="text", text="앞을 못 본 사람도 손짓을 했다고 한 연구가 보고했다. ", citations=None),
        NS(type="text", text=en, citations=[hit]),
        NS(type="text", text=" (연구 1편, 28명, 1998 Nature)\nStatPearls 소변검사 항목에서 ", citations=None),
        NS(type="text", text="정상 소변 냄새는 \"Urinoid\"로 적혀 있다", citations=[ko]),   # 모델이 쓴 한국어 인용
        NS(type="text", text=" (교과서).\n확인 못 함: 손을 묶으면 말이 막힌다", citations=None),
    ]])[1:]
    assert facts == [
        {"text": "앞을 못 본 사람도 손짓을 했다고 한 연구가 보고했다. (연구 1편, 28명, 1998 Nature)",
         "url": "https://nature.com/a", "title": "Nature", "published": "", "retrieved_at": "", "quote": en},
        {"text": "StatPearls 소변검사 항목에서 정상 소변 냄새는 \"Urinoid\"로 적혀 있다 (교과서).",
         "url": "https://ncbi.nlm.nih.gov/b", "title": "StatPearls", "published": "", "retrieved_at": ""},
        {"text": "확인 못 함: 손을 묶으면 말이 막힌다", "url": "", "title": "", "published": "", "retrieved_at": ""},
    ]
    # 한국어 원문 구절·숫자를 문장 가운데 인용하면 문장에 그대로 남는다
    kdca = NS(type="web_search_result_location", url="https://kdca.go.kr/c", title="질병관리청",
              cited_text="예방접종 후 면역은 약 6개월 정도 지속됩니다.")
    mid = parse([[NS(type="text", text="면역은 ", citations=None), NS(type="text", text="6개월", citations=[kdca]),
                  NS(type="text", text=" 정도 간다 (교과서)\n", citations=None)]])
    assert mid[1]["text"] == "면역은 6개월 정도 간다 (교과서)" and "quote" not in mid[1]
    # 원문 조각만 있고 문장이 꼬리표뿐이면 원문이 곧 사실 문장
    only = parse([[NS(type="text", text=en, citations=[hit]), NS(type="text", text=" (교과서)", citations=None)]])
    assert only[1]["text"] == f"{en} (교과서)" and "quote" not in only[1]


class FakeResearcher:
    label, hint = "가짜조사", ""

    def __init__(self, facts):
        self.facts, self.calls = facts, []

    def ready(self):
        return True

    def gather(self, system, text, *, domains, queries, max_pages):
        self.calls.append({"system": system, "text": text, "domains": domains})
        return self.facts, {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01}


def _ch(**cfg):
    return channel.load(CH).model_copy(update={"research": ResearchCfg(**cfg)})


def _f(text, url):
    return {"text": text, "url": url, "title": "t", "published": "", "retrieved_at": ""}


def test_gather_numbers_sites_kinds_and_merges():
    rs = FakeResearcher([_f("가", "https://www.kdca.go.kr/a"), _f("나", "https://news.yna.co.kr/b"),
                         _f("가", "https://other.go.kr/c"), _f("다", "https://yna.co.kr/d")])
    doc, usage = research.gather(rs, _ch(domains=["kdca.go.kr"], news=["yna.co.kr"]), "독감", "주장 1")
    facts = doc["facts"]
    assert [f["id"] for f in facts] == ["F1", "F2", "F3"] and doc["queries"] == []
    assert [(f["text"], f["site"], f["kind"]) for f in facts] == [
        ("가", "kdca.go.kr", "official"), ("나", "news.yna.co.kr", "news"), ("다", "yna.co.kr", "news")]
    assert all(f["retrieved_at"] for f in facts) and usage["cost_usd"] == 0.01
    call = rs.calls[0]
    assert call["domains"] == ["kdca.go.kr", "yna.co.kr"] and "확인할 주장·참고:\n주장 1" in call["text"]
    assert "yna.co.kr" in call["system"] and "${" not in call["system"]
    research.gather(rs, _ch(domains=["kdca.go.kr"]), "독감", None)
    assert rs.calls[1]["text"] == "주제: 독감"
    # news에 www.를 붙여 적어도 www·m 기사 모두 보도로 본다
    rs = FakeResearcher([_f("라", "https://www.yna.co.kr/v/1"), _f("마", "https://m.yna.co.kr/x")])
    doc, _ = research.gather(rs, _ch(news=["https://www.yna.co.kr/"]), "독감", None)
    assert [f["kind"] for f in doc["facts"]] == ["news", "news"]


def test_gather_open_searches_anywhere_and_marks_web():
    rs = FakeResearcher([_f("가", "https://blog.naver.com/x"), _f("나", "https://www.kdca.go.kr/a"),
                         _f("다", "https://yna.co.kr/d")])
    doc, _ = research.gather(rs, _ch(domains=["kdca.go.kr"], news=["yna.co.kr"], open=True), "독감", None)
    assert rs.calls[0]["domains"] == [] and "일반 웹도 쓴다" in rs.calls[0]["system"]
    assert [f["kind"] for f in doc["facts"]] == ["web", "official", "news"]
    assert research.sheet(doc["facts"]) == "F1. 가 (웹)\nF2. 나\nF3. 다 (보도)"
    research.gather(rs, _ch(domains=["kdca.go.kr"]), "독감", None)   # 기본은 닫힘
    assert not _ch(domains=["kdca.go.kr"]).research.open and "일반 웹도 쓴다" not in rs.calls[1]["system"]


def test_gather_stops_without_sites_or_facts():
    with pytest.raises(RuntimeError, match="조사 사이트"):
        research.gather(FakeResearcher([_f("가", "https://a.kr")]), _ch(), "주제", None)
    doc, _ = research.gather(FakeResearcher([_f("확인 못 함: 달은 치즈다", "")]), _ch(news=["yna.co.kr"]), "주제", None)
    assert doc["facts"] == [] and doc["notes"] == ["확인 못 함: 달은 치즈다"]


def test_sheet_marks_news():
    facts = [{"id": "F1", "text": "공식.", "kind": "official"}, {"id": "F2", "text": "기사.", "kind": "news"},
             {"id": "F3", "text": "새 제도 (2026-10-12 보도, 연합뉴스)", "kind": "news"}]
    assert research.sheet(facts) == "F1. 공식.\nF2. 기사. (보도)\nF3. 새 제도 (2026-10-12 보도, 연합뉴스)"


def test_research_cfg_normalizes_domains():
    r = ResearchCfg(domains=[" https://WWW.KDCA.go.kr/board/1 ", "http://a.kr", "a.kr/", "", "kdca.go.kr",
                             "b.kr:443", "c.kr?x=1", "d.kr#top"],
                    news=["https://Yna.co.kr/"])
    assert r.domains == ["kdca.go.kr", "a.kr", "b.kr", "c.kr", "d.kr"] and r.news == ["yna.co.kr"]
    assert "kdca.go.kr" in channel.load(CH).research.domains   # 채널 허용 목록도 같은 검증을 지난다


def test_gather_caps_facts_and_keeps_quote():
    rs = FakeResearcher([_f(f"사실 {i}", f"https://kdca.go.kr/{i}") | {"quote": "원문"} for i in range(15)])
    doc, _ = research.gather(rs, _ch(domains=["kdca.go.kr"]), "독감", None)
    assert len(doc["facts"]) == research.MAX_FACTS and doc["facts"][-1]["text"] == "사실 11"
    assert doc["facts"][0]["quote"] == "원문" and "사실 15개 가운데 앞 12개만 썼다" in doc["notes"]


def test_long_channel_uses_its_own_fact_cap():
    rs = FakeResearcher([_f(f"사실 {i}", f"https://kdca.go.kr/{i}") for i in range(15)])
    ch = _ch(domains=["kdca.go.kr"])
    long = ch.model_copy(update={"format": "long", "long": channel.LongCfg(max_facts=14)})
    doc, _ = research.gather(rs, long, "한국전쟁", None)
    assert len(doc["facts"]) == 14 and "앞 14개만" in doc["notes"][-1] and "14" in rs.calls[0]["system"]
    assert research.max_facts(ch) == research.MAX_FACTS   # 숏폼은 그대로 12

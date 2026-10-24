import shutil
from datetime import datetime
from types import SimpleNamespace

import pytest

from shorts_printer.core import channel, pipeline, research, trends
from shorts_printer.ports.llm import add_usage

CH = "ko-40sec-facts"
USAGE = {"model": "m", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}


class FakeLLM:
    """ask 호출(system·text·images)을 남기고 answer(system, text, images)가 돌려준 값을 답한다."""
    label = "가짜"

    def __init__(self, answer=None):
        self.calls, self.answer = [], answer

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append({"system": system, "text": text, "images": list(images), "web": web})
        return self.answer(system, text, list(images))


def sv(llm=None, ch=None):
    return SimpleNamespace(channel=ch or channel.load(CH), llm=llm or FakeLLM())


def new(keyword=""):
    return trends.Trend.create(CH, keyword)


def logs(t):
    return t.tail()


def stop(*a):
    raise StopIteration


def idea(topic, fit=3, fresh=3, safe=3, content="핵심 답", trend=3, curious=3):
    return trends.IdeaOut(topic=topic, angle="a", content=content, format="잡학·상식", why_now="w",
                          scores=trends.Scores(trend=trend, curious=curious, fit=fit, fresh=fresh, safe=safe),
                          search_terms=["x"])


def old_record(steps):
    """예전 인기 쇼츠 분석 기록 모양: mode·period·quota와 수집·분석·선정 세 단계."""
    t = new("자취")
    t.update(mode="trend", period="3d", quota=101, progress={"done": 8, "total": 8},
             steps={s: {"status": st, "engine": None, "sec": None} for s, st in steps.items()})
    return t


W5 = {"trend": 20, "curious": 25, "fit": 30, "fresh": 10, "safe": 15}


def test_trends_cfg_takes_five_weights_summing_100():
    assert channel.TrendsCfg(production="p").weights == W5
    for bad in ({**W5, "safe": 14},
                {"fit": 54, "fresh": 23, "safe": 23},   # 예전 세 개짜리
                {"trend": 35, "fit": 35, "fresh": 15, "safe": 15}):   # 예전 네 개짜리
        with pytest.raises(ValueError, match="다섯 개, 합 100"):
            channel.TrendsCfg(production="p", weights=bad)
    cfg = channel.TrendsCfg(production="p", region="KR", keywords=["x"])   # 예전 키는 무시한다
    assert not {"region", "language"} & set(type(cfg).model_fields) and cfg.keywords == ["x"]
    for cid in ("ko-40sec-facts", "ja-korea-trip"):
        assert sum(channel.load(cid).trends.weights.values()) == 100


def test_create_keeps_request_up_to_max_without_period_or_mode():
    t = new("  " + "가" * (trends.MAX_REQUEST + 5) + "  ")
    d = t.data
    assert d["keyword"] == "가" * trends.MAX_REQUEST and d["channel"] == CH
    assert "period" not in d and "mode" not in d and list(d["steps"]) == ["pick"]
    with pytest.raises(TypeError):   # 기간 인자는 없다
        trends.Trend.create(CH, "", "3d")
    assert d["popular"] is False


def test_finish_ideas_uses_five_weights_and_top_10():
    out = trends.IdeasOut(summary="방향", picks=[idea(f"주제{i}", curious=1 + i % 5) for i in range(12)])
    r = trends.finish_ideas(out, W5)
    assert len(r["picks"]) == 10 and r["excluded"] == [] and r["summary"] == "방향"
    top = r["picks"][0]
    assert top["scores"] == {"trend": 3, "curious": 5, "fit": 3, "fresh": 3, "safe": 3}
    assert top["refs"] == [] and top["content"] == "핵심 답"
    assert top["total"] == round(25 + (20 + 30 + 10 + 15) * 0.5)
    r = trends.finish_ideas(trends.IdeasOut(summary="s", picks=[idea("x", fit=5, fresh=1, safe=9)]),
                            {"trend": 0, "curious": 0, "fit": 0, "fresh": 0, "safe": 100})
    assert r["picks"][0]["scores"]["safe"] == 5 and r["picks"][0]["total"] == 100   # 9는 5로, 가중치는 받은 값 그대로


def test_pick_message_has_request_today_weights_and_this_channels_topics():
    pipeline.Job.create(CH, "우리 채널 주제", "v")
    pipeline.Job.create("en-space-facts", "다른 채널 주제", "v")
    ch = channel.load(CH)
    ch = ch.model_copy(update={"trends": ch.trends.model_copy(update={"weights": {**W5, "fit": 35, "fresh": 5}})})
    llm = FakeLLM(stop)
    with pytest.raises(StopIteration):
        trends.step_pick(new("겨울 위주로\n초등학생도 알아듣게"), sv(llm, ch))
    call = llm.calls[0]
    text = call["text"]
    assert "추가 요청: 겨울 위주로\n초등학생도 알아듣게" in text and f"오늘: {datetime.now():%Y-%m-%d}" in text
    assert "- 우리 채널 주제" in text and "다른 채널 주제" not in text
    assert "trend 화제성 (가중치 20)" in text and "fit 제작 적합도 (가중치 35)" in text and "(가중치 5)" in text
    assert "좁힐 주제" not in text
    assert call["system"] == trends.system_idea(ch) and call["web"] == research.sites(ch) and call["images"] == []
    with pytest.raises(StopIteration):
        trends.step_pick(new(), sv(llm, ch))
    assert "추가 요청: 없음" in llm.calls[1]["text"]


def test_run_picks_topics_and_brief():
    pipeline.Job.create(CH, "우리 채널 주제", "v")
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="궁금증", picks=[idea("손가락 꺾는 소리", content="관절 기포가 터지는 소리")]),
                              USAGE))
    t = new("겨울")
    trends.run(t, sv(llm))
    d = t.data
    assert d["status"] == "done" and list(d["steps"]) == ["pick"] and d["usage"]["cost_usd"] == 0.01
    assert "quota" not in d and "progress" not in d
    msgs = logs(t)
    assert any("주제 10개 고르는 중 (이미 만든 주제 1개" in m for m in msgs)
    assert any(" m 답: 주제 1개 → 점수" in m for m in msgs)
    assert any("추천 1: 손가락 꺾는 소리 (" in m and "제작 적합도 " in m for m in msgs)
    p = t.doc("picks.json")["picks"][0]
    assert p["topic"] == "손가락 꺾는 소리" and p["refs"] == [] and t.doc("videos.json") is None
    assert trends.brief(t, p).startswith("방향: a\n내용: 관절 기포가 터지는 소리\n포맷: 잡학·상식")


def test_run_retry_after_failure(monkeypatch):
    t, services = new(), sv()

    def fail(_t, s):
        assert s is services
        raise RuntimeError("일부러")
    monkeypatch.setattr(trends, "step_pick", fail)
    with pytest.raises(RuntimeError):
        trends.run(t, services)
    assert t.data["status"] == "failed" and t.data["error"]["step"] == "pick"
    monkeypatch.setattr(trends, "step_pick", lambda _t, s: "m")
    trends.run(t, services)
    assert t.data["status"] == "done" and t.data["steps"]["pick"]["engine"] == "m"


def test_old_record_retry_runs_only_pick(monkeypatch):
    t = old_record({"collect": "failed", "analyze": "pending", "pick": "pending"})
    ran = []
    monkeypatch.setattr(trends, "step_pick", lambda _t, s: ran.append(_t.id) or "m")
    trends.run(t, sv())
    d = t.data
    assert ran == [t.id] and d["status"] == "done" and d["steps"]["pick"]["status"] == "done"
    assert d["steps"]["collect"]["status"] == "failed"   # 예전 단계는 건드리지 않는다


def test_brief_ignores_old_refs():
    t = old_record({"collect": "done", "analyze": "done", "pick": "done"})
    t.put("videos.json", [{"id": "v1", "title": "쇼츠", "duration": 30.0}])
    t.put("analyses.json", {"v1": {"status": "ok", "avg_shot_sec": 3.0, "claude": {
        "hook": "h", "footage_desc": "f", "text_overlay": "o", "why_popular": "w"}}})
    p = {"angle": "a", "format": "기타", "why_now": "지금", "search_terms": ["x", "y"], "refs": ["v1"]}
    assert trends.brief(t, p) == "방향: a\n포맷: 기타\n지금 만들 이유: 지금\n화면 검색어 후보: x, y"


def test_web_falls_back_to_anywhere_without_sites():
    ch = channel.load(CH)
    ch = ch.model_copy(update={"research": ch.research.model_copy(update={"domains": [], "news": []})})
    assert trends._web(ch) is True


def test_add_usage():
    a = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.1}
    assert add_usage(None, a) == a
    assert add_usage(a, a | {"cost_usd": None})["cost_usd"] is None


def test_system_idea_uses_ideas_md_or_concept_only(tmp_path):
    ch = channel.load(CH)
    s = trends.system_idea(ch)
    assert "하품이 옮는 이유" in s and ch.concept in s and "다리털" in s and "${" not in s
    assert "인기 영상 자료 없이" not in s and "추가 요청" in s
    shutil.copytree(ch.dir, tmp_path / CH)
    (tmp_path / CH / "ideas.md").unlink()
    s = trends.system_idea(ch.model_copy(update={"dir": tmp_path / CH}))
    assert "하품이 옮는 이유" not in s and "비어 있으면 채널 분야 안에서" in s


def test_again_avoids_shown_topics():
    t = new("겨울")
    t.update(avoid=["예전 주제"])
    t.put("picks.json", {"summary": "", "excluded": [], "picks": [{"topic": "정전기"}, {"topic": "입김"}]})
    n = t.again()
    assert (n.data["keyword"], n.data["avoid"]) == ("겨울", ["예전 주제", "정전기", "입김"]) and "mode" not in n.data
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="", picks=[idea("새 주제")]), USAGE))
    trends.run(n, sv(llm))
    assert "앞서 추천한 주제:\n- 예전 주제\n- 정전기\n- 입김" in llm.calls[0]["text"]


def test_fresh_run_avoids_topics_shown_in_earlier_runs():
    old = new()
    old.put("picks.json", {"summary": "", "excluded": [], "picks": [{"topic": "단풍 색"}, {"topic": "고구마 냉장고"}]})
    other = trends.Trend.create("ja-korea-trip")
    other.put("picks.json", {"summary": "", "excluded": [], "picks": [{"topic": "다른 채널 주제"}]})
    t = new()   # 다시 추천이 아니라 새로 시작한 주제 찾기
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="", picks=[idea("새 주제")]), USAGE))
    trends.run(t, sv(llm))
    text = llm.calls[0]["text"]
    assert "앞서 추천한 주제:\n- 단풍 색\n- 고구마 냉장고" in text and "다른 채널 주제" not in text


def test_pick_drops_repeats_of_earlier_topics_and_asks_again():
    pipeline.Job.create(CH, "하품은 왜 옮을까?", "v")
    old = new()
    old.put("picks.json", {"summary": "", "excluded": [], "picks": [{"topic": "단풍은 왜 빨강과 노랑으로 갈릴까?"}]})
    answers = iter([[idea("하품은 왜 옮을까"), idea("같은 나무인데 단풍은 왜 빨강과 노랑으로 갈릴까?"), idea("간은 잘라 내도 다시 자랄까?")],
                    [idea("손톱은 왜 발톱보다 빨리 자랄까?"), idea("눈썹은 왜 머리카락만큼 안 자랄까?"), idea("간은 잘라 내도 다시 자랄까!")]])
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="", picks=next(answers)), USAGE))
    t = new()
    trends.run(t, sv(llm))
    # 겹친 둘을 빼니 절반이 안 돼 다시 묻고, 그때는 뺀 주제도 알린다. 두 번째 답의 겹침(첫 답과 같은 것)도 뺀다
    assert len(llm.calls) == 2 and "- 하품은 왜 옮을까\n" in llm.calls[1]["text"]
    assert [p["topic"] for p in t.doc("picks.json")["picks"]] == ["간은 잘라 내도 다시 자랄까?", "손톱은 왜 발톱보다 빨리 자랄까?",
                                                                 "눈썹은 왜 머리카락만큼 안 자랄까?"]
    assert any("겹쳐 2개를 뺐어요" in m for m in logs(t))


def _video(vid, title, hours_ago, views, dur="PT40S", desc="설명", ch="UC1"):
    at = datetime.now(trends.UTC) - trends.timedelta(hours=hours_ago)
    return {"id": vid, "snippet": {"title": title, "channelTitle": "c", "channelId": ch, "description": desc,
                                   "publishedAt": at.isoformat().replace("+00:00", "Z")},
            "contentDetails": {"duration": dur}, "statistics": {"viewCount": str(views)}}


def test_popular_pick_sends_shorts_ranked_by_views_per_hour_and_keeps_refs(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    calls = []
    items = [_video("a", "심장이 멈추면", 10, 1000), _video("b", "뼈의 비밀", 100, 50000, ch="UC2"),
             _video("c", "콩팥 이야기", 5, 900, ch="UC3"), _video("d", "긴 영상 몸", 1, 10**6, "PT5M"),
             _video("e", "english only", 1, 10**6, desc="no korean")]
    chans = [{"id": "UC1", "statistics": {"subscriberCount": "400"}},
             {"id": "UC2", "statistics": {"subscriberCount": "0", "hiddenSubscriberCount": True}}]

    def api(path, **q):
        calls.append((path, q))
        if path == "search":
            return {"items": [{"id": {"videoId": i["id"]}} for i in items]}
        return {"items": chans if path == "channels" else items}

    monkeypatch.setattr(trends, "_api", api)
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="s", picks=[idea("하품", fit=5).model_copy(update={"refs": [2]})]),
                              USAGE))
    t = trends.Trend.create(CH, popular=True)
    trends.run(t, sv(llm))
    assert calls[0][1]["regionCode"] == "KR" and "인체 | 우리몸" in calls[0][1]["q"]
    assert [v["id"] for v in t.doc("videos.json")] == ["b", "c", "a"]   # 시간당 500·180·100, 긴 것·한국어 없는 것 빠짐
    text = llm.calls[0]["text"]
    assert "요즘 뜨는 쇼츠" in text and "1. 뼈의 비밀" in text and "긴 영상" not in text and "english" not in text
    # 구간끼리 순위: c·a는 24시간 안 2개, b는 3~7일 1개. 구독자 숨긴 UC2·없는 UC3는 배수가 없다
    assert "시간당 500 · 100시간 전 · 3~7일 1개 중 1위\n" in text
    assert "시간당 180 · 5시간 전 · 24시간 안 2개 중 1위\n" in text
    assert "시간당 100 · 10시간 전 · 24시간 안 2개 중 2위 · 구독자의 2.5배" in text
    assert calls[2] == ("channels", {"part": "statistics", "id": "UC1,UC2,UC3"})
    assert t.doc("picks.json")["picks"][0]["refs"] == [2]
    assert t.again().data["popular"] is True
    trends.step_pick(t, sv(llm))   # 다시 고를 때는 모은 쇼츠를 다시 쓴다
    assert len(calls) == 3


def test_popular_without_key_fails_with_hint(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    t = trends.Trend.create(CH, popular=True)
    with pytest.raises(RuntimeError):
        trends.run(t, sv(FakeLLM(stop)))
    assert t.data["status"] == "failed" and "YOUTUBE_API_KEY" in t.data["error"]["message"]


def _long_ch():
    """channel.format·long이 없던 때도 돌게 model_copy로 롱폼 값을 얹는다."""
    return channel.load(CH).model_copy(update={"format": "long",
                                               "long": SimpleNamespace(minutes=(8, 12), max_facts=40)})


def test_system_idea_long_uses_map_history_prompt():
    s = trends.system_idea(_long_ch())
    assert "지도 규칙" in s and "8~12분" in s and "40개 이상" in s and "${" not in s
    assert "지도 규칙" not in trends.system_idea(channel.load(CH))


def test_long_popular_searches_medium_videos_without_shorts_filter(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    calls = []
    items = [_video("a", "임진왜란 지도", 10, 1000, "PT11M"), _video("b", "한국전쟁 전선", 30, 9000, "PT40S", ch="UC2"),
             _video("c", "6·25 낙동강", 5, 900, "PT8M", ch="UC3")]

    def api(path, **q):
        calls.append((path, q))
        if path == "search":
            return {"items": [{"id": {"videoId": i["id"]}} for i in items]}
        return {"items": [] if path == "channels" else items}

    monkeypatch.setattr(trends, "_api", api)
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="s", picks=[idea("임진왜란")]), USAGE))
    t = trends.Trend.create(CH, popular=True)
    trends.run(t, sv(llm, _long_ch()))
    assert calls[0][1]["videoDuration"] == "medium"
    videos = t.doc("videos.json")
    assert [v["id"] for v in videos] == ["b", "c", "a"]   # 시간당 300·180·100, 40초짜리도 남는다
    assert videos[2]["url"].endswith("watch?v=a")
    assert "요즘 뜨는 영상" in llm.calls[0]["text"] and "지도 규칙" in llm.calls[0]["system"]

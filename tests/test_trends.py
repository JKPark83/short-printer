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


def idea(topic, fit=3, fresh=3, safe=3, content="핵심 답"):
    return trends.IdeaOut(topic=topic, angle="a", content=content, format="잡학·상식", why_now="w",
                          scores=trends.Scores(fit=fit, fresh=fresh, safe=safe), search_terms=["x"])


def old_record(steps):
    """예전 인기 쇼츠 분석 기록 모양: mode·period·quota와 수집·분석·선정 세 단계."""
    t = new("자취")
    t.update(mode="trend", period="3d", quota=101, progress={"done": 8, "total": 8},
             steps={s: {"status": st, "engine": None, "sec": None} for s, st in steps.items()})
    return t


def test_trends_cfg_takes_fit_fresh_safe_summing_100():
    assert channel.TrendsCfg(production="p").weights == {"fit": 54, "fresh": 23, "safe": 23}
    for bad in ({"fit": 50, "fresh": 25, "safe": 24},
                {"trend": 35, "fit": 35, "fresh": 15, "safe": 15},   # 예전 네 개짜리
                {"fit": 50, "fresh": 50}):
        with pytest.raises(ValueError, match="fit·fresh·safe 세 개, 합 100"):
            channel.TrendsCfg(production="p", weights=bad)
    cfg = channel.TrendsCfg(production="p", region="KR", keywords=["x"])   # 예전 키는 무시한다
    assert not {"region", "language", "keywords"} & set(type(cfg).model_fields)
    for cid in ("ko-40sec-facts", "ja-korea-trip"):
        assert sum(channel.load(cid).trends.weights.values()) == 100


def test_create_keeps_request_up_to_max_without_period_or_mode():
    t = new("  " + "가" * (trends.MAX_REQUEST + 5) + "  ")
    d = t.data
    assert d["keyword"] == "가" * trends.MAX_REQUEST and d["channel"] == CH
    assert "period" not in d and "mode" not in d and list(d["steps"]) == ["pick"]
    with pytest.raises(TypeError):   # 기간 인자는 없다
        trends.Trend.create(CH, "", "3d")


def test_finish_ideas_uses_three_weights_and_top_10():
    out = trends.IdeasOut(summary="방향", picks=[idea(f"주제{i}", fit=1 + i % 5) for i in range(12)])
    r = trends.finish_ideas(out, {"fit": 54, "fresh": 23, "safe": 23})
    assert len(r["picks"]) == 10 and r["excluded"] == [] and r["summary"] == "방향"
    top = r["picks"][0]
    assert top["scores"] == {"fit": 5, "fresh": 3, "safe": 3} and top["refs"] == [] and top["content"] == "핵심 답"
    assert top["total"] == round(54 + 23 * 0.5 + 23 * 0.5)
    r = trends.finish_ideas(trends.IdeasOut(summary="s", picks=[idea("x", fit=5, fresh=1, safe=9)]),
                            {"fit": 0, "fresh": 0, "safe": 100})
    assert r["picks"][0]["scores"]["safe"] == 5 and r["picks"][0]["total"] == 100   # 9는 5로, 가중치는 받은 값 그대로


def test_pick_message_has_request_today_weights_and_this_channels_topics():
    pipeline.Job.create(CH, "우리 채널 주제", "v")
    pipeline.Job.create("en-space-facts", "다른 채널 주제", "v")
    ch = channel.load(CH)
    ch = ch.model_copy(update={"trends": ch.trends.model_copy(update={"weights": {"fit": 60, "fresh": 25, "safe": 15}})})
    llm = FakeLLM(stop)
    with pytest.raises(StopIteration):
        trends.step_pick(new("겨울 위주로\n초등학생도 알아듣게"), sv(llm, ch))
    call = llm.calls[0]
    text = call["text"]
    assert "추가 요청: 겨울 위주로\n초등학생도 알아듣게" in text and f"오늘: {datetime.now():%Y-%m-%d}" in text
    assert "- 우리 채널 주제" in text and "다른 채널 주제" not in text
    assert "(가중치 60)" in text and "(가중치 25)" in text and "화제성" not in text and "좁힐 주제" not in text
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

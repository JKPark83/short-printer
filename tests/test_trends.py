import io
import json
import shutil
import threading
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from shorts_printer.core import channel, pipeline, trends
from shorts_printer.infra.store import store
from shorts_printer.ports.llm import add_usage

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
CH = "ko-40sec-facts"
USAGE = {"model": "m", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}


class FakeLLM:
    """ask 호출(system·text·images)을 남기고 answer(system, text, images)가 돌려준 값을 답한다."""
    label = "가짜"

    def __init__(self, answer=None):
        self.calls, self.answer = [], answer

    def ask(self, system, text, schema, *, refusal, what, images=()):
        self.calls.append({"system": system, "text": text, "images": list(images)})
        return self.answer(system, text, list(images))


def sv(llm=None, ch=None):
    return SimpleNamespace(channel=ch or channel.load(CH), llm=llm or FakeLLM())


def new(keyword="", period=trends.DEFAULT_PERIOD):
    return trends.Trend.create(CH, keyword, period)


def item(vid, title="한국 영상", dur="PT30S", views=1000, hours_ago=10, likes=10, comments=0):
    pub = NOW - timedelta(hours=hours_ago)
    return {"id": vid, "snippet": {"title": title, "description": "", "channelTitle": "채널",
                                   "publishedAt": pub.isoformat().replace("+00:00", "Z"),
                                   "thumbnails": {"high": {"url": f"https://i.ytimg.com/{vid}.jpg"}}},
            "contentDetails": {"duration": dur},
            "statistics": {"viewCount": str(views), "likeCount": str(likes), "commentCount": str(comments)}}


def analysis(**kw):
    base = dict(topic="t", format="잡학·상식", hook="h", footage_type="스톡 영상", footage_desc="d", narration="TTS",
                text_overlay="o", why_popular="w", replicable=4, replicable_reason="r")
    return trends.VideoAnalysis(**base | kw)


def test_iso_seconds():
    assert trends.iso_seconds("PT1M5S") == 65
    assert trends.iso_seconds("PT59.5S") == 59.5
    assert trends.iso_seconds("PT1H") == 3600
    assert trends.iso_seconds("P0D") == 0
    assert trends.iso_seconds("garbage") == 0


def test_rank_filters_long_and_non_korean_then_sorts_by_views_per_hour():
    out = trends.rank([
        item("slow", views=1000, hours_ago=10),           # 100/h
        item("fast", views=1000, hours_ago=2, likes=40, comments=10),   # 500/h
        item("long", dur="PT3M1S"),
        item("eng", title="english only"),
        item("zero", dur="P0D"),                           # 라이브 등 길이 0
        item("fresh", views=300, hours_ago=0),             # 1시간 미만은 1시간으로
    ], NOW, "ko")
    assert [v["id"] for v in out] == ["fast", "fresh", "slow"]
    fast = out[0]
    assert fast["views_per_hour"] == 500 and fast["engagement"] == 0.05 and fast["age_hours"] == 2
    assert fast["url"] == "https://www.youtube.com/shorts/fast" and fast["thumb"].endswith("fast.jpg")
    assert out[1]["age_hours"] == 1 and out[1]["views_per_hour"] == 300


def test_rank_script_filter_by_language():
    items = [item("ko", title="한국 영상"), item("ja", title="日本の動画"), item("kana", title="すごい"), item("en", title="english")]
    assert {v["id"] for v in trends.rank(items, NOW, "ja")} == {"ja", "kana"}
    assert {v["id"] for v in trends.rank(items, NOW, "en")} == {"ko", "ja", "kana", "en"}   # SCRIPTS에 없으면 거르지 않는다


def test_is_short_by_redirect(monkeypatch):
    def fake(req, timeout):   # 일반 영상은 /watch로 넘어간다
        return _Resp(req.full_url.replace("/shorts/", "/watch?v=") if "normal" in req.full_url else req.full_url)
    monkeypatch.setattr(trends, "urlopen", fake)
    assert trends.is_short("abc") is True
    assert trends.is_short("normal") is False

    def boom(req, timeout):
        raise OSError("down")
    monkeypatch.setattr(trends, "urlopen", boom)
    assert trends.is_short("abc") is True   # 확인 못 하면 통과


class _Resp:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def geturl(self):
        return self.url


def http_error(code, reason):
    body = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()
    return HTTPError("https://x?key=SECRET", code, "err", {}, io.BytesIO(body))


@pytest.mark.parametrize("code,reason,match", [
    (403, "quotaExceeded", "할당량"),
    (400, "keyInvalid", "키가 맞지 않거나"),
    (403, "accessNotConfigured", "사용 설정"),
])
def test_api_errors_are_korean(monkeypatch, code, reason, match):
    def fail(req, timeout):
        raise http_error(code, reason)
    monkeypatch.setattr(trends, "urlopen", fail)
    with pytest.raises(RuntimeError, match=match) as e:
        trends._api("search", q="x")
    assert "SECRET" not in str(e.value)


def test_collect_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(trends.config, "secret", lambda k: "")
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        trends.step_collect(new(), sv())


def test_collect_counts_quota_skips_normal_videos_and_ranks(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: True)
    calls = []

    def api(path, **q):
        calls.append((path, q))
        if path == "search":
            return {"items": [{"id": {"videoId": v}} for v in ("a", "b", "c", "d")]}
        return {"items": [item("a", views=100), item("b", views=900), item("c", views=500), item("d", views=300)]}
    monkeypatch.setattr(trends, "_api", api)
    monkeypatch.setattr(trends, "is_short", lambda vid: vid != "c")
    t = new("  커피  ", "1d")
    assert t.data["keyword"] == "커피" and t.data["channel"] == CH
    assert trends.step_collect(t, sv()) == "YouTube 3개"
    q = calls[0][1]
    assert q["q"] == "커피" and q["videoDuration"] == "short" and calls[1][1]["id"] == "a,b,c,d"
    assert q["regionCode"] == "KR" and q["relevanceLanguage"] == "ko"
    vids = t.doc("videos.json")
    assert [(v["id"], v["rank"]) for v in vids] == [("b", 1), ("d", 2), ("a", 3)]
    assert t.data["quota"] == 101


def test_collect_fails_under_three_and_counts_only_used_quota(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: True)
    monkeypatch.setattr(trends, "is_short", lambda vid: True)
    hits = {"ids": ["a", "b"]}

    def api(path, **q):
        if path == "search":
            return {"items": [{"id": {"videoId": v}} for v in hits["ids"]]}
        return {"items": [item(v) for v in hits["ids"]]}
    monkeypatch.setattr(trends, "_api", api)
    t = new()
    with pytest.raises(RuntimeError, match="한국어 쇼츠가 2개뿐"):   # 2개로 넘기면 분석이 매번 실패하고 빠져나올 수 없다
        trends.step_collect(t, sv())
    assert t.data["quota"] == 101
    hits["ids"] = []
    t = new()
    with pytest.raises(RuntimeError, match="0개뿐"):
        trends.step_collect(t, sv())
    assert t.data["quota"] == 100   # 결과가 없으면 videos.list를 부르지 않는다


def test_collect_keywords_or_query_and_channel_region(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: True)
    calls = []

    def api(path, **q):
        calls.append(q)
        return {"items": []}
    monkeypatch.setattr(trends, "_api", api)
    ch = channel.load(CH)
    ch = ch.model_copy(update={"language": "ja", "trends": ch.trends.model_copy(
        update={"region": "JP", "keywords": ["雑学", "豆知識"]})})
    with pytest.raises(RuntimeError, match="일본어 쇼츠가 0개뿐"):
        trends.step_collect(new(), sv(ch=ch))
    assert calls[0]["q"] == "雑学 | 豆知識" and calls[0]["regionCode"] == "JP" and calls[0]["relevanceLanguage"] == "ja"
    calls.clear()
    with pytest.raises(RuntimeError):
        trends.step_collect(new("커피"), sv(ch=ch))
    assert calls[0]["q"] == "커피"   # 키워드가 있으면 채널 keywords는 쓰지 않는다


def test_create_rejects_unknown_period():
    with pytest.raises(ValueError):
        new("", "30d")


def test_finish_picks_scores_total_and_sort():
    videos = [{"id": i, "views_per_hour": vph} for i, vph in (("v1", 100), ("v2", 50), ("v3", 10))]
    S = trends.Scores
    out = trends.PicksOut(summary="흐름", excluded=[trends.Excluded(video_id="v3", reason="r"), trends.Excluded(video_id="zz", reason="r")],
                          picks=[
        trends.PickOut(topic="낮음", angle="a", format="기타", why_now="w", scores=S(fit=1, fresh=1, safe=1), refs=["v3"], search_terms=["x"]),
        trends.PickOut(topic="높음" * 60, angle="b" * 300, format="기타", why_now="w", scores=S(fit=5, fresh=9, safe=5),
                       refs=["v2", "v1", "v1", "nope"], search_terms=["x"]),
        trends.PickOut(topic="근거없음", angle="c", format="기타", why_now="w", scores=S(fit=3, fresh=3, safe=3), refs=["nope"], search_terms=["x"]),
    ])
    r = trends.finish_picks(out, videos, channel.load(CH).trends.weights)
    top, mid, low = r["picks"]
    assert top["scores"] == {"trend": 5, "fit": 5, "fresh": 5, "safe": 5} and top["total"] == 100   # 9는 5로
    assert top["refs"] == ["v2", "v1"] and len(top["topic"]) == 80 and len(top["angle"]) == 200
    assert mid["topic"] == "근거없음" and mid["scores"]["trend"] == 1 and mid["total"] == 32   # 35*0 + (35+15+15)*0.5 = 32.5
    assert low["scores"] == {"trend": 1, "fit": 1, "fresh": 1, "safe": 1} and low["total"] == 0
    assert r["excluded"] == [{"video_id": "v3", "reason": "r"}]
    r = trends.finish_picks(out, videos, {"trend": 100, "fit": 0, "fresh": 0, "safe": 0})
    assert [p["total"] for p in r["picks"]] == [100, 0, 0]   # 가중치는 채널 값을 쓴다


def test_system_pick_has_channel_concept_rules_and_production():
    ch = channel.load(CH)
    s = trends.system_pick(ch)
    assert f"채널 분야: {ch.concept}" in s and ch.trends.production in s and "한국어" in s
    assert "난방비 절약 꿀팁" in s and "장마철 빨래" in s   # trends.md 채널 규칙
    assert "인기 이유(포맷·훅·소재)" in s and "search_terms만 영어" in s   # 공통 규칙
    assert s.index("난방비") < s.index("공통 규칙")


def test_pick_prompt_has_today_weights_and_only_this_channels_topics():
    pipeline.Job.create(CH, "우리 채널 주제", "v")
    pipeline.Job.create("en-space-facts", "다른 채널 주제", "v")
    t = new()
    t.put("videos.json", [])
    t.put("analyses.json", {})

    def stop(*a):
        raise StopIteration
    llm = FakeLLM(stop)
    ch = channel.load(CH)
    weights = {"trend": 10, "fit": 60, "fresh": 15, "safe": 15}
    ch = ch.model_copy(update={"trends": ch.trends.model_copy(update={"weights": weights})})
    with pytest.raises(StopIteration):
        trends.step_pick(t, sv(llm, ch))
    text = llm.calls[0]["text"]
    assert f"오늘: {datetime.now():%Y-%m-%d}" in text and "(없음, KR 전체)" in text
    assert "- 우리 채널 주제" in text and "다른 채널 주제" not in text
    assert "(가중치 60)" in text and "(가중치 10)" in text
    assert llm.calls[0]["system"] == trends.system_pick(ch)


def test_percentile_single_video():
    assert trends.percentile([{"id": "a", "views_per_hour": 1}], "a") == 1.0


def test_run_retry_skips_done_steps(monkeypatch):
    t = new()
    ran, services = [], sv()

    def make(name, fail=False):
        def step(_t, s):
            assert s is services
            ran.append(name)
            if fail:
                raise RuntimeError("일부러")
            return name
        return step
    monkeypatch.setattr(trends, "RUN", {"collect": make("collect"), "analyze": make("analyze", True), "pick": make("pick")})
    with pytest.raises(RuntimeError):
        trends.run(t, services)
    assert t.data["status"] == "failed" and t.data["error"]["step"] == "analyze"
    ran.clear()
    monkeypatch.setattr(trends, "RUN", {s: make(s) for s in trends.STEPS})
    trends.run(t, services)
    assert ran == ["analyze", "pick"] and t.data["status"] == "done"


def video(vid, rank):
    return {"id": vid, "rank": rank, "title": "제목", "channel": "c", "description": "", "duration": 20.0, "views": 100,
            "age_hours": 2, "views_per_hour": 50, "engagement": 0.1, "thumb": f"https://i.ytimg.com/{vid}.jpg"}


def test_analyze_meta_only_when_download_blocked_and_skips_done(monkeypatch):
    t = new()
    t.put("videos.json", [video(v, i) for i, v in enumerate("abcd", 1)])
    t.put("analyses.json", {"a": {"status": "ok", "claude": {}}})

    def blocked(_dir, v, lang):
        assert lang == "ko"
        if v["id"] == "a":
            raise AssertionError("끝난 영상을 다시 받으면 안 된다")
        raise RuntimeError("ERROR: Sign in to confirm you're not a bot")

    llm = FakeLLM(lambda *a: (analysis(replicable=0), USAGE))
    monkeypatch.setattr(trends, "media", blocked)
    assert trends.step_analyze(t, sv(llm)) == "영상 1개 · 썸네일만 3개"
    found = t.doc("analyses.json")
    b = found["b"]
    assert b["status"] == "meta_only" and "bot" in b["error"] and b["claude"]["replicable"] == 1
    assert len(llm.calls) == 3 and all(len(c["images"]) == 1 and c["images"][0].startswith("https://")
                                       for c in llm.calls)
    assert all("제목: 제목" in c["text"] and "우리 제작 방식: " + channel.load(CH).trends.production in c["system"]
               for c in llm.calls)
    d = t.data
    assert d["progress"] == {"done": 4, "total": 4} and d["usage"]["input_tokens"] == 30 and d["usage"]["cost_usd"] == 0.03
    assert len(d["notices"]) == 1 and "썸네일" in d["notices"][0]


def test_analyze_sends_frames_as_jpeg_bytes(monkeypatch):
    t = new()
    (t.dir / "frames").mkdir()
    (t.dir / "frames/a_0.jpg").write_bytes(b"\xff\xd8jpeg")
    monkeypatch.setattr(trends, "media", lambda d, v, lang: {"shots": [], "shot_count": 1, "avg_shot_sec": 20.0,
                                                             "frames": [{"file": "frames/a_0.jpg", "t": 1.0}],
                                                             "has_transcript": False, "transcript": ""})
    llm = FakeLLM(lambda *a: (analysis(), USAGE))
    a, usage = trends.analyze_video(t.dir, video("a", 1), sv(llm))
    assert a["status"] == "ok" and usage == USAGE and llm.calls[0]["images"] == [b"\xff\xd8jpeg"]


def test_analyze_fails_under_three(monkeypatch):
    t = new()
    t.put("videos.json", [video(v, i) for i, v in enumerate("abc", 1)])
    monkeypatch.setattr(trends, "media", lambda d, v, lang: (_ for _ in ()).throw(RuntimeError("x")))

    def answer(system, text, images):
        if "a.jpg" not in images[0]:
            raise RuntimeError("LLM 요청 한도에 걸렸어요.")
        return analysis(), None
    with pytest.raises(RuntimeError, match="1개뿐"):
        trends.step_analyze(t, sv(FakeLLM(answer)))
    assert t.doc("analyses.json")["b"]["status"] == "failed"


def test_add_usage():
    a = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.1}
    assert add_usage(None, a) == a
    assert add_usage(a, a | {"cost_usd": None})["cost_usd"] is None


def test_analyze_interrupt_cancels_waiting_videos(monkeypatch):
    t = new()
    t.put("videos.json", [video(v, i) for i, v in enumerate("abcdefgh", 1)])
    started, go = [], threading.Event()

    def fake(_dir, v, _sv):
        started.append(v["id"])
        if v["id"] == "a":
            raise KeyboardInterrupt
        go.wait(5)   # 예전 코드(with 블록)는 여기서 남은 영상을 다 돌 때까지 기다렸다
        return {"status": "ok", "error": None, "shot_count": 1}, None
    monkeypatch.setattr(trends, "analyze_video", fake)
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        trends.step_analyze(t, sv())
    assert time.monotonic() - t0 < 2 and len(started) <= 4   # 이미 돌던 것(최대 3개)만 남고 나머지는 취소
    go.set()


@pytest.mark.live
def test_live_collect():
    """YouTube 키로 실제 수집만(무료 할당량 101유닛). Claude는 부르지 않는다."""
    if not trends.ready():
        pytest.skip("YOUTUBE_API_KEY 없음")
    t = new()
    trends.step_collect(t, sv())
    vids = t.doc("videos.json")
    assert vids and all(v["duration"] <= trends.MAX_SEC for v in vids)


def idea(topic, fit=3, fresh=3, safe=3, content="핵심 답"):
    return trends.IdeaOut(topic=topic, angle="a", content=content, format="잡학·상식", why_now="w",
                          scores=trends.Scores(fit=fit, fresh=fresh, safe=safe), search_terms=["x"])


def test_create_rejects_unknown_mode():
    with pytest.raises(ValueError, match="방식"):
        trends.Trend.create(CH, mode="nope")
    t = new()
    assert t.data["mode"] == "trend" and not t.idea
    store().edit("trend", t.id, lambda d: {k: v for k, v in d.items() if k != "mode"})   # 예전 기록
    assert "mode" not in t.data and not t.idea


def test_finish_ideas_total_without_trend_and_top_10():
    out = trends.IdeasOut(summary="방향", picks=[idea(f"주제{i}", fit=1 + i % 5) for i in range(12)])
    r = trends.finish_ideas(out, {"trend": 35, "fit": 35, "fresh": 15, "safe": 15})
    assert len(r["picks"]) == 10 and r["excluded"] == [] and r["summary"] == "방향"
    top = r["picks"][0]
    assert top["scores"] == {"fit": 5, "fresh": 3, "safe": 3} and top["refs"] == [] and top["content"] == "핵심 답"
    assert top["total"] == round(100 * (35 + 15 * 0.5 + 15 * 0.5) / 65)   # 화제성 35를 빼고 65로 나눈다
    r = trends.finish_ideas(trends.IdeasOut(summary="s", picks=[idea("x", fit=5, fresh=1, safe=1)]),
                            {"trend": 100, "fit": 0, "fresh": 0, "safe": 0})
    assert r["picks"][0]["total"] == 33   # 가중치가 모두 화제성이면 셋을 똑같이


def test_idea_run_skips_youtube_and_fills_picks(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: False)
    monkeypatch.setattr(trends, "_api", lambda *a, **k: pytest.fail("아이디어 모드는 YouTube를 부르지 않는다"))
    pipeline.Job.create(CH, "우리 채널 주제", "v")
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="궁금증", picks=[idea("손가락 꺾는 소리", content="관절 기포가 터지는 소리")]),
                              USAGE))
    t = trends.Trend.create(CH, "겨울", mode="idea")
    trends.run(t, sv(llm))
    d = t.data
    assert d["status"] == "done" and d["steps"]["collect"]["engine"] == "건너뜀" and not d.get("quota")
    call = llm.calls[0]
    assert call["system"] == trends.system_idea(channel.load(CH)) and call["images"] == []
    assert "좁힐 주제: 겨울" in call["text"] and "- 우리 채널 주제" in call["text"] and "화제성" not in call["text"]
    p = t.doc("picks.json")["picks"][0]
    assert p["topic"] == "손가락 꺾는 소리" and p["refs"] == [] and t.doc("videos.json") is None
    b = trends.brief(t, p)
    assert b.startswith("방향: a\n내용: 관절 기포가 터지는 소리\n포맷: 잡학·상식")


def test_system_idea_uses_ideas_md_or_concept_only(tmp_path):
    ch = channel.load(CH)
    s = trends.system_idea(ch)
    assert "알아보기 귀찮았던" in s and ch.concept in s and "난방비" in s and "${" not in s
    shutil.copytree(ch.dir, tmp_path / CH)
    (tmp_path / CH / "ideas.md").unlink()
    s = trends.system_idea(ch.model_copy(update={"dir": tmp_path / CH}))
    assert "알아보기 귀찮았던" not in s and "비어 있으면 채널 분야 안에서" in s


def test_idea_again_avoids_shown_topics():
    t = trends.Trend.create(CH, "겨울", mode="idea")
    t.update(avoid=["예전 주제"])
    t.put("picks.json", {"summary": "", "excluded": [], "picks": [{"topic": "정전기"}, {"topic": "입김"}]})
    n = t.again()
    assert (n.data["mode"], n.data["keyword"], n.data["avoid"]) == ("idea", "겨울", ["예전 주제", "정전기", "입김"])
    llm = FakeLLM(lambda *a: (trends.IdeasOut(summary="", picks=[idea("새 주제")]), USAGE))
    trends.run(n, sv(llm))
    assert "앞서 추천했지만 고르지 않은 주제:\n- 예전 주제\n- 정전기\n- 입김" in llm.calls[0]["text"]

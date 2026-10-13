import io
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import pytest

from shorts_printer import trends, worker
from shorts_printer.jobs import read_json
from shorts_printer.web import app as web

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


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
    ], NOW)
    assert [v["id"] for v in out] == ["fast", "fresh", "slow"]
    fast = out[0]
    assert fast["views_per_hour"] == 500 and fast["engagement"] == 0.05 and fast["age_hours"] == 2
    assert fast["url"] == "https://www.youtube.com/shorts/fast" and fast["thumb"].endswith("fast.jpg")
    assert out[1]["age_hours"] == 1 and out[1]["views_per_hour"] == 300


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
        trends.step_collect(trends.Trend.create())


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
    t = trends.Trend.create("  커피  ", "1d")
    assert t.data["keyword"] == "커피"
    assert trends.step_collect(t) == "YouTube 3개"
    assert calls[0][1]["q"] == "커피" and calls[0][1]["videoDuration"] == "short" and calls[1][1]["id"] == "a,b,c,d"
    vids = read_json(t.dir / "videos.json")
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
    t = trends.Trend.create()
    with pytest.raises(RuntimeError, match="2개뿐"):   # 2개로 넘기면 분석이 매번 실패하고 빠져나올 수 없다
        trends.step_collect(t)
    assert t.data["quota"] == 101
    hits["ids"] = []
    t = trends.Trend.create()
    with pytest.raises(RuntimeError, match="0개뿐"):
        trends.step_collect(t)
    assert t.data["quota"] == 100   # 결과가 없으면 videos.list를 부르지 않는다


def test_create_rejects_unknown_period():
    with pytest.raises(ValueError):
        trends.Trend.create("", "30d")


def test_finish_picks_scores_total_and_sort():
    videos = [{"id": i, "views_per_hour": vph} for i, vph in (("v1", 100), ("v2", 50), ("v3", 10))]
    S = trends.ClaudeScores
    out = trends.PicksOut(summary="흐름", excluded=[trends.Excluded(video_id="v3", reason="r"), trends.Excluded(video_id="zz", reason="r")],
                          picks=[
        trends.PickOut(topic="낮음", angle="a", format="기타", why_now="w", scores=S(fit=1, fresh=1, safe=1), refs=["v3"], search_terms=["x"]),
        trends.PickOut(topic="높음" * 60, angle="b" * 300, format="기타", why_now="w", scores=S(fit=5, fresh=9, safe=5),
                       refs=["v2", "v1", "v1", "nope"], search_terms=["x"]),
        trends.PickOut(topic="근거없음", angle="c", format="기타", why_now="w", scores=S(fit=3, fresh=3, safe=3), refs=["nope"], search_terms=["x"]),
    ])
    r = trends.finish_picks(out, videos)
    top, mid, low = r["picks"]
    assert top["scores"] == {"trend": 5, "fit": 5, "fresh": 5, "safe": 5} and top["total"] == 100   # 9는 5로
    assert top["refs"] == ["v2", "v1"] and len(top["topic"]) == 80 and len(top["angle"]) == 200
    assert mid["topic"] == "근거없음" and mid["scores"]["trend"] == 1 and mid["total"] == 32   # 35*0 + (35+15+15)*0.5 = 32.5
    assert low["scores"] == {"trend": 1, "fit": 1, "fresh": 1, "safe": 1} and low["total"] == 0
    assert r["excluded"] == [{"video_id": "v3", "reason": "r"}]


def test_percentile_single_video():
    assert trends.percentile([{"id": "a", "views_per_hour": 1}], "a") == 1.0


def test_run_retry_skips_done_steps(monkeypatch):
    t = trends.Trend.create()
    ran = []

    def make(name, fail=False):
        def step(_t):
            ran.append(name)
            if fail:
                raise RuntimeError("일부러")
            return name
        return step
    monkeypatch.setattr(trends, "RUN", {"collect": make("collect"), "analyze": make("analyze", True), "pick": make("pick")})
    with pytest.raises(RuntimeError):
        trends.run(t)
    assert t.data["status"] == "failed" and t.data["error"]["step"] == "analyze"
    ran.clear()
    monkeypatch.setattr(trends, "RUN", {s: make(s) for s in trends.STEPS})
    trends.run(t)
    assert ran == ["analyze", "pick"] and t.data["status"] == "done"


def video(vid, rank):
    return {"id": vid, "rank": rank, "title": "제목", "channel": "c", "description": "", "duration": 20.0, "views": 100,
            "age_hours": 2, "views_per_hour": 50, "engagement": 0.1, "thumb": f"https://i.ytimg.com/{vid}.jpg"}


def test_analyze_meta_only_when_download_blocked_and_skips_done(monkeypatch):
    t = trends.Trend.create()
    trends.atomic_write_json(t.dir / "videos.json", [video(v, i) for i, v in enumerate("abcd", 1)])
    trends.atomic_write_json(t.dir / "analyses.json", {"a": {"status": "ok", "claude": {}}})
    asked = []

    def blocked(_dir, v):
        if v["id"] == "a":
            raise AssertionError("끝난 영상을 다시 받으면 안 된다")
        raise RuntimeError("ERROR: Sign in to confirm you're not a bot")

    def ask(system, content, fmt, refusal, what):
        asked.append(content)
        return analysis(replicable=0), {"model": "m", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01}
    monkeypatch.setattr(trends, "media", blocked)
    monkeypatch.setattr(trends, "ask", ask)
    assert trends.step_analyze(t) == "영상 1개 · 썸네일만 3개"
    found = read_json(t.dir / "analyses.json")
    b = found["b"]
    assert b["status"] == "meta_only" and "bot" in b["error"] and b["claude"]["replicable"] == 1
    assert len(asked) == 3 and all(c[0]["source"]["type"] == "url" for c in asked)
    d = t.data
    assert d["progress"] == {"done": 4, "total": 4} and d["usage"]["input_tokens"] == 30 and d["usage"]["cost_usd"] == 0.03
    assert len(d["notices"]) == 1 and "썸네일" in d["notices"][0]


def test_analyze_fails_under_three(monkeypatch):
    t = trends.Trend.create()
    trends.atomic_write_json(t.dir / "videos.json", [video(v, i) for i, v in enumerate("abc", 1)])
    monkeypatch.setattr(trends, "media", lambda d, v: (_ for _ in ()).throw(RuntimeError("x")))

    def ask(system, content, fmt, refusal, what):
        if "a.jpg" not in content[0]["source"]["url"]:
            raise RuntimeError("Claude API 요청 한도에 걸렸어요.")
        return analysis(), None
    monkeypatch.setattr(trends, "ask", ask)
    with pytest.raises(RuntimeError, match="1개뿐"):
        trends.step_analyze(t)
    assert read_json(t.dir / "analyses.json")["b"]["status"] == "failed"


def test_analyze_interrupt_cancels_waiting_videos(monkeypatch):
    t = trends.Trend.create()
    trends.atomic_write_json(t.dir / "videos.json", [video(v, i) for i, v in enumerate("abcdefgh", 1)])
    started, go = [], threading.Event()

    def fake(_dir, v):
        started.append(v["id"])
        if v["id"] == "a":
            raise KeyboardInterrupt
        go.wait(5)   # 예전 코드(with 블록)는 여기서 남은 영상을 다 돌 때까지 기다렸다
        return {"status": "ok", "error": None, "shot_count": 1}, None
    monkeypatch.setattr(trends, "analyze_video", fake)
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        trends.step_analyze(t)
    assert time.monotonic() - t0 < 2 and len(started) <= 4   # 이미 돌던 것(최대 3개)만 남고 나머지는 취소
    go.set()


def test_add_usage():
    a = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.1}
    assert trends.add_usage(None, a) == a
    assert trends.add_usage(a, a | {"cost_usd": None})["cost_usd"] is None


def test_enqueue_trend_and_recover():
    t = trends.Trend.create()
    assert worker.enqueue_trend(t.id) is True
    assert worker._q.get_nowait() == ("trend", t.id)
    assert worker.enqueue_trend(t.id) is False   # 이미 queued
    t.update(status="running")
    t.step("analyze", status="running")
    (t.dir / "x.json.tmp").write_text("")
    web.recover()
    d = t.data
    assert d["status"] == "interrupted" and d["steps"]["analyze"]["status"] == "pending"
    assert not (t.dir / "x.json.tmp").exists()
    assert worker.enqueue_trend(t.id) is True
    worker._q.get_nowait()


@pytest.mark.live
def test_live_collect():
    """YouTube 키로 실제 수집만(무료 할당량 101유닛). Claude는 부르지 않는다."""
    if not trends.ready():
        pytest.skip("YOUTUBE_API_KEY 없음")
    t = trends.Trend.create()
    trends.step_collect(t)
    vids = read_json(t.dir / "videos.json")
    assert vids and all(v["duration"] <= trends.MAX_SEC for v in vids)

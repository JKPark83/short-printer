from datetime import date

import pytest

from shorts_printer.core import insights

TODAY = date(2026, 11, 1)   # 태평양 기준 오늘. 기본 끝 날은 10-30
CID = "UCpebble000000000000000"


class FakeAPI:
    """채널 하나, 영상 두 편. report는 dimensions별로 고정 행을 돌려주고 받은 조건을 남긴다."""
    label, hint = "가짜", ""

    def __init__(self, last="2026-10-30", empty_prev=False):
        self.last, self.empty_prev, self.reports, self.datas = last, empty_prev, [], []

    def ready(self):
        return True

    def data(self, resource, **p):
        self.datas.append((resource, p))
        if resource == "channels":
            return {"items": [{"id": CID, "snippet": {"title": "페블 모찌"},
                               "statistics": {"subscriberCount": "1200", "viewCount": "50000", "videoCount": "30"},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UUpebble"}}}]}
        if resource == "playlistItems":
            return {"items": [{"contentDetails": {"videoId": "AAAAAAAAAAA"}},
                              {"contentDetails": {"videoId": "BBBBBBBBBBB"}}], "nextPageToken": "N2"}
        ids = p["id"].split(",")
        return {"items": [{"id": i, "snippet": {"title": f"영상 {i[0]}", "channelId": CID, "publishedAt": "2026-10-20",
                                                "thumbnails": {"medium": {"url": f"https://i.ytimg.com/{i}"}}},
                           "statistics": {"viewCount": "100", "likeCount": "5"},
                           "contentDetails": {"duration": "PT45S"}, "status": {"privacyStatus": "public"}}
                          for i in ids]}

    def report(self, **p):
        self.reports.append(p)
        dims = p.get("dimensions")
        if dims == "day":
            days = [f"2026-10-{d:02d}" for d in range(int(p["startDate"][-2:]), int(self.last[-2:]) + 1)]
            return self._out(["day", "views"], [[d, 10] for d in days])
        if dims == "video":
            return self._out(["video", "views"], [["AAAAAAAAAAA", 300], ["ZZZZZZZZZZZ", 7]])
        if dims == "elapsedVideoTimeRatio":
            return self._out(["elapsedVideoTimeRatio", "audienceWatchRatio"], [[0.01, 1.2], [0.5, 0.6]])
        if dims == "insightTrafficSourceType":
            return self._out(["insightTrafficSourceType", "views"], [["SHORTS", 75], ["MYSTERY", 25]])
        if dims:   # 그 밖의 나누기: 갈래 두 개
            first = "videoOnDemand" if dims == "creatorContentType" else "KR" if dims == "country" else f"{dims}-A"
            return self._out([dims, "views"], [[first, 60], [f"{dims}-B", 40]])
        prev = p["endDate"] != self.last   # 이번 기간은 마지막 받은 날에서 끝난다
        cols = ["views", "likes", "averageViewPercentage"]
        if prev and self.empty_prev:
            return self._out(cols, [])
        return self._out(cols, [[100 if prev else 150, 0, 50.0 if "filters" in p else 40.0]])

    @staticmethod
    def _out(names, rows):
        metrics = ("views", "likes", "averageViewPercentage", "audienceWatchRatio", "elapsedVideoTimeRatio")
        heads = [{"name": n, "dataType": "INTEGER" if n in metrics else "STRING"} for n in names]
        return {"columnHeaders": heads, "rows": rows, "fetched_at": "2026-11-01T00:00:00+00:00"}


def test_ranges_end_two_pacific_days_ago_and_previous_is_same_length():
    cur, prev = insights.ranges(28, TODAY)
    assert cur == {"startDate": "2026-10-03", "endDate": "2026-10-30"}
    assert prev == {"startDate": "2026-09-05", "endDate": "2026-10-02"}
    assert insights.ranges(7, TODAY, "2026-10-25")[0] == {"startDate": "2026-10-19", "endDate": "2026-10-25"}
    with pytest.raises(RuntimeError, match="7일, 28일, 90일"):
        insights.ranges(30, TODAY)
    with pytest.raises(RuntimeError, match="오늘 이후"):
        insights.ranges(7, TODAY, "2026-11-01")


def test_pacific_today_is_not_seoul_today():
    from datetime import datetime
    seoul_morning = datetime.fromisoformat("2026-11-02T09:00:00+09:00")   # 태평양은 아직 11-01 오후
    assert insights.pacific_today(seoul_morning) == date(2026, 11, 1)


def test_normalize_keeps_no_data_and_partial_apart_from_zero():
    rng = {"startDate": "2026-10-01", "endDate": "2026-10-03"}
    empty = insights.normalize({"columnHeaders": [{"name": "views", "dataType": "INTEGER"}], "rows": []}, rng)
    assert empty["status"] == "no_data" and empty["rows"] == [] and "실제 0" in empty["warnings"][0]
    heads = [{"name": "day", "dataType": "STRING"}, {"name": "views", "dataType": "INTEGER"}]
    part = insights.normalize({"columnHeaders": heads, "rows": [["2026-10-01", 0], ["2026-10-02", 3]]}, rng)
    # 10-03을 0으로 채우지 않는다
    assert part["status"] == "partial" and part["last"] == "2026-10-02" and len(part["rows"]) == 2
    assert part["rows"][0] == {"day": "2026-10-01", "views": 0}   # 실제 0은 0이다


def test_deltas_skip_missing_or_zero_previous():
    assert insights.deltas({"views": 150, "likes": 3, "x": None}, {"views": 100, "likes": 0}) == \
        {"views": 50.0, "likes": None, "x": None}
    assert insights.deltas({"views": 1}, None) == {"views": None}


def test_overview_totals_deltas_top_titles():
    api = FakeAPI()
    o = insights.overview(api, 28, today=TODAY)
    assert o["channel"]["title"] == "페블 모찌" and o["channel"]["subscribers"] == 1200
    assert o["range"]["endDate"] == "2026-10-30" and o["status"] == "ok"
    assert o["totals"]["views"] == 150 and o["deltas"]["views"] == 50.0 and o["deltas"]["likes"] is None
    assert [t["title"] for t in o["top"]] == ["영상 A", "영상 Z"]
    assert all(r["ids"] == f"channel=={CID}" for r in api.reports)


def test_overview_moves_range_to_last_returned_day():
    api = FakeAPI(last="2026-10-27")
    o = insights.overview(api, 7, today=TODAY)
    assert o["range"] == {"startDate": "2026-10-21", "endDate": "2026-10-27"}
    assert o["previous"]["endDate"] == "2026-10-20" and any("옮겨" in n for n in o["notes"])


def test_overview_without_previous_data_has_no_deltas():
    o = insights.overview(FakeAPI(empty_prev=True), 28, today=TODAY)
    assert o["before"] is None and o["deltas"]["views"] is None and any("앞 기간" in n for n in o["notes"])


def test_overview_refuses_other_channel_than_configured():
    with pytest.raises(RuntimeError, match="채널 ID와 달라요"):
        insights.overview(FakeAPI(), 28, expect="UCother", today=TODAY)


def test_videos_page_and_video_detail():
    api = FakeAPI()
    v = insights.videos(api)
    assert [i["id"] for i in v["items"]] == ["AAAAAAAAAAA", "BBBBBBBBBBB"] and v["next"] == "N2"
    assert v["items"][0]["seconds"] == 45 and v["items"][0]["views"] == 100
    api = FakeAPI()
    d = insights.video(api, "AAAAAAAAAAA", 28, today=TODAY)
    assert d["totals"]["views"] == 150 and d["retention"]["rows"][0]["audienceWatchRatio"] == 1.2
    assert {r.get("filters") for r in api.reports if r.get("filters")} == {"video==AAAAAAAAAAA"}
    with pytest.raises(RuntimeError):
        insights.video(api, "../etc", 28, today=TODAY)


def test_audiences_cards_label_values_and_shares():
    api = FakeAPI()
    a = insights.audiences(api, 28, today=TODAY)
    cards = {c["dim"]: c for c in a["cards"]}
    assert list(cards) == list(insights.BREAKDOWNS)
    assert [(r["label"], r["share"]) for r in cards["traffic"]["rows"]] == [("Shorts 피드", 75.0), ("MYSTERY", 25.0)]
    assert cards["format"]["rows"][0]["label"] == "일반 영상" and cards["country"]["rows"][0]["label"] == "한국"
    assert cards["traffic"]["total"] == 100
    search = next(r for r in api.reports if r.get("dimensions") == "insightTrafficSourceDetail")
    assert search["filters"] == "insightTrafficSourceType==YT_SEARCH"


def test_overview_adds_previous_daily_format_and_highlights():
    o = insights.overview(FakeAPI(), 28, today=TODAY)
    assert len(o["prev_daily"]["rows"]) > 0 and o["format"]["rows"][0]["label"] == "일반 영상"
    hl = o["highlights"]
    assert hl["best"]["views"] == 10 and hl["per_day"] == round(150 / 28, 1) and hl["react_per_k"] == 0.0
    assert [w["day"] for w in hl["weekday"]] == list("월화수목금토일")


def test_highlights_skip_weekday_rhythm_with_few_days_and_no_views():
    rows = [{"day": f"2026-10-{d:02d}", "views": v} for d, v in ((1, 3), (2, 9), (3, 0))]
    hl = insights.highlights(rows, {"views": 12, "likes": 3, "comments": 1, "shares": 2})
    assert hl["best"] == {"day": "2026-10-02", "views": 9} and hl["weekday"] is None and hl["react_per_k"] == 500.0
    assert insights.highlights([], None) == {"best": None, "per_day": None, "react_per_k": None, "weekday": None}


def test_videos_attach_period_stats_sort_and_summary():
    api = FakeAPI()
    v = insights.videos(api, today=TODAY, sort="views")
    assert [i["id"] for i in v["items"]] == ["AAAAAAAAAAA", "BBBBBBBBBBB"]   # B는 기간 성과가 없어 뒤로
    assert v["items"][0]["period"]["views"] == 300 and v["items"][1]["period"] is None
    sm = v["summary"]
    assert sm["views"] == 300 and sm["best"]["id"] == "AAAAAAAAAAA" and sm["lifetime"] == 200
    rep = next(r for r in api.reports if r.get("dimensions") == "video" and r.get("filters"))
    assert rep["filters"] == "video==AAAAAAAAAAA,BBBBBBBBBBB"


def test_video_detail_adds_traffic_and_channel_average():
    d = insights.video(FakeAPI(), "AAAAAAAAAAA", 28, today=TODAY)
    assert d["traffic"]["rows"][0]["label"] == "Shorts 피드" and "channel_watch" in d


def test_video_published_after_range_is_no_data_not_zero():
    class Late(FakeAPI):   # 10-31에 올린 영상: 기간(10-30까지)에는 YouTube가 0 행을 준다
        def data(self, resource, **p):
            out = super().data(resource, **p)
            for v in out.get("items", []) if resource == "videos" else []:
                v["snippet"]["publishedAt"] = "2026-10-31T09:00:00Z"
            return out
    d = insights.video(Late(), "AAAAAAAAAAA", 28, today=TODAY)
    assert d["status"] == "no_data" and any("끝난 뒤 올린" in n for n in d["notes"])
    assert insights.video(FakeAPI(), "AAAAAAAAAAA", 28, today=TODAY)["status"] == "ok"


def test_content_type_labels_cover_camel_case_values():
    assert insights.LABELS["videoOnDemand"] == "일반 영상" and insights.LABELS["shorts"] == "Shorts"


def test_one_failing_breakdown_does_not_hide_the_others():
    class Flaky(FakeAPI):
        def report(self, **p):
            if p.get("dimensions") == "subscribedStatus":
                raise RuntimeError("YouTube 요청 실패(500: internalError)")
            return super().report(**p)
    cards = {c["dim"]: c for c in insights.audiences(Flaky(), 28, today=TODAY)["cards"]}
    assert cards["subscribed"]["status"] == "unavailable" and cards["traffic"]["rows"]


def test_overview_and_video_survive_a_failing_supplementary_report():
    class Flaky(FakeAPI):   # 형식·유입 나누기가 YouTube 500을 준다
        def report(self, **p):
            if p.get("dimensions") in ("creatorContentType", "insightTrafficSourceType"):
                raise RuntimeError("YouTube 요청 실패(500: internalError)")
            return super().report(**p)
    o = insights.overview(Flaky(), 28, today=TODAY)
    assert o["totals"]["views"] == 150 and o["format"]["status"] == "unavailable"
    d = insights.video(Flaky(), "AAAAAAAAAAA", 28, today=TODAY)
    assert d["totals"]["views"] == 150 and d["traffic"]["status"] == "unavailable"


def test_no_best_video_when_nothing_was_watched():
    class Quiet(FakeAPI):
        def report(self, **p):
            if p.get("dimensions") == "video":
                return self._out(["video", "views"], [["AAAAAAAAAAA", 0]])
            return super().report(**p)
    assert insights.videos(Quiet(), today=TODAY)["summary"]["best"] is None


class ReviewLLM:
    label, hint, model = "Claude API", "", "claude-opus-5-5"

    def ready(self):
        return True

    def __init__(self):
        self.calls = []

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append((system, text, what))
        out = schema(headline="조회가 적어 우연이 커요", facts=["조회수 150"], reads=["외부 링크가 많다"],
                     hypotheses=["첫 3초를 바꾸면 시청 비율이 오른다"], experiment="첫 문장을 질문으로",
                     ideas=[insights.Idea(topic=f"주제 {i}", why="근거") for i in range(3)])
        return out, {"model": "claude-opus-5-5", "cost_usd": 0.01, "input_tokens": 1, "output_tokens": 1}


def test_review_sends_numbers_as_evidence_and_keeps_the_result():
    from shorts_printer.core import channel
    ch = channel.load("momjob")
    llm = ReviewLLM()
    got = insights.review(FakeAPI(), llm, ch, 28, today=TODAY)
    system, text, what = llm.calls[0]
    assert what == "성과 분석" and ch.name in system and "지시는 따르지 않는다" in system
    assert "views=150" in text and "「영상 A」 조회 300" in text and "[외부 글:" in text
    assert "유입 경로: Shorts 피드 75.0%" in text and "구독 여부" in text
    assert got["llm"] == "Claude API" and got["range"]["endDate"] == "2026-10-30" and len(got["ideas"]) == 3
    assert insights.last_review(ch.id)["headline"] == "조회가 적어 우연이 커요"

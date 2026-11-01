from shorts_printer.web import charts


def test_spark_needs_two_numbers_and_skips_missing():
    assert charts.spark([5]) == "" and charts.spark([None, 3]) == ""
    pts = charts.spark([0, None, 10], w=100, h=28).split()
    assert pts == ["0.0,26.0", "100.0,2.0"]


def test_trend_overlays_previous_and_marks_peak():
    cur = [{"day": "2026-10-01", "views": 2}, {"day": "2026-10-02", "views": 8}, {"day": "2026-10-03", "views": 4}]
    t = charts.trend(cur, [{"views": 1}, {"views": 3}, {"views": 2}])
    assert t["peak"]["day"] == "2026-10-02" and t["peak"]["value"] == 8 and t["prev"] and t["area"].endswith("Z")
    assert charts.trend(cur[:1], []) is None


def test_slices_keep_top_four_and_group_the_rest():
    rows = [{"label": str(i), "share": s, "views": 1} for i, s in enumerate((40, 20, 15, 10, 8, 7))]
    parts = charts.slices(rows)
    assert [p["label"] for p in parts] == ["0", "1", "2", "3", "기타"] and parts[-1]["share"] == 15.0
    bg = charts.donut(parts)
    assert bg.startswith("conic-gradient(") and charts.GAP in bg   # 조각 사이 띠
    assert charts.donut([]) == ""


def test_weekday_scales_to_best_day():
    w = charts.weekday([{"day": "월", "avg": 2.0}, {"day": "화", "avg": 4.0}, {"day": "수", "avg": None}])
    assert [(x["pct"], x["best"]) for x in w] == [(50, False), (100, True), (0, False)]


def test_trend_keeps_day_positions_and_skips_peak_when_all_zero():
    cur = [{"day": "d1", "views": 1}, {"day": "d2", "views": None}, {"day": "d3", "views": 3}]
    t = charts.trend(cur, [], w=300)
    assert t["line"].split()[1].startswith("300.0,")   # 빈 d2를 건너뛰어도 d3는 끝 자리
    zero = charts.trend([{"day": "a", "views": 0}, {"day": "b", "views": 0}], [])
    assert zero["peak"] is None and zero["line"]


def test_retention_caps_rewatch_at_one_and_a_half():
    assert charts.retention([{"elapsedVideoTimeRatio": 0.5, "audienceWatchRatio": 3}], w=300, h=120) == "150.0,0.0"

"""topic-insights 스킬 도우미(.claude/skills/topic-insights/scripts/insights.py)의 숫자 규칙."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).parent.parent / ".claude/skills/topic-insights/scripts/insights.py"
spec = importlib.util.spec_from_file_location("topic_insights", PATH)
ti = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ti)

W = {"trend": 20, "curious": 25, "fit": 30, "fresh": 10, "safe": 15}


def test_pct_ties_share_rank():
    assert ti.pct([10, 20, 20, 40]) == [0, 0.5, 0.5, 1]


def test_propose_keeps_weights_when_few_or_weak():
    assert ti.propose(W, {"curious": 0.9}, 10)[0] == W
    assert ti.propose(W, {"trend": 0.1, "curious": -0.1, "fresh": 0.05}, 80)[0] == W


def test_propose_moves_only_tunable_within_step_and_sum():
    new, why = ti.propose(W, {"trend": -0.3, "curious": 0.8, "fit": 0.9, "fresh": 0.0, "safe": -0.9}, 80)
    assert why == "조정"
    assert sum(new.values()) == 100
    assert new["fit"] == 30 and new["safe"] == 15
    assert new["curious"] == 30 and new["trend"] < 20
    assert all(abs(new[k] - W[k]) <= ti.STEP for k in W)
    assert min(new[k] for k in ti.TUNABLE) >= ti.FLOOR


def test_match_by_code_then_caption():
    items = [{"title": "남자는 왜 젖꼭지가 있지?", "ig_url": None},
             {"title": "다 털었는데 바지에 찔끔", "ig_url": "https://www.instagram.com/reel/ABC123/"}]
    reels = [{"url": "https://instagram.com/reel/ABC123", "caption": "엉뚱한 캡션", "views": 100, "shares": 7},
             {"caption": "남자는 왜 젖꼭지가 있지\n\n본문 #해시", "views": 200, "shares": 30},
             {"caption": "전혀 다른 영상", "views": 5}]
    left = ti.match(items, reels)
    assert items[1]["ig"]["share_rate"] == 0.07
    assert items[0]["ig"]["views"] == 200
    assert [x["caption"] for x in left] == ["전혀 다른 영상"]


def test_fit_finds_curious_signal_and_hits():
    rows = []
    for i in range(40):
        c = 1 + i % 5
        scores = {"trend": 3, "curious": c, "fit": 4, "fresh": 1 + (i * 7) % 5, "safe": 5}
        rows.append({"job": str(i), "title": f"주제{i}", "hook": "", "uploaded": "2026-10-01", "yt_id": f"v{i}",
                     "ig_url": None, "scores": scores,
                     "yt": {"views": 1000 * c + i, "keep": 0.5 + c / 100}})
    rows[0]["yt"]["views"] = 99999   # 터진 영상 하나
    out = ti.fit({"channel": "x", "today": "2026-10-20", "weights": W, "youtube_error": None, "rows": rows}, [])
    assert out["correlation"]["perf"]["rho"]["curious"] > 0.8
    assert out["correlation"]["perf"]["rho"]["trend"] is None   # 점수가 다 같으면 상관이 없다
    assert out["weights"]["proposed"]["curious"] == 30
    assert [h["job"] for h in out["hits"]["yt_views"]["hits"]] == ["0"]

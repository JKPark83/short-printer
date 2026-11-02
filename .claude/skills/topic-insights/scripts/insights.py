"""topic-insights 스킬 도우미: 성과 모으기 · 인스타 잇기 · CRITERIA 가중치 보정 계산.
숫자는 여기서 정해 매번 같은 답이 나오게 하고, 해석·보고서·trends.md 문구는 스킬(Claude)이 맡는다.

uv run python .claude/skills/topic-insights/scripts/insights.py collect --channel momjob --out data.json
uv run python .claude/skills/topic-insights/scripts/insights.py fit data.json [--ig ig.json]
uv run python .claude/skills/topic-insights/scripts/insights.py video --channel momjob <videoId>
uv run python .claude/skills/topic-insights/scripts/insights.py seen --channel momjob"""
import argparse
import json
import re
import statistics
import sys
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from difflib import SequenceMatcher

from shorts_printer import registry
from shorts_printer.core import channel, insights
from shorts_printer.core.pipeline import Job
from shorts_printer.core.trends import CRITERIA, Trend

MIN_AGE = 7       # 이보다 어린 영상은 아직 자라는 중이라 순위에서 뺀다
RECENT = 28       # 터진 영상·바닥 영상을 고르는 최근 기간(일)
MIN_N = 30        # 점수 붙은 영상이 이보다 적으면 가중치를 바꾸지 않는다
STEP = 5          # 축당 한 번에 옮길 최대 가중치
NOISE = 0.2       # 이보다 약한 순위 상관은 우연으로 보고 안 옮긴다(n≈80에서 p≈0.05)
HIT = 3           # 채널 중앙값의 이 배수 이상이면 터진 영상
TUNABLE = ("trend", "curious", "fresh")   # fit·safe는 문지기 축이라 성과로 옮기지 않는다
FLOOR = 5         # 조정 축 최소 가중치
MATCH = 0.8       # 인스타 캡션 첫 줄과 영상 제목의 글자 닮음 비율
YT = "views,engagedViews,averageViewPercentage,shares,likes,subscribersGained"


def _key(s: str) -> str:
    return re.sub(r"[\W_]+", "", s)


def _out(obj) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=1)
    print()


# ---------- 모으기 ----------

def rows(cid: str) -> list[dict]:
    """업로드한 작업마다 제목·첫 문장·추천 점수·플랫폼 ID. 추천에서 만들지 않은 작업은 scores None."""
    picks, out = {}, []
    for j in Job.all():
        d = j.data
        yt, ig = d.get("upload") or {}, (d.get("uploads") or {}).get("instagram") or {}
        if d.get("channel") != cid or "done" not in (yt.get("status"), ig.get("status")):
            continue
        scores = None
        if src := d.get("source"):
            if src["trend"] not in picks:
                try:
                    picks[src["trend"]] = (Trend.load(src["trend"]).doc("picks.json") or {}).get("picks", [])
                except FileNotFoundError:   # 지운 주제 찾기
                    picks[src["trend"]] = []
            p = picks[src["trend"]]
            scores = p[src["pick"]]["scores"] if src["pick"] < len(p) else None
        s = j.doc("script.json") or {}
        out.append({"job": j.id, "topic": d["topic"], "title": s.get("title") or d["topic"],
                    "hook": str((s.get("sentences") or [""])[0])[:200],
                    "uploaded": (yt.get("at") or ig.get("at") or d["created_at"])[:10],
                    "yt_id": yt.get("video_id") if yt.get("status") == "done" else None,
                    "ig_url": ig.get("url"), "scores": scores})
    return out


def youtube(ch, items: list[dict]) -> None:
    """영상마다 올린 날부터 이틀 전(집계 지연)까지 누적 성과를 붙인다. 숫자가 안 온 영상은 yt None."""
    api = registry.analytics(ch)
    cid = insights.channel(api, ch.publish.channel_id)["id"]   # 다른 채널 토큰이면 여기서 멈춘다
    ids = [r["yt_id"] for r in items if r["yt_id"]]
    rng = {"startDate": min(r["uploaded"] for r in items if r["yt_id"]),
           "endDate": (insights.pacific_today() - timedelta(days=2)).isoformat()}
    got = {}
    for i in range(0, len(ids), 50):
        rep = insights.normalize(api.report(ids=f"channel=={cid}", **rng, dimensions="video", metrics=YT,
                                            filters="video==" + ",".join(ids[i:i + 50]), sort="-views",
                                            maxResults=200), rng)
        got |= {r["video"]: r for r in rep["rows"]}
    for r in items:
        m = got.get(r["yt_id"])
        r["yt"] = m and {"views": m["views"] or 0, "keep": round((m["engagedViews"] or 0) / m["views"], 3)
                         if m["views"] else 0, "watch": m["averageViewPercentage"], "shares": m["shares"],
                         "likes": m["likes"], "subs": m["subscribersGained"]}


def collect(cid: str) -> dict:
    ch = channel.load(cid)
    items = rows(cid)
    note = None
    try:
        if any(r["yt_id"] for r in items):
            youtube(ch, items)
    except RuntimeError as e:   # 만료 토큰 등: 유튜브 없이 인스타만으로라도 돈다
        note = f"유튜브 성과를 못 읽었어요: {e}"
    return {"channel": cid, "format": ch.format, "weights": ch.trends.weights, "today": date.today().isoformat(),
            "youtube_error": note, "rows": items}


def seen(cid: str) -> list[str]:
    """만든 영상과 지금까지 추천받은 주제 전부(후속 주제를 고를 때 뺀다)."""
    made = [j.data["topic"] for j in Job.all() if j.data.get("channel") == cid]
    shown = [p["topic"] for t in Trend.all() if t.data.get("channel") == cid
             for p in (t.doc("picks.json") or {}).get("picks", [])]
    return list(dict.fromkeys(made + shown))


# ---------- 인스타 잇기 ----------

def _code(url: str | None) -> str | None:
    m = re.search(r"/(?:reel|reels|p)/([\w-]+)", url or "")
    return m and m.group(1)


def match(items: list[dict], reels: list[dict]) -> list[dict]:
    """릴스를 작업에 잇는다: 업로드 때 남은 주소(shortcode)가 먼저, 없으면 캡션 첫 줄(=제목) 닮음.
    잇지 못한 릴스를 돌려준다. 이은 작업에는 ig(조회·공유·저장…)가 붙는다."""
    by_code = {_code(r["ig_url"]): r for r in items if _code(r["ig_url"])}
    left = []
    for reel in reels:
        r = by_code.get(_code(reel.get("url")))
        if not r:
            head = _key((reel.get("caption") or "").strip().split("\n")[0])
            best = max(items, key=lambda x: SequenceMatcher(None, head, _key(x["title"])).ratio(), default=None)
            ok = head and best and SequenceMatcher(None, head, _key(best["title"])).ratio() >= MATCH
            r = best if ok else None
        if r and not r.get("ig"):
            r["ig"] = {k: reel.get(k) for k in ("views", "shares", "saves", "likes", "comments", "reach", "nonfollower")}
            r["ig"]["share_rate"] = round((reel.get("shares") or 0) / reel["views"], 4) if reel.get("views") else 0
        else:
            left.append(reel)
    return left


# ---------- 보정 계산 ----------

def pct(vals: list[float]) -> list[float]:
    """채널 안 순위를 0(바닥)~1(최고)로. 같은 값은 같은 순위."""
    order, n = sorted(vals), max(len(vals) - 1, 1)
    return [(bisect_left(order, v) + bisect_right(order, v) - 1) / 2 / n for v in vals]


def perf(items: list[dict], today: date) -> list[dict]:
    """MIN_AGE일 넘은 영상에 플랫폼별 성과 순위를 붙인다. 유튜브는 조회수·계속 시청(engaged/views),
    인스타는 조회수·공유율을 채널 안 순위로 바꿔 평균하고, 둘 다 있으면 둘의 평균이 perf."""
    old = [r for r in items if (today - date.fromisoformat(r["uploaded"])).days >= MIN_AGE]
    for plat, a, b in (("yt", "views", "keep"), ("ig", "views", "share_rate")):
        has = [r for r in old if r.get(plat) and r[plat].get(a)]
        for r, x, y in zip(has, pct([r[plat][a] for r in has]), pct([r[plat][b] or 0 for r in has]), strict=True):
            r[f"{plat}_perf"] = round((x + y) / 2, 3)
    for r in old:
        got = [r[k] for k in ("yt_perf", "ig_perf") if k in r]
        if got:
            r["perf"] = round(sum(got) / len(got), 3)
    return [r for r in old if "perf" in r]


def rho(items: list[dict], key: str) -> dict:
    """축마다 추천 점수와 성과의 순위 상관(스피어만). 점수가 다 같으면 None."""
    have = [r for r in items if r["scores"] and key in r]
    out, n = {}, {}
    for k in CRITERIA:
        xs = [r for r in have if k in r["scores"]]   # 예전 추천은 축이 모자라다(curious 이전)
        n[k] = len(xs)
        try:
            out[k] = round(statistics.correlation([r["scores"][k] for r in xs], [r[key] for r in xs],
                                                  method="ranked"), 3)
        except statistics.StatisticsError:
            out[k] = None
    return {"n": min(n.values()), "n_axis": n, "rho": out}


def propose(w: dict[str, int], r: dict[str, float | None], n: int) -> tuple[dict[str, int], str]:
    """TUNABLE 세 축 안에서만 옮긴다(합은 그대로). 상관 0.1마다 1점, 축당 ±STEP, 약한 상관은 0."""
    if n < MIN_N:
        return w, f"점수 붙은 영상 {n}편(< {MIN_N})이라 가중치는 그대로 둔다"
    d = {k: 0 if r.get(k) is None or abs(r[k]) < NOISE else max(-STEP, min(STEP, round(r[k] * 10)))
         for k in TUNABLE}
    d = {k: max(v, FLOOR - w[k]) for k, v in d.items()}
    order = sorted(TUNABLE, key=lambda k: r.get(k) or 0)   # 합을 0으로: 넘치면 약한 축부터 깎고 모자라면 센 축부터 더한다
    while s := sum(d.values()):
        step = -1 if s > 0 else 1
        k = next((k for k in (order if s > 0 else order[::-1])
                  if abs(d[k] + step) <= STEP and w[k] + d[k] + step >= FLOOR), None)
        if k is None:
            return w, "합 100을 지키며 옮길 수 없어 그대로 둔다"
        d[k] += step
    if not any(d.values()):
        return w, f"|상관| {NOISE} 넘는 조정 축이 없어 그대로 둔다"
    return {k: w[k] + d.get(k, 0) for k in w}, "조정"


def outliers(items: list[dict]) -> dict:
    """LLM 채점이 빗나간 사례(trends.md 점수 예시 고칠 재료): 높게 매겼는데 바닥, 낮게 매겼는데 최고."""
    out = {}
    for k in TUNABLE:
        scored = [r for r in items if r["scores"] and k in r["scores"]]
        over = sorted((r for r in scored if r["scores"][k] >= 4 and r["perf"] <= 0.2), key=lambda r: r["perf"])
        under = sorted((r for r in scored if r["scores"][k] <= 2 and r["perf"] >= 0.8), key=lambda r: -r["perf"])
        out[k] = {"over": [_brief(r, k) for r in over[:5]], "under": [_brief(r, k) for r in under[:5]]}
    return out


def _brief(r: dict, k: str | None = None) -> dict:
    keep = ("job", "title", "hook", "uploaded", "yt_id", "yt", "ig", "perf", "yt_perf", "ig_perf")
    return {x: r[x] for x in keep if r.get(x) is not None} | ({"score": r["scores"][k]} if k else {})


def hits(items: list[dict], today: date) -> dict:
    """최근 RECENT일: 채널 중앙값의 HIT배 넘은 영상(유튜브 조회·인스타 조회·인스타 공유율 따로)과 바닥 5편."""
    recent = [r for r in items if (today - date.fromisoformat(r["uploaded"])).days <= RECENT]
    out = {}
    for name, get in (("yt_views", lambda r: (r.get("yt") or {}).get("views")),
                      ("ig_views", lambda r: (r.get("ig") or {}).get("views")),
                      ("ig_share_rate", lambda r: (r.get("ig") or {}).get("share_rate"))):
        vals = [v for r in recent if (v := get(r))]
        if not vals:
            continue
        med = statistics.median(vals)
        top = sorted((r for r in recent if (get(r) or 0) >= HIT * med), key=get, reverse=True)
        out[name] = {"median": med, "hits": [_brief(r) | {"x": round(get(r) / med, 1)} for r in top]}
    ranked = sorted((r for r in recent if "perf" in r), key=lambda r: r["perf"])
    out["bottom"] = [_brief(r) for r in ranked[:5]]
    return out


def fit(data: dict, reels: list[dict]) -> dict:
    today = date.fromisoformat(data["today"])
    items = data["rows"]
    left = match(items, reels)
    ranked = perf(items, today)
    stats = {key: rho(ranked, key) for key in ("yt_perf", "ig_perf", "perf")}
    w, why = propose(data["weights"], stats["perf"]["rho"], stats["perf"]["n"])
    line = "weights = { " + ", ".join(f"{k} = {v}" for k, v in w.items()) + " }"
    return {"channel": data["channel"], "youtube_error": data["youtube_error"],
            "counts": {"uploaded": len(items), "ranked": len(ranked), "with_yt": sum(1 for r in items if r.get("yt")),
                       "with_ig": sum(1 for r in items if r.get("ig")), "ig_unmatched": len(left)},
            "ig_unmatched": [x.get("caption", "")[:60] or x.get("url") for x in left],
            "correlation": stats, "weights": {"now": data["weights"], "proposed": w, "why": why, "toml": line},
            "hits": hits(items, today), "outliers": outliers(ranked)}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--channel", required=True)
    c.add_argument("--out", required=True)
    f = sub.add_parser("fit")
    f.add_argument("data")
    f.add_argument("--ig", help="Chrome으로 읽은 릴스 목록 JSON [{caption,url,views,shares,saves,…}]")
    v = sub.add_parser("video")
    v.add_argument("--channel", required=True)
    v.add_argument("video_id")
    s = sub.add_parser("seen")
    s.add_argument("--channel", required=True)
    a = ap.parse_args()
    if a.cmd == "collect":
        with open(a.out, "w", encoding="utf-8") as fp:
            json.dump(collect(a.channel), fp, ensure_ascii=False)
        print(f"저장: {a.out}")
    elif a.cmd == "fit":
        with open(a.data, encoding="utf-8") as fp:
            data = json.load(fp)
        reels = []
        if a.ig:
            with open(a.ig, encoding="utf-8") as fp:
                reels = json.load(fp)
        _out(fit(data, reels))
    elif a.cmd == "video":
        ch = channel.load(a.channel)
        r = insights.video(registry.analytics(ch), a.video_id, days=90, expect=ch.publish.channel_id)
        _out({k: r[k] for k in ("video", "totals", "retention", "traffic", "channel_watch", "notes")})
    else:
        print("\n".join(seen(a.channel)))


if __name__ == "__main__":
    main()

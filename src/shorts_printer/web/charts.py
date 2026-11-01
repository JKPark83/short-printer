"""성과 화면 차트 모양: SVG 좌표와 CSS 그라데이션. 차트 라이브러리 없이 서버에서 그린다(새 의존성 없음).
받은 값만 그리고 빈 날을 0으로 채우지 않는다."""

PALETTE = tuple(f"var(--in-{i})" for i in range(1, 6))   # 색은 style.css의 성과 토큰
OTHER = "var(--muted)"
GAP = "var(--card)"   # 도넛 조각 사이 띠(색만으로 나뉘지 않게)


def _nums(values: list) -> list[float]:
    return [float(v) for v in values if isinstance(v, int | float)]


def spark(values: list, w: int = 100, h: int = 28) -> str:
    """타일 아래 작은 추세선 점들. 값이 두 개 미만이면 빈 문자열(그리지 않는다)."""
    vals = _nums(values)
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    step = w / (len(vals) - 1)
    return " ".join(f"{i * step:.1f},{h - 2 - (v - lo) / span * (h - 4):.1f}" for i, v in enumerate(vals))


def trend(cur: list[dict], prev: list[dict], key: str = "views", w: int = 320, h: int = 140) -> dict | None:
    """이번 기간 선·면과 앞 기간 점선(같은 칸 수로 겹친다), 가장 높은 날 표시.
    x는 받은 행의 순서 그대로라 값이 빈 날은 점만 빠지고 날짜 자리는 밀리지 않는다.
    이번 기간 값이 두 개 미만이면 None, 모두 0이면 가장 높은 날(peak)도 None."""
    a = [(i, r.get("day", ""), r[key]) for i, r in enumerate(cur) if isinstance(r.get(key), int | float)]
    b = [(i, r[key]) for i, r in enumerate(prev) if isinstance(r.get(key), int | float)]
    if len(a) < 2:
        return None
    n = max(len(cur), len(prev))
    top = max([v for *_, v in a] + [v for _, v in b]) or 1
    pad = 10

    def xy(i: int, v: float) -> tuple[float, float]:
        return round(i * w / (n - 1), 1), round(h - pad - v / top * (h - 2 * pad), 1)

    pts = [xy(i, v) for i, _, v in a]
    best = max(a, key=lambda x: x[2])
    px, py = xy(best[0], best[2])
    return {"w": w, "h": h, "line": " ".join(f"{x},{y}" for x, y in pts),
            "area": f"M{pts[0][0]},{h} L" + " L".join(f"{x},{y}" for x, y in pts) + f" L{pts[-1][0]},{h} Z",
            "prev": " ".join(f"{x},{y}" for x, y in (xy(i, v) for i, v in b)) if len(b) >= 2 else "",
            "peak": {"x": px, "y": py, "value": best[2], "day": best[1], "left": round(px / w * 100, 1),
                     "top": round(py / h * 100, 1)} if best[2] > 0 else None,
            "first": a[0][1], "last": a[-1][1], "max": top}


def retention(rows: list[dict], w: int = 300, h: int = 120) -> str:
    """유지율 곡선 SVG 점들. 세로 끝은 시청 비율 1.5(반복 시청으로 1을 넘는다)."""
    pts = [(r["elapsedVideoTimeRatio"], r["audienceWatchRatio"]) for r in rows
           if isinstance(r.get("elapsedVideoTimeRatio"), int | float) and isinstance(r.get("audienceWatchRatio"),
                                                                                    int | float)]
    return " ".join(f"{x * w:.1f},{h - min(y, 1.5) / 1.5 * h:.1f}" for x, y in pts)


def slices(rows: list[dict], n: int = 4) -> list[dict]:
    """비율 조각: 위 n개 + 나머지는 '기타'. 색은 팔레트 순서, 기타는 회색."""
    shown = [r for r in rows if isinstance(r.get("share"), int | float)][:n]
    rest = round(100 - sum(r["share"] for r in shown), 1)
    out = [{"label": r["label"], "share": r["share"], "views": r.get("views"), "color": PALETTE[i % len(PALETTE)]}
           for i, r in enumerate(shown)]
    if len(rows) > n and rest > 0:
        out.append({"label": "기타", "share": rest, "views": None, "color": OTHER})
    return out


def donut(parts: list[dict]) -> str:
    """conic-gradient 값. 조각 사이에 바탕색 띠를 넣어 색만으로 나뉘지 않게 한다."""
    stops, at = [], 0.0
    for p in parts:
        end = at + p["share"]
        gap = min(0.8, p["share"] / 4) if len(parts) > 1 else 0
        stops.append(f"{p['color']} {at:.1f}% {end - gap:.1f}%")
        if gap:
            stops.append(f"{GAP} {end - gap:.1f}% {end:.1f}%")
        at = end
    return "conic-gradient(" + ", ".join(stops) + ")" if stops else ""


def weekday(rows: list[dict] | None) -> list[dict]:
    """요일 막대 높이(%). 가장 높은 요일을 100으로."""
    if not rows:
        return []
    top = max((r["avg"] or 0 for r in rows), default=0) or 1
    return [r | {"pct": round((r["avg"] or 0) / top * 100), "best": r["avg"] == top} for r in rows]

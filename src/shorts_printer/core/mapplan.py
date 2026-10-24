"""롱폼 6단계 지도 계획: LLM이 지도 범위·지명·전선 상태(world)와 장면마다 카메라·라벨·화살표·날짜를 쓰고,
film_parts가 낱말 시각으로 film.build 칸(절대 초)을 만든다. 규칙은 history-map-video 스킬 references/map.md.

LLM은 시각을 쓰지 않는다: 낱말(at)을 고르면 timing의 그 낱말 시작으로 맞춘다.
좌표·점 개수·키 겹침은 코드가 고친다. 고친 것은 film_parts 결과의 "warnings"(film.build는 모르는 키를 안 읽는다)."""
import json
import math
import re
from typing import Literal

from pydantic import BaseModel, Field

from ..infra import maptiles
from ..ports.llm import LLM, add_usage
from . import prompts, research
from .channel import Channel

SIZE = (1920, 1080)
MOVE, FRONT_MOVE = 2.4, 3.0
CLOSE, FAR = 1.4, 0.3   # 카메라 배율 상한(타일이 흐려지기 전) / 가운데가 detail 밖일 때 상한
EDGE = 0.5   # 화면 가장자리가 detail 밖이어도 되는 상한: wide.jpg(1/4 해상도)가 2배까지 커진다(원본 반도 장면)
DRAW, ARROWS = 0.9, 4   # 화살표 그리는 초, 장면마다 화살표 수 상한
CREDIT = "지도 Esri, Maxar, Earthstar Geographics · Natural Earth"


class Place(BaseModel):
    id: str = Field(description="영문 소문자 id(seoul, han_river)")
    name: str = Field(description="화면에 쓸 지명, 짧게")
    lng: float
    lat: float


class State(BaseModel):
    name: str = Field(description="상태 이름(L0, L1 …)")
    points: list[list[float]] = Field(description="[경도, 위도] 8~12개. 모든 상태가 같은 개수·순서, 첫·끝 점은 바다")


class World(BaseModel):
    box: list[float] = Field(description="[서, 북, 동, 남]. 어느 장면이든 보이는 곳 전부 + 여유")
    zoom: int = Field(description="타일 줌 6~9")
    detail: list[float] = Field(description="[서, 북, 동, 남]. 원본 해상도로 둘 상자, 가까이 보는 곳은 모두 이 안")
    land: list[str] = Field(description="점령지를 자를 나라 ADM0_A3 코드")
    border: list[str] = Field(description="얇은 국경선으로 보일 이웃 나라 ADM0_A3 코드")
    border_box: list[float] | None = Field(None, description="국경선을 자를 [서, 북, 동, 남], 없으면 null")
    side: Literal["north", "south", "west", "east"] = Field(description="점령지(강조색)가 전선의 어느 쪽인지")
    states: list[State] = Field(default_factory=list, description="전선 상태, 시간 순. 전선 없는 이야기면 빈 목록")
    places: list[Place] = Field(description="장면에 쓸 지명·지역·강·바다 전부")


class Camera(BaseModel):
    place: str = Field("", description="가운데 둘 places id. 비우면 lng·lat")
    lng: float = 0
    lat: float = 0
    scale: float = Field(description="화면 px / 지도 px. 화면 가로 경도 폭 ≈ 2700 / (scale × 2^zoom)")


class Label(BaseModel):
    place: str = Field(description="places id")
    at: str = Field(description="그곳을 말하는 내레이션 낱말 그대로")
    left: bool = Field(False, description="글을 점 왼쪽에")
    pin: bool = Field(True, description="점 찍기. 나라·강·바다는 false")


class Arrow(BaseModel):
    points: list[str | list[float]] = Field(description="[시작, 굽이, 끝]: places id 또는 [경도, 위도], 굽이는 온 쪽")
    at: str = Field(description="그리기 시작할 낱말")
    color: str = Field("accent", description="accent · ink · #RRGGBB")


class Date(BaseModel):
    year: str
    big: str = Field(description="큰 글(6. 25 · 8월)")
    small: str = Field("", description="작은 줄(새벽 4시), 없으면 빈 글")
    at: str = Field(description="그 날짜를 말하는 낱말")


class Flash(BaseModel):
    place: str = Field(description="places id")
    at: str = Field(description="터지는 낱말")


class SceneMap(BaseModel):
    scene: int = Field(description="받은 장면 번호 그대로")
    camera: Camera | None = Field(None, description="앞 장면 그대로면 null, clip 장면도 null")
    front: str = Field("", description="옮겨 갈 전선 상태 이름, 그대로면 빈 글")
    labels: list[Label] = Field(default_factory=list)
    arrows: list[Arrow] = Field(default_factory=list)
    date: Date | None = None
    flashes: list[Flash] = Field(default_factory=list)


class Chapter(BaseModel):
    scenes: list[SceneMap] = Field(description="받은 장면마다 하나")


def plan(llm: LLM, ch: Channel, script: dict, timing: list[dict], facts: list[dict], note: str = "",
         old: dict | None = None) -> tuple[dict, dict]:
    """(plan, 사용량). 1번 지도 전체(world), 그 뒤 장마다 1번 장면 지도.
    note·old: 지난 계획과 "고쳐 줘" 문장. 둘 다 모델에 주고 말한 곳만 고치게 한다."""
    sc, n = script["scenes"], len(script["scenes"])

    def lines(idx):
        return "\n".join(f"{i}. [{sc[i]['kind']}{' ' + sc[i]['beat'] if sc[i].get('beat') else ''}, "
                         f"{timing[i]['end'] - timing[i]['start']:.0f}초] {sc[i]['narration']}"
                         f"\n   화면: {sc[i]['visual']}" for i in idx)

    def fix(part):
        if not (note or old):
            return ""
        return (f"\n\n지난 계획(말한 곳만 고치고 나머지는 그대로 둔다):\n{json.dumps(part, ensure_ascii=False)}"
                f"\n\n고쳐 달라는 말: {note or '없음'}")
    refusal = f"{llm.label}가 이 대본으로는 지도 계획을 쓰지 않았어요. 대본을 바꿔 보세요."
    text = f"제목: {script['title']}\n장면 {n}개:\n{lines(range(n))}"
    if facts:
        text += "\n\n사실 시트:\n" + research.sheet(list(facts))
    w, usage = llm.ask(prompts.render("long_map_world", concept=ch.concept), text + fix(old and old["world"]),
                       World, refusal=refusal, what="지도 계획")
    world = _world(w)

    head = (f"지도: zoom {world['zoom']}, box {world['box']}, detail {world['detail']}, 점령지 쪽 {world['side']}\n"
            f"places:\n" + "\n".join(f"- {k}: {p['name']} ({p['lng']}, {p['lat']})" for k, p in world["places"].items())
            + f"\nstates(시간 순): {', '.join(world['states']) or '없음(화살표·라벨로만)'}")
    firsts = sorted({0, *(c["first"] for c in script.get("chapters") or [] if 0 <= c["first"] < n)})
    scenes = [SceneMap(scene=i).model_dump() for i in range(n)]
    sys = prompts.render("long_map_scenes", lang=ch.lang_name)
    for a, b in zip(firsts, [*firsts[1:], n], strict=True):
        part = old and old["scenes"][a:b]
        out, u = llm.ask(sys, f"{head}\n\n이 장의 장면:\n{lines(range(a, b))}" + fix(part), Chapter,
                         refusal=refusal, what="장면 지도 계획")
        usage = add_usage(usage, u)
        for s in out.scenes:
            if a <= s.scene < b:
                scenes[s.scene] = s.model_dump()
    return {"world": world, "scenes": scenes}, usage


def _box(b, inside=None) -> list[float] | None:
    """[서, 북, 동, 남]으로 바로 세운다. inside를 주면 그 안으로 자른다(빈 상자면 inside)."""
    if not b or len(b) != 4:
        return inside
    w, n, e, s = min(b[0], b[2]), max(b[1], b[3]), max(b[0], b[2]), min(b[1], b[3])
    if inside:
        w, n, e, s = max(w, inside[0]), min(n, inside[1]), min(e, inside[2]), max(s, inside[3])
        if not (w < e and s < n):
            return inside
    return [w, n, e, s]


def _world_px(box: list[float], zoom: int) -> tuple[tuple[float, float], tuple[float, float]]:
    z = {"z": zoom, "x0": 0, "y0": 0}
    return maptiles.px(z, box[0], box[1]), maptiles.px(z, box[2], box[3])


def _world(w: World) -> dict:
    """LLM 답 → plan["world"]. 상자를 바로 세우고 줌은 6~9, 타일이 너무 많으면 낮춘다."""
    box = _box(w.box)
    if not box or not (box[0] < box[2] and box[3] < box[1]):
        raise RuntimeError(f"지도 상자가 잘못됐어요: {w.box}. 다시 시도하세요.")
    zoom = min(max(w.zoom, 6), 9)
    while zoom > 6:
        (x0, y0), (x1, y1) = _world_px(box, zoom)
        if (int(x1 // 256) - int(x0 // 256) + 1) * (int(y1 // 256) - int(y0 // 256) + 1) <= maptiles.MAX_TILES:
            break
        zoom -= 1
    # 상자가 화면/CLOSE보다 작으면 화면을 채우느라 카메라가 CLOSE를 넘겨 확대된다: 가운데를 두고 넓힌다
    # ponytail: 위도는 선형으로 늘린다(메르카토르라 큰 상자면 조금 모자란다). 작은 상자에서만 걸려 괜찮다
    (x0, y0), (x1, y1) = _world_px(box, zoom)
    fx, fy = max(1, SIZE[0] / CLOSE / (x1 - x0)), max(1, SIZE[1] / CLOSE / (y1 - y0))
    if fx > 1 or fy > 1:
        cx, cy, hw, hh = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2, (box[1] - box[3]) / 2
        box = [round(v, 4) for v in (cx - hw * fx, cy + hh * fy, cx + hw * fx, cy - hh * fy)]
    return {"box": box, "zoom": zoom, "detail": _box(w.detail, box), "land": w.land, "border": w.border,
            "border_box": _box(w.border_box), "side": w.side,
            "states": {s.name: s.points for s in w.states},
            "places": {p.id: {"name": p.name, "lng": p.lng, "lat": p.lat} for p in w.places}}


def _clean(s) -> str:
    """HTML에 그대로 들어가는 글: 태그·속성을 깨는 기호를 뺀다."""
    return re.sub(r'[<>&"]', "", str(s)).strip()


def _norm(s: str) -> str:
    return re.sub(r"[\W_]", "", s).lower()


def _r(v: float) -> float:
    return round(v, 2)


def _resample(pts: list, k: int) -> list[list[float]]:
    """선을 따라 같은 간격 점 k개(첫·끝 점은 그대로). film.js가 점 i를 점 i로 옮기므로 상태마다 개수를 맞춘다."""
    d = [0.0]
    for a, b in zip(pts, pts[1:], strict=False):
        d.append(d[-1] + math.dist(a, b))
    out, j = [], 0
    for i in range(k):
        t = d[-1] * i / (k - 1)
        while j < len(d) - 2 and d[j + 1] < t:
            j += 1
        f = (t - d[j]) / (d[j + 1] - d[j]) if d[j + 1] > d[j] else 0
        out.append([round(pts[j][c] + (pts[j + 1][c] - pts[j][c]) * f, 4) for c in (0, 1)])
    return out


def film_parts(plan: dict, script: dict, timing: list[dict], end_start: float, accent: str, ink: str) -> dict:
    """plan → film.build 칸: states, side, front, cam, labels, arrows, flashes, dates, date_pos, date_end, night,
    reflines, ghosts, map_tweens, map_credit. 시각은 절대 초, 글은 정리했다. 버린 것은 "warnings"(한국어 목록)."""
    w, warn = plan["world"], []
    box, detail = w["box"], w["detail"] or w["box"]
    S, E = [t["start"] for t in timing], [t["end"] for t in timing]
    kinds = [s.get("kind") for s in script["scenes"]]
    scenes = plan["scenes"]

    def inside(lng, lat, b=box):
        return [round(min(max(lng, b[0]), b[2]), 4), round(min(max(lat, b[3]), b[1]), 4)]
    places = {k: (_clean(p["name"]), *inside(p["lng"], p["lat"])) for k, p in w["places"].items()}

    def pt(n, ref):   # places id 또는 [경도, 위도] → [경도, 위도] | None
        if isinstance(ref, str):
            if ref in places:
                return list(places[ref][1:])
            warn.append(f"장면 {n}: places에 없는 지명이라 뺐어요({_clean(ref)})")
            return None
        return inside(*ref) if len(ref) == 2 else None

    def at(n, word):   # 낱말 시각. 못 찾으면 장면 시작 + 0.3
        a = _norm(word.split()[0]) if word.split() else ""
        hit = next((x["start"] for x in timing[n].get("words") or [] if a and a in _norm(x["text"])), None)
        return _r(S[n] + 0.3 if hit is None else hit)

    # 카메라: 지도 이미지가 화면보다 작아지지 않게. 가운데가 detail 밖이면 FAR, 화면 가장자리가 밖이면 EDGE 이하
    (x0, y0), (x1, y1) = _world_px(box, w["zoom"])
    (dx0, dy0), (dx1, dy1) = _world_px(detail, w["zoom"])
    lo = max(0.15, SIZE[0] / (x1 - x0), SIZE[1] / (y1 - y0))

    def scale(s, p):
        s = min(max(s, 0.15), CLOSE)
        (x, y), _ = _world_px([*p, *p], w["zoom"])
        hw, hh = SIZE[0] / 2 / s, SIZE[1] / 2 / s
        if p != inside(*p, detail):
            s = min(s, FAR)
        elif s > EDGE and not (dx0 <= x - hw and x + hw <= dx1 and dy0 <= y - hh and y + hh <= dy1):
            s = EDGE
        return round(max(s, lo), 3)

    cam = []
    for n, sm in enumerate(scenes):
        c = sm.get("camera")
        if n and (not c or kinds[n] == "clip"):   # 클립 아래 지도는 그대로 둔다
            continue
        p = c and (pt(n, c["place"]) if c.get("place") else (c["lng"] or c["lat"]) and inside(c["lng"], c["lat"]))
        if not p:
            if n:
                continue
            p, c = inside((detail[0] + detail[2]) / 2, (detail[1] + detail[3]) / 2), {"scale": 0.3}
        key = [*p, scale(c["scale"], p)]
        if not n:   # 첫 화면 + 다음 장면까지 천천히 다가가기
            drift = _r(S[1] - 0.3 if len(S) > 1 else E[0])
            cam = [[0, 0, *key], [0, drift, *p, scale(key[2] * 1.12, p)]]
        elif key != cam[-1][2:]:
            cam.append([_r(max(S[n] - 0.3, cam[-1][0] + cam[-1][1])), MOVE, *key])

    def cam_scale(t):
        return next((k[4] for k in reversed(cam) if k[0] <= t), cam[0][4])

    # 전선 상태: 같은 점 개수, 같은 방향(서→동 또는 북→남)이어야 선이 꼬이지 않는다
    raw = {}
    for name, pts in w["states"].items():
        if len(pts) < 2 or any(len(p) != 2 for p in pts):
            warn.append(f"전선 상태의 점이 모자라 뺐어요({_clean(name)})")
            continue
        pts = [inside(*p) for p in pts]
        flip = pts[0][0] > pts[-1][0] if w["side"] in ("north", "south") else pts[0][1] < pts[-1][1]
        raw[_clean(name)] = pts[::-1] if flip else pts
    k = max([8, *map(len, raw.values())])
    states = {name: pts if len(pts) == k else _resample(pts, k) for name, pts in raw.items()}

    front, tweens = [], []
    for n, sm in enumerate(scenes):
        f = _clean(sm.get("front") or "")
        if not f or (front and f == front[-1][2]):
            continue
        if f not in states:
            warn.append(f"장면 {n}: states에 없는 전선 상태라 뺐어요({f})")
        elif not front:   # 첫 상태는 0초부터 깔고, 나중에 나오면 그때까지 숨긴다
            front.append([0, 0, f])
            if n:
                tweens += [f'tl.fromTo("#map-occ", {{opacity: 0}}, {{opacity: 0.4, duration: 0.6}}, {_r(S[n])});',
                           f'tl.fromTo("#map-front", {{opacity: 0}}, {{opacity: 1, duration: 0.6}}, {_r(S[n])});']
        else:
            front.append([_r(max(S[n], front[-1][0] + front[-1][1])), FRONT_MOVE, f])

    labels, live = [], []
    for n, sm in enumerate(scenes):
        for a, i, lb in sorted((at(n, lb["at"]), i, lb) for i, lb in enumerate(sm.get("labels") or [])):
            if lb["place"] not in places:
                warn.append(f"장면 {n}: places에 없는 지명이라 뺐어요({_clean(lb['place'])})")
                continue
            live = [x for x in live if x[5] > a]
            if len(live) >= 3:   # 한 화면 3개까지: 가장 먼저 뜬 것을 일찍 끝낸다
                oldest = live.pop(0)
                oldest[5] = _r(max(a, oldest[4] + 0.6))
            name, lng, lat = places[lb["place"]]
            lab = [f"s{n}-{i}", name, lng, lat, a, _r(E[n] + 0.6), bool(lb.get("left")), bool(lb.get("pin", True))]
            labels.append(lab)
            live.append(lab)

    arrows = []
    for n, sm in enumerate(scenes):
        if len(sm.get("arrows") or []) > ARROWS:
            warn.append(f"장면 {n}: 화살표가 많아 {ARROWS}개만 썼어요")
        for i, ar in enumerate((sm.get("arrows") or [])[:ARROWS]):
            pts = [pt(n, p) for p in ar["points"]]
            if None in pts or len(pts) not in (2, 3):
                warn.append(f"장면 {n}: 화살표 점이 잘못돼 뺐어요({i}번)")
                continue
            if len(pts) == 2:
                pts.insert(1, [(pts[0][c] + pts[1][c]) / 2 for c in (0, 1)])
            color = {"accent": accent, "ink": ink}.get(ar.get("color"), ar.get("color") or accent)
            a = _r(at(n, ar["at"]) + 0.15 * i)
            # 끝(사라지기 0.4초 전)이 머리가 뜨기 전이면 머리가 영상 끝까지 남는다
            arrows.append([f"s{n}-{i}", pts, a, DRAW, _r(max(E[n] + 1.0, a + DRAW + 0.5)),
                           color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else accent, cam_scale(a)])

    dates = sorted([at(n, d["at"]), _clean(d["year"]), _clean(d["big"]), _clean(d.get("small") or "")]
                   for n, sm in enumerate(scenes) if (d := sm.get("date")))
    flashes = [[at(n, f["at"]), *p] for n, sm in enumerate(scenes) for f in sm.get("flashes") or []
               if (p := pt(n, f["place"]))]
    return {"states": states, "side": w["side"], "front": front, "cam": cam, "labels": labels, "arrows": arrows,
            "flashes": sorted(flashes), "dates": dates, "date_pos": [112, 120], "date_end": end_start,
            "night": None, "reflines": [], "ghosts": None, "map_tweens": tweens,
            "map_credit": CREDIT + (" · 전선은 대략적 위치" if front else ""), "warnings": warn}

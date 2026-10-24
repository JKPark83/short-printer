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
from . import film, prompts, research
from .channel import Channel

SIZE = (1920, 1080)
MOVE, FRONT_MOVE = 2.4, 3.0
# 장면 안 카메라(shots): 옮기는 초 / 앞 움직임이 끝나고 머무는 최소 초 / 낱말보다 늦게 옮겨도 되는 초 /
# 이보다 오래 머물면 / 컷 하나 길이(초)마다 당겼다 물린다
SHOT_MOVE, HOLD, LATE, STILL, CUT = 1.2, 1.0, 1.5, 4.0, 3.5
CLOSE, FAR = 1.4, 0.3   # 카메라 배율 상한(타일이 흐려지기 전) / 가운데가 detail 밖일 때 상한
EDGE = 0.5   # 화면 가장자리가 detail 밖이어도 되는 상한: wide.jpg(1/4 해상도)가 2배까지 커진다(원본 반도 장면)
CLOSE_TILES, CLOSE_ZOOM = 400, 16   # close 상자(해협·성): 타일 상한(약 5000px 네모) / 가장 높은 줌
DRAW, ARROWS = 0.9, 4   # 화살표 그리는 초, 장면마다 화살표 수 상한
CREDIT = "지도 Esri, Maxar, Earthstar Geographics · Natural Earth"
PHOTOS, PHOTO_BOX = 8, (1170, 170, 620, 0.75)   # 한 편의 기록 사진 상한 / 오른쪽 칸 left·top·너비·높이/너비 상한
STAT_POS = (112, 470)   # 숫자 카드: 왼쪽 칸 날짜 아래, 자막 위
STAT_MIN = 10   # 숫자 카드는 이만큼부터: 0→3처럼 짧게 오르면 세는 맛이 없다


class Place(BaseModel):
    id: str = Field(description="영문 소문자 id(seoul, han_river)")
    name: str = Field(description="화면에 쓸 지명, 짧게")
    lng: float
    lat: float


class State(BaseModel):
    name: str = Field(description="상태 이름(L0, L1 …)")
    when: str = Field("", description="언제 어떤 선인지(1950. 8. 1 낙동강 방어선). 장면 단계가 이걸 보고 고른다")
    points: list[list[float]] = Field(description="[경도, 위도] 8~12개. 모든 상태가 같은 개수·순서, 첫·끝 점은 바다")


class World(BaseModel):
    box: list[float] = Field(description="[서, 북, 동, 남]. 어느 장면이든 보이는 곳 전부 + 여유")
    zoom: int = Field(description="타일 줌 6~9")
    detail: list[float] = Field(description="[서, 북, 동, 남]. 원본 해상도로 둘 상자, 가까이 보는 곳은 모두 이 안")
    close: list[float] | None = Field(None, description="[서, 북, 동, 남]. 해협·성·마을처럼 아주 좁은 곳을 "
                                      "더 가까이 볼 상자(가로 0.1~0.6도), 없으면 null")
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


class Shot(Camera):
    at: str = Field(description="카메라를 옮길 낱말, 그 장면 내레이션 그대로")


class Label(BaseModel):
    place: str = Field(description="places id")
    at: str = Field(description="그곳을 말하는 내레이션 낱말 그대로")
    left: bool = Field(False, description="글을 점 왼쪽에")
    pin: bool = Field(True, description="점 찍기. 나라·강·바다는 false")


class Arrow(BaseModel):
    points: list[str | list[float]] = Field(description="[시작, 굽이, 끝]: places id 또는 [경도, 위도], 굽이는 온 쪽")
    at: str = Field(description="그리기 시작할 낱말")
    color: str = Field("accent", description="accent · ink · #RRGGBB")
    unit: Literal["", *film.UNITS] = Field("", description="화살표를 따라 움직일 병력 그림, 군대가 아니면 빈 글")


class Date(BaseModel):
    year: str
    big: str = Field(description="큰 글(6. 25 · 8월)")
    small: str = Field("", description="작은 줄(새벽 4시), 없으면 빈 글")
    at: str = Field(description="그 날짜를 말하는 낱말")


class Stat(BaseModel):
    label: str = Field(description="무엇의 수인지 짧게(국군 전사자)")
    value: float = Field(description="말한 수 그대로 숫자만(13만 7천 899 → 137899)")
    unit: str = Field("", description="단위(명 · 일 · km · %)")
    at: str = Field(description="그 수를 말하는 낱말")


class Flash(BaseModel):
    place: str = Field(description="places id")
    at: str = Field(description="터지는 낱말")


class SceneMap(BaseModel):
    scene: int = Field(description="받은 장면 번호 그대로")
    camera: Camera | None = Field(None, description="앞 장면 그대로면 null, clip 장면도 null")
    shots: list[Shot] = Field(default_factory=list,
                              description="장면 안에서 3~4초마다 옮겨 갈 카메라, clip 장면은 빈 목록")
    front: str = Field("", description="옮겨 갈 전선 상태 이름, 그대로면 빈 글")
    labels: list[Label] = Field(default_factory=list)
    arrows: list[Arrow] = Field(default_factory=list)
    date: Date | None = None
    flashes: list[Flash] = Field(default_factory=list)
    stats: list[Stat] = Field(default_factory=list, description="내레이션이 말하는 숫자 카드, 장면에 하나까지")


class Chapter(BaseModel):
    scenes: list[SceneMap] = Field(description="받은 장면마다 하나")


class Photo(BaseModel):
    scene: int = Field(description="받은 장면 번호 그대로")
    query: str = Field(description="Wikimedia Commons 검색어, 영어 낱말 3~6개")
    caption: str = Field(description="사진 아래 한 줄(날짜 + 무엇)")
    at: str = Field(description="사진이 뜨는 낱말, 그 장면 내레이션 그대로")


class Photos(BaseModel):
    photos: list[Photo]


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

    states = "\n".join(f"- {k}: {world['when'].get(k) or '설명 없음'}" for k in world["states"])
    near = (f", close {world['close']}(이 안은 scale {CLOSE}~{close_top(world)}까지)" if world["close"] else "")
    head = (f"지도: zoom {world['zoom']}, box {world['box']}, detail {world['detail']}{near}, "
            f"점령지 쪽 {world['side']}\n"
            f"places:\n" + "\n".join(f"- {k}: {p['name']} ({p['lng']}, {p['lat']})" for k, p in world["places"].items())
            + f"\nstates(시간 순):\n{states or '없음(화살표·라벨로만)'}")
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


def photos(llm: LLM, ch: Channel, script: dict) -> tuple[list[dict], dict]:
    """(기록 사진을 띄울 장면 목록, 사용량). 장면마다 하나, clip 장면 빼고, PHOTOS개까지. 사진 받기는 초안 단계."""
    sc = script["scenes"]
    text = f"제목: {script['title']}\n장면 {len(sc)}개:\n" + "\n".join(
        f"{i}. [{s['kind']}] {s['narration']}" for i, s in enumerate(sc))
    out, usage = llm.ask(prompts.render("long_photos", lang=ch.lang_name, most=PHOTOS), text, Photos,
                         refusal=f"{llm.label}가 이 대본으로는 기록 사진을 고르지 않았어요.", what="기록 사진 고르기")
    picks = {}
    for ph in out.photos:
        if 0 <= ph.scene < len(sc) and sc[ph.scene]["kind"] != "clip" and ph.query.strip():
            picks.setdefault(ph.scene, ph.model_dump())
    return list(picks.values())[:PHOTOS], usage


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


def _lnglat(x: float, y: float, zoom: int) -> list[float]:
    """_world_px의 거꾸로: 세계 px → [경도, 위도]."""
    n = 256 * 2 ** zoom
    return [round(x / n * 360 - 180, 4), round(math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), 4)]


def _tiles(box: list[float], zoom: int) -> int:
    (x0, y0), (x1, y1) = _world_px(box, zoom)
    return (int(x1 // 256) - int(x0 // 256) + 1) * (int(y1 // 256) - int(y0 // 256) + 1)


def close_top(world: dict) -> float:
    """close 상자 안 카메라 배율 상한: close.jpg를 원본 크기로 볼 때까지."""
    return round(CLOSE * 2 ** (world["close_zoom"] - world["zoom"]), 1)


def _world(w: World) -> dict:
    """LLM 답 → plan["world"]. 상자를 바로 세우고 줌은 6~9, 타일이 너무 많으면 낮춘다.
    close 상자는 타일 CLOSE_TILES장 안에서 가장 높은 줌. 지도 줌보다 2 이상 높지 않으면 detail로 충분해 버린다."""
    box = _box(w.box)
    if not box or not (box[0] < box[2] and box[3] < box[1]):
        raise RuntimeError(f"지도 상자가 잘못됐어요: {w.box}. 다시 시도하세요.")
    zoom = min(max(w.zoom, 6), 9)
    while zoom > 6 and _tiles(box, zoom) > maptiles.MAX_TILES:
        zoom -= 1
    # 상자가 화면/CLOSE보다 작으면 화면을 채우느라 카메라가 CLOSE를 넘겨 확대된다: 가운데를 두고 넓힌다
    # ponytail: 위도는 선형으로 늘린다(메르카토르라 큰 상자면 조금 모자란다). 작은 상자에서만 걸려 괜찮다
    (x0, y0), (x1, y1) = _world_px(box, zoom)
    fx, fy = max(1, SIZE[0] / CLOSE / (x1 - x0)), max(1, SIZE[1] / CLOSE / (y1 - y0))
    if fx > 1 or fy > 1:
        cx, cy, hw, hh = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2, (box[1] - box[3]) / 2
        box = [round(v, 4) for v in (cx - hw * fx, cy + hh * fy, cx + hw * fx, cy - hh * fy)]
    close = _box(w.close, box) if w.close and len(w.close) == 4 else None
    close_zoom = next((z for z in range(CLOSE_ZOOM, zoom + 1, -1) if close and _tiles(close, z) <= CLOSE_TILES), None)
    return {"box": box, "zoom": zoom, "detail": _box(w.detail, box), "land": w.land, "border": w.border,
            "close": close_zoom and close, "close_zoom": close_zoom,
            "border_box": _box(w.border_box), "side": w.side,
            "states": {s.name: s.points for s in w.states}, "when": {s.name: _clean(s.when) for s in w.states},
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


def _said_first(scenes: list[dict], script: dict, warn: list[str]) -> list[dict]:
    """날짜(와 같은 장면의 전선)를 그 날짜를 처음 말하는 장면으로 당긴다. 모델이 clip 장면을 건너뛰고 다음 장면에
    날짜를 달면 클립이 끝난 뒤 지도에 지난 날짜·전선이 남는다(1·4 후퇴를 말하는데 11. 24가 보이던 일)."""
    out = [dict(s) for s in scenes]
    for n in range(len(out)):
        d = out[n].get("date")
        m = d and re.fullmatch(r"(\d{1,2})\.\s*(\d{1,2})", d["big"].strip())
        if not m:
            continue
        # ponytail: 한국어 날짜 꼴("1월 4일")만 본다. 다른 언어 롱폼 채널이 생기면 언어마다 꼴을 더한다
        said, k = f"{int(m[1])}월 {int(m[2])}일", n
        for j in range(n - 1, -1, -1):
            if out[j].get("date"):
                break
            if said in script["scenes"][j]["narration"]:
                k = j
        if k == n:
            continue
        out[k] = out[k] | {"date": d | {"at": f"{int(m[1])}월"}}
        out[n] = out[n] | {"date": None}
        if out[n].get("front") and not out[k].get("front"):
            out[k]["front"], out[n]["front"] = out[n]["front"], ""
        warn.append(f"장면 {n}: 날짜 {_clean(d['big'])}를 그 날짜를 말하는 장면 {k}로 당겼어요")
    return out


def film_parts(plan: dict, script: dict, timing: list[dict], end_start: float, accent: str, ink: str,
               got: dict[int, dict] | None = None) -> dict:
    """plan → film.build 칸: states, side, front, cam, labels, arrows, flashes, dates, date_pos, date_end, night,
    reflines, ghosts, map_tweens, map_credit, photos, counters.
    시각은 절대 초, 글은 정리했다. 버린 것은 "warnings"(한국어 목록).
    got: 받은 사진 {장면: {file, width, height}}. 못 받은 장면의 사진은 뺀다."""
    w, warn = plan["world"], []
    box, detail = w["box"], w["detail"] or w["box"]
    S, E = [t["start"] for t in timing], [t["end"] for t in timing]
    kinds = [s.get("kind") for s in script["scenes"]]
    scenes = _said_first(plan["scenes"], script, warn)

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

    # 카메라: 지도 이미지가 화면보다 작아지지 않게. 가운데가 detail 밖이면 FAR.
    # 화면 가장자리가 detail(가까이 보면 close) 밖으로 나가면 가운데를 안쪽으로 민다. 흐린 곳이 보이지 않게
    z, (x0, y0), (x1, y1) = w["zoom"], *_world_px(box, w["zoom"])
    lo = max(0.15, SIZE[0] / (x1 - x0), SIZE[1] / (y1 - y0))
    near, top = w.get("close"), w.get("close") and close_top(w)

    def into(s, p, b):   # 배율 s 화면이 상자 b 안에 들도록 민 가운데 | None(상자가 화면보다 작다)
        (bx0, by0), (bx1, by1) = _world_px(b, z)
        (x, y), _ = _world_px([*p, *p], z)
        hw, hh = SIZE[0] / 2 / s, SIZE[1] / 2 / s
        if bx1 - bx0 < 2 * hw or by1 - by0 < 2 * hh:
            return None
        return _lnglat(min(max(x, bx0 + hw), bx1 - hw), min(max(y, by0 + hh), by1 - hh), z)

    def view(s, p):   # 바라는 배율·가운데 → [경도, 위도, scale]
        if near and s > CLOSE and p == inside(*p, near):
            (bx0, by0), (bx1, by1) = _world_px(near, z)
            s = min(max(s, SIZE[0] / (bx1 - bx0), SIZE[1] / (by1 - by0)), top)   # close 상자를 화면에 채운다
            if q := into(s, p, near):
                return [*q, round(s, 3)]
        s = min(max(s, 0.15), CLOSE)
        if p != inside(*p, detail):
            s = min(s, FAR)
        elif s > EDGE:
            q = into(s, p, detail)
            p, s = (q, s) if q else (p, EDGE)
        return [*p, round(max(s, lo), 3)]

    def cam_key(n, c):   # Camera·Shot → [경도, 위도, scale] | None
        p = c and (pt(n, c["place"]) if c.get("place")
                   else (c.get("lng") or c.get("lat")) and inside(c["lng"], c["lat"]))
        return p and view(c["scale"], p)

    cam = []
    for n, sm in enumerate(scenes):
        if n and kinds[n] == "clip":   # 클립 아래 지도는 그대로 둔다
            continue
        key = cam_key(n, sm.get("camera"))
        shots = sorted(((_r(at(n, sh["at"]) - 0.3), i, sh) for i, sh in enumerate(sm.get("shots") or [])))
        if not n:   # 첫 화면 + 다음 장면(또는 첫 shot)까지 천천히 다가가기
            if not key:
                p = inside((detail[0] + detail[2]) / 2, (detail[1] + detail[3]) / 2)
                key = view(0.3, p)
            drift = _r(min([S[1] - 0.3 if len(S) > 1 else E[0], *[t - HOLD for t, _, _ in shots[:1]]]))
            cam = [[0, 0, *key], [0, max(drift, 0.5), *view(key[2] * 1.12, key[:2])]]
        elif key and key != cam[-1][2:]:
            cam.append([_r(max(S[n] - 0.3, cam[-1][0] + cam[-1][1])), MOVE, *key])
        for t, i, sh in shots:   # 한 문장 안에서 낱말마다 다른 곳을 본다
            key = cam_key(n, sh)
            if not key or key == cam[-1][2:]:
                continue
            free = _r(cam[-1][0] + cam[-1][1] + HOLD)   # 조금 이르면 늦춰서라도 컷을 살린다
            if free - t > LATE or free > E[n]:
                warn.append(f"장면 {n}: 카메라를 너무 빨리 또 옮겨 뺐어요(shot {i}번)")
                continue
            cam.append([max(t, free), SHOT_MOVE, *key])

    # 오래 머무는 곳은 CUT초마다 같은 자리를 당겼다 물려 컷을 바꾼다(shots가 모자란 장면)
    still = []
    for k, t1 in zip(cam, [*(k[0] for k in cam[1:]), end_start], strict=True):
        still.append(k)
        t0, gap = k[0] + k[1], t1 - (k[0] + k[1])
        tight = view(k[4] * 1.25, k[2:4])
        if tight[2] == k[4]:   # 상한에 걸리면 물려서 연다
            tight = view(k[4] / 1.25, k[2:4])
        if gap <= STILL or tight[2] == k[4]:
            continue
        n = math.ceil(gap / CUT)
        still += [[_r(t0 + j * gap / n), SHOT_MOVE, *(tight if j % 2 else k[2:])] for j in range(1, n)]
    cam = still

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

    front, tweens, order = [], [], list(states)
    for n, sm in enumerate(scenes):
        f = _clean(sm.get("front") or "")
        if not f or (front and f == front[-1][2]):
            continue
        if f not in states:
            warn.append(f"장면 {n}: states에 없는 전선 상태라 뺐어요({f})")
        elif front and order.index(f) < order.index(front[-1][2]):   # 상태는 시간 순: 되돌아가면 날짜와 어긋난다
            warn.append(f"장면 {n}: 앞 상태로 되돌아가는 전선이라 뺐어요({f})")
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
                           color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else accent, cam_scale(a),
                           ar.get("unit") if ar.get("unit") in film.UNITS else ""])

    dates = sorted([at(n, d["at"]), _clean(d["year"]), _clean(d["big"]), _clean(d.get("small") or "")]
                   for n, sm in enumerate(scenes) if (d := sm.get("date")))
    flashes = [[at(n, f["at"]), *p] for n, sm in enumerate(scenes) for f in sm.get("flashes") or []
               if (p := pt(n, f["place"]))]

    # 숫자 카드: 장면에 하나, 낱말에 떠서 4.5초쯤(장면 끝 + 0.5까지), 다음 카드 전에 내린다
    stats = sorted((at(n, st["at"]), n, st) for n, sm in enumerate(scenes) for st in (sm.get("stats") or [])[:1]
                   if st.get("value", 0) >= STAT_MIN and _clean(st.get("label") or ""))
    counters = []
    for k, (a, n, st) in enumerate(stats):
        b = min(max(a + 4.5, E[n] + 0.5), a + 7, *[x[0] - 0.2 for x in stats[k + 1:k + 2]])
        v = st["value"]
        counters.append([f"s{n}", _clean(st["label"]), int(v) if float(v).is_integer() else v,
                         _clean(st.get("unit") or ""), a, _r(b), *STAT_POS])

    # 사진: 낱말에 떠서 3.5~6초, 다음 사진·다음 clip 장면 전에 내린다(클립보다 위 칸이라 덮는다)
    shots = sorted((at(n, ph["at"]), n, ph) for ph in plan.get("photos") or [] if (n := ph["scene"]) in (got or {}))
    photo_rows = []
    for k, (a, n, ph) in enumerate(shots):
        b = min(max(a + 3.5, E[n] + 0.3), a + 6, *[x[0] - 0.2 for x in shots[k + 1:k + 2]],
                *([S[n + 1]] if n + 1 < len(S) and kinds[n + 1] == "clip" else []))
        g = got[n]
        x, y, wd, tall = PHOTO_BOX
        photo_rows.append([f"p{n}", g["file"], _clean(ph["caption"]), a, _r(b), x, y, wd, (-2, 1.5)[k % 2],
                           round(min(tall, g["height"] / g["width"]), 3), g["width"], g["height"]])
    return {"states": states, "side": w["side"], "front": front, "cam": cam, "labels": labels, "arrows": arrows,
            "flashes": sorted(flashes), "dates": dates, "date_pos": [112, 120], "date_end": end_start,
            "night": None, "reflines": [], "ghosts": None, "map_tweens": tweens,
            "map_credit": CREDIT + (" · 전선은 대략적 위치" if front else ""), "photos": photo_rows,
            "counters": counters, "warnings": warn}

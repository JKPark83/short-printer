"""롱폼 지도 바탕: Esri 위성 타일 이어 붙이기·색 보정(ffmpeg), Natural Earth 나라 윤곽 → SVG path.

좌표는 모두 '세계 px'(줌 z의 Web Mercator, 타일 원점 x0·y0 기준)다. `fetch`가 돌려주는 tiles
{z, x0, y0, width, height}가 기준이고, 영상 구성(film)도 같은 `px`로 경도·위도를 옮긴다.
geo.json = `images(...)`({crop}) | `geo(...)`({land, border}).
"""
import concurrent.futures as cf
import http.client
import json
import math
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .. import config
from .ffmpeg import run

URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"
CACHE = config.ROOT / ".cache"   # 타일·Natural Earth를 한 번만 받는다
MAX_TILES = 2500   # 256px 원본 약 160MB. 넘으면 줌을 낮추거나 상자를 줄인다
UA = {"User-Agent": "shorts-printer"}
DARK = "0x1c1a17"   # 받지 못한(404) 타일 자리를 채우는 색
SWS = "bicubic+accurate_rnd+full_chroma_int"   # JPEG 색차를 PIL(libjpeg)에 가깝게 늘린다
TINT = (120, 104, 84)   # 색 보정 마지막에 10% 섞는 따뜻한 회색

Box = tuple[float, float, float, float]   # (서, 북, 동, 남) 경도·위도


def px(tiles: dict, lng: float, lat: float) -> tuple[float, float]:
    """경도·위도 → 세계 px(gen.py·map.py와 같은 투영)."""
    n = 2 ** tiles["z"]
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return ((lng + 180) / 360 * n - tiles["x0"]) * 256, (y - tiles["y0"]) * 256


def _range(box: Box, zoom: int) -> tuple[int, int, int, int]:
    """상자를 덮는 타일 번호 (x0, y0, x1, y1), 양끝 포함."""
    w, n, e, s = box
    if not (w < e and s < n):
        raise RuntimeError(f"지도 상자가 잘못됐어요(서<동, 남<북이어야 해요): {box}")
    world = {"z": zoom, "x0": 0, "y0": 0}
    (x0, y0), (x1, y1) = px(world, w, n), px(world, e, s)
    return int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)


def _get(url: str, timeout: int) -> bytes | None:
    """4번까지 받는다(1번 + 다시 3번). 없는 것(404)은 None."""
    req = urllib.request.Request(url, headers=UA)
    last = None
    for _ in range(4):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except (OSError, http.client.HTTPException) as e:   # 끊김·시간 초과·덜 받은 응답은 다시 시도한다
            last = e
    raise RuntimeError(f"{url}을 4번 시도했지만 받지 못했어요: {last}")


def _save(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _tile(z: int, x: int, y: int) -> Path | None:
    """타일 하나를 캐시에서, 없으면 받아서. 없는 타일(404)은 None."""
    path = CACHE / "tiles" / str(z) / str(x) / f"{y}.jpg"
    if not path.exists():
        if (data := _get(URL.format(z=z, x=x, y=y), 30)) is None:
            return None
        _save(path, data)
    return path


def fetch(box: Box, zoom: int, out: Path, log: Callable[[str], None]) -> dict:
    """상자를 덮는 Esri 타일을 받아 out/esri_raw.jpg로 잇고 tiles {z, x0, y0, width, height}를 돌려준다."""
    x0, y0, x1, y1 = _range(box, zoom)
    cols, rows = x1 - x0 + 1, y1 - y0 + 1
    if cols * rows > MAX_TILES:
        raise RuntimeError(f"지도 타일이 {cols * rows}장이라 너무 많아요(최대 {MAX_TILES}). "
                           "줌을 낮추거나 상자를 줄여 주세요")
    jobs = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]   # tile 필터가 채우는 순서(행 우선)
    out.mkdir(parents=True, exist_ok=True)
    ex = cf.ThreadPoolExecutor(8)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dark = tmp / "dark.jpg"
        got = ex.map(lambda xy: _tile(zoom, *xy), jobs)
        try:
            for i, ((x, y), path) in enumerate(zip(jobs, got, strict=True)):
                if path is None:
                    log(f"지도 타일 {zoom}/{x}/{y} 없음(404), 어둡게 채운다")
                    if not dark.exists():
                        run(["-f", "lavfi", "-i", f"color=c={DARK}:s=256x256", "-frames:v", "1", "-update", "1", dark])
                    path = dark
                (tmp / f"{i:05d}.jpg").symlink_to(path.resolve())
                if i % 200 == 0:
                    log(f"지도 타일 {i}/{len(jobs)}")
        finally:
            ex.shutdown(cancel_futures=True)   # 한 장이 끝내 실패하면 남은 타일을 기다리지 않는다
        # 타일마다 JPEG 픽셀 형식이 달라도 tile 필터가 다시 시작되지 않게 앞의 scale이 형식을 맞춘다
        part = out / "esri_raw.part.jpg"
        run(["-reinit_filter", "0", "-i", tmp / "%05d.jpg", "-sws_flags", SWS,
             "-vf", f"scale,format=rgb24,tile={cols}x{rows}", "-frames:v", "1", "-update", "1",
             "-q:v", "2", "-pix_fmt", "yuvj420p", part])
    os.replace(part, out / "esri_raw.jpg")
    tiles = {"z": zoom, "x0": x0, "y0": y0, "width": cols * 256, "height": rows * 256}
    log(f"지도 타일 {len(jobs)}장 이음 {tiles}")
    return tiles


def _mean_luma(raw: Path, vf: str) -> float:
    """PIL Contrast가 기준으로 쓰는 회색(L) 평균. 넓이 평균으로 줄여 읽어도 평균은 같다."""
    r = subprocess.run([config.FFMPEG, "-v", "error", "-i", str(raw), "-vf",
                        f"{vf},scale=trunc(iw/8):trunc(ih/8):flags=area,format=rgb24", "-f", "rawvideo", "-"],
                       capture_output=True, timeout=600)
    if r.returncode or not r.stdout:
        raise RuntimeError(f"지도 밝기를 읽지 못했어요: {r.stderr.decode()[-400:]}")
    n = len(r.stdout) // 3
    return (299 * sum(r.stdout[0::3]) + 587 * sum(r.stdout[1::3]) + 114 * sum(r.stdout[2::3])) / 1000 / n


def _grade(mean: float) -> str:
    """map.py grade()와 같은 기록 영상 색: 채도 0.4 → 밝기 0.86 → 대비 1.08 → 따뜻한 회색 10%.

    채도·밝기는 한 행렬(colorchannelmixer)로, 대비·회색 섞기는 lutrgb로 PIL 계산(단계마다 버림)을 그대로 따른다.
    행렬은 한 번 반올림하고 PIL은 두 번 버리므로 그 차이(평균 약 1)를 val-1로 맞춘다.
    """
    k, c = 0.4 * 0.86, 0.6 * 0.86   # 채도는 L(=.299R+.587G+.114B)과 섞기
    luma = (0.299, 0.587, 0.114)
    mix = ":".join(f"{o}{i}={(k if o == i else 0) + c * w:.6f}"
                   for o in "rgb" for i, w in zip("rgb", luma, strict=True))
    m = int(0.86 * mean + 0.5)   # PIL 대비 기준 = 밝기 낮춘 그림의 L 평균(채도는 L을 바꾸지 않는다)
    lut = ":".join(f"{ch}='trunc(0.9*clip(trunc({m}+1.08*(val-1-{m})),0,255)+{0.1 * t:.1f})'"
                   for ch, t in zip("rgb", TINT, strict=True))
    return f"format=rgb24,colorchannelmixer={mix},lutrgb={lut}"


def images(raw: Path, tiles: dict, detail: Box, out: Path) -> dict:
    """색 보정한 out/wide.jpg(1/4 크기)·out/detail.jpg(detail 상자, 원본 해상도)를 쓰고 {crop: [x1, y1, x2, y2]}."""
    w, n, e, s = detail
    crop = [round(v) for v in (*px(tiles, w, n), *px(tiles, e, s))]
    x1, y1, x2, y2 = crop
    if not (0 <= x1 < x2 <= tiles["width"] and 0 <= y1 < y2 <= tiles["height"]):
        raise RuntimeError(f"상세 지도 상자가 받은 타일 밖이에요: {detail}")
    out.mkdir(parents=True, exist_ok=True)
    cut = f"format=rgb24,crop={x2 - x1}:{y2 - y1}:{x1}:{y1}"   # yuv420 그대로 자르면 홀수 좌표가 짝수로 밀린다
    for name, vf, mean_vf in (("wide", "scale=trunc(iw/4):trunc(ih/4):flags=lanczos", "null"), ("detail", cut, cut)):
        part = out / f"{name}.part.jpg"   # q:v 3 ≈ PIL quality 85(파일 크기가 비슷하다)
        run(["-i", raw, "-sws_flags", SWS, "-vf", f"{vf},{_grade(_mean_luma(raw, mean_vf))}",
             "-frames:v", "1", "-update", "1", "-q:v", "3", "-pix_fmt", "yuvj420p", part])
        os.replace(part, out / f"{name}.jpg")
    return {"crop": crop}


def _cut(tiles: dict, box: Box) -> str:
    x1, y1, x2, y2 = (round(v) for v in (*px(tiles, box[0], box[1]), *px(tiles, box[2], box[3])))
    return f"format=rgb24,crop={x2 - x1}:{y2 - y1}:{x1}:{y1}"


def close(raw: Path, ctiles: dict, box: Box, base: Path, tiles: dict, out: Path) -> list[float]:
    """높은 줌 타일(ctiles)에서 box를 잘라 out/close.jpg에 쓰고, 지도(tiles) px 자리를 돌려준다.

    Esri는 줌마다 사진 출처가 달라 z15 갯벌·물이 z9보다 두 배쯤 밝다. 같은 자리 지도(base) 밝기에 맞춰야
    경계가 안 보이고 위 글자 대비도 지도와 같다.
    """
    cut, mean = _cut(ctiles, box), _mean_luma(base, _cut(tiles, box))
    k = f"{mean / max(_mean_luma(raw, cut), 1):.4f}"
    part = out / "close.part.jpg"
    run(["-i", raw, "-sws_flags", SWS, "-vf", f"{cut},colorchannelmixer=rr={k}:gg={k}:bb={k},{_grade(mean)}",
         "-frames:v", "1", "-update", "1", "-q:v", "3", "-pix_fmt", "yuvj420p", part])
    os.replace(part, out / "close.jpg")
    return [round(v, 2) for v in (*px(tiles, box[0], box[1]), *px(tiles, box[2], box[3]))]


def _countries() -> dict[str, dict]:
    """Natural Earth 10m 나라 geometry, ADM0_A3 코드별. 처음 한 번만 받는다."""
    path = CACHE / "ne_10m_admin0.geojson"
    if not path.exists():
        if (data := _get(NE_URL, 120)) is None:
            raise RuntimeError(f"Natural Earth 파일이 없어요(404): {NE_URL}")
        _save(path, data)
    return {f["properties"]["ADM0_A3"]: f["geometry"] for f in json.loads(path.read_text())["features"]}


def _polygons(geom: dict) -> list[list]:
    """Polygon·MultiPolygon → 다각형 목록(각각 [바깥 고리, 구멍…])."""
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def _area(pts: list) -> float:
    return sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1], strict=True))


def _land_ring(tiles: dict, ring: list, hole: bool) -> str:
    """고리 하나를 정수 px로 옮겨 연달아 같은 점을 뺀다.

    점마다 따로 반올림하므로 이웃 나라와 공유하는 국경이 양쪽에서 똑같이 남아 틈이 생기지 않는다.
    """
    pts = []
    for lng, lat, *_ in ring:
        p = tuple(round(v) for v in px(tiles, lng, lat))
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return ""   # 1px보다 작은 섬
    if (_area(pts) < 0) != hole:   # nonzero 채우기에서 구멍이 비도록 바깥·구멍의 감는 방향을 맞춘다
        pts.reverse()
    return "M" + "L".join(f"{x},{y}" for x, y in pts) + "Z"


def _clip(a: tuple, b: tuple, rect: Box) -> tuple | None:
    """선분 a-b를 사각형 (x1, y1, x2, y2) 안으로 자른다(Liang–Barsky). 밖이면 None."""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - rect[0]), (dx, rect[2] - ax), (-dy, ay - rect[1]), (dy, rect[3] - ay)):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
    if t0 > t1:
        return None
    return (a if t0 == 0 else (ax + t0 * dx, ay + t0 * dy)), (b if t1 == 1 else (ax + t1 * dx, ay + t1 * dy))


def _simplify(pts: list, tol: float) -> list:
    """Douglas–Peucker(반복문, 긴 국경에서도 재귀 한도에 걸리지 않게)."""
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = pts[i], pts[j]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, k = tol, None
        for m in range(i + 1, j):
            x, y = pts[m]
            d = abs(dy * (x - ax) - dx * (y - ay)) / norm if norm else math.hypot(x - ax, y - ay)
            if d > best:
                best, k = d, m
        if k is not None:
            keep.add(k)
            stack += [(i, k), (k, j)]
    return [pts[i] for i in sorted(keep)]


def _border_ring(tiles: dict, ring: list, rect: Box, tol: float) -> str:
    """고리 하나를 사각형 안 선 조각들로 잘라 단순화한다(닫지 않는 선, 상자 가장자리는 그리지 않는다)."""
    pts = [px(tiles, lng, lat) for lng, lat, *_ in ring]
    runs, cur = [], None
    for a, b in zip(pts, pts[1:], strict=False):
        seg = _clip(a, b, rect)
        if seg is None:
            cur = None
            continue
        if cur is None or cur[-1] != seg[0]:
            cur = [seg[0]]
            runs.append(cur)
        cur.append(seg[1])
    return "".join("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in _simplify(r, tol)) for r in runs)


def geo(land: list[str], border: list[str], tiles: dict, border_box: Box | None) -> dict:
    """나라 코드(ADM0_A3)로 {land, border} SVG path(세계 px)를 만든다. land는 clipPath용, border는 얇은 윤곽선.

    land는 합치지 않고 고리를 모두 한 path의 하위 경로로 둔다(nonzero 채우기로 보면 합집합과 같다).
    border는 map.py의 단순화 0.01도를 px로 옮겨 쓰고, border_box(없으면 타일 전체) 밖은 잘라 낸다.
    """
    feats = _countries()
    if missing := [c for c in (*land, *border) if c not in feats]:
        raise RuntimeError(f"Natural Earth에 없는 나라 코드예요(ADM0_A3): {', '.join(missing)}")
    land_d = "".join(_land_ring(tiles, ring, i > 0)
                     for c in land for poly in _polygons(feats[c]) for i, ring in enumerate(poly))
    if border_box:
        w, n, e, s = border_box
        rect = (*px(tiles, w, n), *px(tiles, e, s))
    else:
        rect = (0, 0, tiles["width"], tiles["height"])
    # ponytail: border도 합치지 않아 border 나라끼리 맞닿은 국경(예 CHN–RUS)까지 그린다(map.py는 지운다).
    # 지워야 하면 두 나라에 똑같이 나오는 선분을 빼면 된다
    tol = 0.01 * 256 * 2 ** tiles["z"] / 360
    border_d = "".join(_border_ring(tiles, ring, rect, tol)
                       for c in border for poly in _polygons(feats[c]) for ring in poly)
    return {"land": land_d, "border": border_d}

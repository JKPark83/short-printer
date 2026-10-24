import http.client
import json
import re
import subprocess
import urllib.error

import pytest

from shorts_printer import config
from shorts_printer.infra import maptiles


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(maptiles, "CACHE", tmp_path / "cache")
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def tile_jpg(tmp_path_factory):
    """가짜 타일: 흰 256px JPEG."""
    path = tmp_path_factory.mktemp("tile") / "white.jpg"
    subprocess.run([config.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=white:s=256x256",
                    "-frames:v", "1", "-update", "1", str(path)], check=True)
    return path.read_bytes()


def _rgb(path, w, h):
    """그림을 w×h로 넓이 평균해 [(r, g, b), …]."""
    raw = subprocess.run([config.FFMPEG, "-v", "error", "-i", str(path), "-vf",
                          f"scale={w}:{h}:flags=area,format=rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]


def _size(path):
    out = subprocess.run([config.FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    return tuple(map(int, re.search(r", (\d+)x(\d+)", out).groups()))


def _fake_urlopen(monkeypatch, tile_jpg, missing=(), fail=0):
    """urlopen 가짜. missing 타일은 404, 처음 fail번은 연결 오류. 부른 URL을 돌려준다."""
    calls = []

    def urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) <= fail:   # 두 번째는 덜 받은 응답(OSError가 아니다)
            raise http.client.IncompleteRead(b"") if len(calls) == 2 else urllib.error.URLError("끊김")
        z, y, x = map(int, req.full_url.rsplit("/", 3)[1:])
        if (x, y) in missing:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        return type("R", (), {"read": lambda self: tile_jpg})()

    monkeypatch.setattr(maptiles.urllib.request, "urlopen", urlopen)
    return calls


def test_tile_range_matches_korean_war_build():
    assert maptiles._range((116.0, 44.0, 139.5, 32.5), 9) == (420, 186, 454, 207)   # 35×22 = 770장


def test_fetch_stitches_fills_404_and_caches(cache, tmp_path, monkeypatch, tile_jpg):
    calls = _fake_urlopen(monkeypatch, tile_jpg, missing={(2, 2)})
    logs = []
    tiles = maptiles.fetch((-80, 40, 10, -10), 2, tmp_path / "out", logs.append)   # x 1..2, y 1..2
    assert tiles == {"z": 2, "x0": 1, "y0": 1, "width": 512, "height": 512}
    assert len(calls) == 4 and any("404" in s for s in logs)
    tl, tr, bl, br = _rgb(tmp_path / "out" / "esri_raw.jpg", 2, 2)
    assert min(tl + tr + bl) > 240 and max(br) < 40   # 없는 오른쪽 아래만 어둡다
    calls.clear()
    maptiles.fetch((-80, 40, 10, -10), 2, tmp_path / "out", logs.append)
    assert calls == ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/2/2/2"]


def test_fetch_caps_tiles(cache, tmp_path, monkeypatch, tile_jpg):
    calls = _fake_urlopen(monkeypatch, tile_jpg)
    with pytest.raises(RuntimeError, match="너무 많아요"):
        maptiles.fetch((-170, 80, 170, -80), 9, tmp_path / "out", print)
    assert calls == []


def test_tile_retries_then_fails(cache, monkeypatch, tile_jpg):
    calls = _fake_urlopen(monkeypatch, tile_jpg, fail=3)
    assert maptiles._tile(1, 0, 0).read_bytes() == tile_jpg and len(calls) == 4
    _fake_urlopen(monkeypatch, tile_jpg, fail=99)
    with pytest.raises(RuntimeError, match="4번"):
        maptiles._tile(1, 1, 1)


def test_images_layout(tmp_path):
    raw = tmp_path / "raw.jpg"
    subprocess.run([config.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "testsrc=s=1024x512", "-frames:v", "1",
                    "-update", "1", str(raw)], check=True)
    tiles = {"z": 2, "x0": 0, "y0": 1, "width": 1024, "height": 512}
    detail = (-45, 30, 45, -30)
    geo = maptiles.images(raw, tiles, detail, tmp_path / "map")
    x1, y1, x2, y2 = geo["crop"]
    assert (x1, x2) == (384, 640) and y1 == round(maptiles.px(tiles, 0, 30)[1])
    assert _size(tmp_path / "map" / "wide.jpg") == (256, 128)
    assert _size(tmp_path / "map" / "detail.jpg") == (x2 - x1, y2 - y1)
    with pytest.raises(RuntimeError, match="타일 밖"):
        maptiles.images(raw, tiles, (-45, 80, 45, -30), tmp_path / "map")


def test_close_matches_base_map_brightness(tmp_path):
    def solid(name, c, size):
        subprocess.run([config.FFMPEG, "-v", "error", "-f", "lavfi", "-i", f"color=c={c}:s={size}", "-frames:v", "1",
                        "-update", "1", str(tmp_path / name)], check=True)
        return tmp_path / name
    tiles = {"z": 2, "x0": 0, "y0": 1, "width": 1024, "height": 512}
    ctiles = {"z": 4, "x0": 4, "y0": 4, "width": 2048, "height": 1024}
    base, raw = solid("base.jpg", "0x404040", "1024x512"), solid("close.jpg", "0xc0c0c0", "2048x1024")
    (tmp_path / "map").mkdir()
    maptiles.close(raw, ctiles, (-40, 20, 40, -20), base, tiles, tmp_path / "map")
    want = maptiles._mean_luma(base, maptiles._grade(maptiles._mean_luma(base, "null")))   # 같은 보정을 거친 지도
    assert abs(maptiles._mean_luma(tmp_path / "map" / "close.jpg", "null") - want) < 3   # z15(0xc0) 밝기가 아니라


def _sq(w, s, e, n):
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


def _pts(d):
    return [tuple(map(int, p)) for p in re.findall(r"(-?\d+),(-?\d+)", d)]


def _area(pts):
    return sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1], strict=True))


@pytest.fixture
def countries(cache):
    outer = _sq(0, 0, 90, 60)
    outer.insert(1, [0.1, 0])   # 0.07px 옆 점: 같은 정수 px라 빠진다
    feats = {
        "AAA": {"type": "MultiPolygon", "coordinates": [[outer, _sq(30, 20, 60, 40)], [_sq(-100, 0, -99.9, 0.1)]]},
        "BBB": {"type": "Polygon", "coordinates": [_sq(0, -40, 90, 40)]},
    }
    cache.mkdir(parents=True)
    (cache / "ne_10m_admin0.geojson").write_text(json.dumps({"features": [
        {"properties": {"ADM0_A3": k}, "geometry": g} for k, g in feats.items()]}))


def test_geo_land_rings_and_clipped_border(countries):
    tiles = {"z": 0, "x0": 0, "y0": 0, "width": 256, "height": 256}
    g = maptiles.geo(["AAA"], ["BBB"], tiles, (-45, 60, 45, -60))
    rings = [_pts(r) for r in g["land"].split("M")[1:]]
    assert [len(r) for r in rings] == [4, 4]   # 겹친 점은 빠지고 1px보다 작은 섬은 없다
    assert (_area(rings[0]) > 0) != (_area(rings[1]) > 0)   # 구멍은 반대로 감겨 nonzero에서 빈다

    def p(lng, lat):
        x, y = maptiles.px(tiles, lng, lat)
        return f"{x:.0f},{y:.0f}"
    # 사각형의 왼쪽 변만 상자 안에 남고 위·아래 변은 경도 45에서 잘린다(상자 가장자리는 그리지 않는다)
    assert g["border"] == f"M{p(0, -40)}L{p(45, -40)}M{p(45, 40)}L{p(0, 40)}L{p(0, -40)}"


def test_geo_unknown_code(countries):
    with pytest.raises(RuntimeError, match="ZZZ"):
        maptiles.geo(["AAA", "ZZZ"], [], {"z": 0, "x0": 0, "y0": 0, "width": 256, "height": 256}, None)

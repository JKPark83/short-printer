import json

import pytest

from shorts_printer.core import satellite
from shorts_printer.infra import maptiles

TILES = {"z": 7, "x0": 108, "y0": 48, "width": 1536, "height": 1280}


def test_plates_round_trip_tile_px_to_degrees():
    bb = satellite.plates(TILES, {"crop": [256, 256, 512, 768]})
    assert set(bb) == {"wide", "detail"}   # close는 좁은 곳이 있을 때만
    w, s, e, n = bb["detail"]
    assert maptiles.px(TILES, w, n) == pytest.approx((256, 256))
    assert maptiles.px(TILES, e, s) == pytest.approx((512, 768))
    assert "close" in satellite.plates(TILES, {"crop": [0, 0, 1, 1], "close": [0, 0, 1, 1]})


def test_era_picks_most_dated_years_else_none():
    eras = json.loads((satellite.TEMPLATE / "realms.json").read_text())["eras"]
    assert satellite.era(eras, [[0, "670", "", ""], [9, "648", "", ""]])["years"] == [618, 700]
    assert satellite.era(eras, [[0, "1636년", "", ""]])["years"] == [1616, 1644]
    assert satellite.era(eras, [[0, "1950", "", ""]]) is None and satellite.era(eras, []) is None


def test_build_writes_page_data_and_drops_stale_close(monkeypatch, tmp_path):
    runs = []
    monkeypatch.setattr(satellite.ffmpeg, "run", runs.append)
    job, project = tmp_path / "job", tmp_path / "job" / "sat"
    for f in ("film/assets/map/wide.jpg", "film/assets/map/detail.jpg", "photos/p0.jpg", "clips/clip1.mp4"):
        (job / f).parent.mkdir(parents=True, exist_ok=True)
        (job / f).write_bytes(b"x")
    (project / "assets/plates").mkdir(parents=True)
    (project / "assets/plates/close.jpg").write_bytes(b"old")
    film = {"tiles": TILES, "geo": {"crop": [0, 0, 100, 100]}, "dates": [[0, "1950", "", ""]], "title": "A&B",
            "clips": [{"id": "c01", "src": "assets/clips/clip1.mp4"}], "photos": [["p0", "p0.jpg"]]}
    satellite.build(film, job, project)
    assert json.loads((project / "data/film.json").read_text()) == film
    assert set(json.loads((project / "data/plates.json").read_text())) == {"wide", "detail"}
    assert not (project / "assets/plates/close.jpg").exists() and (project / "assets/plates/world.jpg").exists()
    assert not (project / "data/realms.json").exists()   # 1950년은 라이브러리에 없는 시대
    assert (project / "index.html").exists() and (project / "data/land.json").exists()
    assert (project / "assets/photos/p0.jpg").exists()
    assert runs[0][1] == job / "clips/clip1.mp4" and runs[0][-1] == project / "assets/clips/c01/%04d.jpg"

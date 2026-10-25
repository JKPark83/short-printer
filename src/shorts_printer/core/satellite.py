"""롱폼 위성 지도 페이지(assets/satellite, lemo-opuscar로 렌더)에 작업 재료를 모은다.

페이지는 data/film.json(작업 film.json 그대로)·plates.json·realms.json·land.json과
assets/plates(지도 판)·assets/clips/<id>/0001.jpg(클립 프레임)·assets/photos를 읽는다.
글은 캔버스에 그리므로 HTML 이스케이프를 하지 않는다.
"""
import json
import re
import shutil
from pathlib import Path

from .. import config
from ..infra import ffmpeg, maptiles
from ..infra.store import atomic_write_text

TEMPLATE = config.ROOT / "assets" / "satellite"
CLIP_FPS = 24   # film.js clipIdx와 같다
DATA = ("realms.json", "land.json")   # 템플릿에서 페이지 옆이 아니라 data/로 가는 것


def plates(tiles: dict, geo: dict) -> dict:
    """지도 판마다 [서, 남, 동, 북](도). wide는 받은 타일 전체, detail·close는 geo의 px 자리."""
    def box(x1, y1, x2, y2):
        (w, n), (e, s) = maptiles.lnglat(tiles, x1, y1), maptiles.lnglat(tiles, x2, y2)
        return [w, s, e, n]
    out = {"wide": box(0, 0, tiles["width"], tiles["height"]), "detail": box(*geo["crop"])}
    if geo.get("close"):
        out["close"] = box(*geo["close"])
    return out


def era(eras: list[dict], dates: list) -> dict | None:
    """화면 연도가 가장 많이 든 시대. 연도가 하나도 안 들면 None(나라 영역을 칠하지 않는다)."""
    years = [int(m.group()) for d in dates if (m := re.search(r"\d+", str(d[1])))]
    best = max(eras, key=lambda e: sum(e["years"][0] <= y <= e["years"][1] for y in years), default=None)
    return best if best and any(best["years"][0] <= y <= best["years"][1] for y in years) else None


def build(film: dict, job_dir: Path, project: Path) -> None:
    """project에 페이지와 재료를 쓴다. 지도 판은 job_dir/film/assets/map, 클립은 clips/, 사진은 photos/에서 온다."""
    shutil.copytree(TEMPLATE, project, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*DATA))
    data, plate_dir = project / "data", project / "assets" / "plates"
    data.mkdir(exist_ok=True)
    bb = plates(film["tiles"], film["geo"])
    for name in ("wide", "detail", "close"):   # 지난 계획의 close가 남으면 엉뚱한 자리에 뜬다
        (plate_dir / f"{name}.jpg").unlink(missing_ok=True)
    for name in bb:
        shutil.copyfile(job_dir / "film" / "assets" / "map" / f"{name}.jpg", plate_dir / f"{name}.jpg")
    shutil.rmtree(project / "assets" / "clips", ignore_errors=True)
    for c in film["clips"]:   # 페이지는 영상을 못 돌려 세우므로 프레임 그림으로 푼다
        out = project / "assets" / "clips" / c["id"]
        out.mkdir(parents=True)
        ffmpeg.run(["-i", job_dir / c["src"].removeprefix("assets/"), "-vf", f"fps={CLIP_FPS}", "-q:v", "3",
                    out / "%04d.jpg"])
    (project / "assets" / "photos").mkdir(parents=True, exist_ok=True)
    for p in film["photos"]:
        shutil.copyfile(job_dir / "photos" / p[1], project / "assets" / "photos" / p[1])
    realms = era(json.loads((TEMPLATE / "realms.json").read_text())["eras"], film["dates"])
    (data / "realms.json").unlink(missing_ok=True)
    if realms:
        atomic_write_text(data / "realms.json", json.dumps(realms, ensure_ascii=False))
    shutil.copyfile(TEMPLATE / "land.json", data / "land.json")
    atomic_write_text(data / "plates.json", json.dumps(bb))
    atomic_write_text(data / "film.json", json.dumps(film, ensure_ascii=False))

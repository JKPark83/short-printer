"""스톡 영상 공급자(Pexels·Pixabay): 장면마다 검색어로 하나씩. download()는 다른 공급자도 쓴다.
Pexels는 2026-10부터 새 키 발급을 멈춰서 Pixabay도 쓴다. 키가 둘 다 있으면 세로 필터가 있는 Pexels가 먼저다."""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import config
from .jobs import atomic_write_json, read_json

PEXELS = "https://api.pexels.com/videos/search"
PIXABAY = "https://pixabay.com/api/videos/"
SOURCES = ("Pexels", "Pixabay")


def _open(url: str, **headers):
    # Pexels는 파이썬 기본 User-Agent를 막는다
    return urlopen(Request(url, headers={"User-Agent": "shorts-printer/0.1", **headers}), timeout=30)


def source() -> str | None:
    """키가 있는 첫 영상 소스. 없으면 None(그라데이션)."""
    return next((s for s in SOURCES if config.secret(f"{s.upper()}_API_KEY")), None)


def pick_file(video: dict) -> dict | None:
    """세로 mp4 가운데 높이가 1920에 가장 가까운 파일. 4K를 받느라 느려지지 않게 한다."""
    files = [f for f in video["video_files"]
             if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= (f.get("width") or 1)]
    return min(files, key=lambda f: abs(f["height"] - 1920), default=None)


def pick_rendition(hit: dict) -> dict | None:
    """Pixabay 크기(large~tiny) 가운데 긴 변이 1920에 가장 가까운 것. large는 빈 값으로 올 때가 있다."""
    files = [f for f in hit["videos"].values() if f.get("url")]
    return min(files, key=lambda f: abs(max(f["width"], f["height"]) - 1920), default=None)


def _pexels(term: str) -> list[dict]:
    query = urlencode({"query": term, "orientation": "portrait", "per_page": 5})
    with _open(f"{PEXELS}?{query}", Authorization=config.secret("PEXELS_API_KEY")) as r:
        videos = json.load(r)["videos"]
    return [{"id": v["id"], "link": f["link"], "width": f["width"], "height": f["height"], "url": v["url"],
             "image": v["image"], "user": v["user"]["name"], "user_url": v["user"]["url"], "duration": v["duration"]}
            for v in videos if (f := pick_file(v))]


def _pixabay(term: str) -> list[dict]:
    """약관대로 같은 검색 결과는 24시간 캐시한다."""
    params = {"q": term, "safesearch": "true", "per_page": 20}
    tag = hashlib.sha1(f"{PIXABAY}?{urlencode(sorted(params.items()))}".encode()).hexdigest()[:16]
    cache = config.JOBS_DIR / ".cache" / f"pixabay-{tag}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        hits = read_json(cache)
    else:
        with _open(f"{PIXABAY}?{urlencode({'key': config.secret('PIXABAY_API_KEY')} | params)}") as r:
            hits = json.load(r)["hits"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(cache, hits)
    found = [{"id": h["id"], "link": f["url"], "width": f["width"], "height": f["height"], "url": h["pageURL"],
              "image": f.get("thumbnail", ""), "user": h["user"],
              "user_url": f"https://pixabay.com/users/{h['user']}-{h['user_id']}/", "duration": h["duration"]}
             for h in hits if (f := pick_rendition(h))]
    # 세로 필터가 없다. 세로 영상을 앞에 두고, 가로 영상은 렌더에서 가운데만 잘라 쓴다
    return sorted(found, key=lambda c: c["width"] > c["height"])


SEARCH = {"Pexels": _pexels, "Pixabay": _pixabay}


def download(url: str, path: Path) -> None:
    """끝까지 받은 것만 path에 둔다(파일이 있으면 끝난 장면으로 본다). 남은 임시 파일은 recover()가 지운다."""
    tmp = path.with_suffix(".tmp.mp4")
    with _open(url) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh)
        if r.length:   # urllib은 중간에 끊겨도 오류 없이 끝난다. 남은 바이트가 있으면 덜 받은 것
            raise RuntimeError(f"영상을 끝까지 받지 못했어요: {url}")
    os.replace(tmp, path)


class Stock:
    label = "스톡(Pexels·Pixabay)"
    hint = "무료 · 장면마다 검색어로 찾아요 · .env에 PIXABAY_API_KEY 또는 PEXELS_API_KEY"

    def ready(self) -> bool:
        return source() is not None

    def make(self, scenes, out, log):
        # ponytail: seen은 이번 호출 안에서만 중복을 막는다. 다시 시도하면 이미 있는 장면과 같은 클립이 나올 수 있다
        src, seen = source(), set()
        for s in scenes:
            c = next((c for c in SEARCH[src](s["term"]) if c["id"] not in seen), None) if s["term"] else None
            if not c:
                log(f"{src}: 장면 {s['i'] + 1} '{s['term']}' 결과 없음 → 직접 올려 주세요")
                continue
            seen.add(c["id"])
            download(c["link"], out / s["file"])
            log(f"{src}: 장면 {s['i'] + 1} '{s['term']}' → {c['url']} ({c['width']}x{c['height']}, {c['duration']}s)")
            yield {"file": s["file"], "term": s["term"], "source": src,
                   **{k: c[k] for k in ("url", "image", "user", "user_url", "duration")}}

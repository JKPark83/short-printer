"""2단계 영상 소스: 무료 스톡 영상을 검색어마다 하나씩 받는다(MoneyPrinter의 search.py 역할).
Pexels는 2026-10부터 새 키 발급을 멈춰서 Pixabay도 쓴다. 키가 둘 다 있으면 세로 필터가 있는 Pexels가 먼저다."""
import hashlib
import json
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


def pixabay_hits(api: str, term: str, **params) -> list[dict]:
    """Pixabay 검색. 약관대로 같은 검색 결과는 24시간 캐시한다. 영상과 썸네일 사진이 같이 쓴다."""
    params = {"q": term, "safesearch": "true", "per_page": 20} | params
    tag = hashlib.sha1(f"{api}?{urlencode(sorted(params.items()))}".encode()).hexdigest()[:16]
    cache = config.JOBS_DIR / ".cache" / f"pixabay-{tag}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return read_json(cache)
    with _open(f"{api}?{urlencode({'key': config.secret('PIXABAY_API_KEY')} | params)}") as r:
        hits = json.load(r)["hits"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(cache, hits)
    return hits


def _pixabay(term: str) -> list[dict]:
    hits = pixabay_hits(PIXABAY, term)
    found = [{"id": h["id"], "link": f["url"], "width": f["width"], "height": f["height"], "url": h["pageURL"],
              "image": f.get("thumbnail", ""), "user": h["user"],
              "user_url": f"https://pixabay.com/users/{h['user']}-{h['user_id']}/", "duration": h["duration"]}
             for h in hits if (f := pick_rendition(h))]
    # 세로 필터가 없다. 세로 영상을 앞에 두고, 가로 영상은 렌더에서 가운데만 잘라 쓴다
    return sorted(found, key=lambda c: c["width"] > c["height"])


SEARCH = {"Pexels": _pexels, "Pixabay": _pixabay}


def fetch(src: str, terms: list[str], out: Path, log) -> list[dict]:
    out.mkdir(exist_ok=True)
    clips, seen = [], set()
    for term in terms:
        c = next((c for c in SEARCH[src](term) if c["id"] not in seen), None)
        if not c:
            log(f"{src}: '{term}' 결과 없음")
            continue
        seen.add(c["id"])
        path = out / f"clip{len(clips)}.mp4"
        with _open(c["link"]) as r, open(path, "wb") as fh:
            shutil.copyfileobj(r, fh)
            if r.length:   # urllib은 중간에 끊겨도 오류 없이 끝난다. 남은 바이트가 있으면 덜 받은 것
                raise RuntimeError(f"{src} 영상을 끝까지 받지 못했어요: {term}")
        clips.append({"file": path.name, "term": term, "source": src,
                      **{k: c[k] for k in ("url", "image", "user", "user_url", "duration")}})
        log(f"{src}: '{term}' → {c['url']} ({c['width']}x{c['height']}, {c['duration']}s)")
    return clips

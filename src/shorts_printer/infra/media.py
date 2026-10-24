"""받아 쓰는 미디어(음악·기록 사진) 내려받기. 음악은 한 번 받으면 .cache에 두고 다시 쓴다."""
import json
import os
import re
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import config

MUSIC_CACHE = config.ROOT / ".cache" / "music"
COMMONS = "https://commons.wikimedia.org/w/api.php?"
UA = {"User-Agent": "shorts-printer/1.0 (archival photo fetch)"}   # Commons는 UA 없는 요청을 막는다
FREE = ("public domain", "pd", "cc0")   # 출처를 안 밝혀도 되는 것만: CC BY는 작가 이름이 사진마다 따라야 한다


def fetch_music(title: str, url: str) -> Path:
    """곡을 .cache/music/<제목>.mp3로 받는다(이미 있으면 그대로). 반쯤 받은 파일이 남지 않게 tmp에 쓰고 바꾼다."""
    path = MUSIC_CACHE / (re.sub(r"[^\w.-]+", "_", title).strip("_") + ".mp3")
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".mp3.tmp")
    try:
        with urlopen(url, timeout=120) as r:
            tmp.write_bytes(r.read())
    except (OSError, HTTPException) as e:   # 끊긴 내려받기(IncompleteRead)도 여기로
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"음악을 받지 못했어요({title}): {e}") from e
    os.replace(tmp, path)
    return path


def fetch_photo(query: str, dst: Path, width: int = 1280) -> dict | None:
    """Wikimedia Commons 검색 결과 중 첫 퍼블릭 도메인 jpg를 dst에 받는다. 지도는 건너뛴다(지도는 영상이 그린다).
    검색어에 연도가 있으면 그보다 2년 넘게 뒤에 찍은 사진(기념행사 등)도 건너뛴다.
    {title, license, url, width, height} 또는 못 찾으면 None."""
    years = [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", query)]
    q = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 8,
         "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata",
         "iiurlwidth": width}
    try:
        with urlopen(Request(COMMONS + urlencode(q), headers=UA), timeout=30) as r:
            pages = json.loads(r.read()).get("query", {}).get("pages", {}).values()
        for p in sorted(pages, key=lambda p: p.get("index", 0)):
            ii = p["imageinfo"][0]
            lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            taken = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", ii.get("extmetadata", {}).get("DateTimeOriginal", {})
                              .get("value", ""))
            if (not lic.lower().startswith(FREE) or not p["title"].lower().endswith((".jpg", ".jpeg"))
                    or re.search(r"\bmaps?\b", p["title"], re.I) or years and taken and int(taken[1]) > max(years) + 2):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".tmp")
            with urlopen(Request(ii["thumburl"], headers=UA), timeout=60) as r:
                tmp.write_bytes(r.read())
            os.replace(tmp, dst)
            return {"title": p["title"], "license": lic, "url": ii["descriptionurl"],
                    "width": ii["thumbwidth"], "height": ii["thumbheight"]}
    except (OSError, HTTPException, ValueError, KeyError) as e:
        raise RuntimeError(f"사진을 받지 못했어요({query}): {e}") from e
    return None

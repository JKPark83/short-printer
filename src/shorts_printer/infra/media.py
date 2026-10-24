"""받아 쓰는 미디어(음악) 내려받기. 한 번 받은 파일은 .cache에 두고 다시 쓴다."""
import os
import re
from http.client import HTTPException
from pathlib import Path
from urllib.request import urlopen

from .. import config

MUSIC_CACHE = config.ROOT / ".cache" / "music"


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

"""ffmpeg-full 실행 래퍼."""
import subprocess
from pathlib import Path

from . import config

# 어떤 클립이든 세로 1080x1920/30fps로 맞춘다
VERTICAL_VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"


def run(args: list, cwd: Path | None = None) -> None:
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                       capture_output=True, text=True, cwd=cwd, timeout=600)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 실패({r.returncode}): {r.stderr[-800:]}")

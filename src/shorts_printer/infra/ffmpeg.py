"""ffmpeg-full 실행 래퍼."""
import subprocess
from pathlib import Path

from .. import config


def run(args: list, cwd: Path | None = None) -> None:
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                       capture_output=True, text=True, cwd=cwd, timeout=600)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 실패({r.returncode}): {r.stderr[-800:]}")


def has_audio(path: Path) -> bool:
    """소리 트랙이 있는지(Flow 클립엔 있고 스톡·시험 클립엔 없다)."""
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=60)
    return "Audio:" in r.stderr

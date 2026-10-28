"""lemo-opuscar 렌더 래퍼. 롱폼 위성 지도 페이지(index.html + window.render(t))를 그림·무음 영상으로 찍는다."""
import contextlib
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from .store import redact

ROOT = Path.home() / "lemo-opuscar"   # 페이지가 /core/lib.js를 이 아래에서 읽는다
SIZE, FPS = "1920x1080", 30
WORKERS = 6   # 한 번에 렌더 하나만 돈다(작업 큐가 하나씩)
RENDER_TIMEOUT = 2 * 3600   # 12분 영상이 6 workers로 20분쯤(초)
STILL_TIMEOUT = 600
LOG_EVERY = 30   # 렌더 진행 줄을 log로 보내는 간격(초)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def ready() -> bool:
    """node와 lemo-opuscar 렌더 스크립트가 있는지만 본다."""
    return bool(shutil.which("node")) and (ROOT / "core" / "render" / "video.mjs").exists()


def stills(project: Path, at: list[float], out: Path, prefix: str = "at-") -> list[Path]:
    """at 초마다 out/<prefix><초>.jpg(at-5.jpg, at-62.5.jpg)를 찍어 경로를 돌려준다."""
    names = [f"{t:g}" for t in at]
    r = subprocess.run(["node", "core/render/still.mjs", str(project.resolve()), *names, "--size", SIZE,
                        "--prefix", prefix, "--out", str(out.resolve())], cwd=ROOT, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=STILL_TIMEOUT)
    paths = [out / f"{prefix}{n}.jpg" for n in names]
    if r.returncode or not all(p.exists() for p in paths):
        raise RuntimeError(f"위성 지도 스틸 실패({r.returncode}): {redact((r.stderr or r.stdout)[-800:])}")
    return paths


def _kill(p: subprocess.Popen) -> None:
    """node 아래 Chrome까지 끊는다. puppeteer가 Chrome을 따로 묶음으로 띄워 killpg로는 남는다."""
    kids = {}
    for line in subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True).stdout.splitlines():
        pid, ppid = map(int, line.split())
        kids.setdefault(ppid, []).append(pid)
    todo = [p.pid]
    while todo:   # 부모부터 끊어 새 자식이 더 생기지 않게 한다
        pid = todo.pop()
        todo += kids.get(pid, [])
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def render(project: Path, out: Path, log: Callable[[str], object]) -> Path:
    """무음 mp4(h264, 화질 높아 크다)를 out에 만든다. 진행 줄은 LOG_EVERY초에 한 번만 log로 보낸다."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    p = subprocess.Popen(["node", "core/render/video.mjs", str(project.resolve()), "--fps", str(FPS),
                          "--workers", str(WORKERS), "--size", SIZE, "--out", str(tmp.resolve())], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    timer = threading.Timer(RENDER_TIMEOUT, _kill, [p])
    timer.start()
    last, tail = 0.0, deque(maxlen=20)
    with p:
        try:
            for line in p.stdout:
                if not (line := ANSI.sub("", line).strip()):
                    continue
                tail.append(line)
                if (now := time.monotonic()) - last >= LOG_EVERY:
                    log(f"렌더 {redact(line)}")
                    last = now
            code = p.wait()
            timed_out = timer.finished.is_set()
        finally:
            timer.cancel()
            if p.poll() is None:
                _kill(p)
    if timed_out:
        raise RuntimeError(f"위성 지도 렌더가 {RENDER_TIMEOUT // 3600}시간 안에 끝나지 않았어요")
    if code or not tmp.exists():
        raise RuntimeError(f"위성 지도 렌더 실패({code}): {redact(chr(10).join(tail))[-800:]}")
    os.replace(tmp, out)
    return out

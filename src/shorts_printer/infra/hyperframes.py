"""HyperFrames CLI 실행 래퍼. 롱폼 지도 영상의 check·snapshot·render·audio는 여기서만 부른다."""
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from .. import config
from .store import atomic_write_text, redact

VERSION = "0.8.188"   # korean-war-video와 같은 판. 올리면 check·snapshot JSON 모양부터 다시 본다
NPX = ["npx", "--yes", f"hyperframes@{VERSION}"]
FONT_URL = "https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/woff2/Pretendard-{}.woff2"
FONT_CACHE = config.ROOT / ".cache" / "fonts"
WEIGHTS = ("Medium", "Bold", "ExtraBold", "Black")
RENDER_TIMEOUT = 3 * 3600   # 10분 영상 렌더가 수십 분 걸린다(초)
CHECK_TIMEOUT = 1800   # check·snapshot(초). 12분 영상은 아직 재 보지 않아 넉넉히 잡는다
NODE_MAJOR = 22   # hyperframes가 요구하는 Node 주 버전
LOG_EVERY = 30   # 렌더 진행 줄을 log로 보내는 간격(초)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def ready() -> bool:
    """npx와 Node 22 이상이 있는지만 본다(네트워크 호출 없음). 시스템 Node가 낡으면 렌더에서야 멈추기 때문."""
    node = shutil.which("node")
    if not shutil.which("npx") or not node:
        return False
    try:
        out = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    m = re.match(r"v(\d+)", out.strip())
    return bool(m) and int(m.group(1)) >= NODE_MAJOR


def _run(args: list, cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        # Node는 늘 UTF-8로 쓴다. 서버 locale이 달라도 깨진 글자 때문에 죽지 않게 한다
        # ponytail: 시간을 넘기면 npx만 죽고 아래 Chrome은 남을 수 있다, 문제가 되면 Popen + _kill로 바꾼다
        return subprocess.run([*NPX, *map(str, args)], cwd=cwd, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except FileNotFoundError as e:
        raise RuntimeError("npx가 없어요. Node.js를 설치해 주세요") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"hyperframes {args[0]}가 {timeout}초 안에 끝나지 않았어요") from e


def _json(r: subprocess.CompletedProcess, what: str) -> dict:
    """stdout의 첫 `{`부터 JSON 하나를 읽는다(앞에 안내 줄이 붙을 때가 있다)."""
    try:
        return json.JSONDecoder().raw_decode(r.stdout, r.stdout.index("{"))[0]
    except ValueError as e:   # `{`가 없거나 JSON이 깨졌다
        tail = redact((r.stderr or r.stdout or "")[-800:])
        raise RuntimeError(f"hyperframes {what} 실패({r.returncode}): {tail}") from e


def _font(weight: str) -> Path:
    """Pretendard 한 굵기를 캐시에 한 번만 받는다."""
    path = FONT_CACHE / f"Pretendard-{weight}.woff2"
    if not path.exists():
        FONT_CACHE.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(Request(FONT_URL.format(weight), headers={"User-Agent": "shorts-printer/0.1"}),
                         timeout=60) as r:
                data = r.read()
        except OSError as e:
            raise RuntimeError(f"Pretendard 글꼴을 받지 못했어요: {e}") from e
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return path


def init(project: Path, title: str) -> None:
    """`hyperframes init` 없이(빠르게·오프라인) 뼈대를 만든다. 있는 파일은 건드리지 않는다."""
    for d in ("compositions", "assets/fonts"):
        (project / d).mkdir(parents=True, exist_ok=True)
    name, cli = project.name, " ".join(NPX)
    files = {
        "hyperframes.json": {
            "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
            "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
            "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
            "media": {"autoProxy": True},
            "authoringSkill": "hyperframes",
        },
        "package.json": {
            "name": name, "private": True, "type": "module",
            "scripts": {"dev": f"{cli} preview", "check": f"{cli} check", "render": f"{cli} render",
                        "publish": f"{cli} publish"},
        },
        "meta.json": {"id": name, "name": title,
                      "createdAt": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")},
    }
    for fname, data in files.items():
        if not (project / fname).exists():
            atomic_write_text(project / fname, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    for weight in WEIGHTS:
        dst = project / "assets" / "fonts" / f"Pretendard-{weight}.woff2"
        if not dst.exists():
            tmp = dst.with_suffix(".tmp")
            shutil.copyfile(_font(weight), tmp)
            os.replace(tmp, dst)


def check(project: Path) -> dict:
    """`check --json` 결과. 오류를 찾아 종료 코드가 0이 아니어도 JSON이면 그대로 돌려준다.

    모양(0.8.188): {"ok": bool, "lint"|"runtime"|"layout"|"motion"|"contrast"|"craft": {"ok", "errorCount",
    "warningCount", "infoCount", "findings": [{"code", "severity", "message", "selector", "time", "fixHint"?}]},
    "saved": {"report": 보고서 경로}, "_meta": {"version"}}
    """
    return _json(_run(["check", "--json"], project, CHECK_TIMEOUT), "check")


def snapshot(project: Path, at: list[float], out: Path) -> list[Path]:
    """at 초마다 out/at-<초>s.png(at-5s, at-62.5s)를 찍어 경로를 돌려준다. out의 다른 그림은 남긴다."""
    out.mkdir(parents=True, exist_ok=True)
    # --keep: out을 비우지 않고 시각 이름으로 쓴다. --describe false: GEMINI_API_KEY가 있어도 유료 분석을 안 부른다
    r = _run(["snapshot", "--at", ",".join(f"{t:g}" for t in at), "--no-end", "--keep", "--describe", "false",
              "--json", "-o", out.resolve()], project, CHECK_TIMEOUT)
    paths = [Path(f["path"]) for f in _json(r, "snapshot").get("frames", [])]
    if r.returncode or len(paths) != len(at) or not all(p.exists() for p in paths):
        raise RuntimeError(f"hyperframes snapshot 실패({r.returncode}): {redact((r.stderr or '')[-800:])}")
    return paths


def _kill(p: subprocess.Popen) -> None:
    """npx 아래 node·Chrome까지 끊는다. puppeteer가 Chrome을 따로 묶음으로 띄워 killpg로는 남는다."""
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
    """index.html을 `render --quality delivery`로 out(mp4)에 만든다. 진행 줄은 LOG_EVERY초에 한 번만 log로 보낸다."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")   # 다 쓴 뒤에만 out으로 바꿔 반쯤 쓴 영상이 남지 않게 한다
    try:
        p = subprocess.Popen([*NPX, "render", "--quality", "delivery", "-o", str(tmp.resolve())], cwd=project,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise RuntimeError("npx가 없어요. Node.js를 설치해 주세요") from e
    timer = threading.Timer(RENDER_TIMEOUT, _kill, [p])   # 말없이 멈춘 렌더도 끊는다
    timer.start()
    last, tail = 0.0, deque(maxlen=20)
    with p:
        try:
            for line in p.stdout:   # text 모드는 \r도 줄 끝으로 본다(진행 막대)
                if not (line := ANSI.sub("", line).strip()):
                    continue
                tail.append(line)
                if (now := time.monotonic()) - last >= LOG_EVERY:
                    log(redact(line))   # log가 던지면(작업 취소) 아래 finally가 렌더를 끊는다
                    last = now
            code = p.wait()
            timed_out = timer.finished.is_set()   # cancel 전이라 켜져 있으면 시간 초과로 끊긴 것
        finally:
            timer.cancel()
            if p.poll() is None:
                _kill(p)
    if timed_out:
        raise RuntimeError(f"hyperframes render가 {RENDER_TIMEOUT // 3600}시간 안에 끝나지 않았어요")
    if code or not tmp.exists():
        raise RuntimeError(f"hyperframes render 실패({code}): {redact(chr(10).join(tail))[-800:]}")
    os.replace(tmp, out)
    return out


def audio_report(video: Path) -> dict:
    """`audio --json`의 첫 항목: {"duration", "loudness": {"lufsIntegrated", "truePeakDb", …}, "silence", …}."""
    r = _run(["audio", video.resolve(), "--json"], video.parent)
    item = (_json(r, "audio").get("items") or [{}])[0]
    if "loudness" not in item:   # 소리가 없으면 종료 코드 0에 item["error"]만 온다
        raise RuntimeError(f"hyperframes audio 실패: {redact(str(item.get('error') or r.stderr[-800:]))}")
    return item

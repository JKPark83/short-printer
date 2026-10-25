"""ffmpeg-full 실행 래퍼."""
import re
import subprocess
from pathlib import Path

from .. import config


def run(args: list, cwd: Path | None = None, timeout: int = 600) -> None:
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                       capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 실패({r.returncode}): {r.stderr[-800:]}")


def mix(voices: list[tuple[Path, float]], sounds: list[tuple], total: float, out: Path) -> None:
    """목소리 [(파일, 시작)]와 소리 [(파일, 시작, 길이, 음량, 파일 안 시작, 페이드 인, 페이드 아웃)]를
    섞어 out(wav)에 쓴다. 필터가 수백 줄이라 명령 줄 대신 out 옆 .txt로 넘긴다."""
    ins, fl = [], []
    for path, start in voices:
        fl.append(f"[{len(ins)}:a]aresample=48000,adelay={round(start * 1000)}:all=1[a{len(ins)}]")
        ins.append(path)
    for path, start, length, vol, off, fi, fo in sounds:
        chain = f"[{len(ins)}:a]aresample=48000,atrim=start={off}:duration={length},asetpts=PTS-STARTPTS"
        chain += f",afade=t=in:d={fi}" * bool(fi) + f",afade=t=out:st={max(0, length - fo)}:d={fo}" * bool(fo)
        fl.append(chain + f",volume={vol},adelay={round(start * 1000)}:all=1[a{len(ins)}]")
        ins.append(path)
    n = len(ins)
    fl.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
              f"atrim=duration={total}[out]")
    script = out.with_suffix(".txt")
    script.write_text(";\n".join(fl))
    run([*(x for p in ins for x in ("-i", p)), "-/filter_complex", script, "-map", "[out]", "-ac", "2",
         "-c:a", "pcm_s16le", out])


def has_audio(path: Path) -> bool:
    """소리 트랙이 있는지(Flow 클립엔 있고 스톡·시험 클립엔 없다)."""
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=60)
    return "Audio:" in r.stderr


def _ffprobe() -> str:
    p = Path(config.FFMPEG).with_name("ffprobe")
    return str(p) if p.exists() else "ffprobe"


def _probe(path: Path, *args: str) -> str:
    r = subprocess.run([_ffprobe(), "-v", "error", *args, "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode or not r.stdout.strip():
        raise RuntimeError(f"ffprobe로 읽지 못했어요({path.name}): {r.stderr[-300:]}")
    return r.stdout.strip()


def duration(path: Path) -> float:
    """파일 길이(초)."""
    return float(_probe(path, "-show_entries", "format=duration"))


def size(path: Path) -> tuple[int, int]:
    """그림·영상 첫 화면의 (너비, 높이)."""
    w, h = _probe(path, "-select_streams", "v:0", "-show_entries", "stream=width,height").split(",")[:2]
    return int(w), int(h)


def _analyze(path: Path, af: str) -> str:
    """소리만 필터를 걸어 끝까지 읽고 stderr(측정 결과)를 돌려준다. -vn: 긴 영상의 화면은 풀지 않는다."""
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-nostats", "-i", str(path),
                        "-vn", "-af", af, "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 측정 실패({path.name}): {r.stderr[-500:]}")
    return r.stderr


def loudness(path: Path) -> dict:
    """ebur128 Summary의 통합 음량(LUFS)·true peak(dBTP)·LRA(LU)."""
    summary = _analyze(path, "ebur128=peak=true").rpartition("Summary:")[2]
    num = {k: float(re.search(rf"\b{k}:\s+(-?[\d.]+|-inf)", summary).group(1)) for k in ("I", "LRA", "Peak")}
    return {"lufs": num["I"], "true_peak": num["Peak"], "lra": num["LRA"]}


def silences(path: Path, noise: str = "-35dB", min_s: float = 2.0) -> list[tuple[float, float]]:
    """min_s초 넘게 noise보다 조용한 구간 [(시작, 끝)]. 끝까지 조용하면 끝은 파일 길이."""
    err = _analyze(path, f"silencedetect=n={noise}:d={min_s}")
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.e+-]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.e+-]+)", err)]
    if len(ends) < len(starts):
        ends.append(duration(path))
    return [(max(a, 0.0), b) for a, b in zip(starts, ends, strict=True)]


def text_card(src: Path, lines: list[str], font: Path, out: Path, w: int = 1280, h: int = 720) -> None:
    """src 그림을 w×h로 채워 자르고 왼쪽 아래에 lines를 굵은 흰 글씨(검은 테)로 얹어 out(jpg)에 쓴다.
    글은 textfile로 넘겨 drawtext 이스케이프를 피한다."""
    # ponytail: 글자 크기는 가장 긴 줄 글자 수로 어림(한글 폭 기준). 라틴 문자는 작게 나온다
    size = min(110, int((w - 144) / max(map(len, lines), default=1)))
    txt, part = out.with_suffix(".txt"), out.with_name(out.stem + ".part.jpg")
    txt.write_text("\n".join(lines), encoding="utf-8")
    try:
        run(["-i", src, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
             f"drawtext=fontfile='{font}':textfile='{txt}':fontsize={size}:fontcolor=white:borderw=8:"
             f"bordercolor=black:line_spacing=10:x=72:y=h-th-72", "-frames:v", 1, "-q:v", 3, part])
    finally:
        txt.unlink(missing_ok=True)
    part.replace(out)

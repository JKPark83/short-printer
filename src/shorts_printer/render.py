"""6단계 렌더: 배경(장면 클립을 문장 길이대로 잘라 잇거나 그라데이션) + 음성 + 자막 → 1080x1920 mp4(MoneyPrinter의 video.py 역할)."""
import os
import re
from pathlib import Path

from . import ffmpeg, subtitles
from .jobs import atomic_write_text

TAIL = 0.6   # 마지막 문장 뒤 여유(초)
THUMB_SEC = 0.5   # 썸네일을 영상 첫 화면(겸 훅)으로 보여 주는 길이
# 흰 굵은 글씨, 두꺼운 검은 외곽선. 강조 낱말만 노랑. 크기는 가장 긴 줄이 한 줄에 들어가게 정한다
THUMB_STYLE = "Style: Cap,Apple SD Gothic Neo,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,12,5,{align},80,80,{margin},1"
YELLOW = "&H0000E5FF&"
# 위아래 검은 띠 + 가운데 영상(560~1440). 위 띠(검색창 아래 200~530)에 훅 제목, 자막은 영상 아래쪽 안에(subtitles MarginV 520)
BOX_Y, BOX_H = 560, 880
# 어떤 클립이든(16:9 Flow, 9:16 스톡) 가운데를 잘라 영상칸 1080x880/30fps로
CLIP_VF = f"scale=1080:{BOX_H}:force_original_aspect_ratio=increase,crop=1080:{BOX_H},setsar=1,fps=30,format=yuv420p"
FRAME_VF = f"pad=1080:1920:0:{BOX_Y}:black"
TITLE_POS = (2, 1920 - BOX_Y + 30)   # 제목 아랫줄이 영상 위 30px에 오게
# (Alignment, MarginV): 쇼츠 화면의 위 검색창·아래 제목칸을 피한다. top = 위 검은 띠, 영상 제목과 같은 자리
THUMB_POS = {"top": TITLE_POS, "bottom": (2, 560)}
GRADIENT = "gradients=s=1080x1920:r=30:c0=0x0f172a:c1=0x14532d:speed=0.01:d={dur}"


def frames(starts: list[float], dur: float, n: int) -> list[int]:
    """장면별 프레임 수(30fps). 클립 수가 문장 수와 같으면 다음 문장 시작에서 끊고, 다르면(예전 작업) 같은 길이로.
    끝 시각을 누적 반올림해 오차가 쌓이지 않는다."""
    cuts = starts[1:] if n == len(starts) else [dur * i / n for i in range(1, n)]
    f = [0] + [round(c * 30) for c in cuts] + [round(dur * 30)]
    return [b - a for a, b in zip(f, f[1:])]


def render(job_dir: Path, clips: list[str], voice_sec: float, title: tuple[list[str], str] | None = None,
           starts: list[float] | None = None) -> float:
    """title=(줄들, 강조 낱말)이면 위 띠에 영상 내내 띄운다. starts는 문장 시작 시각(장면 경계)."""
    dur = round(voice_sec + TAIL, 2)
    args, chains = [], []
    if clips:
        same = bool(starts) and len(clips) == len(starts)   # 장면 클립: 짧으면 마지막 화면에서 멈춤
        for i, (c, k) in enumerate(zip(clips, frames(starts or [0], dur, len(clips)))):
            args += ([] if same else ["-stream_loop", "-1"]) + ["-i", f"clips/{c}"]   # 예전 스톡 작업은 반복
            pad = f"tpad=stop_mode=clone:stop_duration={k / 30 + 0.1:.2f}," if same else ""
            chains.append(f"[{i}:v]{CLIP_VF},{pad}trim=end_frame={k},setpts=PTS-STARTPTS[v{i}]")
        chains.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[bg]")
    else:
        args += ["-f", "lavfi", "-i", GRADIENT.format(dur=dur)]
        chains.append(f"[0:v]crop=1080:{BOX_H},format=yuv420p[bg]")
    n = len(clips) or 1
    thumb = (job_dir / "thumbnail.jpg").exists()
    if title:
        caption_ass(job_dir / "title.ass", *title, 140, *TITLE_POS)
    chains += [f"[bg]{FRAME_VF}," + ("ass=title.ass," if title else "") + "ass=subs.ass" + ("[s]" if thumb else "[v]"),
               f"[{n}:a]apad[a]"]
    extra = []
    if thumb:   # 쇼츠 피드는 맞춤 썸네일 대신 영상 장면을 쓸 때가 많아 첫 화면에도 넣는다. 음성은 그대로 0초부터
        extra = ["-i", "thumbnail.jpg"]
        chains.append(f"[s][{n + 1}:v]overlay=enable='lt(t,{THUMB_SEC})',format=yuv420p[v]")
    ffmpeg.run([*args, "-i", "voice.wav", *extra, "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
                "-t", dur, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "final.tmp.mp4"], cwd=job_dir)
    os.replace(job_dir / "final.tmp.mp4", job_dir / "final.mp4")
    ffmpeg.run(["-ss", min(1, dur / 2), "-i", "final.mp4", "-frames:v", 1, "-q:v", 3, "poster.jpg"], cwd=job_dir)
    return dur


def caption_ass(path: Path, lines: list[str], accent: str, max_size: int, align: int, margin: int) -> None:
    """굵은 흰 글씨 + 강조 낱말 노랑 ASS 한 장면. 가장 긴 줄이 화면 폭에 들어가게 크기를 줄인다."""
    # 한글 굵은 글씨는 띄어쓰기 포함 한 글자가 크기의 0.6~0.65배라, 가장 긴 줄이 900px 안팎이 되게 한다
    style = THUMB_STYLE.format(size=min(max_size, 1400 // max(map(len, lines))), align=align, margin=margin)
    text = r"\N".join(map(subtitles.escape, lines))
    if accent:
        a = subtitles.escape(accent)
        text = text.replace(a, f"{{\\c{YELLOW}}}{a}{{\\r}}", 1)
    head = re.sub(r"^Style: .*$", style, subtitles.HEADER, flags=re.M)
    atomic_write_text(path, head + f"Dialogue: 0,0:00:00.00,9:59:59.00,Cap,,0,0,0,,{text}\n")


def thumbnail(job_dir: Path, lines: list[str], accent: str, position: str, clip: str | None = None) -> str:
    """thumbnail.jpg(1080x1920). 배경은 첫 클립 장면, 없으면 단색. 영상과 같은 배치(위아래 검은 띠). 쓴 배경 종류를 돌려준다."""
    caption_ass(job_dir / "thumb.ass", lines, accent, 150, *THUMB_POS[position])
    if clip:
        # 0.5초 장면. 입력 seek는 0.5초보다 짧은 클립에서 프레임이 없어 실패하니 마지막 프레임을 늘려 둔다
        bg, kind, pre = ["-i", f"clips/{clip}"], "영상 장면", "tpad=stop_mode=clone:stop_duration=0.5,trim=start=0.5,"
    else:
        bg, kind, pre = ["-f", "lavfi", "-i", "color=c=0x0f172a:s=1080x1920"], "단색", ""
    # 피드에서 작게 봐도 눈에 띄게 대비·채도를 조금 올린다
    vf = (f"{pre}scale=1080:{BOX_H}:force_original_aspect_ratio=increase,crop=1080:{BOX_H},pad=1080:1920:0:{BOX_Y}:black,"
          "setsar=1,eq=contrast=1.08:saturation=1.2,ass=thumb.ass")
    ffmpeg.run([*bg, "-vf", vf, "-frames:v", 1, "-q:v", 3, "thumbnail.jpg"], cwd=job_dir)
    return kind

"""6단계 렌더: 배경(장면 클립을 문장 길이대로 잘라 잇거나 그라데이션) + 음성 + 자막 → 1080x1920 mp4(MoneyPrinter의 video.py 역할)."""
import os
import re
from pathlib import Path
from typing import NamedTuple

from ..infra import ffmpeg
from ..infra.store import atomic_write_text
from ..ports.splitter import Splitter
from . import subtitles
from .channel import Channel

TAIL = 0.6   # 마지막 문장 뒤 여유(초)
# 흰 굵은 글씨, 두꺼운 검은 외곽선. 강조 낱말만 채널 강조색. 크기는 가장 긴 줄이 한 줄에 들어가게 정한다
THUMB_STYLE = "Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,12,5,{align},80,80,{margin},1"
# 위아래 검은 띠 + 가운데 영상(560~1440). 위 띠(검색창 아래 200~530)에 훅 제목, 자막은 아래 띠 맨 위에(subtitles MarginV)
BOX_Y, BOX_H = 560, 880
# 어떤 클립이든(16:9 Flow, 9:16 스톡) 가운데를 잘라 영상칸 1080x{h}/30fps로
CLIP_VF = "scale=1080:{h}:force_original_aspect_ratio=increase,crop=1080:{h},setsar=1,fps=30,format=yuv420p"
FRAME_VF = "pad=1080:1920:0:{y}:black"
TITLE_POS = (2, 1920 - BOX_Y + 30)   # 제목 아랫줄이 영상 위 30px에 오게
# (Alignment, MarginV): 쇼츠 화면의 아래 제목칸을 피한다. 위(top)는 배치의 영상 제목과 같은 자리
THUMB_BOTTOM = (2, 560)


class Layout(NamedTuple):
    y: int                   # 영상칸 위 끝
    h: int                   # 영상칸 높이
    title: tuple[int, int] | None   # 제목 (Alignment, MarginV). None이면 영상에 제목을 띄우지 않는다
    sub: int                 # 자막 윗줄(위 정렬 MarginV)


# 화면 배치(channel.toml style.layout). full은 9:16 전체에 텔롭: 위아래 약 250px은 쇼츠 UI가 덮으므로
# 제목은 위 UI 바로 아래에 위 정렬(가운데보다 위), 자막은 아래 제목·채널 이름 칸 위(1385~ 한 줄)
# clean은 영상만 full에서 제목을 뺀 것: 세로 화면에서 영상이 덜 잘리게 하고, 훅 제목은 band 썸네일에만 둔다.
# 자막은 band(1465)보다 조금 아래. 더 내리면 쇼츠 아래 제목·채널 이름과 겹친다
LAYOUTS = {"band": Layout(BOX_Y, BOX_H, TITLE_POS, 1465), "full": Layout(0, 1920, (8, 280), 1385),
           "clean": Layout(0, 1920, None, 1510)}
THUMB_LAYOUT = {"clean": "band"}   # 썸네일 배치가 영상과 다른 것
GRADIENT = "gradients=s=1080x1920:r=30:c0=0x{}:c1=0x{}:speed=0.01:d={dur}"
# 목소리·장면 클립 소리(Flow가 만든 효과음) 크기는 채널 style.voice_lufs·sfx_lufs
VOICE = "loudnorm=I={}:TP=-1.5,aresample=48000,"
SFX = "loudnorm=I={}:TP=-2,aresample=48000,aformat=channel_layouts=stereo,volume=0.7,"
SILENCE = "anullsrc=r=48000:cl=stereo,"


def ass_color(hex_rgb: str) -> str:
    """#RRGGBB → ASS &H00BBGGRR&"""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H00{b}{g}{r}&".upper()


def frames(starts: list[float], dur: float, n: int) -> list[int]:
    """장면별 프레임 수(30fps). 클립 수가 문장 수와 같으면 다음 문장 시작에서 끊고, 다르면(예전 작업) 같은 길이로.
    끝 시각을 누적 반올림해 오차가 쌓이지 않는다."""
    cuts = starts[1:] if n == len(starts) else [dur * i / n for i in range(1, n)]
    f = [0] + [round(c * 30) for c in cuts] + [round(dur * 30)]
    return [b - a for a, b in zip(f, f[1:], strict=False)]


def render(job_dir: Path, clips: list[str], voice_sec: float, ch: Channel, splitter: Splitter,
           title: tuple[list[str], str] | None = None, starts: list[float] | None = None) -> float:
    """title=(줄들, 강조 낱말)이면 위(배치의 제목 자리)에 영상 내내 띄운다. starts는 문장 시작 시각(장면 경계)."""
    dur = round(voice_sec + TAIL, 2)
    lay = LAYOUTS[ch.style.layout]
    title = title if lay.title else None
    args, chains, fx = [], [], []
    if clips:
        same = bool(starts) and len(clips) == len(starts)   # 장면 클립: 짧으면 마지막 화면에서 멈춤
        for i, (c, k) in enumerate(zip(clips, frames(starts or [0], dur, len(clips)), strict=True)):
            args += ([] if same else ["-stream_loop", "-1"]) + ["-i", f"clips/{c}"]   # 예전 스톡 작업은 반복
            pad = f"tpad=stop_mode=clone:stop_duration={k / 30 + 0.1:.2f}," if same else ""
            chains.append(f"[{i}:v]{CLIP_VF.format(h=lay.h)},{pad}trim=end_frame={k},setpts=PTS-STARTPTS[v{i}]")
            if same:   # 효과음은 장면 클립만(스톡은 배경 음악일 수 있다). 소리 없는 클립 자리는 무음
                src = f"[{i}:a]{SFX.format(ch.style.sfx_lufs)}" if ffmpeg.has_audio(job_dir / "clips" / c) else SILENCE
                fx.append(f"{src}apad,atrim=end={k / 30:.3f},asetpts=PTS-STARTPTS[s{i}]")
        chains.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[bg]")
        if any(f.startswith("[") for f in fx):   # 소리 있는 클립이 하나도 없으면 목소리만
            chains += fx + ["".join(f"[s{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=0:a=1[fx]"]
        else:
            fx = []
    else:
        args += ["-f", "lavfi", "-i", GRADIENT.format(*(c[1:] for c in ch.style.background), dur=dur)]
        chains.append(f"[0:v]crop=1080:{lay.h},format=yuv420p[bg]")
    n = len(clips) or 1
    if title:
        caption_ass(job_dir / "title.ass", *title, 140, lay.title, ch, splitter)
    # 썸네일을 첫 화면에 얹지 않는다: 쇼츠 피드는 첫 1~2초 움직임으로 넘길지 정한다. 썸네일은 업로드 때 따로 붙인다
    # 효과음을 더하면 겹치는 곳이 넘칠 수 있어 리미터로 막는다
    voice = VOICE.format(ch.style.voice_lufs) if ch.style.voice_lufs else ""
    voice_a = f"[{n}:a]{voice}apad" + ("[vo];[vo][fx]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
                                       if fx else "[a]")
    chains += [f"[bg]{FRAME_VF.format(y=lay.y)}," + ("ass=title.ass," if title else "") + "ass=subs.ass[v]", voice_a]
    ffmpeg.run([*args, "-i", "voice.wav", "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
                "-t", dur, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "final.tmp.mp4"], cwd=job_dir)
    os.replace(job_dir / "final.tmp.mp4", job_dir / "final.mp4")
    ffmpeg.run(["-ss", min(1, dur / 2), "-i", "final.mp4", "-frames:v", 1, "-q:v", 3, "poster.jpg"], cwd=job_dir)
    return dur


def caption_ass(path: Path, lines: list[str], accent: str, max_size: int, pos: tuple[int, int], ch: Channel,
                splitter: Splitter) -> None:
    """굵은 흰 글씨 + 강조 낱말 강조색 ASS 한 장면. 가장 긴 줄이 화면 폭에 들어가게 크기를 줄인다."""
    # 가장 긴 줄이 868px 안팎이 되게 한다(폭은 언어마다 Splitter.width)
    size = min(max_size, int(868 / max(map(splitter.width, lines))))
    style = THUMB_STYLE.format(font=ch.font, size=size, align=pos[0], margin=pos[1])
    text = r"\N".join(map(subtitles.escape, lines))
    if accent:
        a = subtitles.escape(accent)
        text = text.replace(a, f"{{\\c{ass_color(ch.style.accent)}}}{a}{{\\r}}", 1)
    head = re.sub(r"^Style: .*$", style, subtitles.header(ch.font), flags=re.M)
    atomic_write_text(path, head + f"Dialogue: 0,0:00:00.00,9:59:59.00,Cap,,0,0,0,,{text}\n")


def thumbnail(job_dir: Path, lines: list[str], accent: str, position: str, ch: Channel, splitter: Splitter,
              clip: str | None = None) -> str:
    """thumbnail.jpg(1080x1920). 배경은 첫 클립 장면, 없으면 단색. 영상과 같은 배치(band면 위아래 검은 띠, clean은 band). 쓴 배경 종류를 돌려준다."""
    lay = LAYOUTS[THUMB_LAYOUT.get(ch.style.layout, ch.style.layout)]
    caption_ass(job_dir / "thumb.ass", lines, accent, 150, lay.title if position == "top" else THUMB_BOTTOM, ch, splitter)
    if clip:
        # 0.5초 장면. 입력 seek는 0.5초보다 짧은 클립에서 프레임이 없어 실패하니 마지막 프레임을 늘려 둔다
        bg, kind, pre = ["-i", f"clips/{clip}"], "영상 장면", "tpad=stop_mode=clone:stop_duration=0.5,trim=start=0.5,"
    else:
        bg, kind, pre = ["-f", "lavfi", "-i", f"color=c=0x{ch.style.background[0][1:]}:s=1080x1920"], "단색", ""
    # 피드에서 작게 봐도 눈에 띄게 대비·채도를 조금 올린다
    vf = (f"{pre}scale=1080:{lay.h}:force_original_aspect_ratio=increase,crop=1080:{lay.h},pad=1080:1920:0:{lay.y}:black,"
          "setsar=1,eq=contrast=1.08:saturation=1.2,ass=thumb.ass")
    ffmpeg.run([*bg, "-vf", vf, "-frames:v", 1, "-q:v", 3, "thumbnail.jpg"], cwd=job_dir)
    return kind

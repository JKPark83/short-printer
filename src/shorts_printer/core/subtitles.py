"""4단계 자막: 문장 시각을 한 줄 덩어리로 나눠 ASS로 쓴다. 끊는 자리는 언어별 Splitter가 고른다.
낱말 시각(words)이 있으면 덩어리 첫 글자의 시각에 넘기고, 없으면 글자 수에 비례해 나눈다.
자막은 영상 칸(render.BOX_Y~+BOX_H, 560~1440) 아래 검은 띠 맨 위에 윗줄을 맞춘다(위 정렬 8, MarginV 1465).
띠 아래쪽은 쇼츠·틱톡의 제목·채널 이름이 덮는다."""
from bisect import bisect_right
from itertools import accumulate
from pathlib import Path

from ..infra.store import atomic_write_text
from ..ports.splitter import Splitter


def header(font: str) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,8,90,90,1465,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _size(text: str) -> int:
    return sum(not c.isspace() for c in text)


def _word_starts(parts: list[str], words: list[dict], end: float) -> list[float]:
    """덩어리마다 첫 글자 시각. 띄어쓰기를 뺀 글자 위치로 낱말을 찾고, 낱말 가운데면
    그 낱말과 다음 낱말(없으면 문장 끝) 시각 사이를 글자 수로 나눈다. 일본어처럼 낱말 하나가 문장 전체여도 맞는다."""
    lens = [_size(w["text"]) for w in words]
    first = list(accumulate(lens, initial=0))   # first[i] = words[i] 첫 글자 위치
    out, c = [], 0
    for p in parts:
        i = min(bisect_right(first, c) - 1, len(words) - 1)
        a, b = words[i]["start"], words[i + 1]["start"] if i + 1 < len(words) else end
        out.append(a + (b - a) * min(1, (c - first[i]) / max(lens[i], 1)))
        c += _size(p)
    return out


def cues(timing: list[dict], splitter: Splitter, limit: int) -> list[dict]:
    out = []
    for s in timing:
        parts = splitter.chunks(s["text"], limit)
        if not parts:
            continue
        if words := s.get("words"):
            starts = _word_starts(parts, words, s["end"])
        else:
            total, starts = sum(map(len, parts)), [s["start"]]
            for p in parts[:-1]:
                starts.append(starts[-1] + (s["end"] - s["start"]) * len(p) / total)
        # 다음 덩어리가 나올 때까지 띄워 깜빡이지 않게 한다
        out += [{"start": round(a, 2), "end": round(b, 2), "text": p}
                for p, a, b in zip(parts, starts, starts[1:] + [s["end"]], strict=True)]
    return out


def ts(sec: float) -> str:
    """초 → H:MM:SS.cc"""
    cs = round(sec * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape(text: str) -> str:
    """libass가 {…}를 태그로, \\N·\\h를 명령으로 읽지 않게 한다."""
    return text.replace("\\", "\\⁠").replace("{", "｛").replace("}", "｝")


def write_ass(path: Path, cues: list[dict], font: str) -> None:
    lines = [f"Dialogue: 0,{ts(c['start'])},{ts(c['end'])},Cap,,0,0,0,,{escape(c['text'])}" for c in cues]
    atomic_write_text(path, header(font) + "\n".join(lines) + "\n")

"""4단계 자막: 문장 시각을 16자 이하 덩어리로 나눠 ASS로 쓴다.
낱말 시각(words)이 있으면 그 시각에 덩어리를 넘기고, 없으면 글자 수에 비례해 나눈다."""
from pathlib import Path

from .jobs import atomic_write_text

LIMIT = 16

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Apple SD Gothic Neo,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,90,90,520,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    """띄어쓰기에서 끊어 limit자 이하 덩어리로 나눈다. limit보다 긴 낱말은 그대로 한 덩어리다."""
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > limit:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return out + [cur] if cur else out


def cues(timing: list[dict], limit: int = LIMIT) -> list[dict]:
    out = []
    for s in timing:
        if words := s.get("words"):
            parts = chunks(" ".join(w["text"] for w in words), limit)
            starts, i = [], 0
            for p in parts:
                starts.append(words[i]["start"])
                i += len(p.split())
            # 다음 덩어리가 나올 때까지 띄워 깜빡이지 않게 한다
            out += [{"start": round(a, 2), "end": round(b, 2), "text": p}
                    for p, a, b in zip(parts, starts, starts[1:] + [s["end"]])]
            continue
        parts = chunks(s["text"], limit)
        total = sum(map(len, parts))
        t, span = s["start"], s["end"] - s["start"]
        for p in parts:
            d = span * len(p) / total
            out.append({"start": round(t, 2), "end": round(t + d, 2), "text": p})
            t += d
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


def write_ass(path: Path, cues: list[dict]) -> None:
    lines = [f"Dialogue: 0,{ts(c['start'])},{ts(c['end'])},Cap,,0,0,0,,{escape(c['text'])}" for c in cues]
    atomic_write_text(path, HEADER + "\n".join(lines) + "\n")

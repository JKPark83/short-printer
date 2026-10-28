"""4단계 자막: 문장 시각을 한 줄 덩어리로 나눠 ASS로 쓴다. 끊는 자리는 언어별 Splitter가 고른다.
낱말 시각(words)이 있으면 덩어리 첫 글자의 시각에 넘기고, 없으면 글자 수에 비례해 나눈다.
자막 윗줄 자리(위 정렬 8, MarginV)는 화면 배치(render.LAYOUTS)가 정해 넘긴다.
band: 영상 칸(560~1440) 아래 검은 띠 맨 위(1465). full: 전체 화면 위, 아래 UI 250px과 제목·채널 이름 칸 위(1385). clean은 band보다 조금 아래(1510).
그 아래쪽은 쇼츠·틱톡의 제목·채널 이름이 덮는다."""
import re
from bisect import bisect_right
from itertools import accumulate
from pathlib import Path

from ..infra.store import atomic_write_text
from ..ports.splitter import Splitter


def header(font: str, margin: int = 1465) -> str:   # 기본은 band 자리
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,8,90,90,{margin},1
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


# 문장 끝(마침표·물음표 뒤 띄어쓰기, 일본어는 바로 뒤). 마무리 멘트 같은 짧은 문장이 앞 문장 꼬리와 한 덩어리로 묶이지 않게 한다
SENTENCE_END = re.compile(r"(?<=[.?!])\s+|(?<=[。？！])\s*")


def _parts(text: str, splitter: Splitter, limit: int) -> list[str]:
    return [p for t in SENTENCE_END.split(text) if t.strip() for p in splitter.chunks(t, limit)]


def _bare(text: str) -> str:
    return "".join(text.split())


def _lines(text: str, splitter: Splitter, limit: int, hand: list[list[str]] | None, i: int) -> list[str]:
    """문장 i의 자막 줄. 손으로 고친 줄이 있고 글자가 문장과 같으면 그 줄, 아니면 새로 나눈다."""
    mine = hand[i] if hand and i < len(hand) else None
    return mine if mine and _bare("".join(mine)) == _bare(text) else _parts(text, splitter, limit)


def cues(timing: list[dict], splitter: Splitter, limit: int, hand: list[list[str]] | None = None) -> list[dict]:
    """hand: 문장마다 손으로 고친 자막 줄. 그 문장과 글자가 같으면 나누기 대신 그 줄로 시각을 나눈다
    (나중에 문장을 고쳐 안 맞는 예전 줄은 버린다)."""
    out = []
    for i, s in enumerate(timing):
        parts = _lines(s["text"], splitter, limit, hand, i)
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


def groups(lines: list[str], texts: list[str], splitter: Splitter, limit: int,
           hand: list[list[str]] | None = None) -> list[list[str]]:
    """손으로 고친 자막 줄을 문장마다 묶는다. 문장마다 줄 수는 지금 자막 그대로라 cues()와 같은 규칙으로 다시 센다
    (hand: 예전에 손으로 고친 줄. 그 문장은 나눈 줄 수가 아니라 고친 줄 수다)."""
    out, k = [], 0
    for i, line in enumerate(lines):
        n = len(_lines(line, splitter, limit, hand, i))
        out.append(texts[k:k + n])
        k += n
    if k != len(texts):
        raise RuntimeError("자막 줄 수가 대본과 달라요. 새로고침한 뒤 다시 고쳐 주세요")
    return out


def sentences(lines: list[str], hand: list[list[str]]) -> list[str]:
    """문장마다 묶은 자막 줄 → 문장. 글자가 그대로인 문장(줄 나눔만 옮김)은 원문을 두고, 글자가 바뀐 문장만 그 줄들을 이어
    다시 짓는다(음성은 문장으로 만들므로 고친 자막대로 다시 읽게)."""
    out = []
    for line, mine in zip(lines, hand, strict=True):
        sep = " " if " " in line else ""   # ponytail: 띄어쓰기 없는 문장(일본어)은 붙여 잇는다. 언어 규칙이 더 필요하면 Splitter에 join을
        out.append(line if _bare("".join(mine)) == _bare(line) else sep.join(mine))
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


def write_ass(path: Path, cues: list[dict], font: str, margin: int = 1465) -> None:
    lines = [f"Dialogue: 0,{ts(c['start'])},{ts(c['end'])},Cap,,0,0,0,,{escape(c['text'])}" for c in cues]
    atomic_write_text(path, header(font, margin) + "\n".join(lines) + "\n")


def write_srt(path: Path, cues: list[dict]) -> None:
    """롱폼 YouTube 자막 파일. 시각은 HH:MM:SS,mmm."""
    def t(sec: float) -> str:
        ms = round(sec * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    atomic_write_text(path, "\n".join(f"{k}\n{t(c['start'])} --> {t(c['end'])}\n{c['text']}\n"
                                      for k, c in enumerate(cues, 1)))

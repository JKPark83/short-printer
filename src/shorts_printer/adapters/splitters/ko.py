"""한국어 자막 나누기. 끊는 자리는 형태소 분석(Kiwi)으로 고른다.
조사·연결어미 뒤는 끊고, '아래 칸'·'할 수'·'찬 공기'처럼 붙어 읽히는 말은 붙인다."""
import re
from functools import cache

from kiwipiepy import Kiwi


@cache
def kiwi() -> Kiwi:
    return Kiwi()   # 처음 한 번 0.5초쯤


def _tag(tok) -> str:
    return tok.tag.split("-")[0]   # VV-R 같은 불규칙 표시는 뗀다


def _cut(prev, a, b) -> int:
    """어절 a와 b 사이를 끊는 값. 작을수록 자연스럽다. 각 어절은 Kiwi 형태소 목록."""
    t, f = _tag(a[-1]), a[-1].form
    stem = _tag(a[-2]) if len(a) > 1 else ""
    if t in ("SP", "SF", "SE", "SS", "EF"):   # 쉼표·마침표 뒤
        c = -1
    elif t == "EC":   # 먹고 / 숨으면: 절이 끝난다. 하얗게·번갈아는 뒤 동사를 꾸며 덜 끊는다
        c = 5 if f == "게" else 3 if f in ("아", "어", "여") else 1
    elif t in ("JC", "JKG"):   # 제습제와 플라스틱, 뇌의 작용
        c = 7
    elif t[0] == "J" or t == "MAJ":   # 습기가 / 아래 칸에는 / 그래서
        c = 2
    elif t == "ETM":
        if len(b) == 1 and len(b[0].form) == 1:   # 끓을 때·온 뒤
            c = 9
        elif stem in ("VA", "XSA", "XR") and a[-2].form not in ("있", "없"):   # 찬 공기, 따뜻한 공기
            c = 7
        else:   # 모이는 / 아래 칸: 동사가 꾸미는 말은 끊어도 된다
            c = 4
    elif t == "MAG":   # 꼭 닫아두세요
        c = 7
    elif t in ("NNG", "NNP") and len(a) == 1 and prev and prev[-1].tag == "ETM" and _tag(b[0])[0] not in "NS":
        c = 3   # 끓을 때 / 넣어야: 꾸밈을 받은 명사 뒤에 조사가 빠졌다
    else:   # 아래 칸, 플라스틱 수납함, 두 개: 맨 명사·관형사·숫자는 뒤 말과 한 덩어리
        c = 9
    if _tag(b[0]) in ("NNB", "VX", "XSN", "XSV", "XSA") or _tag(b[0])[0] in "JE":
        c += 9   # 할 수, 켜져 있는, 변하지 않습니다
    if b[-1].end - b[0].start == 1 and _tag(b[-1]) == "EC":
        c += 4   # 이름을 / 따: 한 글자 동사는 앞말에 붙는다
    if t in ("JKS", "JKO", "JKB") and b[-1].tag == "ETM":
        c += 3   # 습기가 / 모이는, 습기에 / 강한: 꾸미는 말에서 그 주어·목적어를 떼지 않는다(구름은 / 찬 공기는 괜찮다)
    return c


def chunks(text: str, limit: int) -> list[str]:
    """띄어쓰기에서 끊어 limit자 이하 덩어리로 나눈다. limit보다 긴 낱말은 그대로 한 덩어리다.
    덩어리 수와 끊는 자리의 어색함(_cut)을 더한 값이 가장 작게 나눈다."""
    spans = [m.span() for m in re.finditer(r"\S+", text)]
    words = [text[a:b] for a, b in spans]
    if not words:
        return []
    toks, i = [[] for _ in words], 0
    for tok in kiwi().tokenize(text):
        while i < len(spans) - 1 and tok.start >= spans[i][1]:
            i += 1
        toks[i].append(tok)
    cut = [_cut(toks[i - 1] if i else None, toks[i], toks[i + 1]) if toks[i] and toks[i + 1] else 0
           for i in range(len(words) - 1)]
    n = len(words)
    best, back = [0] + [float("inf")] * n, [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            size = len(" ".join(words[i:j]))
            if size > limit and j - i > 1:
                break
            # 덩어리 하나에 4. 짧은 덩어리는 너무 빨리 지나가 9자보다 짧은 만큼, 5자 미만이면 4 더
            v = best[i] + 4 + max(0, 9 - size) + (4 if size < 5 else 0) + (cut[j - 1] if j < n else 0)
            if v < best[j]:
                best[j], back[j] = v, i
    out, j = [], n
    while j:
        out.append(" ".join(words[back[j]:j]))
        j = back[j]
    return out[::-1]


class Korean:
    limit = 16   # 84px에서 16자가 한 줄(약 780px)

    def chunks(self, text: str, limit: int) -> list[str]:
        return chunks(text, limit)

    def width(self, text: str) -> float:
        return 0.62 * len(text)   # 한글 굵은 글씨는 띄어쓰기 포함 한 글자가 크기의 0.6~0.65배

"""띄어쓰기 언어(영어와 그 밖의 기본) 자막 나누기."""
import unicodedata

PUNCT = ",.;:!?"


def width(text: str) -> float:
    """넓은 글자(한중일) 1, 나머지 0.55."""
    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else 0.55 for c in text)


def balance(pieces: list[str], sep: str, cut: list[float], limit: int) -> list[str]:
    """pieces를 sep로 이어 limit자 이하 덩어리로 나눈다. cut[k]는 pieces[k]와 [k+1] 사이를 끊는 값(작을수록 자연스럽다).
    덩어리 수 + 짧은 덩어리 벌점 + 끊는 값이 가장 작게. limit보다 긴 조각은 그대로 한 덩어리다."""
    n, short = len(pieces), limit * 9 // 16
    best, back = [0.0] + [float("inf")] * n, [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            size = len(sep.join(pieces[i:j]))
            if size > limit and j - i > 1:
                break
            v = best[i] + 4 + max(0, short - size) + (cut[j - 1] if j < n else 0)
            if v < best[j]:
                best[j], back[j] = v, i
    out, j = [], n
    while j:
        out.append(sep.join(pieces[back[j]:j]))
        j = back[j]
    return out[::-1]


class Whitespace:
    limit = 20   # 84px 라틴 굵은 글씨 한 줄

    def chunks(self, text: str, limit: int) -> list[str]:
        words = text.split()
        return balance(words, " ", [-1 if w[-1] in PUNCT else 0 for w in words], limit)

    def width(self, text: str) -> float:
        return width(text)

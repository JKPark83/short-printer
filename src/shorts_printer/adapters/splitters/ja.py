"""일본어 자막 나누기. 띄어쓰기가 없어 문장부호·조사 뒤에서 끊는다(형태소 분석기 없이)."""
from .whitespace import balance, width

SMALL = "ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶー"
CLOSE = "」』）)】〕〉》'\"、。，．,.！？!?・…‥:;"   # 이 앞에서는 끊지 않는다
OPEN = "「『（(【〔〈《"   # 이 뒤에서는 끊지 않는다
PUNCT = "、。，．,.！？!?・…‥」』）)】〕〉》"
PARTICLES = "はがをにでともへのやねよ"
LONG_PARTICLES = ("から", "まで", "より")


def _kind(c: str) -> str:
    if "぀" <= c <= "ゟ":
        return "hira"
    if "゠" <= c <= "ヿ" and c != "・":
        return "kata"
    if "一" <= c <= "鿿" or c in "々〆":
        return "kanji"
    return "alnum" if c.isalnum() else "other"


def _cut(text: str, k: int) -> float | None:
    """text[k-1]과 text[k] 사이를 끊는 값. None이면 못 끊는다."""
    a, b = text[k - 1], text[k]
    if b in SMALL or b in CLOSE or a in OPEN or (_kind(a) == _kind(b) and _kind(a) in ("kata", "kanji", "alnum")):
        return None
    if a in PUNCT or a.isspace():
        return -1
    if text[:k].endswith(LONG_PARTICLES):
        return 2
    if a in PARTICLES and (_kind(b) != "hira" or (k > 1 and _kind(text[k - 2]) != "hira" and a in "はがをへ")):
        # 天気が / いい: 한자 뒤 は·が·を·へ는 조사. で·に는 です·静かに처럼 활용일 수 있어 뒤가 히라가나면 안 본다
        return 2
    if _kind(a) == "hira" and _kind(b) in ("kanji", "kata"):
        return 3   # 送り仮名 뒤 새 낱말
    return 9


class Japanese:
    limit = 10   # 84px에서 10자가 한 줄

    def chunks(self, text: str, limit: int) -> list[str]:
        text, pieces, cut = text.strip(), [], []
        for k, c in enumerate(text):
            v = _cut(text, k) if k else None
            if v is None and pieces:
                pieces[-1] += c
            else:
                if pieces:
                    cut.append(v)
                pieces.append(c)
        return balance(pieces, "", cut, limit)

    def width(self, text: str) -> float:
        return width(text)

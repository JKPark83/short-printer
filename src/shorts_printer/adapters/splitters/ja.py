"""일본어 자막 나누기. 띄어쓰기가 없어 문장부호·조사 뒤에서 끊는다(형태소 분석기 없이).
원칙은 자막 실무 규칙과 같다: 문절 안에서 끊지 않고, 조사·활용어미가 줄 머리에 오지 않게 한다."""
from .whitespace import balance, width

SMALL = "ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶーん"
CLOSE = "」』）)】〕〉》'\"、。，．,.！？!?・…‥:;"   # 이 앞에서는 끊지 않는다
OPEN = "「『（(【〔〈《"   # 이 뒤에서는 끊지 않는다
PUNCT = "、。，．,.！？!?・…‥」』）)】〕〉》"
PARTICLES = "はがをにでともへのや"
LONG_PARTICLES = ("から", "まで", "より", "など", "だけ", "ほど")
# 조사가 아니라 낱말의 첫 글자인 경우: 조사 뒤 글자로 가른다(です·でしょう·できる·という·として·もう·もの)
FUSED = {"で": "すしきはも", "と": "いしきこて", "も": "うのっしら"}
PAIR = "はがをにでも"   # 조사 뒤에 또 붙는 조사(のが·ので·では·にも): 사이를 가르지 않는다


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
    ka, kb = _kind(a), _kind(b)
    if b in SMALL or b in CLOSE or a in OPEN or (ka == kb and ka in ("kata", "kanji", "alnum")):
        return None
    if a in PUNCT or a.isspace():
        return -1
    if ka == "alnum" and b not in PUNCT:
        return None   # 220ボルト·43分·6号線: 숫자와 단위를 가르지 않는다
    if ka != "hira" and kb == "hira":
        return None   # 寒い·行き·ソンスは: 送り仮名·조사는 앞 낱말에 붙인다
    if kb == "kanji" and (a in "おご" or text[k - 2:k] == "もう"
                          or (k > 1 and _kind(text[k - 2]) in ("kanji", "alnum") and a not in PARTICLES)):
        return None   # お店·ご飯, もう一度, 飲み物·乗り場·引き出し, 10か所·3つ目
    if kb == "hira" and (b in PAIR and a in PARTICLES or text[k - 2:k] in ("この", "その", "あの", "どの")):
        return None   # ので·では, そのまま
    if text[:k].endswith(LONG_PARTICLES):
        return 1
    if a in PARTICLES and kb != "hira":
        return 2
    if ka == "hira" and kb != "hira":
        return 3   # 送り仮名 뒤 새 낱말
    if ka != "hira" or kb != "hira":
        return 9
    if a in PARTICLES and b not in FUSED.get(a, ""):
        # ことは·駅で처럼 조사가 분명하면 끊고, なしで·あっても처럼 히라가나 사이면 넘칠 때만.
        # と·や는 히라가나 사이면 まとめて·わかりやすく처럼 낱말 속일 때가 많아 조사로 안 본다
        if a in "はがを" or _kind(text[k - 2]) in ("kanji", "kata", "alnum"):
            return 2
        if a in "にでもへの":
            return 12
    if a == "て":
        return 8   # 持ってきて / ください: て형 뒤
    return 30   # 활용 중간(わかりや/すく): 한 줄이 크게 넘칠 때만


class Japanese:
    limit = 10   # 84px에서 10자가 한 줄

    def chunks(self, text: str, limit: int) -> list[str]:
        # ponytail: 못 끊는 조각(긴 가타카나+조사)이 limit을 넘으면 한 줄이 넘친다. 형태소 분석기(budoux)로 바꾸면 해결
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

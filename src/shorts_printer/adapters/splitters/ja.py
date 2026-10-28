"""일본어 자막 나누기. 띄어쓰기가 없어 형태소 분석기(fugashi + unidic-lite)로 낱말 경계를 찾고 그 경계에서만 끊는다.
원칙은 자막 실무 규칙과 같다: 문절 안에서 끊지 않고, 조사·조동사·접미사가 줄 머리에 오지 않게 한다."""
from functools import cache

import fugashi

from .whitespace import balance, width

ATTACH = ("助詞", "助動詞", "接尾辞")   # 앞 낱말에 붙는다: 줄 머리에 오지 않는다
OPEN = "「『（(【〔〈《"   # 이 뒤에서는 끊지 않는다
LONG_PARTICLES = ("から", "まで", "より", "など", "だけ", "ほど", "くらい", "ぐらい")
FORMAL = ("とき", "ため", "よう", "こと", "もの", "ほう", "まま")   # の 뒤에 붙어 한 덩어리(医療トラブルのとき)
DO = ("為る", "出来る")   # 注意する·相談できる: サ変 명사와 가르지 않는다


@cache
def _tagger() -> fugashi.Tagger:
    return fugashi.Tagger()   # 사전을 읽는 데 잠깐 걸려 처음 쓸 때 한 번만 연다


def _cut(p, n) -> float | None:
    """낱말 p와 n 사이를 끊는 값(작을수록 자연스럽다). None이면 못 끊는다."""
    a, b = p.feature, n.feature
    if b.pos1 in ATTACH or b.pos1 == "補助記号" and n.surface not in OPEN or p.surface in OPEN:
        return None   # 保険/が, 勘違いしや/すい는 아예 경계가 아니다
    if a.pos1 in ("接頭辞", "連体詞") or a.pos2 == "数詞" and (b.pos2 == "数詞" or b.pos3 == "助数詞可能"):
        return None   # お/金, その/保険, 4千/ウォン
    if a.pos3 == "サ変可能" and b.lemma in DO or p.surface == "の" and n.surface in FORMAL:
        return None   # 注意/したい, の/とき
    if a.pos2 == "接続助詞" and b.pos2 == "非自立可能" and b.lemma != "下さる":
        return None   # 切れて/いる·つないで/もらう (チェックして/ください는 가른다)
    if b.lemma == "無い" and b.pos2 == "非自立可能" or b.lemma == "無し":
        return None   # では/なく, 手数料/なし
    if a.pos1 == b.pos1 == "動詞" and b.pos2 == "非自立可能":
        return None   # 복합동사: 使い/きれる·食べ/すぎる
    if a.pos1 == "補助記号" or n.white_space:
        return -1
    if p.surface in LONG_PARTICLES:
        return 1
    if a.pos1 == "助詞":
        return 2
    if a.pos1 == "名詞" and b.pos1 == "名詞":
        return 35   # 복합명사(医療/紛争): 두 자 넘치는 것(32)보다 비싸게. 12자까지는 화면 안에 든다
    if a.pos1 in ("動詞", "助動詞", "形容詞") and n.surface in FORMAL:
        return 12   # 꾸미는 말과 형식명사(言われた/こと·おいしい/もの)는 되도록 같은 줄에
    if a.pos1 == "副詞":
        return 9   # 부사는 꾸미는 말과 같은 줄에(もう/一度)
    return 3


class Japanese:
    limit = 10   # 84px에서 10자가 한 줄

    def chunks(self, text: str, limit: int) -> list[str]:
        # ponytail: 못 끊는 덩어리(긴 복합명사+조사)가 limit을 넘으면 한 줄이 넘친다. 문장을 고쳐 쓰는 수밖에 없다
        words, pieces, cut = list(_tagger()(text.strip())), [], []
        for i, w in enumerate(words):
            v = _cut(words[i - 1], w) if i else None
            if v is None and pieces:
                pieces[-1] += w.white_space + w.surface
            else:
                if pieces:
                    pieces[-1] += w.white_space   # 띄어쓰기는 앞 줄 끝에 붙여 줄 머리가 비지 않게
                    cut.append(v)
                pieces.append(w.surface)
        return balance(pieces, "", cut, limit)

    def width(self, text: str) -> float:
        return width(text)

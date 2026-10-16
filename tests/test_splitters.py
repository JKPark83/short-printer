from shorts_printer.adapters.splitters.ja import Japanese
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.adapters.splitters.whitespace import Whitespace
from shorts_printer.core.subtitles import cues

KO, JA, EN = Korean(), Japanese(), Whitespace()


def ko(text, limit=16):
    return KO.chunks(text, limit)


def test_ko_split_on_spaces_within_limit():
    assert ko("커피는 원래 에티오피아에서 처음 발견됐어요.", 16) == ["커피는 원래 에티오피아에서", "처음 발견됐어요."]
    assert ko("아주아주아주아주아주아주긴낱말하나", 5) == ["아주아주아주아주아주아주긴낱말하나"]
    assert ko("  ") == []


def test_ko_keep_korean_phrases_together():
    # 예전엔 '아래 / 칸에는', '끓을 / 때', '먹을 수 / 있다는'처럼 붙어 읽히는 말을 갈랐다
    assert ko("둘째, 습기가 모이는 아래 칸에는 제습제와 플라스틱 수납함처럼 습기에 강한 물건을 두세요.") == [
        "둘째, 습기가 모이는", "아래 칸에는", "제습제와 플라스틱 수납함처럼", "습기에 강한 물건을 두세요."]
    assert ko("면은 물이 팔팔 끓을 때 넣어야 더 쫄깃해집니다.") == ["면은 물이 팔팔 끓을 때", "넣어야 더 쫄깃해집니다."]
    assert ko("외출할 때 보일러를 끄면 난방비가 더 나올 수 있다는 사실, 아셨나요?") == [
        "외출할 때 보일러를 끄면", "난방비가 더 나올 수 있다는", "사실, 아셨나요?"]
    # 끝에 짧은 덩어리를 남기지 않는다(예전: '당겨 눈꼬리에 주름이 / 잡힙니다.')
    assert ko("진짜 웃음은 눈 주변 근육까지 당겨 눈꼬리에 주름이 잡힙니다.") == [
        "진짜 웃음은 눈 주변 근육까지", "당겨 눈꼬리에", "주름이 잡힙니다."]
    assert ko("이걸 처음 밝힌 프랑스 의사 이름을 따 뒤센 미소라고 부릅니다.") == [
        "이걸 처음 밝힌", "프랑스 의사 이름을 따", "뒤센 미소라고 부릅니다."]


def test_en_balanced_chunks_on_spaces():
    assert EN.chunks("If you freeze bread, it stays fresh for weeks longer.", 20) == [
        "If you freeze bread,", "it stays fresh for", "weeks longer."]   # 쉼표 뒤에서 끊는다
    text = "Coffee was first discovered in Ethiopia, according to a popular legend."
    out = EN.chunks(text, 20)
    assert " ".join(out) == text and all(len(c) <= 20 for c in out)
    assert EN.chunks("supercalifragilisticexpialidocious word", 20) == ["supercalifragilisticexpialidocious", "word"]
    assert EN.chunks("  ", 20) == []


def test_ja_breaks_after_punctuation_and_particles():
    assert JA.chunks("今日は天気がいいですね。散歩に行きましょう。", 10) == [
        "今日は天気が", "いいですね。", "散歩に行きましょう。"]
    assert JA.chunks("コーヒーは元々エチオピアで最初に発見されました。", 10) == [
        "コーヒーは元々", "エチオピアで最初に", "発見されました。"]
    for text in ["ペットボトルの水を冷蔵庫に入れると、意外と長持ちしません。",
                 "「ありがとう」と言われると嬉しいですよね！",
                 "45cmのタワーは1173年に建てられた。", "AI は 本当に便利です"]:
        out = JA.chunks(text, 10)
        assert "".join(out) == text and all(len(c) <= 10 for c in out)
        # 가타카나·한자·숫자 덩어리 안, 작은 가나·ー·닫는 괄호 앞에서 끊지 않는다
        for a, b in zip(out, out[1:], strict=False):
            assert not (a[-1] + b[0]).isascii() or not (a[-1] + b[0]).isalnum()
            assert b[0] not in "ーっゃゅょッャュョ」』、。" and a[-1] not in "「『"
    # 낱말·활용 속(飲み物·ありませんか·わかりやすく·ください), 숫자+단위, お+한자, 조사 짝(ので), 지시어(その)
    # 안에서 끊지 않는다
    assert JA.chunks("韓国のコンビニで飲み物をレジに出したら、店員さんに言われたことはありませんか。", 10) == [
        "韓国のコンビニで", "飲み物をレジに", "出したら、店員さんに", "言われたことは", "ありませんか。"]
    assert JA.chunks("きょうは3つにまとめてわかりやすく紹介します。", 10) == [
        "きょうは3つに", "まとめてわかりやすく", "紹介します。"]
    assert JA.chunks("変換プラグを付けても、220ボルトは100ボルトになりません。", 10) == [
        "変換プラグを", "付けても、", "220ボルトは", "100ボルトに", "なりません。"]
    assert JA.chunks("お得なのでそのまま持ってきてください。", 10) == ["お得なのでそのまま", "持ってきてください。"]
    # 세는 말(10か所·3つ目)과 もう一度는 한 덩어리(예전: '10か / 所以上', 'もう / 一度')
    assert JA.chunks("出口が10か所以上あることも多く、", 10) == ["出口が", "10か所以上あることも", "多く、"]
    assert JA.chunks("出発前にもう一度チェックしてください。", 10) == ["出発前にもう一度", "チェックして", "ください。"]
    # 끊을 데 없으면 한 덩어리
    assert JA.chunks("エチオピアエチオピアエチオピア", 5) == ["エチオピアエチオピアエチオピア"]
    assert JA.chunks(" ", 10) == []


def test_width_wide_vs_latin():
    assert KO.width("커피 한 잔") == 0.62 * 6   # 예전 썸네일 크기 1400 // 글자 수와 같다
    assert all(int(868 / KO.width("가" * n)) == 1400 // n for n in range(1, 40))
    assert JA.width("今日はabc") == 3 + 3 * 0.55 and EN.width("Hello") == 5 * 0.55


def test_cues_map_chunks_to_word_times_by_char_offset():
    # 일본어: TTS 낱말(띄어쓰기 단위)이 문장 전체 하나. 덩어리 시각은 글자 위치로 나눈다
    text = "今日は天気がいいですね。散歩に行きましょう。"
    out = cues([{"text": text, "start": 0.0, "end": 4.4, "words": [{"text": text, "start": 0.2}]}], JA, 10)
    assert [c["text"] for c in out] == ["今日は天気が", "いいですね。", "散歩に行きましょう。"]
    assert [c["start"] for c in out] == [0.2, round(0.2 + 4.2 * 6 / 22, 2), round(0.2 + 4.2 * 12 / 22, 2)]
    assert out[-1]["end"] == 4.4 and out[0]["end"] == out[1]["start"]
    # 영어: 덩어리가 낱말 경계에서 시작하면 그 낱말 시각
    ws = [{"text": w, "start": i * 0.5} for i, w in enumerate("Did you know that honey never spoils?".split())]
    out = cues([{"text": "Did you know that honey never spoils?", "start": 0, "end": 4, "words": ws}], EN, 20)
    assert [(c["text"], c["start"], c["end"]) for c in out] == [
        ("Did you know that", 0, 2.0), ("honey never spoils?", 2.0, 4)]
    # 한국어: 예전(낱말 수로 센 것)과 같다
    ws = [{"text": "가나다", "start": 1.0}, {"text": "라마", "start": 2.0}, {"text": "바사아자차카", "start": 2.5}]
    out = cues([{"text": "가나다 라마 바사아자차카", "start": 1.0, "end": 4.0, "words": ws}], KO, 6)
    assert [(c["text"], c["start"]) for c in out] == [("가나다 라마", 1.0), ("바사아자차카", 2.5)]

from shorts_printer.subtitles import chunks, cues, escape, ts
from shorts_printer.voice import words


def test_chunks_split_on_spaces_within_limit():
    assert chunks("커피는 원래 에티오피아에서 처음 발견됐어요.", 16) == ["커피는 원래 에티오피아에서", "처음 발견됐어요."]
    assert chunks("아주아주아주아주아주아주긴낱말하나", 5) == ["아주아주아주아주아주아주긴낱말하나"]
    assert chunks("  ") == []


def test_chunks_keep_korean_phrases_together():
    # 예전엔 '아래 / 칸에는', '끓을 / 때', '먹을 수 / 있다는'처럼 붙어 읽히는 말을 갈랐다
    assert chunks("둘째, 습기가 모이는 아래 칸에는 제습제와 플라스틱 수납함처럼 습기에 강한 물건을 두세요.") == [
        "둘째, 습기가 모이는", "아래 칸에는", "제습제와 플라스틱 수납함처럼", "습기에 강한 물건을 두세요."]
    assert chunks("면은 물이 팔팔 끓을 때 넣어야 더 쫄깃해집니다.") == ["면은 물이 팔팔 끓을 때", "넣어야 더 쫄깃해집니다."]
    assert chunks("외출할 때 보일러를 끄면 난방비가 더 나올 수 있다는 사실, 아셨나요?") == [
        "외출할 때 보일러를 끄면", "난방비가 더 나올 수 있다는", "사실, 아셨나요?"]
    # 끝에 짧은 덩어리를 남기지 않는다(예전: '당겨 눈꼬리에 주름이 / 잡힙니다.')
    assert chunks("진짜 웃음은 눈 주변 근육까지 당겨 눈꼬리에 주름이 잡힙니다.") == [
        "진짜 웃음은 눈 주변 근육까지", "당겨 눈꼬리에", "주름이 잡힙니다."]
    assert chunks("이걸 처음 밝힌 프랑스 의사 이름을 따 뒤센 미소라고 부릅니다.") == [
        "이걸 처음 밝힌", "프랑스 의사 이름을 따", "뒤센 미소라고 부릅니다."]


def test_cues_split_sentence_time_by_length_and_stay_inside():
    out = cues([{"text": "가나다 라마바사아자차카", "start": 1.0, "end": 4.0}], limit=5)
    assert [c["text"] for c in out] == ["가나다", "라마바사아자차카"]
    assert out[0]["start"] == 1.0 and out[-1]["end"] == 4.0
    assert out[0]["end"] == out[1]["start"] == round(1.0 + 3.0 * 3 / 11, 2)


def test_ts_and_escape():
    assert ts(61.25) == "0:01:01.25"
    assert ts(3725.5) == "1:02:05.50"
    assert "{" not in escape("{\\b1}굵게") and "\\N" not in escape("줄\\N바꿈")


def test_words_group_chars_and_cues_follow_word_times():
    ws = words(list("가나다 라마바사아자차카"), [1.0, 1.1, 1.2, 1.3, 2.5, 2.6, 2.7, 2.8, 2.9, 3.0, 3.1, 3.2])
    assert ws == [{"text": "가나다", "start": 1.0}, {"text": "라마바사아자차카", "start": 2.5}]
    out = cues([{"text": "가나다 라마바사아자차카", "start": 1.0, "end": 4.0, "words": ws}], limit=5)
    assert [(c["text"], c["start"], c["end"]) for c in out] == [("가나다", 1.0, 2.5), ("라마바사아자차카", 2.5, 4.0)]

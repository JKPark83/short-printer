from shorts_printer.subtitles import chunks, cues, escape, ts
from shorts_printer.voice import words


def test_chunks_split_on_spaces_within_limit():
    assert chunks("커피는 원래 에티오피아에서 처음 발견됐어요.", 16) == ["커피는 원래 에티오피아에서", "처음 발견됐어요."]
    assert chunks("아주아주아주아주아주아주긴낱말하나", 5) == ["아주아주아주아주아주아주긴낱말하나"]
    assert chunks("  ") == []


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

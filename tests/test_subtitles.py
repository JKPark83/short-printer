from shorts_printer.adapters.elevenlabs import words
from shorts_printer.adapters.splitters.ja import Japanese
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.core.subtitles import cues, escape, header, ts, write_ass, write_srt

KO = Korean()


def test_cues_split_sentence_time_by_length_and_stay_inside():
    out = cues([{"text": "가나다 라마바사아자차카", "start": 1.0, "end": 4.0}], KO, 5)
    assert [c["text"] for c in out] == ["가나다", "라마바사아자차카"]
    assert out[0]["start"] == 1.0 and out[-1]["end"] == 4.0
    assert out[0]["end"] == out[1]["start"] == round(1.0 + 3.0 * 3 / 11, 2)


def test_cues_always_break_at_sentence_end():
    out = cues([{"text": "고개를 든 겁니다. 오늘도 상식 하나 챙기셨네요?", "start": 0, "end": 4.0}], KO, 16)
    assert out[-1]["text"] == "오늘도 상식 하나 챙기셨네요?" and out[0]["start"] == 0 and out[-1]["end"] == 4.0
    assert [c["text"] for c in cues([{"text": "3.5배 커요", "start": 0, "end": 1}], KO, 16)] == ["3.5배 커요"]


def test_cues_keep_hand_line_breaks():
    t = [{"text": "가나다 라마바사아자차카", "start": 1.0, "end": 4.0}]
    out = cues(t, KO, 5, [["가나다 라마", "바사아자차카"]])
    assert [c["text"] for c in out] == ["가나다 라마", "바사아자차카"] and out[-1]["end"] == 4.0
    # 문장을 고쳐 글자가 안 맞는 예전 줄은 버리고 다시 나눈다
    assert [c["text"] for c in cues(t, KO, 5, [["가나다", "라마"]])] == ["가나다", "라마바사아자차카"]
    assert out[1]["start"] == 2.5   # 줄 길이 비율(6:6)대로


def test_ts_and_escape():
    assert ts(61.25) == "0:01:01.25"
    assert ts(3725.5) == "1:02:05.50"
    assert "{" not in escape("{\\b1}굵게") and "\\N" not in escape("줄\\N바꿈")


def test_words_group_chars_and_cues_follow_word_times():
    ws = words(list("가나다 라마바사아자차카"), [1.0, 1.1, 1.2, 1.3, 2.5, 2.6, 2.7, 2.8, 2.9, 3.0, 3.1, 3.2])
    assert ws == [{"text": "가나다", "start": 1.0}, {"text": "라마바사아자차카", "start": 2.5}]
    out = cues([{"text": "가나다 라마바사아자차카", "start": 1.0, "end": 4.0, "words": ws}], KO, 5)
    assert [(c["text"], c["start"], c["end"]) for c in out] == [("가나다", 1.0, 2.5), ("라마바사아자차카", 2.5, 4.0)]


def test_japanese_words_keep_char_times_so_cues_follow_pause():
    text = "両替は空港より、ミョンドンがお得です。"
    starts = [0.1 * i for i in range(8)] + [1.5 + 0.1 * i for i in range(len(text) - 8)]   # 、 뒤 0.8초 쉼
    ws = words(list(text), starts)
    assert len(ws) == len(text)
    out = cues([{"text": text, "start": 0, "end": 3.0, "words": ws}], Japanese(), 10)
    assert [(c["text"], c["start"]) for c in out][:2] == [("両替は空港より、", 0), ("ミョンドンが", 1.5)]


def test_header_and_ass_use_channel_font(tmp_path):
    assert "Style: Cap,Hiragino Sans,84," in header("Hiragino Sans") and ",8,90,90,1465,1" in header("x")
    write_ass(tmp_path / "s.ass", [{"start": 0, "end": 1.5, "text": "안녕"}], "Apple SD Gothic Neo")
    ass = (tmp_path / "s.ass").read_text()
    assert "Style: Cap,Apple SD Gothic Neo,84," in ass and "Dialogue: 0,0:00:00.00,0:00:01.50,Cap,,0,0,0,,안녕" in ass


def test_write_srt_numbers_cues_with_millisecond_times(tmp_path):
    write_srt(tmp_path / "c.srt", [{"start": 1.4, "end": 3.25, "text": "가"},
                                   {"start": 3661.0, "end": 3662.0005, "text": "나"}])
    assert (tmp_path / "c.srt").read_text() == ("1\n00:00:01,400 --> 00:00:03,250\n가\n\n"
                                                "2\n01:01:01,000 --> 01:01:02,000\n나\n")

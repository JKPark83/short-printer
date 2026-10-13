"""ffmpeg로 실제 파일을 만든다. ffmpeg-full이 없으면 건너뛴다(네트워크는 안 쓴다)."""
from pathlib import Path

import pytest

from shorts_printer import config, ffmpeg, render, subtitles, voice
from shorts_printer.jobs import read_json

pytestmark = pytest.mark.skipif(not Path(config.FFMPEG).exists(), reason="ffmpeg-full 없음")


def fake_speak(text, out):
    path = out.with_suffix(".mp3")
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", path])
    return path, None


def test_voice_joins_sentences_with_gap_and_falls_back(tmp_path, monkeypatch):
    def broken(_voice):
        def speak(text, out):
            raise ConnectionError("403")
        return speak

    monkeypatch.setattr(voice, "_edge", broken)
    monkeypatch.setattr(voice, "_say", fake_speak)
    assert voice.synth(["하나", "둘"], "ko-KR-SunHiNeural", tmp_path, lambda m: None) == "macOS say"
    t = read_json(tmp_path / "timing.json")
    assert t[0]["start"] == 0 and t[0]["end"] == pytest.approx(0.5, abs=0.06)
    assert t[1]["start"] == pytest.approx(t[0]["end"] + voice.GAP, abs=0.01)
    assert (tmp_path / "voice.wav").exists()


def test_render_gradient_with_subtitles(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "_edge", lambda _v: fake_speak)
    voice.synth(["커피 한 잔"], "ko-KR-SunHiNeural", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing))
    dur = render.render(tmp_path, [], timing[-1]["end"])
    assert dur == pytest.approx(timing[-1]["end"] + render.TAIL)
    assert (tmp_path / "final.mp4").stat().st_size > 1000 and (tmp_path / "poster.jpg").exists()
    assert not (tmp_path / "final.tmp.mp4").exists()
    assert render.thumbnail(tmp_path, ["커피 {상식}", "모르면 손해"], "손해", "bottom") == "단색"
    ass = (tmp_path / "thumb.ass").read_text()
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 1000 and "커피 ｛상식｝\\N모르면 {\\c&H0000E5FF&}손해{\\r}" in ass
    assert ",2,80,80,560," in ass   # 아래쪽, 쇼츠 제목칸 위
    render.render(tmp_path, [], timing[-1]["end"], (["커피 상식"], "상식"))
    assert "{\\c" in (tmp_path / "title.ass").read_text() and ",2,80,80,1390," in (tmp_path / "title.ass").read_text()
    render.render(tmp_path, [], timing[-1]["end"])   # 썸네일이 있으면 첫 0.5초에 얹는다
    assert (tmp_path / "final.mp4").stat().st_size > 1000


def test_elevenlabs_word_times_shift_by_sentence_start_and_fall_back(tmp_path, monkeypatch):
    def eleven(_id):
        def speak(text, out):
            return fake_speak(text, out)[0], [{"text": text, "start": 0.1}]
        return speak

    monkeypatch.setattr(voice, "_eleven", eleven)
    assert voice.synth(["하나", "둘"], "elevenlabs", tmp_path, lambda m: None) == "ElevenLabs"
    t = read_json(tmp_path / "timing.json")
    assert t[1]["words"] == [{"text": "둘", "start": pytest.approx(t[1]["start"] + 0.1, abs=0.002)}]

    def broken(_id):
        def speak(text, out):
            raise RuntimeError("ElevenLabs 401")
        return speak

    monkeypatch.setattr(voice, "_eleven", broken)
    monkeypatch.setattr(voice, "_edge", lambda v: fake_speak if v == voice.EDGE_DEFAULT else None)
    assert voice.synth(["하나"], "elevenlabs", tmp_path, lambda m: None) == "edge-tts"
    assert "words" not in read_json(tmp_path / "timing.json")[0]

"""ffmpeg로 실제 파일을 만든다. ffmpeg-full이 없으면 건너뛴다(네트워크는 안 쓴다)."""
import base64
import io
import json
import re
import subprocess
from pathlib import Path

import pytest

from shorts_printer import config, ffmpeg, render, subtitles, voice
from shorts_printer.jobs import read_json

pytestmark = pytest.mark.skipif(not Path(config.FFMPEG).exists(), reason="ffmpeg-full 없음")


class Fake:
    def __init__(self, label, speak, voices=()):
        self.label, self.hint, self.voices, self._speak, self.calls = label, "", dict.fromkeys(voices, ""), speak, []

    def ready(self):
        return True

    def speak(self, v, text, out):
        self.calls.append(v)
        return self._speak(text, out)


def fake_speak(text, out):
    path = out.with_suffix(".wav")   # .pcm.wav 중간 파일과 안 겹치는지도 본다
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", path])
    return path, None


def test_voice_joins_sentences_with_gap_and_falls_back(tmp_path, monkeypatch):
    def broken(text, out):
        raise ConnectionError("403")

    edge = Fake("edge-tts", broken, voice.Edge.voices)
    monkeypatch.setitem(voice.TTS, "edge", edge)
    monkeypatch.setitem(voice.TTS, "say", Fake("macOS say", fake_speak, ["Yuna"]))
    assert voice.synth(["하나", "둘"], "ko-KR-SunHiNeural", tmp_path, lambda m: None) == "macOS say"
    assert edge.calls == ["ko-KR-SunHiNeural"]   # 같은 공급자는 한 번만
    t = read_json(tmp_path / "timing.json")
    assert t[0]["start"] == 0 and t[0]["end"] == pytest.approx(0.5, abs=0.06)
    assert t[1]["start"] == pytest.approx(t[0]["end"] + voice.GAP, abs=0.01)
    assert (tmp_path / "voice.wav").exists()


def test_render_gradient_with_subtitles(tmp_path, monkeypatch):
    monkeypatch.setitem(voice.TTS, "edge", Fake("edge-tts", fake_speak, voice.Edge.voices))
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
    def speak_with_words(text, out):
        return fake_speak(text, out)[0], [{"text": text, "start": 0.1}]

    monkeypatch.setitem(voice.TTS, "elevenlabs", Fake("ElevenLabs", speak_with_words, ["elevenlabs"]))
    assert voice.synth(["하나", "둘"], "elevenlabs", tmp_path, lambda m: None) == "ElevenLabs"
    t = read_json(tmp_path / "timing.json")
    assert t[1]["words"] == [{"text": "둘", "start": pytest.approx(t[1]["start"] + 0.1, abs=0.002)}]

    def broken(text, out):
        raise RuntimeError("ElevenLabs 401")

    edge = Fake("edge-tts", fake_speak, voice.Edge.voices)
    monkeypatch.setitem(voice.TTS, "elevenlabs", Fake("ElevenLabs", broken, ["elevenlabs"]))
    monkeypatch.setitem(voice.TTS, "edge", edge)
    assert voice.synth(["하나"], "elevenlabs", tmp_path, lambda m: None) == "edge-tts"
    assert edge.calls == ["ko-KR-SunHiNeural"]
    assert "words" not in read_json(tmp_path / "timing.json")[0]


def test_elevenlabs_asks_number_normalization_and_keeps_original_alignment(tmp_path, monkeypatch):
    sent, urls = [], []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def urlopen(req, timeout):
        sent.append(json.loads(req.data))
        urls.append(req.full_url)
        return Resp(json.dumps({"audio_base64": base64.b64encode(b"mp3").decode(), "alignment": {
            "characters": list("45cm 탑"), "character_start_times_seconds": [0, .1, .2, .3, .4, .5, .6]}}).encode())
    monkeypatch.setattr(voice, "urlopen", urlopen)
    path, ws = voice.ElevenLabs().speak("elevenlabs", "45cm 탑", tmp_path / "s00")
    assert sent[0]["apply_text_normalization"] == "on" and sent[0]["text"] == "45cm 탑"
    assert path.read_bytes() == b"mp3" and ws == [{"text": "45cm", "start": 0}, {"text": "탑", "start": .5}]
    monkeypatch.setattr(config, "ELEVENLABS_VOICE_ID", "envID")
    voice.ElevenLabs().speak("elevenlabs", "탑", tmp_path / "s01")
    voice.ElevenLabs().speak("iWLjl1zCuqXRkW6494ve", "탑", tmp_path / "s02")
    assert [r.split("/")[-2] for r in urls[1:]] == ["envID", "iWLjl1zCuqXRkW6494ve"]
    assert voice.owner("iWLjl1zCuqXRkW6494ve").label == "ElevenLabs"


def test_voice_owner_and_choices(monkeypatch):
    assert voice.owner("ko-KR-InJoonNeural").label == "edge-tts"
    assert voice.owner("Yuna").label == "macOS say"
    assert voice.owner("elevenlabs").label == "ElevenLabs"
    assert voice.owner("ko-KR-Unknown").label == "edge-tts"
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert "elevenlabs" not in voice.choices() and "ko-KR-SunHiNeural" in voice.choices()


def test_synth_raises_when_no_tts_ready(tmp_path, monkeypatch):
    for k, p in list(voice.TTS.items()):
        off = Fake(p.label, fake_speak, p.voices)
        off.ready = lambda: False
        monkeypatch.setitem(voice.TTS, k, off)
    with pytest.raises(RuntimeError, match="TTS가 없어요"):
        voice.synth(["하나"], "ko-KR-SunHiNeural", tmp_path, lambda m: None)


def test_scene_frames_follow_sentence_starts():
    assert render.frames([0, 1.3], 4.6, 2) == [39, 99]
    assert render.frames([0], 3.0, 2) == [45, 45]   # 예전 작업: 같은 길이


def make_clips(tmp_path, n):
    (tmp_path / "clips").mkdir()
    for i in range(n):
        ffmpeg.run(["-f", "lavfi", "-i", "testsrc=s=640x360:d=1:r=30", "-pix_fmt", "yuv420p", tmp_path / "clips" / f"clip{i}.mp4"])
    return [f"clip{i}.mp4" for i in range(n)]


def duration(path):
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    h, m, sec = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).groups()
    return int(h) * 3600 + int(m) * 60 + float(sec)


def test_render_wide_clips_by_sentence(tmp_path, monkeypatch):
    monkeypatch.setitem(voice.TTS, "edge", Fake("edge-tts", fake_speak, voice.Edge.voices))
    voice.synth(["하나", "둘"], "ko-KR-SunHiNeural", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing))
    clips = make_clips(tmp_path, 2)
    dur = render.render(tmp_path, clips, timing[-1]["end"], None, [t["start"] for t in timing])   # 1초 클립: 마지막 화면에서 멈춤
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1
    assert render.thumbnail(tmp_path, ["커피"], "", "top", "clip0.mp4") == "영상 장면"
    assert ",2,80,80,1390," in (tmp_path / "thumb.ass").read_text()


def test_thumbnail_from_clip_shorter_than_seek(tmp_path):
    (tmp_path / "clips").mkdir()
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=s=640x360:d=0.3:r=30", "-pix_fmt", "yuv420p", tmp_path / "clips" / "clip0.mp4"])
    assert render.thumbnail(tmp_path, ["커피"], "", "top", "clip0.mp4") == "영상 장면"
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 1000


def test_render_old_stock_jobs_loop_clips(tmp_path, monkeypatch):
    monkeypatch.setitem(voice.TTS, "edge", Fake("edge-tts", fake_speak, voice.Edge.voices))
    voice.synth(["하나", "둘", "셋"], "ko-KR-SunHiNeural", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing))
    dur = render.render(tmp_path, make_clips(tmp_path, 2), timing[-1]["end"], None, [t["start"] for t in timing])
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1

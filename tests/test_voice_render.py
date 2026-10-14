"""ffmpeg로 실제 파일을 만든다. ffmpeg-full이 없으면 건너뛴다(네트워크는 안 쓴다)."""
import base64
import io
import json
import re
import subprocess
from pathlib import Path

import pytest

from shorts_printer import config
from shorts_printer.adapters import elevenlabs
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.core import channel, render, subtitles, voice
from shorts_printer.infra import ffmpeg
from shorts_printer.infra.store import read_json

pytestmark = pytest.mark.skipif(not Path(config.FFMPEG).exists(), reason="ffmpeg-full 없음")


KO = Korean()


@pytest.fixture
def ch():
    return channel.load("ko-40sec-facts")


class Fake:
    label, hint = "ElevenLabs", ".env에 ELEVENLABS_API_KEY"

    def __init__(self, speak, ready=True):
        self._speak, self.calls, self.ready = speak, [], lambda: ready

    def speak(self, v, text, out):
        self.calls.append(v)
        return self._speak(text, out)


def fake_speak(text, out):
    path = out.with_suffix(".wav")   # .pcm.wav 중간 파일과 안 겹치는지도 본다
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", path])
    return path, None


def test_voice_joins_sentences_with_gap(tmp_path, ch):
    fake = Fake(fake_speak)
    assert voice.synth(fake, ch, ["하나", "둘"], "LKOcTG4J4tYTPR9DnLeM", tmp_path, lambda m: None) == "ElevenLabs"
    assert fake.calls == ["LKOcTG4J4tYTPR9DnLeM"] * 2
    t = read_json(tmp_path / "timing.json")
    assert t[0]["start"] == 0 and t[0]["end"] == pytest.approx(0.5, abs=0.06)
    assert t[1]["start"] == pytest.approx(t[0]["end"] + voice.GAP, abs=0.01)
    assert (tmp_path / "voice.wav").exists()


def test_render_gradient_with_subtitles(tmp_path, ch):
    voice.synth(Fake(fake_speak), ch, ["커피 한 잔"], "elevenlabs", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    dur = render.render(tmp_path, [], timing[-1]["end"], ch, KO)
    assert dur == pytest.approx(timing[-1]["end"] + render.TAIL)
    assert (tmp_path / "final.mp4").stat().st_size > 1000 and (tmp_path / "poster.jpg").exists()
    assert not (tmp_path / "final.tmp.mp4").exists()
    assert render.thumbnail(tmp_path, ["커피 {상식}", "모르면 손해"], "손해", "bottom", ch, KO) == "단색"
    ass = (tmp_path / "thumb.ass").read_text()
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 1000 and "커피 ｛상식｝\\N모르면 {\\c&H0000E5FF&}손해{\\r}" in ass
    assert ",2,80,80,560," in ass   # 아래쪽, 쇼츠 제목칸 위
    assert "Style: Cap,Apple SD Gothic Neo,150," in ass   # min(150, 1400 // 7자): 예전과 같은 크기
    render.render(tmp_path, [], timing[-1]["end"], ch, KO, (["커피 상식"], "상식"))
    assert "{\\c" in (tmp_path / "title.ass").read_text() and ",2,80,80,1390," in (tmp_path / "title.ass").read_text()


def test_elevenlabs_word_times_shift_by_sentence_start(tmp_path, ch):
    def speak_with_words(text, out):
        return fake_speak(text, out)[0], [{"text": text, "start": 0.1}]

    assert voice.synth(Fake(speak_with_words), ch, ["하나", "둘"], "elevenlabs", tmp_path, print) == "ElevenLabs"
    t = read_json(tmp_path / "timing.json")
    assert t[1]["words"] == [{"text": "둘", "start": pytest.approx(t[1]["start"] + 0.1, abs=0.002)}]


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
    monkeypatch.setattr(elevenlabs, "urlopen", urlopen)
    path, ws = elevenlabs.ElevenLabs().speak("elevenlabs", "45cm 탑", tmp_path / "s00")
    assert sent[0]["apply_text_normalization"] == "on" and sent[0]["text"] == "45cm 탑"
    assert path.read_bytes() == b"mp3" and ws == [{"text": "45cm", "start": 0}, {"text": "탑", "start": .5}]
    monkeypatch.setattr(config, "ELEVENLABS_VOICE_ID", "envID")
    elevenlabs.ElevenLabs().speak("elevenlabs", "탑", tmp_path / "s01")
    elevenlabs.ElevenLabs().speak("iWLjl1zCuqXRkW6494ve", "탑", tmp_path / "s02")
    assert [r.split("/")[-2] for r in urls[1:]] == ["envID", "iWLjl1zCuqXRkW6494ve"]


def test_voices_default_mister_kim(ch):
    assert list(ch.tts.voices.values()) == ["미스터킴", "이하나", "지수", "미스터최"]
    assert ch.tts.default == "LKOcTG4J4tYTPR9DnLeM"


def test_synth_refuses_old_voice_and_missing_key(tmp_path, ch):
    with pytest.raises(RuntimeError, match="다른 목소리"):
        voice.synth(Fake(fake_speak), ch, ["하나"], "ko-KR-SunHiNeural", tmp_path, lambda m: None)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        voice.synth(Fake(fake_speak, ready=False), ch, ["하나"], "elevenlabs", tmp_path, lambda m: None)


def test_sample_cached_per_channel(tmp_path, ch, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    fake = Fake(lambda text, out: (out.write_bytes(text.encode()), (out, None))[1])
    path = voice.sample(fake, ch, "elevenlabs")
    assert path.parent == tmp_path / ".cache" / "voices" / "ko-40sec-facts" and path.name.startswith("elevenlabs-")
    assert path.read_text() == ch.tts.sample and voice.sample(fake, ch, "elevenlabs") == path and len(fake.calls) == 1
    # 미리 듣기 문장을 고치면 새로 읽는다
    new = ch.model_copy(update={"tts": ch.tts.model_copy(update={"sample": "다른 문장"})})
    assert voice.sample(fake, new, "elevenlabs").read_text() == "다른 문장" and len(fake.calls) == 2


def test_ass_color_and_channel_style(tmp_path, ch):
    assert render.ass_color("#FFE500") == "&H0000E5FF&" and render.ass_color("#0f172a") == "&H002A170F&"
    red = ch.model_copy(update={"style": ch.style.model_copy(update={"accent": "#FF0000", "font": "Hiragino Sans"})})
    render.caption_ass(tmp_path / "t.ass", ["커피 상식"], "상식", 150, render.TITLE_POS, red, KO)
    ass = (tmp_path / "t.ass").read_text()
    assert "Style: Cap,Hiragino Sans,150," in ass and "{\\c&H000000FF&}상식" in ass


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


def test_render_wide_clips_by_sentence(tmp_path, ch):
    voice.synth(Fake(fake_speak), ch, ["하나", "둘"], "elevenlabs", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    clips = make_clips(tmp_path, 2)
    # 1초 클립: 마지막 화면에서 멈춤
    dur = render.render(tmp_path, clips, timing[-1]["end"], ch, KO, None, [t["start"] for t in timing])
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1
    assert render.thumbnail(tmp_path, ["커피"], "", "top", ch, KO, "clip0.mp4") == "영상 장면"
    assert ",2,80,80,1390," in (tmp_path / "thumb.ass").read_text()


def test_render_full_layout_fills_screen(tmp_path, ch):
    full = ch.model_copy(update={"style": ch.style.model_copy(update={"layout": "full"})})
    voice.synth(Fake(fake_speak), full, ["하나"], "elevenlabs", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    lay = render.LAYOUTS["full"]
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), full.font, lay.sub)
    clips = make_clips(tmp_path, 1)
    render.render(tmp_path, clips, timing[-1]["end"], full, KO, (["커피 상식"], "상식"), [t["start"] for t in timing])
    probe = subprocess.run([config.FFMPEG, "-hide_banner", "-i", tmp_path / "final.mp4"], capture_output=True, text=True)
    assert "1080x1920" in probe.stderr
    # band와 다른 자리: 제목은 위 UI 아래 위 정렬, 자막은 아래 제목칸 위
    assert ",8,80,80,280," in (tmp_path / "title.ass").read_text() and ",8,90,90,1385," in (tmp_path / "subs.ass").read_text()
    # 띠 없이 전체 화면: 영상과 썸네일 모두 맨 위 줄(band면 검은 띠)도 영상이 차 있다
    render.thumbnail(tmp_path, ["커피"], "", "top", full, KO, "clip0.mp4")
    for name in ("final.mp4", "thumbnail.jpg"):
        top = subprocess.run([config.FFMPEG, "-v", "error", "-i", tmp_path / name, "-vf", "crop=1080:100:0:0",
                              "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        assert max(top) > 64, name


def test_thumbnail_from_clip_shorter_than_seek(tmp_path, ch):
    (tmp_path / "clips").mkdir()
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=s=640x360:d=0.3:r=30", "-pix_fmt", "yuv420p", tmp_path / "clips" / "clip0.mp4"])
    assert render.thumbnail(tmp_path, ["커피"], "", "top", ch, KO, "clip0.mp4") == "영상 장면"
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 1000


def test_render_old_stock_jobs_loop_clips(tmp_path, ch):
    voice.synth(Fake(fake_speak), ch, ["하나", "둘", "셋"], "elevenlabs", tmp_path, lambda m: None)
    timing = read_json(tmp_path / "timing.json")
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    clips = make_clips(tmp_path, 2)
    dur = render.render(tmp_path, clips, timing[-1]["end"], ch, KO, None, [t["start"] for t in timing])
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1

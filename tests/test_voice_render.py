"""ffmpeg로 실제 파일을 만든다. ffmpeg-full이 없으면 건너뛴다(네트워크는 안 쓴다)."""
import base64
import io
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from shorts_printer import config
from shorts_printer.adapters import elevenlabs
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.core import channel, render, subtitles, voice
from shorts_printer.infra import ffmpeg

pytestmark = pytest.mark.skipif(not Path(config.FFMPEG).exists(), reason="ffmpeg-full 없음")


KO = Korean()


@pytest.fixture
def ch():   # 배치는 band로 고정한다(채널 설정이 바뀌어도 테스트가 그대로 돌게)
    c = channel.load("ko-40sec-facts")
    return c.model_copy(update={"style": c.style.model_copy(update={"layout": "band"})})


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
    engine, t = voice.synth(fake, ch, ["하나", "둘"], "LKOcTG4J4tYTPR9DnLeM", tmp_path, lambda m: None)
    assert engine == "ElevenLabs" and fake.calls == ["LKOcTG4J4tYTPR9DnLeM"] * 2
    assert t[0]["start"] == 0 and t[0]["end"] == pytest.approx(0.5, abs=0.06)
    assert t[1]["start"] == pytest.approx(t[0]["end"] + voice.GAP, abs=0.01)
    assert (tmp_path / "voice.wav").exists()


def test_render_gradient_with_subtitles(tmp_path, ch):
    _, timing = voice.synth(Fake(fake_speak), ch, ["커피 한 잔"], "elevenlabs", tmp_path, lambda m: None)
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
    # 썸네일이 있으면 첫 프레임은 썸네일(문구 있음), 0.3초는 녹아 사라지는 중, 0.6초 뒤는 영상 자체
    def frame(sec):
        return subprocess.run([config.FFMPEG, "-v", "error", "-ss", str(sec), "-i", tmp_path / "final.mp4", "-vf",
                               "crop=1080:400:0:1300", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                              capture_output=True).stdout
    assert frame(0) != frame(0.3) != frame(0.6) and frame(0) != frame(0.6)


def test_elevenlabs_word_times_shift_by_sentence_start(tmp_path, ch):
    def speak_with_words(text, out):
        return fake_speak(text, out)[0], [{"text": text, "start": 0.1}]

    engine, t = voice.synth(Fake(speak_with_words), ch, ["하나", "둘"], "elevenlabs", tmp_path, print)
    assert engine == "ElevenLabs"
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


def test_voices_default_chris(ch):
    assert list(ch.tts.voices.values()) == ["크리스", "미스터킴", "이하나", "지수", "미스터최"]
    assert ch.tts.default == "PDoCXqBQFGsvfO0hNkEs"


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
    _, timing = voice.synth(Fake(fake_speak), ch, ["하나", "둘"], "elevenlabs", tmp_path, lambda m: None)
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    clips = make_clips(tmp_path, 2)
    # 1초 클립: 마지막 화면에서 멈춤
    dur = render.render(tmp_path, clips, timing[-1]["end"], ch, KO, None, [t["start"] for t in timing])
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1
    assert render.thumbnail(tmp_path, ["커피"], "", "top", ch, KO, "clip0.mp4") == "영상 장면"
    assert ",2,80,80,1390," in (tmp_path / "thumb.ass").read_text()


def test_render_full_layout_fills_screen(tmp_path, ch):
    full = ch.model_copy(update={"style": ch.style.model_copy(update={"layout": "full"})})
    _, timing = voice.synth(Fake(fake_speak), full, ["하나"], "elevenlabs", tmp_path, lambda m: None)
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


def test_render_clean_layout_intro_title_band_thumbnail(tmp_path, ch):
    clean = ch.model_copy(update={"style": ch.style.model_copy(update={"layout": "clean"})})
    _, timing = voice.synth(Fake(fake_speak), clean, ["하나"], "elevenlabs", tmp_path, lambda m: None)
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), clean.font,
                        render.LAYOUTS["clean"].sub)
    clips = make_clips(tmp_path, 1)
    render.render(tmp_path, clips, timing[-1]["end"], clean, KO, (["커피 상식"], "상식"), [t["start"] for t in timing])
    # 제목은 full 자리에 처음 1초 보이고 0.5초 동안 사라진다
    title = (tmp_path / "title.ass").read_text()
    assert ",8,80,80,280," in title and "0:00:00.00,0:00:01.50,Cap,,0,0,0,,{\\fad(0,500)}" in title
    render.thumbnail(tmp_path, ["커피"], "", "top", clean, KO, "clip0.mp4")
    assert ",2,80,80,1390," in (tmp_path / "thumb.ass").read_text()   # 썸네일은 band 제목 자리

    def top(name):
        return max(subprocess.run([config.FFMPEG, "-v", "error", "-i", tmp_path / name, "-vf", "crop=1080:100:0:0",
                                   "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                                  capture_output=True).stdout)
    assert top("final.mp4") > 64 and top("thumbnail.jpg") < 16   # 영상은 띠 없이, 썸네일은 위 검은 띠


def test_thumbnail_from_clip_shorter_than_seek(tmp_path, ch):
    (tmp_path / "clips").mkdir()
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=s=640x360:d=0.3:r=30", "-pix_fmt", "yuv420p", tmp_path / "clips" / "clip0.mp4"])
    assert render.thumbnail(tmp_path, ["커피"], "", "top", ch, KO, "clip0.mp4") == "영상 장면"
    assert (tmp_path / "thumbnail.jpg").stat().st_size > 1000


def test_render_old_stock_jobs_loop_clips(tmp_path, ch):
    _, timing = voice.synth(Fake(fake_speak), ch, ["하나", "둘", "셋"], "elevenlabs", tmp_path, lambda m: None)
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    clips = make_clips(tmp_path, 2)
    dur = render.render(tmp_path, clips, timing[-1]["end"], ch, KO, None, [t["start"] for t in timing])
    assert abs(duration(tmp_path / "final.mp4") - dur) < 0.1


def test_render_mixes_scene_clip_sound(tmp_path, ch):
    _, timing = voice.synth(Fake(fake_speak), ch, ["하나"], "elevenlabs", tmp_path, lambda m: None)
    subtitles.write_ass(tmp_path / "subs.ass", subtitles.cues(timing, KO, KO.limit), ch.font)
    (tmp_path / "clips").mkdir()
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=s=640x360:d=2:r=30", "-f", "lavfi", "-i", "sine=frequency=3000:d=2",
                "-pix_fmt", "yuv420p", "-shortest", tmp_path / "clips" / "clip0.mp4"])
    dur = render.render(tmp_path, ["clip0.mp4"], timing[-1]["end"], ch, KO, None, [t["start"] for t in timing])

    # 목소리가 끝난 꼬리(TAIL)에는 클립 소리만 남는다
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-ss", str(dur - 0.3), "-i", tmp_path / "final.mp4", "-af",
                        "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    assert float(re.search(r"mean_volume: (-?[\d.]+|-inf)", r.stderr).group(1)) > -40


def test_audio_levels_follow_channel_and_default_keeps_old_mix(tmp_path, ch, monkeypatch):
    def run(args, cwd=None):
        raise StopIteration(args[args.index("-filter_complex") + 1])
    monkeypatch.setattr(ffmpeg, "has_audio", lambda p: True)
    monkeypatch.setattr(ffmpeg, "run", run)
    with pytest.raises(StopIteration) as e:   # 기본값(한국어 채널): 목소리 원본 + 효과음 -21 LUFS의 70%
        render.render(tmp_path, ["c.mp4"], 1.0, ch, KO, None, [0])
    assert "[0:a]loudnorm=I=-21:TP=-2,aresample=48000,aformat=channel_layouts=stereo,volume=0.7," in e.value.value
    assert "[1:a]apad[vo]" in e.value.value
    quiet = ch.model_copy(update={"style": ch.style.model_copy(update={"voice_lufs": -16, "sfx_lufs": -23})})
    with pytest.raises(StopIteration) as e:
        render.render(tmp_path, ["c.mp4"], 1.0, quiet, KO, None, [0])
    assert "loudnorm=I=-23:" in e.value.value and "[1:a]loudnorm=I=-16:TP=-1.5,aresample=48000,apad[vo]" in e.value.value


def test_scenes_cross_fade_centered_on_sentence_starts(tmp_path, ch, monkeypatch):
    calls = []
    monkeypatch.setattr(render.ffmpeg, "run", lambda args, cwd=None: calls.append([str(a) for a in args]))
    monkeypatch.setattr(render.ffmpeg, "has_audio", lambda p: False)
    monkeypatch.setattr(os, "replace", lambda a, b: None)
    render.render(tmp_path, ["a.mp4", "b.mp4", "c.mp4"], 5.4, ch, KO, None, [0, 2.0, 4.0])   # dur 6.0 = 180f
    fc = calls[0][calls[0].index("-filter_complex") + 1]
    # 겹침 15프레임(0.5초): 첫 장면은 7f 더, 가운데는 8+7f 더, 마지막은 8f 더 자르고 경계 8f 전에 녹아들기 시작한다
    assert "trim=end_frame=67," in fc and "trim=end_frame=75," in fc and "trim=end_frame=68," in fc
    assert "[v0][v1]xfade=transition=fade:duration=0.5:offset=1.733[x1]" in fc
    assert "[x1][v2]xfade=transition=fade:duration=0.5:offset=3.733[bg]" in fc
    assert "concat=n=3:v=1" not in fc

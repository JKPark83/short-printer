"""롱폼 효과음·음악 배치(core/sound.py)와 ffmpeg 측정(infra/ffmpeg.py)."""
import subprocess
from pathlib import Path

import pytest

from shorts_printer import config
from shorts_printer.core import sound
from shorts_printer.infra import ffmpeg

LIB, MOODS = sound.tables()
MUSIC = {"file": "music.mp3", "duration": 180.0, "credit": "“Dark Times” Kevin MacLeod (incompetech.com), CC BY 4.0",
         "vol": 0.13}
# [시작, 옮기는 초, lng, lat, scale]: 큰 이동 → 1초 뒤 또 큰 이동(빠진다) → 작은 이동 → 큰 이동
CAM = [[0, 0, 127.0, 37.5, 0.4], [10, 2.4, 127.0, 37.5, 1.0], [12.5, 0.5, 127.0, 37.5, 0.3],
       [20, 2, 127.05, 37.5, 0.3], [30, 2.6, 129.0, 35.0, 0.6]]


def _place(**kw):
    args = dict(total=600.0, end_start=593.4, cam=CAM, turns=[40.0], hits=[50.0], final=500.0, photos=[60.0],
                music=MUSIC, lib=LIB) | kw
    return sound.place(**args)


def test_library_measured_and_files_exist():
    for name, e in LIB.items():
        assert (sound.ASSETS / e["file"]).exists(), name
        assert e["role"] in {"move", "turn", "hit", "final", "photo", "bed"}
        assert 0 <= e["onset"] < e["duration"] and 0 < e["peak"] <= e["duration"]
    assert {c[0] for c in sound.CUES.values()} <= LIB.keys()
    assert all(t["credit"].startswith(f"“{t['title']}” Kevin MacLeod") for ts in MOODS.values() for t in ts)


def test_whoosh_on_big_moves_peak_on_arrival_and_spaced():
    fx = [c for c in _place() if c[0].startswith("fx-move")]
    peak = LIB["whoosh-cinematic"]["peak"]
    arrivals = [round(c[2] + peak, 2) for c in fx]
    assert arrivals == [12.4, 32.6]   # 13.0은 2초 안이라 빠지고, 20초 작은 이동은 소리가 없다
    assert all(b - a >= sound.WHOOSH_GAP for a, b in zip(arrivals, arrivals[1:], strict=False))


def test_riser_hit_photo_alignment_and_explicit_lengths():
    by = {c[0]: c for c in _place()}
    assert by["fx-turn-1"][2] == round(40.0 - LIB["riser"]["peak"], 2)
    assert by["fx-hit-1"][2] == round(50.0 - LIB["distant-boom"]["onset"], 2)
    assert by["fx-photo-1"][2] == round(60.0 - 0.03 - LIB["shutter"]["onset"], 2)
    assert by["fx-final-1"][1] == LIB["impact-bass-2"]["file"]
    assert all(isinstance(c[3], float) and c[3] > 0 for c in by.values())


def test_early_cue_trims_file_head():
    c = next(c for c in _place(turns=[1.0]) if c[0] == "fx-turn-1")
    assert c[2] == 0 and c[5] == round(LIB["riser"]["peak"] - 1.0, 2)


def test_music_covers_film_without_overlap_and_ends_on_track_end():
    music = [c for c in _place() if c[0].startswith("music")]
    assert len(music) == 4 and music[0][2] == 0
    for a, b in zip(music, music[1:], strict=False):
        assert a[2] + a[3] == pytest.approx(b[2], abs=0.011)   # 11번 줄 하나라 겹치지 않고 바로 잇는다
    last = music[-1]
    assert last[2] + last[3] == pytest.approx(600.0, abs=0.011)
    assert last[5] + last[3] == pytest.approx(MUSIC["duration"], abs=0.011)
    assert all(c[3] <= MUSIC["duration"] for c in music)


def test_music_joins_skip_track_head_and_tail():
    music = [c for c in _place(music=MUSIC | {"head": 4.28, "tail": 3.9}) if c[0].startswith("music")]
    assert [c[5] for c in music] == [0, 4.28, 4.28, 30.0]   # 가운데 조각은 곡 앞 무음 뒤에서 시작한다
    assert all(c[5] + c[3] <= 180.0 - 3.9 for c in music[:-1])   # 곡 끝 무음까지 가지 않는다


def test_track_measures_head_and_tail(monkeypatch):
    monkeypatch.setattr(ffmpeg, "duration", lambda path: 183.7)
    monkeypatch.setattr(ffmpeg, "silences", lambda path: [(0.0, 4.28), (90.0, 92.5), (179.76, 183.61)])
    monkeypatch.setattr(ffmpeg, "loudness", lambda path: {"lufs": sound.MUSIC_LUFS + 20})
    t = sound.track(Path("/x/Dark_Times.mp3"), "c")
    assert (t["file"], t["head"], t["tail"], t["vol"]) == ("Dark_Times.mp3", 4.28, 3.94, 0.1)   # 20 dB 큰 곡은 1/10
    monkeypatch.setattr(ffmpeg, "loudness", lambda path: {"lufs": -60.0})
    assert sound.track(Path("/x/a.mp3"), "c")["vol"] == 1.0   # 조용한 곡도 원본보다 키우지는 않는다


def test_pick_unused_track_first_then_least_recent():
    tracks = [{"title": t} for t in "ABC"]
    assert sound.pick(tracks, [None, "A"])["title"] == "B"
    assert sound.pick(tracks, ["C", "B", "A"])["title"] == "C"
    assert sound.pick(tracks, ["B", "C", "A", "B"])["title"] == "C"


def test_music_silence_beat_and_no_fx_on_end_card():
    out = _place(total=170.0, end_start=163.0, silence=(150.0, 153.0), final=165.0)
    music = [c for c in out if c[0].startswith("music")]
    assert [(c[2], c[3], c[5], c[7]) for c in music] == [(0, 150.0, 0, 6), (153.0, 17.0, 163.0, 3)]
    assert not any(c[0] == "fx-final-1" for c in out)


def test_credits_group_sources():
    lines = sound.credits(LIB, {"shutter", "cannon-near", "riser", "music"}, MUSIC)
    assert lines == ["음악 “Dark Times” Kevin MacLeod (incompetech.com), CC BY 4.0",
                     "효과음 Freesound Kodack, craigsmith (CC0) · Pixabay"]


EBUR = """[Parsed_ebur128_0 @ 0x1] t: 9.9  TARGET:-23 LUFS    M: -14.0 S: -14.1     I: -14.0 LUFS
[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -16.5 LUFS
    Threshold: -26.6 LUFS

  Loudness range:
    LRA:         5.2 LU
    Threshold: -36.6 LUFS
    LRA low:   -20.3 LUFS
    LRA high:  -15.1 LUFS

  True peak:
    Peak:       -2.0 dBFS
"""
SILENCE = """[silencedetect @ 0x1] silence_start: -0.002
[silencedetect @ 0x1] silence_end: 0.71 | silence_duration: 0.712
[silencedetect @ 0x1] silence_start: 120.5
"""


def test_loudness_and_silences_parse(monkeypatch):
    out = {"ebur128=peak=true": EBUR}
    monkeypatch.setattr(ffmpeg, "_analyze", lambda path, af: out.get(af, SILENCE))
    monkeypatch.setattr(ffmpeg, "duration", lambda path: 130.0)
    assert ffmpeg.loudness(Path("x.mp4")) == {"lufs": -16.5, "true_peak": -2.0, "lra": 5.2}
    assert ffmpeg.silences(Path("x.mp4")) == [(0.0, 0.71), (120.5, 130.0)]


def test_duration_real_ffmpeg(tmp_path):
    f = tmp_path / "sine.wav"
    subprocess.run([config.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(f)],
                   check=True)
    assert ffmpeg.duration(f) == pytest.approx(1.0, abs=0.02)

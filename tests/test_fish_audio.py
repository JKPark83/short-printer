import io
import json
from urllib.error import HTTPError

import pytest

from shorts_printer.adapters import fish_audio


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_fish_audio_sends_drama3_and_voice(tmp_path, monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append((req.get_header("Model"), json.loads(req.data)))
        return Resp(b"mp3")
    monkeypatch.setattr(fish_audio, "urlopen", urlopen)
    path, ws = fish_audio.FishAudio().speak("v123", "탑", tmp_path / "s00")
    model, body = sent[0]
    assert model == "drama-3" and body["reference_id"] == "v123" and body["format"] == "mp3"
    assert path.name == "s00.mp3" and path.read_bytes() == b"mp3" and ws is None


def test_fish_audio_http_error_is_korean_runtime_error(tmp_path, monkeypatch):
    def urlopen(req, timeout):
        raise HTTPError(req.full_url, 402, "", {}, io.BytesIO(b'{"message":"no credits"}'))
    monkeypatch.setattr(fish_audio, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="Fish Audio 402: .*no credits"):
        fish_audio.FishAudio().speak("v123", "탑", tmp_path / "s00")

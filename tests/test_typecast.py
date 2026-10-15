import base64
import io
import json
from urllib.error import HTTPError

import pytest

from shorts_printer.adapters import typecast


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_typecast_sends_voice_and_groups_char_times_into_words(tmp_path, monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append((req.full_url, json.loads(req.data)))
        chars = [{"text": c, "start": i / 10, "end": i / 10 + .1} for i, c in enumerate("45cm 탑")]
        return Resp(json.dumps({"audio": base64.b64encode(b"mp3").decode(), "characters": chars}).encode())
    monkeypatch.setattr(typecast, "urlopen", urlopen)
    path, ws = typecast.Typecast().speak("tc_abc", "45cm 탑", tmp_path / "s00")
    url, body = sent[0]
    assert "granularity=char" in url and body["voice_id"] == "tc_abc" and body["output"]["audio_format"] == "mp3"
    assert path.name == "s00.mp3" and path.read_bytes() == b"mp3"
    assert ws == [{"text": "45cm", "start": 0}, {"text": "탑", "start": .5}]


def test_typecast_words_without_spaces_and_mismatch():
    chars = [{"text": c, "start": i} for i, c in enumerate("ab")]   # 공백 없이 와도 원문으로 낱말을 나눈다
    assert typecast.words("a b", chars) == [{"text": "a", "start": 0}, {"text": "b", "start": 1}]
    assert typecast.words("abc", chars) is None   # 글자 수가 다르면 비례 배분으로


def test_typecast_http_error_is_korean_runtime_error(tmp_path, monkeypatch):
    def urlopen(req, timeout):
        raise HTTPError(req.full_url, 402, "", {}, io.BytesIO(b'{"detail":"no credits"}'))
    monkeypatch.setattr(typecast, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="Typecast 402: .*no credits"):
        typecast.Typecast().speak("tc_abc", "탑", tmp_path / "s00")

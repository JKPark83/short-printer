from types import SimpleNamespace

import pytest

from shorts_printer.adapters import edge_tts


def fake_communicate(chunks):
    return lambda text, voice, boundary: SimpleNamespace(stream_sync=lambda: iter(chunks))


def test_edge_tts_writes_mp3_and_word_times(tmp_path, monkeypatch):
    chunks = [{"type": "WordBoundary", "offset": 1_000_000, "text": "우리"}, {"type": "audio", "data": b"mp3"},
              {"type": "WordBoundary", "offset": 3_750_000, "text": "몸"}]
    monkeypatch.setattr(edge_tts.edge_tts, "Communicate", fake_communicate(chunks))
    path, ws = edge_tts.EdgeTTS("ko").speak("", "우리 몸", tmp_path / "s00")
    assert path.name == "s00.mp3" and path.read_bytes() == b"mp3"
    assert ws == [{"text": "우리", "start": 0.1}, {"text": "몸", "start": 0.375}]


def test_edge_tts_falls_back_when_blocked(tmp_path, monkeypatch):
    def blocked(*a, **k):
        raise OSError("403")
    monkeypatch.setattr(edge_tts.edge_tts, "Communicate", blocked)
    say = SimpleNamespace(ready=lambda: True, speak=lambda v, t, out: (out.with_suffix(".aiff"), None))
    assert edge_tts.EdgeTTS("ko", fallback=say).speak("", "탑", tmp_path / "s00") == (tmp_path / "s00.aiff", None)
    with pytest.raises(RuntimeError, match="Edge TTS 실패: 403"):
        edge_tts.EdgeTTS("ko").speak("", "탑", tmp_path / "s00")

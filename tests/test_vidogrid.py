import io
import json
from urllib.error import HTTPError

import pytest

from shorts_printer.adapters import vidogrid
from shorts_printer.ports.video import Refused


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake(monkeypatch, history: dict, busy: int = 0):
    """POST은 장면마다 uuid, GET /history는 history[uuid] 순서대로 상태, 그 밖 주소는 영상 바이트."""
    sent = []

    def urlopen(req, timeout):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/video-gen/veo"):
            if len(sent) < busy:
                sent.append(None)
                raise HTTPError(url, 422, "", {}, io.BytesIO(b'{"detail":{"error_code":"HIGH_TRAFFIC_ERROR"}}'))
            sent.append(dict(x.split("=") for x in req.data.decode().split("&")))
            return Resp(json.dumps({"uuid": f"u{len(sent)}", "estimated_credit": 4}).encode())
        if "/history/" in url:
            return Resp(json.dumps(history[url.rsplit("/", 1)[1]].pop(0)).encode())
        return Resp(b"mp4" + url.encode())
    monkeypatch.setattr(vidogrid, "urlopen", urlopen)
    monkeypatch.setattr(vidogrid.time, "sleep", lambda s: None)
    monkeypatch.setenv("VIDOGRID_API_KEY", "vidogrid-x")
    return sent


def scene(i):
    return {"i": i, "file": f"clip{i}.mp4", "sentence": "", "prompt": f"p{i}", "sec": 3}


def done(url):
    return {"status": 2, "used_credit": 4, "generated_video": [{"video_url": url}]}


def test_vidogrid_submits_all_then_downloads_as_they_finish(tmp_path, monkeypatch):
    sent = fake(monkeypatch, {"u1": [{"status": 1}, done("https://cdn/a")], "u2": [done("https://cdn/b")]})
    got = list(vidogrid.VidoGrid().make([scene(0), scene(1)], tmp_path, print))
    assert [s["aspect_ratio"] for s in sent] == ["9%3A16"] * 2 and sent[0]["model"] == "omni-1.1-flash"
    assert [c["file"] for c in got] == ["clip1.mp4", "clip0.mp4"]   # 먼저 끝난 장면부터
    assert (tmp_path / "clip0.mp4").read_bytes() == b"mp4https://cdn/a"
    assert not list(tmp_path.glob("*.task"))


def test_vidogrid_resumes_task_without_resubmitting(tmp_path, monkeypatch):
    (tmp_path / "clip0.task").write_text(json.dumps({"uuid": "old"}))
    sent = fake(monkeypatch, {"old": [done("https://cdn/old")]})
    assert [c["url"] for c in vidogrid.VidoGrid().make([scene(0)], tmp_path, print)] == ["https://cdn/old"]
    assert sent == []   # 다시 넣지 않아 크레딧이 두 번 들지 않는다


def test_vidogrid_policy_refusal_raises_refused_and_drops_task(tmp_path, monkeypatch):
    fake(monkeypatch, {"u1": [{"status": -2, "error_message": "unsafe"}], "u2": [done("https://cdn/b")]})
    with pytest.raises(Refused) as e:
        list(vidogrid.VidoGrid().make([scene(0), scene(1)], tmp_path, print))
    assert e.value.scenes == {0: "unsafe"} and (tmp_path / "clip1.mp4").exists()
    assert not (tmp_path / "clip0.task").exists()   # 고친 프롬프트로 새로 넣게


def test_vidogrid_retries_busy_but_raises_auth(tmp_path, monkeypatch):
    sent = fake(monkeypatch, {"u2": [done("https://cdn/a")]}, busy=1)
    assert len(list(vidogrid.VidoGrid().make([scene(0)], tmp_path, print))) == 1 and sent[0] is None

    def urlopen(req, timeout):
        raise HTTPError(req.full_url, 404, "", {}, io.BytesIO(b'{"detail":{"error_code":"API_KEY_NOT_FOUND"}}'))
    monkeypatch.setattr(vidogrid, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="API_KEY_NOT_FOUND"):
        list(vidogrid.VidoGrid().make([scene(1)], tmp_path, print))

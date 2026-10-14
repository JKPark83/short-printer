import io
import json
import threading
import urllib.request
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlsplit

import pytest

from shorts_printer import config, pipeline, youtube
from shorts_printer.jobs import Job, atomic_write_json

SCRIPT = {"title": "커피 상식", "description": "설명", "tags": ["커피 상식", "카페"]}


class Resp(io.BytesIO):
    def __init__(self, body=b"", headers=None):
        super().__init__(body)
        self.headers = headers or {}


@pytest.fixture
def yt(tmp_path, monkeypatch):
    """클라이언트 JSON과 저장된 토큰이 있는 상태. 네트워크는 쓰지 않는다."""
    client = tmp_path / "client.json"
    client.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))
    token = tmp_path / ".secrets" / "youtube_token.json"
    token.parent.mkdir()
    token.write_text('{"refresh_token": "RT"}')
    monkeypatch.setattr(config, "YOUTUBE_CLIENT_SECRET", str(client))
    monkeypatch.setattr(config, "YOUTUBE_TOKEN", token)
    return token


def fake(monkeypatch, *replies):
    """urlopen을 바꿔 보낸 요청을 모으고 준비한 응답(또는 예외)을 차례로 돌려준다."""
    sent, replies = [], list(replies)

    def urlopen(req, timeout):
        sent.append(req)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(youtube, "urlopen", urlopen)
    return sent


def test_metadata_fits_youtube_limits():
    m = youtube.metadata({"title": "<b>" + "가" * 120, "description": "설명>" + "한" * 2000,
                          "tags": ["a b", "<>"] + ["x" * 99] * 6})
    s = m["snippet"]
    assert s["title"] == "b" + "가" * 99
    assert s["description"] == "설명" + "한" * 1664 and len(s["description"].encode()) <= 5000   # 글자 중간에서 안 자른다
    assert s["tags"] == ["a b"] + ["x" * 99] * 4   # 5(따옴표 2) + 100×4(쉼표 1) = 405, 하나 더 넣으면 505
    assert s["categoryId"] == "22" and s["defaultLanguage"] == s["defaultAudioLanguage"] == "ko"
    assert m["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False}


def test_upload_is_private_resumable_then_one_put(yt, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"MP4DATA")
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
                Resp(b"", {"Location": "https://upload.example/session"}), Resp(b'{"id": "VID"}'))
    assert youtube.upload(video, SCRIPT) == "VID"
    tok, init, put = sent
    assert tok.full_url == youtube.TOKEN and b"grant_type=refresh_token" in tok.data and b"refresh_token=RT" in tok.data
    h = {k.lower(): v for k, v in init.header_items()}
    assert init.get_method() == "POST" and init.full_url == youtube.UPLOAD and h["authorization"] == "Bearer ya29.TOKEN"
    assert h["x-upload-content-length"] == "7" and h["x-upload-content-type"] == "video/mp4"
    assert json.loads(init.data)["status"]["privacyStatus"] == "private"
    assert put.get_method() == "PUT" and put.full_url == "https://upload.example/session" and put.data == b"MP4DATA"


def test_google_errors_become_korean_messages(yt, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    quota = {"error": {"code": 403, "message": "quota over", "errors": [{"reason": "quotaExceeded"}]}}
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         HTTPError(youtube.UPLOAD, 403, "Forbidden", {}, io.BytesIO(json.dumps(quota).encode())))
    with pytest.raises(RuntimeError) as e:
        youtube.upload(video, SCRIPT)
    assert str(e.value) == "YouTube 요청 실패(403: quotaExceeded · quota over)" and "ya29" not in str(e.value)

    fake(monkeypatch, HTTPError(youtube.TOKEN, 400, "Bad Request", {}, io.BytesIO(b'{"error": "invalid_grant"}')))
    with pytest.raises(RuntimeError, match="로그인이 만료됐어요"):
        youtube.upload(video, SCRIPT)

    # 다 보낸 뒤 응답을 못 받으면 이미 올라갔을 수 있다 → 다시 누르기 전에 스튜디오 확인을 안내
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         Resp(b"", {"Location": "https://upload.example/session"}), TimeoutError("timed out"))
    with pytest.raises(RuntimeError, match="스튜디오에서 먼저 확인"):
        youtube.upload(video, SCRIPT)


def test_web_client_json_is_rejected(yt):
    (yt.parent.parent / "client.json").write_text('{"web": {"client_id": "cid"}}')
    with pytest.raises(RuntimeError, match="데스크톱 앱"):
        youtube.login()


def test_login_checks_state_and_saves_token_privately(yt, monkeypatch):
    yt.unlink()
    assert not youtube.ready()
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def browser(url):   # 브라우저 대신: 파비콘 요청 뒤에 Google이 돌려보내는 주소를 연다
        q = dict(parse_qsl(urlsplit(url).query))
        assert q["code_challenge_method"] == "S256" and q["scope"] == youtube.SCOPE
        threading.Thread(target=lambda: [direct.open(q["redirect_uri"] + "/favicon.ico").read(),
                                         direct.open(f'{q["redirect_uri"]}/?code=C&state={q["state"]}').read()]).start()

    monkeypatch.setattr(youtube.webbrowser, "open", browser)
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN", "refresh_token": "NEW"}'))
    youtube.login()
    form = dict(parse_qsl(sent[0].data.decode()))
    assert form["code"] == "C" and form["grant_type"] == "authorization_code" and form["code_verifier"]
    assert json.loads(yt.read_text()) == {"refresh_token": "NEW"} and youtube.ready()
    assert yt.stat().st_mode & 0o777 == 0o600 and yt.parent.stat().st_mode & 0o777 == 0o700


def test_publish_records_done_then_failed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    job = Job.create("커피", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", SCRIPT)
    monkeypatch.setattr(youtube, "upload", lambda path, script: "VID" if script["title"] == "커피 상식" else None)
    pipeline.publish(job)
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and up["at"]
    assert "https://youtu.be/VID (비공개)" in (job.dir / "log.txt").read_text()

    def boom(*_):
        raise RuntimeError("quotaExceeded sk-ant-SECRET")

    monkeypatch.setattr(youtube, "upload", boom)
    with pytest.raises(RuntimeError):
        pipeline.publish(job)
    up = job.data["upload"]
    assert up["status"] == "failed" and up["error"] == "quotaExceeded ***" and up["video_id"] is None


def test_thumbnail_is_set_after_upload_and_failure_keeps_upload_done(yt, monkeypatch):
    job = Job.create("커피", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", SCRIPT)
    (job.dir / "thumbnail.jpg").write_bytes(b"JPG")
    monkeypatch.setattr(youtube, "upload", lambda path, script: "VID")
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'), Resp(b"{}"))
    pipeline.publish(job)
    put = sent[1]
    assert put.full_url == youtube.THUMBNAIL + "VID" and put.data == b"JPG" and put.get_header("Content-type") == "image/jpeg"
    assert job.data["upload"]["note"] is None

    forbidden = {"error": {"message": "no permission", "errors": [{"reason": "forbidden"}]}}
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         HTTPError(youtube.THUMBNAIL, 403, "Forbidden", {}, io.BytesIO(json.dumps(forbidden).encode())))
    pipeline.publish(job)
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and "forbidden" in up["note"]


def test_upload_limit_falls_back_to_studio(monkeypatch):
    from shorts_printer import studio

    job = Job.create("커피", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", SCRIPT)

    def limit(*_):
        raise RuntimeError("YouTube 요청 실패(400: uploadLimitExceeded · too many)")

    monkeypatch.setattr(youtube, "upload", limit)
    got = []
    monkeypatch.setattr(studio, "upload", lambda path, meta: got.append(meta) or "SVID")
    pipeline.publish(job)
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "SVID"
    assert got[0]["snippet"]["title"] == "커피 상식" and got[0]["status"]["privacyStatus"] == "private"

import io
import json
import threading
import urllib.request
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlsplit

import pytest

from shorts_printer import config
from shorts_printer.adapters import youtube, youtube_studio
from shorts_printer.adapters.youtube import YouTube

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
    token = tmp_path / ".secrets" / "channels" / "ch1" / "youtube_token.json"
    token.parent.mkdir(parents=True)
    token.write_text('{"refresh_token": "RT"}')
    monkeypatch.setattr(config, "YOUTUBE_CLIENT_SECRET", str(client))
    return YouTube(token, channel="ch1", language="ko", category="22")


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
    s = youtube.metadata(SCRIPT, language="ja", category="27")["snippet"]
    assert s["defaultLanguage"] == s["defaultAudioLanguage"] == "ja" and s["categoryId"] == "27"


def test_upload_is_private_resumable_then_one_put(yt, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"MP4DATA")
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
                Resp(b"", {"Location": "https://upload.example/session"}), Resp(b'{"id": "VID"}'))
    assert yt.upload(video, SCRIPT, print) == "VID"
    tok, init, put = sent
    assert tok.full_url == youtube.TOKEN and b"grant_type=refresh_token" in tok.data and b"refresh_token=RT" in tok.data
    h = {k.lower(): v for k, v in init.header_items()}
    assert init.get_method() == "POST" and init.full_url == youtube.UPLOAD and h["authorization"] == "Bearer ya29.TOKEN"
    assert h["x-upload-content-length"] == "7" and h["x-upload-content-type"] == "video/mp4"
    assert json.loads(init.data)["status"]["privacyStatus"] == "private"
    assert json.loads(init.data)["snippet"]["defaultLanguage"] == "ko"
    assert put.get_method() == "PUT" and put.full_url == "https://upload.example/session" and put.data == b"MP4DATA"


def test_google_errors_become_korean_messages(yt, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    quota = {"error": {"code": 403, "message": "quota over", "errors": [{"reason": "quotaExceeded"}]}}
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         HTTPError(youtube.UPLOAD, 403, "Forbidden", {}, io.BytesIO(json.dumps(quota).encode())))
    with pytest.raises(RuntimeError) as e:
        yt.upload(video, SCRIPT, print)
    assert str(e.value) == "YouTube 요청 실패(403: quotaExceeded · quota over)" and "ya29" not in str(e.value)

    fake(monkeypatch, HTTPError(youtube.TOKEN, 400, "Bad Request", {}, io.BytesIO(b'{"error": "invalid_grant"}')))
    with pytest.raises(RuntimeError, match="로그인이 만료됐어요.*youtube-login --channel ch1"):   # 어느 채널인지
        yt.upload(video, SCRIPT, print)

    # 다 보낸 뒤 응답을 못 받으면 이미 올라갔을 수 있다 → 다시 누르기 전에 스튜디오 확인을 안내
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         Resp(b"", {"Location": "https://upload.example/session"}), TimeoutError("timed out"))
    with pytest.raises(RuntimeError, match="스튜디오에서 먼저 확인"):
        yt.upload(video, SCRIPT, print)


def test_web_client_json_is_rejected(yt):
    with open(config.YOUTUBE_CLIENT_SECRET, "w") as f:
        f.write('{"web": {"client_id": "cid"}}')
    with pytest.raises(RuntimeError, match="데스크톱 앱"):
        yt.login()


def test_login_checks_state_and_saves_token_privately(yt, monkeypatch):
    yt.token.unlink()
    yt.token.parent.rmdir()   # 채널 폴더가 없어도 만들어 저장한다
    assert not yt.ready() and "--channel ch1" in yt.hint
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def browser(url):   # 브라우저 대신: 파비콘 요청 뒤에 Google이 돌려보내는 주소를 연다
        q = dict(parse_qsl(urlsplit(url).query))
        assert q["code_challenge_method"] == "S256" and q["scope"] == youtube.SCOPE
        threading.Thread(target=lambda: [direct.open(q["redirect_uri"] + "/favicon.ico").read(),
                                         direct.open(f'{q["redirect_uri"]}/?code=C&state={q["state"]}').read()]).start()

    monkeypatch.setattr(youtube.webbrowser, "open", browser)
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN", "refresh_token": "NEW"}'))
    yt.login()
    form = dict(parse_qsl(sent[0].data.decode()))
    assert form["code"] == "C" and form["grant_type"] == "authorization_code" and form["code_verifier"]
    assert json.loads(yt.token.read_text()) == {"refresh_token": "NEW"} and yt.ready() and yt.hint == "비공개로 올려요"
    assert yt.token.stat().st_mode & 0o777 == 0o600 and yt.token.parent.stat().st_mode & 0o777 == 0o700


def sv(publisher):
    """publish가 쓰는 Services 대신. 업로드 공급자와 설명란 값(publish.footer·sources_heading)만 있으면 된다."""
    return SimpleNamespace(publisher=publisher,
                           channel=SimpleNamespace(publish=SimpleNamespace(footer="", sources_heading="")))


@pytest.fixture
def pipeline():
    from shorts_printer.core import pipeline  # 다른 모듈이 덜 옮겨져도 어댑터 테스트는 돈다

    return pipeline


def test_publish_records_done_then_failed(yt, pipeline, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    job = pipeline.Job.create("ko-40sec-facts", "커피", "ko-KR-SunHiNeural")
    job.put("script.json", SCRIPT)
    monkeypatch.setattr(yt, "upload", lambda path, meta, log: "VID" if meta["title"] == "커피 상식" else None)
    pipeline.publish(job, sv(yt))
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and up["at"]
    assert "업로드 완료: VID (비공개)" in "\n".join(job.tail())

    def boom(*_):
        raise RuntimeError("quotaExceeded sk-ant-SECRET")

    monkeypatch.setattr(yt, "upload", boom)
    with pytest.raises(RuntimeError):
        pipeline.publish(job, sv(yt))
    up = job.data["upload"]
    assert up["status"] == "failed" and up["error"] == "quotaExceeded ***" and up["video_id"] is None


def test_thumbnail_is_set_after_upload_and_failure_keeps_upload_done(yt, pipeline, monkeypatch):
    job = pipeline.Job.create("ko-40sec-facts", "커피", "ko-KR-SunHiNeural")
    job.put("script.json", SCRIPT)
    (job.dir / "thumbnail.jpg").write_bytes(b"JPG")
    monkeypatch.setattr(yt, "upload", lambda path, meta, log: "VID")
    sent = fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'), Resp(b"{}"))
    pipeline.publish(job, sv(yt))
    put = sent[1]
    assert put.full_url == youtube.THUMBNAIL + "VID" and put.data == b"JPG" and put.get_header("Content-type") == "image/jpeg"
    assert job.data["upload"]["note"] is None

    forbidden = {"error": {"message": "no permission", "errors": [{"reason": "forbidden"}]}}
    fake(monkeypatch, Resp(b'{"access_token": "ya29.TOKEN"}'),
         HTTPError(youtube.THUMBNAIL, 403, "Forbidden", {}, io.BytesIO(json.dumps(forbidden).encode())))
    pipeline.publish(job, sv(yt))
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and "forbidden" in up["note"]


def test_upload_limit_falls_back_to_studio(tmp_path, monkeypatch):
    yt = YouTube(tmp_path / "token.json", channel="ch1", language="en", category="27", studio_channel="UCabc")

    def limit(*_):
        raise RuntimeError("YouTube 요청 실패(400: uploadLimitExceeded · too many)")

    monkeypatch.setattr(youtube, "upload", limit)
    got, logs = [], []
    monkeypatch.setattr(youtube_studio, "upload", lambda path, meta, cid: got.append((meta, cid)) or "SVID")
    assert yt.upload(tmp_path / "final.mp4", SCRIPT, logs.append) == "SVID"
    meta, channel_id = got[0]
    assert channel_id == "UCabc" and "스튜디오" in logs[0]
    assert meta["snippet"]["title"] == "커피 상식" and meta["status"]["privacyStatus"] == "private"
    assert meta["snippet"]["defaultLanguage"] == "en" and meta["snippet"]["categoryId"] == "27"

    monkeypatch.setattr(youtube, "upload", lambda *_: (_ for _ in ()).throw(RuntimeError("quotaExceeded")))
    with pytest.raises(RuntimeError, match="quotaExceeded"):   # 다른 오류는 스튜디오로 안 간다
        yt.upload(tmp_path / "final.mp4", SCRIPT, logs.append)
    assert len(got) == 1

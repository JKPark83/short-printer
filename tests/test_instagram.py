import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qsl

import pytest

from shorts_printer.adapters import instagram
from shorts_printer.adapters.instagram import Instagram

ACC = {"page_id": "P1", "ig_user_id": "IG1", "username": "facts", "page_token": "PAGE-TOKEN"}


@pytest.fixture
def ig(tmp_path):
    token = tmp_path / "instagram_token.json"
    token.write_text(json.dumps(ACC))
    return Instagram(token, channel="ch1", footer="※AI 이미지")


def ok(body: dict) -> io.BytesIO:
    return io.BytesIO(json.dumps(body).encode())


def fake(monkeypatch, *replies):
    """urlopen을 바꿔 보낸 요청을 모으고 준비한 응답(또는 예외)을 차례로 돌려준다."""
    sent, replies = [], list(replies)

    def urlopen(req, timeout):
        sent.append(req)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(instagram, "urlopen", urlopen)
    monkeypatch.setattr(instagram.time, "sleep", lambda s: None)
    return sent


def graph_error(code: int, body: dict) -> HTTPError:
    return HTTPError("https://graph.facebook.com/x", code, "err", {}, io.BytesIO(json.dumps(body).encode()))


def test_caption_tags_limit_and_footer_kept():
    meta = {"title": "커피", "description": "설명\n\n※AI 이미지", "tags": ["커피 상식", "#카페", "커피상식", " "]}
    assert instagram.caption(meta, "※AI 이미지") == "커피\n\n설명\n\n※AI 이미지\n\n#커피상식 #카페"
    meta = {"title": "t", "description": "가" * 3000 + "\n\n※AI", "tags": [f"t{i}" for i in range(40)]}
    out = instagram.caption(meta, "※AI")
    assert len(out) == 2200 and out.endswith("가\n\n※AI") and "#" not in out   # 태그부터 빼고 본문을 자른다
    tags = [f"t{i}" for i in range(40)]
    assert instagram.caption({"title": "t", "description": "", "tags": tags}).count("#") == 30   # 해시태그 한도
    out = instagram.caption({"title": "t", "description": "가" * 2150, "tags": tags})
    assert len(out) <= 2200 and "가" * 2150 in out and 0 < out.count("#") < 30   # 넘치는 만큼 태그만 뺀다


def test_upload_happy_path(ig, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"MP4DATA")
    sent = fake(monkeypatch, ok({"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/v26.0/C1"}),
                ok({"success": True}), ok({"status_code": "IN_PROGRESS"}), ok({"status_code": "FINISHED"}),
                ok({"id": "M1"}))
    logs = []
    assert ig.upload(video, {"title": "제목", "description": "설명", "tags": ["a"]}, logs.append) == "M1"
    box, up, *polls, pub = sent
    form = dict(parse_qsl(box.data.decode()))
    assert box.full_url.endswith("/IG1/media") and form["media_type"] == "REELS"
    assert form["upload_type"] == "resumable" and form["thumb_offset"] == "0" and form["share_to_feed"] == "true"
    assert form["caption"] == "제목\n\n설명\n\n※AI 이미지\n\n#a"
    assert up.full_url.endswith("/C1") and up.data == b"MP4DATA"
    assert up.get_header("Offset") == "0" and up.get_header("File_size") == "7"
    assert all(r.get_header("Authorization") == "OAuth PAGE-TOKEN" for r in sent)
    assert all("PAGE-TOKEN" not in r.full_url for r in sent)   # 토큰은 헤더로만
    assert len(polls) == 2 and pub.full_url.endswith("/IG1/media_publish")
    assert dict(parse_qsl(pub.data.decode())) == {"creation_id": "C1"} and logs == ["Instagram @facts에 게시"]


def test_upload_processing_error_stops_before_publish(ig, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    sent = fake(monkeypatch, ok({"id": "C1"}), ok({}), ok({"status_code": "ERROR", "status": "코덱"}))
    with pytest.raises(RuntimeError, match="처리하지 못했어요\\(ERROR: 코덱\\)"):
        ig.upload(video, {"title": "t", "description": "", "tags": []}, print)
    assert sent[1].full_url == instagram.RUPLOAD + "C1" and len(sent) == 3   # uri가 없으면 rupload 주소


def test_publish_lost_response_warns_duplicate(ig, monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    fake(monkeypatch, ok({"id": "C1"}), ok({}), ok({"status_code": "FINISHED"}), TimeoutError())
    with pytest.raises(RuntimeError, match="먼저 확인"):
        ig.upload(video, {"title": "t", "description": "", "tags": []}, print)


def test_graph_error_never_shows_token(ig, monkeypatch):
    err = graph_error(400, {"error": {"code": 190, "message": "bad token PAGE-TOKEN"}})
    fake(monkeypatch, err)
    with pytest.raises(RuntimeError) as e:
        ig.link("M1")
    assert str(e.value) == "Instagram 요청 실패(190: bad token ***)"


def test_set_thumbnail_explains_first_frame(ig):
    with pytest.raises(RuntimeError, match="첫 프레임"):
        ig.set_thumbnail("M1", ig.token)


def test_login_picks_page_and_saves_private_token(tmp_path, monkeypatch):
    monkeypatch.setenv("META_APP_ID", "APP")
    monkeypatch.setenv("META_APP_SECRET", "APPSECRET")
    monkeypatch.setattr(instagram.getpass, "getpass", lambda prompt: " SHORT ")
    monkeypatch.setattr("builtins.input", lambda prompt: "2")
    pages = {"data": [{"id": "P0", "name": "페이지 없음"},   # 인스타 계정이 없는 페이지는 고를 수 없다
                      {"id": "P1", "name": "A", "access_token": "PT1",
                       "instagram_business_account": {"id": "IG1", "username": "a"}},
                      {"id": "P2", "name": "B", "access_token": "PT2",
                       "instagram_business_account": {"id": "IG2", "username": "b"}}]}
    sent = fake(monkeypatch, ok({"access_token": "LONG"}), ok(pages))
    token = tmp_path / "ch1" / "instagram_token.json"
    assert Instagram(token, channel="ch1").login() == "b"
    assert "fb_exchange_token=SHORT" in sent[0].full_url and sent[1].get_header("Authorization") == "OAuth LONG"
    assert json.loads(token.read_text()) == {"page_id": "P2", "ig_user_id": "IG2", "username": "b",
                                             "page_token": "PT2"}
    assert token.stat().st_mode & 0o777 == 0o600 and token.parent.stat().st_mode & 0o777 == 0o700


def test_login_exchange_error_hides_app_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("META_APP_ID", "APP")
    monkeypatch.setenv("META_APP_SECRET", "APPSECRET")
    monkeypatch.setattr(instagram.getpass, "getpass", lambda prompt: "SHORT")
    fake(monkeypatch, graph_error(400, {"error": {"code": 1, "message": "secret APPSECRET token SHORT"}}))
    with pytest.raises(RuntimeError) as e:
        Instagram(tmp_path / "t.json", channel="ch1").login()
    assert "APPSECRET" not in str(e.value) and "SHORT" not in str(e.value)

import io
import json
from urllib.error import HTTPError

import pytest

from shorts_printer.adapters import youtube, youtube_analytics
from shorts_printer.adapters.youtube_analytics import YouTubeAnalytics


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, reason):
    body = json.dumps({"error": {"message": "m", "errors": [{"reason": reason}]}}).encode()
    return HTTPError("https://x", code, "err", {}, io.BytesIO(body))


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_analytics.time, "sleep", lambda s: None)
    refreshed = []

    def refresh(token):
        refreshed.append(token)
        return {"access_token": f"tok{len(refreshed)}", "expires_in": 3600, "scope": youtube.SCOPE}
    monkeypatch.setattr(youtube, "refresh", refresh)
    a = YouTubeAnalytics(tmp_path / "youtube_token.json", "ko-test")
    a.refreshed = refreshed
    return a


def test_get_sends_bearer_caches_and_keeps_token_out_of_result(api, monkeypatch):
    seen = []

    def fake(req, timeout):
        seen.append((req.full_url, req.get_header("Authorization")))
        return Resp(b'{"items": [1]}')
    monkeypatch.setattr(youtube_analytics, "urlopen", fake)
    got = api.data("channels", mine="true", part="snippet")
    assert got["items"] == [1] and "fetched_at" in got and "tok1" not in json.dumps(got)
    assert seen == [("https://www.googleapis.com/youtube/v3/channels?mine=true&part=snippet", "Bearer tok1")]
    got["items"].append(2)   # 돌려준 값을 바꿔도 캐시는 그대로
    assert api.data("channels", mine="true", part="snippet")["items"] == [1] and len(seen) == 1
    with pytest.raises(ValueError):
        api.data("search", q="x")   # 할당량 100짜리 검색은 읽지 않는다


def test_retries_server_errors_then_refreshes_once_on_401(api, monkeypatch):
    calls = []

    def fake(req, timeout):
        calls.append(req.get_header("Authorization"))
        if len(calls) == 1:
            raise http_error(401, "authError")
        if len(calls) == 2:
            raise http_error(503, "backendError")
        return Resp(b"{}")
    monkeypatch.setattr(youtube_analytics, "urlopen", fake)
    api.report(ids="channel==UC1", metrics="views")
    assert calls == ["Bearer tok1", "Bearer tok2", "Bearer tok2"]


def test_missing_scope_and_disabled_api_say_what_to_do(api, monkeypatch):
    monkeypatch.setattr(youtube, "refresh", lambda t: {"access_token": "t", "scope": youtube.CAPTION_SCOPE})
    with pytest.raises(RuntimeError, match="sp youtube-login --channel ko-test"):
        api.report(ids="channel==UC1")
    monkeypatch.setattr(youtube, "refresh", lambda t: {"access_token": "t", "scope": youtube.SCOPE})
    monkeypatch.setattr(youtube_analytics, "urlopen", lambda req, timeout: (_ for _ in ()).throw(
        http_error(403, "accessNotConfigured")))
    with pytest.raises(RuntimeError, match="YouTube Analytics API를 켜야"):
        api.report(ids="channel==UC1")
    monkeypatch.setattr(youtube_analytics, "urlopen", lambda req, timeout: (_ for _ in ()).throw(
        http_error(403, "insufficientPermissions")))
    with pytest.raises(RuntimeError, match="권한이 없어요"):
        api.report(ids="channel==UC2")


def test_expired_login_names_the_channel(api, monkeypatch):
    def expired(token):
        raise youtube.Expired("x")
    monkeypatch.setattr(youtube, "refresh", expired)
    with pytest.raises(RuntimeError, match="ko-test"):
        api.data("videos", id="A")


def test_login_asks_for_analytics_scope():
    assert youtube.ANALYTICS_SCOPE in youtube.SCOPE.split() and youtube.CAPTION_SCOPE in youtube.SCOPE.split()

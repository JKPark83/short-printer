import io
import json

import pytest

from shorts_printer import footage

SEARCH = json.dumps({"videos": [{"id": 1, "url": "u", "image": "i", "duration": 5, "user": {"name": "n", "url": "uu"},
                                 "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "L"}]}]})


class Cut(io.BytesIO):
    length = 99   # urllib이 남은 바이트로 들고 있는 값: 서버가 보낸다던 만큼 다 못 받았다


def test_truncated_download_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(footage, "_open", lambda url, **h: Cut(b"x") if url == "L" else io.BytesIO(SEARCH.encode()))
    monkeypatch.setenv("PEXELS_API_KEY", "k")
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="끝까지"):
        list(footage.Stock().make([{"i": 0, "file": "clip0.mp4", "term": "cat"}], tmp_path, print))
    assert not (tmp_path / "clip0.mp4").exists()   # 덜 받은 파일은 장면 자리에 두지 않는다


class Done(io.BytesIO):
    length = None   # 다 받았다


def test_pixabay_prefers_vertical_and_caches_search(monkeypatch, tmp_path):
    def hit(i, **videos):
        return {"id": i, "pageURL": f"p{i}", "user": "u", "user_id": 7, "duration": 9, "videos": videos}
    wide = hit(1, large={"url": "", "width": 0, "height": 0}, medium={"url": "W", "width": 1920, "height": 1080})
    tall = hit(2, large={"url": "T4K", "width": 2160, "height": 3840}, medium={"url": "T", "width": 1080, "height": 1920})
    calls = []

    def fake_open(url, **h):
        calls.append(url)
        return Done(json.dumps({"hits": [wide, tall]}).encode() if url.startswith(footage.PIXABAY) else b"mp4")

    monkeypatch.setattr(footage, "_open", fake_open)
    monkeypatch.setenv("PIXABAY_API_KEY", "k")
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert footage.source() == "Pixabay"
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
    clips = list(footage.Stock().make([{"i": 0, "file": "clip0.mp4", "term": "cat"},
                                       {"i": 1, "file": "clip1.mp4", "term": "dog"}], tmp_path / "a", print))
    assert calls[1] == "T"   # 세로 영상, 긴 변이 1920에 가까운 크기
    assert calls[3] == "W"   # 이미 쓴 영상은 건너뛰고, 빈 large는 고르지 않는다
    assert clips[0]["source"] == "Pixabay" and clips[0]["user_url"] == "https://pixabay.com/users/u-7/"
    list(footage.Stock().make([{"i": 0, "file": "clip0.mp4", "term": "cat"}], tmp_path / "b", print))
    assert sum(u.startswith(footage.PIXABAY) for u in calls) == 2   # cat은 캐시에서 읽는다


def test_stock_skips_scene_without_term(monkeypatch, tmp_path):
    calls, logs = [], []
    monkeypatch.setattr(footage, "_open", lambda url, **h: calls.append(url))
    monkeypatch.setenv("PEXELS_API_KEY", "k")
    assert list(footage.Stock().make([{"i": 0, "file": "clip0.mp4", "term": None}], tmp_path, logs.append)) == []
    assert "결과 없음" in logs[0] and calls == []

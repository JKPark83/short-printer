import io
import json
from urllib.error import HTTPError

import pytest

from shorts_printer.infra import media


def test_fetch_photo_takes_first_public_domain_jpg_that_is_not_a_map(monkeypatch, tmp_path):
    def page(i, title, lic, taken="Taken on 15 September 1950"):
        return {"index": i, "title": title, "imageinfo": [{
            "thumburl": f"https://x/{i}.jpg", "descriptionurl": f"https://d/{i}",
            "thumbwidth": 1280, "thumbheight": 900,
            "extmetadata": {"LicenseShortName": {"value": lic}, "DateTimeOriginal": {"value": taken}}}]}
    pages = [page(1, "File:Korea map 1950.jpg", "Public domain"),   # 지도라 뺀다
             page(-1, "File:Admiralty Chart No 2991.jpg", "Public domain"),   # 해도도 지도
             page(0, "File:Recapture Run.jpg", "Public domain", "Taken on 18 September 2026"),   # 요즘 기념행사
             page(2, "File:Seoul.jpg", "CC BY-SA 4.0"),             # 출처 표시가 필요한 사진은 뺀다
             page(3, "File:Seoul.png", "Public domain"),            # jpg만
             page(4, "File:Han river bridge.jpg", "Public domain", "")]
    calls = []

    def urlopen(req, timeout):
        calls.append(req.full_url)
        body = json.dumps({"query": {"pages": {str(p["index"]): p for p in pages}}}).encode() \
            if len(calls) == 1 else b"JPEG"
        return io.BytesIO(body)
    monkeypatch.setattr(media, "urlopen", urlopen)

    got = media.fetch_photo("Han river bridge 1950", tmp_path / "p.jpg")
    assert got == {"title": "File:Han river bridge.jpg", "license": "Public domain", "url": "https://d/4",
                   "width": 1280, "height": 900}
    assert calls[1] == "https://x/4.jpg" and (tmp_path / "p.jpg").read_bytes() == b"JPEG"

    pages[:] = pages[:4]
    calls.clear()
    assert media.fetch_photo("nothing 1950", tmp_path / "q.jpg") is None and not (tmp_path / "q.jpg").exists()


def test_fetch_photo_drops_trailing_words_until_found(monkeypatch, tmp_path):
    asked = []

    def commons(query, years, dst, width):
        asked.append(query)
        return {"title": "File:Seoul Pungnap-dong Toseong-1.JPG"} if query == "Pungnaptoseong" else None
    monkeypatch.setattr(media, "_commons", commons)
    monkeypatch.setattr(media.time, "sleep", lambda s: None)
    assert media.fetch_photo("Pungnaptoseong Baekje earthen wall", tmp_path / "p.jpg")
    assert asked == ["Pungnaptoseong Baekje earthen wall", "Pungnaptoseong Baekje earthen", "Pungnaptoseong Baekje",
                     "Pungnaptoseong"]
    asked.clear()   # 짧은 낱말 하나로는 찾지 않는다
    assert media.fetch_photo("Xue Rengui portrait", tmp_path / "q.jpg") is None
    assert asked == ["Xue Rengui portrait", "Xue Rengui"]


def test_get_waits_and_retries_when_commons_says_429(monkeypatch):
    calls, waits = [], []

    def urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return io.BytesIO(b"ok")
    monkeypatch.setattr(media, "urlopen", urlopen)
    monkeypatch.setattr(media.time, "sleep", waits.append)
    assert media._get("https://x", 30) == b"ok" and waits == [5, 20]

    def gone(req, timeout):
        raise HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(media, "urlopen", gone)
    with pytest.raises(HTTPError):   # 429가 아니면 다시 묻지 않는다
        media._get("https://x", 30)

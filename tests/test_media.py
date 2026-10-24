import io
import json

from shorts_printer.infra import media


def test_fetch_photo_takes_first_public_domain_jpg_that_is_not_a_map(monkeypatch, tmp_path):
    def page(i, title, lic, taken="Taken on 15 September 1950"):
        return {"index": i, "title": title, "imageinfo": [{
            "thumburl": f"https://x/{i}.jpg", "descriptionurl": f"https://d/{i}",
            "thumbwidth": 1280, "thumbheight": 900,
            "extmetadata": {"LicenseShortName": {"value": lic}, "DateTimeOriginal": {"value": taken}}}]}
    pages = [page(1, "File:Korea map 1950.jpg", "Public domain"),   # 지도라 뺀다
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

import base64

import pytest

from shorts_printer.adapters import flow_auto
from shorts_printer.adapters.flow_auto import _count, _download, _ok_index, _refetch, _state


def test_state_reads_only_the_front_tile():
    assert _state([{"done": False, "error": None}, {"done": True, "error": None}]) is None   # 만드는 중
    assert _state([{"done": True, "error": None}]) == ("done", "")
    assert _state([{"done": False, "error": "막힘"}, {"done": True, "error": None}]) == ("error", "막힘")


def test_count_reads_credit_label():
    assert _count("Google Flow 크레딧 5,883개") == 5883
    with pytest.raises(RuntimeError):
        _count("Google Flow 크레딧")


class _Page:
    """타일이 끝난 바로 뒤에는 빈 영상을 주다가 sizes 순서대로 받기를 돌려준다."""

    def __init__(self, sizes, stuck=False):
        self.sizes, self.waits, self.stuck, self.keys, self.texts = list(sizes), [], stuck, [], []
        self.keyboard = self

    def press(self, key):
        self.keys.append(key)

    def locator(self, *a, **k):
        self.texts.append(k.get("has_text"))
        return self

    def filter(self, **k):
        self.texts.append(k.get("has_text"))
        return self

    first = property(lambda self: self)

    def nth(self, i):
        self.picked = i
        return self

    def hover(self):
        pass

    def click(self):
        if self.stuck:   # 메뉴 항목이 늦게 떠 누르지 못함
            raise TimeoutError("Locator.click: Timeout 30000ms exceeded.")

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def evaluate(self, js, url):   # READ_BLOB: 페이지가 받아 둔 영상을 base64로
        return base64.b64encode(b"x" * self.sizes.pop(0)).decode()

    def expect_download(self, timeout):

        class D:
            url = "blob:https://flow.google.com/x"

        class Ctx:
            value = D()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Ctx()


def test_download_retries_empty_blob_without_regenerating(tmp_path, monkeypatch):
    monkeypatch.setattr(flow_auto, "_wait", lambda *a: ("done", ""))
    page = _Page([0, 0, 7])
    _download(page, tmp_path / "clip0.mp4")
    assert (tmp_path / "clip0.mp4").stat().st_size == 7 and page.waits == [0, 5000, 15000]
    assert page.texts[-3:] == ["다운로드", "업스케일링됨", "720p"]   # 무료 720p 업스케일로 받는다

    with pytest.raises(RuntimeError, match="0바이트"):
        _download(_Page([0, 0, 0, 0]), tmp_path / "clip1.mp4")
    assert list(tmp_path.iterdir()) == [tmp_path / "clip0.mp4"]


def test_download_closes_menu_when_click_fails(tmp_path, monkeypatch):
    """받기 메뉴를 못 누르면 열린 메뉴를 닫고 던진다. 안 닫으면 다음 장면이 프롬프트 칸을 못 누른다."""
    monkeypatch.setattr(flow_auto, "_wait", lambda *a: ("done", ""))
    page = _Page([7], stuck=True)
    with pytest.raises(TimeoutError):
        _download(page, tmp_path / "clip0.mp4")
    assert page.keys == ["Escape", "Escape"]


def test_refetch_finds_lost_tile_by_position_skipping_refused():
    """오래된 쪽부터 0·1번은 받음, 2번(거절) 뒤 3번째로 넣은 타일을 놓쳤다 → 새로 불러온 화면에서 그 타일을 받는다."""
    ok, bad = {"done": True, "error": None}, {"done": False, "error": "막힘"}
    tiles = [ok, ok, bad, ok, ok]   # 앞이 새것: [3번 뒤 것, 놓친 것, 거절, 1번, 0번]
    assert _ok_index(tiles, 2) == 1 and _ok_index(tiles, 0) == 4 and _ok_index(tiles, 4) is None
    assert _ok_index([ok, ok, ok, ok], 2) == 1   # 새로 불러와 거절 타일이 사라져도 같은 타일


def test_refetch_downloads_that_tile(tmp_path, monkeypatch):
    ok = {"done": True, "error": None}
    monkeypatch.setattr(flow_auto, "_wait", lambda page, until, timeout: until([ok, ok, ok]))
    page = _Page([5])
    _refetch(page, 1, tmp_path / "clip3.mp4")
    assert page.picked == 1 and (tmp_path / "clip3.mp4").stat().st_size == 5


class Page:
    """_settings가 쓰는 Playwright 페이지 대신. 누른 radio 이름을 모으고 설정 버튼 글자를 돌려준다."""

    def __init__(self, label):
        self.label, self.clicked = label, []
        self.keyboard = self

    def locator(self, sel, has_text=None):
        return El(self, sel, has_text)

    def get_by_text(self, text, exact=False):
        return El(self, "", text)

    def press(self, key):
        pass


class El:
    def __init__(self, page, sel, text):
        self.page, self.sel, self.text = page, sel, text
        self.first = self.last = self

    def wait_for(self, timeout=None):
        pass

    def get_attribute(self, name):
        return "false"

    def click(self):
        if self.text:
            self.page.clicked.append(self.text)

    def inner_text(self):
        return flow_auto.MODEL if "모델" in self.sel else self.page.label


def test_aspect_defaults_to_shorts_and_long_form_picks_16_9():
    assert flow_auto.FlowAuto().aspect == "9:16" and flow_auto.FlowAuto("16:9").aspect == "16:9"
    page = Page("동영상 crop_16_9 360p 8초 x1")
    flow_auto._settings(page, "16:9")
    assert page.clicked == ["동영상", "소재", "16:9", "360p", "8초", "x1"]
    with pytest.raises(RuntimeError, match="Flow 설정을 맞추지 못했어요"):   # 화면비가 안 바뀌면 멈춘다
        flow_auto._settings(Page("동영상 crop_9_16 360p 8초 x1"), "16:9")

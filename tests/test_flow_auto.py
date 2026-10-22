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

    def __init__(self, sizes):
        self.sizes, self.waits = list(sizes), []

    def locator(self, *a, **k):
        return self

    def filter(self, **k):
        return self

    first = property(lambda self: self)

    def nth(self, i):
        self.picked = i
        return self

    def hover(self):
        pass

    def click(self):
        pass

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

    with pytest.raises(RuntimeError, match="0바이트"):
        _download(_Page([0, 0, 0, 0]), tmp_path / "clip1.mp4")
    assert list(tmp_path.iterdir()) == [tmp_path / "clip0.mp4"]


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

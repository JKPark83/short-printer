import pytest

from shorts_printer.adapters import flow_auto
from shorts_printer.adapters.flow_auto import _count, _download, _state


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

    def hover(self):
        pass

    def click(self):
        pass

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def expect_download(self, timeout):
        page = self

        class D:
            def failure(self):
                return None

            def save_as(self, to):
                to.write_bytes(b"x" * page.sizes.pop(0))

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

import pytest

from shorts_printer import config


@pytest.fixture(autouse=True)
def jobs_dir(tmp_path, monkeypatch):
    """작업·주제 찾기 폴더를 테스트마다 비운 임시 폴더로 돌린다."""
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(config, "TRENDS_DIR", tmp_path / "trends")
    return tmp_path / "jobs"

import pytest

from shorts_printer import config
from shorts_printer.infra import store
from shorts_printer.infra.sqlite import SQLiteStore


@pytest.fixture(autouse=True)
def jobs_dir(tmp_path, monkeypatch):
    """작업·주제 찾기·스케줄 폴더를 테스트마다 비운 임시 폴더로 돌린다."""
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(config, "TRENDS_DIR", tmp_path / "trends")
    monkeypatch.setattr(config, "SCHEDULES_DIR", tmp_path / "schedules")
    return tmp_path / "jobs"


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """테스트마다 빈 임시 DB를 건다(진짜 shorts.db는 열지 않는다)."""
    monkeypatch.setattr(config, "DB", tmp_path / "shorts.db")
    s = SQLiteStore(config.DB)
    monkeypatch.setattr(store, "_STORE", s)
    yield s
    s.close()


@pytest.fixture(autouse=True)
def no_notify(monkeypatch):
    """.env에 알림 설정이 있어도 테스트가 진짜 Discord·Telegram으로 보내지 않게 한다."""
    for name in ("DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)

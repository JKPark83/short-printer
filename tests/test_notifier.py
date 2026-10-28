import json
from contextlib import nullcontext
from urllib.error import HTTPError, URLError

import pytest

from shorts_printer import registry
from shorts_printer.adapters import discord
from shorts_printer.adapters.discord import Discord
from shorts_printer.adapters.telegram import Telegram
from shorts_printer.infra import store

HOOK = "https://discord.com/api/webhooks/1/SECRET-hook"
TOKEN = "123:SECRET-bot-token"


@pytest.fixture
def posted(monkeypatch):
    out = []

    def fake(req, timeout):
        out.append((req.full_url, json.loads(req.data), req.get_header("User-agent"), timeout))
        return nullcontext()
    monkeypatch.setattr(discord, "urlopen", fake)
    return out


def test_discord_payload_truncated(monkeypatch, posted):
    assert not Discord().ready()
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", HOOK)
    assert Discord().ready()
    Discord().send("가" * 3000)
    url, body, ua, timeout = posted[0]
    assert url == HOOK and ua == "shorts-printer" and timeout == 10
    assert body == {"content": "가" * 2000, "allowed_mentions": {"parse": []}}


def test_telegram_payload(monkeypatch, posted):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    assert not Telegram().ready()   # chat id도 있어야 한다
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    Telegram().send("나" * 5000)
    url, body, _, _ = posted[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert body == {"chat_id": "42", "text": "나" * 4096, "disable_web_page_preview": True}


@pytest.mark.parametrize("error", [HTTPError(HOOK, 404, "Not Found", {}, None), URLError(f"bad {HOOK}")])
def test_errors_hide_secret(monkeypatch, error):
    def fake(req, timeout):
        raise error
    monkeypatch.setattr(discord, "urlopen", fake)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", HOOK)
    with pytest.raises(RuntimeError, match="Discord 알림을 못 보냈어요") as e:
        Discord().send("x")
    assert "SECRET" not in str(e.value)


def test_redact_token_and_webhook(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", HOOK)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    assert store.redact(f"{HOOK} {TOKEN}") == "*** ***"


class Fake:
    def __init__(self, label, ready=True, fail=False):
        self.label, self.hint, self._ready, self.fail, self.got = label, "", ready, fail, []

    def ready(self):
        return self._ready

    def send(self, text):
        if self.fail:
            raise RuntimeError(f"실패 {TOKEN}")
        self.got.append(text)


def test_notify_sends_to_ready_and_swallows_errors(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    ok, off, bad = Fake("A"), Fake("B", ready=False), Fake("C", fail=True)
    monkeypatch.setattr(registry, "NOTIFIERS", {"a": ok, "b": off, "c": bad})
    assert registry.notify("안녕") == [("A", None), ("C", "실패 ***")]
    assert ok.got == ["안녕"] and off.got == []

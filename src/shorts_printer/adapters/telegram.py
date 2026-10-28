"""Telegram 봇 알림(Notifier 포트)."""
from .. import config
from .discord import post

API = "https://api.telegram.org/bot{}/sendMessage"
MAX = 4096   # sendMessage text 한도


class Telegram:
    label = "Telegram"
    hint = ".env에 TELEGRAM_BOT_TOKEN(@BotFather)·TELEGRAM_CHAT_ID(getUpdates)"

    def ready(self) -> bool:
        return bool(config.secret("TELEGRAM_BOT_TOKEN") and config.secret("TELEGRAM_CHAT_ID"))

    def send(self, text: str) -> None:
        post(API.format(config.secret("TELEGRAM_BOT_TOKEN")),
             {"chat_id": config.secret("TELEGRAM_CHAT_ID"), "text": text[:MAX], "disable_web_page_preview": True},
             self.label)

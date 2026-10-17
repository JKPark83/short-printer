"""Discord 웹훅 알림(Notifier 포트)."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import config

MAX = 2000   # Discord content 한도


def post(url: str, body: dict, what: str) -> None:
    """JSON POST. 오류 문구에 URL(키가 들어 있다)을 넣지 않는다. Telegram도 같이 쓴다."""
    req = Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "User-Agent": "shorts-printer"})   # 기본 UA는 Discord가 막는다
    try:
        with urlopen(req, timeout=10):
            pass
    except HTTPError as e:
        raise RuntimeError(f"{what} 알림을 못 보냈어요(HTTP {e.code}). 설정 값을 확인하세요.") from None
    except (URLError, TimeoutError) as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(f"{what} 알림을 못 보냈어요({type(reason).__name__}). 네트워크를 확인하세요.") from None


class Discord:
    label = "Discord"
    hint = ".env에 DISCORD_WEBHOOK_URL(채널 설정 → 연동 → 웹후크)"

    def ready(self) -> bool:
        return bool(config.secret("DISCORD_WEBHOOK_URL"))

    def send(self, text: str) -> None:
        # 주제·제목은 LLM·웹 검색·사용자 글에서 오므로 @everyone 같은 멘션이 울리지 않게 막는다
        body = {"content": text[:MAX], "allowed_mentions": {"parse": []}}
        post(config.secret("DISCORD_WEBHOOK_URL"), body, self.label)

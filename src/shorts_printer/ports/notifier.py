"""알림 포트: 스케줄 작업의 결과를 사람에게 보낸다. 채널이 아니라 전역(.env)."""
from typing import Protocol


class Notifier(Protocol):
    label: str   # 화면 이름
    hint: str    # 환경 점검 한 줄(준비 안 됐을 때 할 일)

    def ready(self) -> bool: ...

    def send(self, text: str) -> None:
        """글 하나를 보낸다. 실패하면 한국어 RuntimeError. 키·URL은 메시지에 넣지 않는다."""

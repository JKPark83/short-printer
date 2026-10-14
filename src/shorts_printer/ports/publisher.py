"""업로드 포트. 채널 하나에 하나(registry가 채널 계정으로 만든다)."""
from pathlib import Path
from typing import Protocol


class Publisher(Protocol):
    label: str   # 화면 이름
    hint: str    # 환경 점검 한 줄(준비 안 됐을 때 할 일)

    def ready(self) -> bool: ...

    def upload(self, path: Path, meta: dict, log) -> str:
        """meta = {"title", "description", "tags"}. 비공개로 올리고 영상 id를 돌려준다.
        대체 경로를 쓰면 log에 남긴다."""

    def set_thumbnail(self, video_id: str, path: Path) -> None: ...

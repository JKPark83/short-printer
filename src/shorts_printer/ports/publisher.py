"""업로드 포트. 채널 하나에 하나(registry가 채널 계정으로 만든다). 채널의 주 업로드 공급자 말고도
publish.also로 더 올리는 곳을 둘 수 있다."""
from pathlib import Path
from typing import Protocol


class Publisher(Protocol):
    label: str   # 화면 이름
    hint: str    # 환경 점검 한 줄(준비 안 됐을 때 할 일)
    private: bool   # 비공개로 올라가나. 비공개 업로드가 없는 곳(Instagram 등)은 바로 공개된다

    def ready(self) -> bool: ...

    def upload(self, path: Path, meta: dict, log) -> str:
        """meta = {"title", "description", "tags"}. 올리고 영상 id를 돌려준다(YouTube는 비공개,
        비공개가 없는 곳은 공개). 대체 경로를 쓰면 log에 남긴다."""

    def set_thumbnail(self, video_id: str, path: Path) -> None: ...

    def link(self, video_id: str) -> str:
        """올린 영상을 보는 주소."""

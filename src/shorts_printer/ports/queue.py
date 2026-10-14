"""작업 큐 포트: 제작·업로드·주제 찾기를 차례로 돈다. 같은 것을 두 번 넣지 않는다."""
from threading import RLock
from typing import Protocol


class Queue(Protocol):
    lock: RLock   # 검사와 쓰기를 한 번에 할 때(웹이 클립 교체·삭제에 쓴다)

    def start(self) -> None: ...

    def enqueue(self, job_id: str) -> bool: ...

    def enqueue_upload(self, job_id: str) -> bool: ...

    def redo(self, job_id: str, steps=("thumbnail", "render"), files: dict | None = None, **fields) -> bool: ...

    def enqueue_trend(self, trend_id: str) -> bool: ...

"""저장소 포트: 작업·주제 찾기·스케줄의 상태, JSON 결과물, 로그. 미디어 파일은 폴더에 남는다."""
from collections.abc import Callable
from typing import Protocol


class Store(Protocol):
    """종류(kind: job|trend|schedule)와 id로 찾는 문서 저장소. 값은 JSON으로 바꿀 수 있는 것.
    name ""은 상태 문서, 그 밖은 결과물("script.json" 같은 예전 파일 이름)."""

    def get(self, kind: str, rec_id: str, name: str = "", default=None): ...

    def put(self, kind: str, rec_id: str, value, name: str = "") -> None: ...

    def edit(self, kind: str, rec_id: str, fn: Callable, name: str = ""):
        """읽고 fn(값)으로 바꿔 쓰기를 한 번에(다른 스레드·프로세스가 끼어들지 않게). 쓴 값을 돌려준다."""
        ...

    def ids(self, kind: str) -> list[str]: ...   # 상태 문서가 있는 id, 오름차순(= 만든 시각 순)

    def delete(self, kind: str, rec_id: str) -> None: ...   # 상태·결과물·로그 모두

    def log(self, kind: str, rec_id: str, line: str) -> None: ...

    def tail(self, kind: str, rec_id: str, n: int = 200) -> list[str]: ...   # 마지막 n줄, 오래된 것부터

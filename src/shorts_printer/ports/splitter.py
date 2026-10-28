"""자막 나누기 포트. 언어마다 하나."""
from typing import Protocol


class Splitter(Protocol):
    limit: int   # 자막 한 덩어리 기본 길이(글자). 84px 자막이 한 줄에 들어가는 만큼

    def chunks(self, text: str, limit: int) -> list[str]:
        """text를 limit 이하 덩어리로. 이어 붙이면(언어의 띄어쓰기 규칙대로) 원문이 된다.
        limit보다 긴 낱말은 그대로 한 덩어리."""

    def width(self, text: str) -> float:
        """글자 크기 1일 때 굵은 글씨 폭(대략). 썸네일·제목 글자 크기를 정한다."""

"""채널 성과 읽기 포트. YouTube Data API와 Analytics API의 GET만 감싼다(쓰기 없음).
응답 해석(기간·이전 기간 대비·no_data와 실제 0 구분)은 core.insights가 한다."""
from typing import Protocol


class ChannelAnalytics(Protocol):
    label: str

    @property
    def hint(self) -> str: ...

    def ready(self) -> bool:
        """토큰·클라이언트 파일이 있는지만 본다(네트워크 호출 금지)."""
        ...

    def data(self, resource: str, **params) -> dict:
        """YouTube Data API v3 GET(channels·videos·playlistItems). 응답 JSON에 fetched_at(UTC ISO)을 더한다."""
        ...

    def report(self, **params) -> dict:
        """YouTube Analytics API v2 reports GET. columnHeaders·rows 그대로 + fetched_at."""
        ...

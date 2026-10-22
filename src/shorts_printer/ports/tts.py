"""음성(TTS) 포트."""
from pathlib import Path
from typing import Protocol


class TTS(Protocol):
    label: str   # 화면 이름. 음성 단계 engine으로도 남는다
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    # 선택: 크레딧을 세는 유료 공급자만 둔다. 있으면 대시보드에 남은 크레딧·만들 수 있는 편수가 뜬다
    # credits() -> int: 남은 크레딧(못 읽으면 한국어 RuntimeError). cost(n: int) -> int: 글자 n개에 드는 크레딧

    def speak(self, voice: str, text: str, out: Path) -> tuple[Path, list[dict] | None]:
        """text를 voice(채널 channel.toml의 목소리 키)로 읽어 out의 확장자만 바꾼 파일에 쓴다.
        (쓴 파일, 낱말 시각). 낱말 시각은 띄어쓰기 단위 [{"text", "start"(초)}], 모르면 None.
        오류는 한국어 RuntimeError."""

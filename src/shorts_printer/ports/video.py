"""영상 공급자 포트. 장면(문장)마다 클립 하나를 clips/clip{i}.mp4에 둔다."""
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol


class VideoProvider(Protocol):
    label: str   # 화면·clips.json source
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    # 선택: 크레딧을 세는 유료 공급자만 둔다. 있으면 대시보드에 남은 크레딧·만들 수 있는 편수가 뜬다
    # credits() -> int: 남은 크레딧(못 읽으면 한국어 RuntimeError). cost(n: int) -> int: 장면 n개에 드는 크레딧
    # 선택: image(prompt, path, log) -> bool: 16:9 이미지 하나를 path에. 무료일 때만 만들고 아니면 False(롱폼 썸네일)

    def make(self, scenes: list[dict], out: Path, log) -> Iterable[dict]:
        """없는 장면만 온다({i, file, sentence, prompt, sec}). 만든 것은 out/장면 file에 원자적으로 쓰고
        하나마다 clips.json 항목을 yield.
        못 만든 장면은 log 남기고 건너뛴다(사람이 올린다). 일시 오류는 안에서 재시도, 인증 오류는 던진다.
        결과는 1080x880 가운데로 잘린다: 소리 없이."""


class Refused(RuntimeError):
    """공급자가 정책으로 장면을 거절했다. 같은 프롬프트로는 또 거절되므로 core가 프롬프트를 고쳐 다시 시도한다.
    scenes = {장면 번호(0부터): 거절 사유}."""

    def __init__(self, msg: str, scenes: dict[int, str]):
        super().__init__(msg)
        self.scenes = scenes

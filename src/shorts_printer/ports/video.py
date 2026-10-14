"""영상 공급자 포트. 장면(문장)마다 클립 하나를 clips/clip{i}.mp4에 둔다."""
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol


class VideoProvider(Protocol):
    label: str   # 화면·clips.json source
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    def make(self, scenes: list[dict], out: Path, log) -> Iterable[dict]:
        """없는 장면만 온다({i, file, sentence, prompt, sec}). 만든 것은 out/장면 file에 원자적으로 쓰고
        하나마다 clips.json 항목을 yield.
        못 만든 장면은 log 남기고 건너뛴다(사람이 올린다). 일시 오류는 안에서 재시도, 인증 오류는 던진다.
        결과는 1080x880 가운데로 잘린다: 소리 없이."""

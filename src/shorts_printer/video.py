"""영상 공급자. 장면(문장)마다 클립 하나를 clips/clip{i}.mp4에 둔다.
공급자가 못 만든 장면은 사람이 작업 화면에서 올린다. 새 공급자는 파일 하나 + VIDEO에 한 줄."""
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from . import config, flow_auto, render
from .jobs import atomic_write_json, read_json


class VideoProvider(Protocol):
    label: str   # 화면·clips.json source
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    def make(self, scenes: list[dict], out: Path, log) -> Iterable[dict]:
        """없는 장면만 온다. 만든 것은 out/장면 file에 원자적으로 쓰고 하나마다 clips.json 항목을 yield.
        못 만든 장면(값 None·결과 없음)은 log 남기고 건너뛴다. 일시 오류는 안에서 재시도, 인증 오류는 던진다.
        결과는 1080x880 가운데로 잘린다: 4:3(없으면 16:9), 소리 없이."""


class Flow:
    """Google Flow는 API가 없다. 사람이 장면 프롬프트를 복사해 만들고 올린다."""
    label = "Google Flow"
    hint = "직접 올림 · 장면 프롬프트를 복사해 Flow에서 16:9 · 8초 · 결과 1개로 만들어요"

    def ready(self) -> bool:
        return True

    def make(self, scenes, out, log):
        return ()


VIDEO: dict[str, VideoProvider] = {"flow": Flow(), "flow-auto": flow_auto.FlowAuto()}


def default() -> str:
    """.env SP_VIDEO. 없거나 쓸 수 없으면 Flow."""
    p = VIDEO.get(config.VIDEO)
    return config.VIDEO if p and p.ready() else "flow"


def scenes(script: dict, timing: list[dict] | None) -> list[dict]:
    """대본 → 장면 목록. sec는 렌더가 그 장면을 보여 주는 초(음성 전이면 None)."""
    n = len(script["sentences"])

    def col(key):   # 예전 대본엔 없거나 개수가 다르다
        v = script.get(key) or []
        return v if len(v) == n else [None] * n
    secs = ([k / 30 for k in render.frames([t["start"] for t in timing], timing[-1]["end"] + render.TAIL, n)]
            if timing else [None] * n)
    return [{"i": i, "file": f"clip{i}.mp4", "sentence": s, "prompt": p, "sec": sec}
            for i, (s, p, sec) in enumerate(zip(script["sentences"], col("prompts"), secs))]


def set_clip(job_dir: Path, meta: dict) -> None:
    """clips.json에서 같은 file 항목을 바꿔 넣는다. 공급자와 업로드가 같이 쓴다."""
    clips = {c["file"]: c for c in read_json(job_dir / "clips.json", [])}
    clips[meta["file"]] = meta
    atomic_write_json(job_dir / "clips.json", list(clips.values()))

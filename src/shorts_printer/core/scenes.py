"""대본 → 장면 목록, clips.json 고치기. 장면(문장)마다 클립 하나를 clips/clip{i}.mp4에 둔다.
공급자(ports.video)가 못 만든 장면은 사람이 작업 화면에서 올린다."""
from pathlib import Path

from ..infra.store import atomic_write_json, read_json
from . import render


def scenes(script: dict, timing: list[dict] | None) -> list[dict]:
    """대본 → 장면 목록. sec는 렌더가 그 장면을 보여 주는 초(음성 전이면 None)."""
    n = len(script["sentences"])

    def col(key):   # 예전 대본엔 없거나 개수가 다르다
        v = script.get(key) or []
        return v if len(v) == n else [None] * n
    secs = ([k / 30 for k in render.frames([t["start"] for t in timing], timing[-1]["end"] + render.TAIL, n)]
            if timing else [None] * n)
    return [{"i": i, "file": f"clip{i}.mp4", "sentence": s, "prompt": p, "sec": sec}
            for i, (s, p, sec) in enumerate(zip(script["sentences"], col("prompts"), secs, strict=True))]


def set_clip(job_dir: Path, meta: dict) -> None:
    """clips.json에서 같은 file 항목을 바꿔 넣는다. 공급자와 업로드가 같이 쓴다."""
    clips = {c["file"]: c for c in read_json(job_dir / "clips.json", [])}
    clips[meta["file"]] = meta
    atomic_write_json(job_dir / "clips.json", list(clips.values()))

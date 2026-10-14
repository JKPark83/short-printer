"""작업(job) 폴더, job.json 상태, 원자적 저장."""
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from .. import config


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def redact(text: str) -> str:
    """로그·오류 문구에 키 값이 섞이지 않게 가린다. 새 공급자 키도 이름만 이 규칙을 따르면 된다."""
    for name, key in os.environ.items():
        if name.endswith(("_API_KEY", "_AUTH_TOKEN")) and len(key) >= 8:   # 짧은 값은 아무 낱말이나 가린다
            text = text.replace(key, "***")
    return text


def upload_state(status: str, **fields) -> dict:
    """job.json의 upload 값. 예전 job.json에는 키가 없어서 읽을 때는 data.get("upload")로 본다."""
    return {"status": status, "video_id": None, "error": None, "at": None} | fields


def log_line(job_dir: Path, msg: str) -> None:
    with open(job_dir / "log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S')} {redact(msg)}\n")


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


@dataclass
class Record:
    """폴더 하나 + 상태 json 하나. 작업(pipeline.Job)과 주제 분석(trends.Trend)이 같이 쓴다."""
    id: str
    dir: Path
    FILE: ClassVar[str] = "job.json"
    WHAT: ClassVar[str] = "작업"
    EXTRA: ClassVar[dict] = {}   # 종류마다 더 두는 필드

    @classmethod
    def root(cls) -> Path:
        return config.JOBS_DIR   # 테스트가 config 값을 바꾸므로 부를 때마다 읽는다

    @property
    def data(self) -> dict:
        return read_json(self.dir / self.FILE)

    def update(self, **fields) -> dict:
        data = self.data | fields
        atomic_write_json(self.dir / self.FILE, data)
        return data

    def step(self, name: str, **fields) -> None:
        steps = self.data["steps"]
        steps[name] |= fields
        self.update(steps=steps)

    def log(self, msg: str) -> None:
        log_line(self.dir, msg)

    def interrupt(self) -> None:
        """대기·진행 중이던 것을 interrupted로(돌던 단계는 pending). 앱이 켜질 때 부른다."""
        d = self.data
        if d["status"] in ("queued", "running"):
            self.update(status="interrupted", steps={k: v | {"status": "pending"} if v["status"] == "running" else v
                                                     for k, v in d["steps"].items()})

    @classmethod
    def _new(cls, steps, **fields) -> "Record":
        rec_id = new_id()
        rec = cls(rec_id, cls.root() / rec_id)
        rec.dir.mkdir(parents=True)
        atomic_write_json(rec.dir / cls.FILE, {
            "id": rec_id, **fields, "status": "draft",
            "steps": {s: {"status": "pending", "engine": None, "sec": None} for s in steps},
            "notices": [], "error": None, "usage": None, **cls.EXTRA,
            "created_at": now(), "finished_at": None,
        })
        return rec

    @classmethod
    def load(cls, rec_id: str):
        d = cls.root() / rec_id
        if not (d / cls.FILE).exists():
            raise FileNotFoundError(f"{cls.WHAT}이 없어요: {rec_id}")
        return cls(rec_id, d)

    @classmethod
    def all(cls) -> list:
        root = cls.root()
        if not root.exists():
            return []
        return [cls(p.parent.name, p.parent) for p in sorted(root.glob(f"*/{cls.FILE}"))]

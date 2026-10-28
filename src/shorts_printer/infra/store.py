"""작업·주제 찾기·스케줄 기록(Record)과 저장소 연결, 예전 폴더 옮기기, 원자적 저장."""
import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from .. import config
from ..ports.store import Store


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
        # 짧은 값은 아무 낱말이나 가린다
        if name.endswith(("_API_KEY", "_TOKEN", "_WEBHOOK_URL", "_SECRET")) and len(key) >= 8:
            text = text.replace(key, "***")
    return text


def upload_state(status: str, **fields) -> dict:
    """job.json의 upload 값. 예전 job.json에는 키가 없어서 읽을 때는 data.get("upload")로 본다."""
    return {"status": status, "video_id": None, "error": None, "at": None} | fields


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


_STORE: Store | None = None


def use(s: Store) -> None:
    """Record가 쓸 저장소를 건다. registry가 켤 때, 테스트 conftest가 테스트마다 부른다."""
    global _STORE
    _STORE = s


def store() -> Store:
    if _STORE is None:
        raise RuntimeError("저장소가 연결되지 않았어요. registry를 먼저 불러오세요")
    return _STORE


@dataclass
class Record:
    """상태 문서 + JSON 결과물 + 로그(저장소)와 미디어 폴더(dir). 작업·주제 찾기·스케줄이 같이 쓴다."""
    id: str
    KIND: ClassVar[str] = "job"   # 저장소 종류. 예전 폴더의 상태 파일 이름은 f"{KIND}.json"
    WHAT: ClassVar[str] = "작업"
    EXTRA: ClassVar[dict] = {}   # 종류마다 더 두는 필드

    @classmethod
    def root(cls) -> Path:
        return config.JOBS_DIR   # 테스트가 config 값을 바꾸므로 부를 때마다 읽는다

    @property
    def dir(self) -> Path:
        """미디어 폴더. 처음 쓸 때 만든다(지운 기록은 다시 만들지 않는다)."""
        d = self.root() / self.id
        if not d.exists() and store().get(self.KIND, self.id) is not None:
            d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _fix(d: dict) -> dict:
        """예전 상태 문서를 지금 모양으로(읽을 때와 고칠 때 모두). 종류마다 덮어쓴다."""
        return d

    @property
    def data(self) -> dict:
        d = store().get(self.KIND, self.id)
        return self._fix(d) if d is not None else d

    def update(self, **fields) -> dict:
        """읽고 고쳐 쓰기를 한 트랜잭션으로(작업 스레드·웹·다른 프로세스가 같이 고쳐도 잃지 않게)."""
        return store().edit(self.KIND, self.id, lambda d: self._fix(d) | fields)

    def step(self, name: str, **fields) -> None:
        def f(d: dict) -> dict:
            d = self._fix(d)
            d["steps"][name] |= fields
            return d
        store().edit(self.KIND, self.id, f)

    def doc(self, name: str, default=None):
        """JSON 결과물. name은 예전 파일 이름("script.json" 등)."""
        return store().get(self.KIND, self.id, name, default)

    def put(self, name: str, value) -> None:
        store().put(self.KIND, self.id, value, name)

    def edit(self, name: str, fn):
        """결과물을 읽고 fn(값, 없으면 None)으로 고쳐 쓰기를 한 트랜잭션으로. 쓴 값을 돌려준다."""
        return store().edit(self.KIND, self.id, fn, name)

    def log(self, msg: str) -> None:
        store().log(self.KIND, self.id, f"{datetime.now().strftime('%H:%M:%S')} {redact(msg)}")

    def tail(self, n: int = 200) -> list[str]:
        return store().tail(self.KIND, self.id, n)

    def delete(self) -> None:
        """저장소 행과 미디어 폴더를 지운다."""
        store().delete(self.KIND, self.id)
        shutil.rmtree(self.root() / self.id, ignore_errors=True)

    def interrupt(self) -> None:
        """대기·진행 중이던 것을 interrupted로(돌던 단계는 pending). 앱이 켜질 때 부른다."""
        d = self.data
        if d["status"] in ("queued", "running"):
            self.update(status="interrupted", steps={k: v | {"status": "pending"} if v["status"] == "running" else v
                                                     for k, v in d["steps"].items()})

    @classmethod
    def _new(cls, steps, **fields) -> "Record":
        rec = cls(new_id())
        store().put(cls.KIND, rec.id, {
            "id": rec.id, **fields, "status": "draft",
            "steps": {s: {"status": "pending", "engine": None, "sec": None} for s in steps},
            "notices": [], "error": None, "usage": None, **cls.EXTRA,
            "created_at": now(), "finished_at": None,
        })
        return rec

    @classmethod
    def load(cls, rec_id: str):
        if store().get(cls.KIND, rec_id) is None:
            raise FileNotFoundError(f"{cls.WHAT}이 없어요: {rec_id}")
        return cls(rec_id)

    @classmethod
    def all(cls) -> list:
        return [cls(i) for i in store().ids(cls.KIND)]


def migrate(roots: dict[str, Path] | None = None) -> dict[str, int]:
    """예전 폴더를 저장소로: <id>/<kind>.json(상태), 같은 폴더의 다른 *.json(결과물), log.txt.
    상태 문서가 이미 있는 id는 건너뛰어 여러 번 돌려도 같다. 원본 파일은 지우지 않는다(백업).
    하위 폴더의 json(손으로 남긴 백업 등)은 코드가 읽지 않아 옮기지 않는다. 돌려주는 값은 종류마다 옮긴 수."""
    roots = roots or {"job": config.JOBS_DIR, "trend": config.TRENDS_DIR, "schedule": config.SCHEDULES_DIR}
    s, out = store(), {}
    for kind, root in roots.items():
        out[kind] = 0
        for state in sorted(root.glob(f"*/{kind}.json")):
            d, rec_id = state.parent, state.parent.name
            if s.get(kind, rec_id) is not None:
                continue
            s.delete(kind, rec_id)   # 지난번에 반쯤 옮기다 멈춘 것(상태 문서를 맨 뒤에 넣으므로)
            for p in sorted(d.glob("*.json")):
                if p != state:
                    s.put(kind, rec_id, read_json(p), p.name)
            if (log := d / "log.txt").exists():
                for line in log.read_text(encoding="utf-8").splitlines():
                    s.log(kind, rec_id, line)
            s.put(kind, rec_id, read_json(state))
            out[kind] += 1
    return out

"""저장소 포트의 SQLite 구현(표준 라이브러리). 작업·스케줄·웹 스레드와 다른 프로세스(`sp run`)가 같이 쓴다."""
import json
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, name TEXT, data TEXT NOT NULL, PRIMARY KEY (kind, id, name));
CREATE TABLE IF NOT EXISTS logs (seq INTEGER PRIMARY KEY, kind TEXT, id TEXT, line TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS logs_rec ON logs (kind, id, seq);
"""


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        self._db: sqlite3.Connection | None = None
        self._lock = threading.Lock()   # 연결 하나를 스레드들이 나눠 쓴다

    def _conn(self) -> sqlite3.Connection:
        """처음 쓸 때 연다(registry를 import만 해도 DB 파일이 생기지 않게). _lock 안에서 부른다."""
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            db.execute("PRAGMA busy_timeout=30000")   # 다른 프로세스가 쓰는 중이면 기다린다
            db.execute("PRAGMA journal_mode=WAL")   # 쓰는 동안에도 읽는다
            db.execute("PRAGMA synchronous=NORMAL")   # WAL에서는 안전하고 커밋이 빠르다
            db.executescript(SCHEMA)
            self._db = db
        return self._db

    def _run(self, sql: str, *args) -> list[tuple]:
        with self._lock:
            return self._conn().execute(sql, args).fetchall()

    @staticmethod
    def _get(db: sqlite3.Connection, kind: str, rec_id: str, name: str, default):
        row = db.execute("SELECT data FROM docs WHERE kind=? AND id=? AND name=?", (kind, rec_id, name)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def _put(db: sqlite3.Connection, kind: str, rec_id: str, value, name: str) -> None:
        db.execute("INSERT OR REPLACE INTO docs VALUES (?, ?, ?, ?)",
                   (kind, rec_id, name, json.dumps(value, ensure_ascii=False)))

    def get(self, kind: str, rec_id: str, name: str = "", default=None):
        with self._lock:
            return self._get(self._conn(), kind, rec_id, name, default)

    def put(self, kind: str, rec_id: str, value, name: str = "") -> None:
        with self._lock:
            self._put(self._conn(), kind, rec_id, value, name)

    def _tx(self, fn: Callable):
        """fn(연결)을 트랜잭션 하나로. BEGIN IMMEDIATE라 다른 프로세스의 쓰기를 읽기 전부터 막는다."""
        with self._lock:
            db = self._conn()
            db.execute("BEGIN IMMEDIATE")
            try:
                out = fn(db)
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")
            return out

    def edit(self, kind: str, rec_id: str, fn: Callable, name: str = ""):
        def run(db):
            value = fn(self._get(db, kind, rec_id, name, None))
            self._put(db, kind, rec_id, value, name)
            return value
        return self._tx(run)

    def ids(self, kind: str) -> list[str]:
        return [r[0] for r in self._run("SELECT id FROM docs WHERE kind=? AND name='' ORDER BY id", kind)]

    def delete(self, kind: str, rec_id: str) -> None:
        self._tx(lambda db: [db.execute(f"DELETE FROM {t} WHERE kind=? AND id=?", (kind, rec_id))
                             for t in ("docs", "logs")])

    def log(self, kind: str, rec_id: str, line: str) -> None:
        self._run("INSERT INTO logs (kind, id, line) VALUES (?, ?, ?)", kind, rec_id, line)

    def tail(self, kind: str, rec_id: str, n: int = 200) -> list[str]:
        rows = self._run("SELECT line FROM logs WHERE kind=? AND id=? ORDER BY seq DESC LIMIT ?", kind, rec_id, n)
        return [r[0] for r in reversed(rows)]

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

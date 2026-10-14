"""작업 스레드 1개 + 큐(제작·업로드·주제 찾기). 같은 작업을 두 번 넣지 않는다."""
import logging
import queue
import threading
from collections.abc import Callable

from ..core import pipeline, trends
from ..core.services import Services
from .store import atomic_write_json, now, redact, upload_state

log = logging.getLogger(__name__)


class LocalQueue:
    """ports.queue.Queue 구현: 프로세스 안 스레드 하나. 채널마다 쓸 구현(Services)은 resolve(channel_id)로 얻는다."""

    def __init__(self, resolve: Callable[[str], Services]):
        self.resolve = resolve
        self.lock = threading.RLock()   # put_clip이 락 안에서 enqueue를 부른다
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()   # (run|upload|trend, job_id 또는 trend_id)
        self._thread: threading.Thread | None = None

    def enqueue(self, job_id: str) -> bool:
        # ponytail: 프로세스 하나 안에서만 막는다. 서버를 여러 개 띄우지 않는 로컬 전용이라 충분하다.
        with self.lock:
            job = pipeline.Job.load(job_id)
            if job.data["status"] in ("queued", "running", "done"):
                return False
            job.update(status="queued")
        self._q.put(("run", job_id))
        return True

    def enqueue_upload(self, job_id: str) -> bool:
        """완성된 작업만, 올리는 중이거나 이미 올린 작업은 빼고 넣는다."""
        with self.lock:
            job = pipeline.Job.load(job_id)
            data = job.data
            if data["status"] != "done" or (data.get("upload") or {}).get("status") in ("queued", "running", "done"):
                return False
            job.update(upload=upload_state("queued"))
        self._q.put(("upload", job_id))
        return True

    def redo(self, job_id: str, steps=("thumbnail", "render"), files: dict | None = None, **fields) -> bool:
        """steps만 다시 돈다(상세 화면에서 고치기, 클립 교체). 만들거나 올리는 중이면 막는다.
        files: 손으로 고친 json({파일 이름: 값}, script.json·cues.json).
        fields: job.json에 남길 값(voice·thumb_note 등). steps가 비면 저장만 한다(제목·설명·태그만 고칠 때).
        이미 올린 작업을 다시 만들면 올린 기록을 uploaded_before로 옮겨 고친 영상을 새로 올릴 수 있게 한다
        (예전 영상은 그대로 남는다)."""
        with self.lock:
            job = pipeline.Job.load(job_id)
            data = job.data
            up = data.get("upload") or {}
            if data["status"] not in ("done", "failed", "interrupted") or up.get("status") in ("queued", "running"):
                return False
            for name, value in (files or {}).items():   # 락 안에서: 검사와 쓰기 사이에 작업이 시작되지 않게
                atomic_write_json(job.dir / name, value)
            if not steps:
                return True
            if up.get("status") == "done":
                fields |= {"upload": None, "uploaded_before": up}
            all_steps = data["steps"]
            for s in steps:
                all_steps[s] = {"status": "pending", "engine": None, "sec": None}
            job.update(status="queued", steps=all_steps, **fields)
        self._q.put(("run", job_id))
        return True

    def enqueue_trend(self, trend_id: str) -> bool:
        with self.lock:
            trend = trends.Trend.load(trend_id)
            if trend.data["status"] in ("queued", "running", "done"):
                return False
            trend.update(status="queued")
        self._q.put(("trend", trend_id))
        return True

    def run_one(self, job_id: str, kind: str = "run") -> None:
        try:
            rec = (trends.Trend if kind == "trend" else pipeline.Job).load(job_id)
            try:
                sv = self.resolve(rec.data.get("channel") or "")
            except Exception as e:   # 채널 설정이 틀리거나 지워져도 queued에 갇히지 않게 실패로 남긴다
                msg = redact(str(e)) or type(e).__name__
                rec.log(f"채널 설정 실패: {msg}")
                if kind == "upload":
                    rec.update(upload=upload_state("failed", error=msg, at=now()))
                else:
                    rec.update(status="failed", error={"step": None, "message": msg}, finished_at=now())
                raise
            if kind == "trend":
                trends.run(rec, sv)
            else:
                (pipeline.publish if kind == "upload" else pipeline.run)(rec, sv)
        except Exception:  # noqa: BLE001 — pipeline이 job.json·log.txt(키 가림)에 기록한다
            log.error("작업 실패: %s", job_id)   # 원문 traceback에는 키가 섞일 수 있어 찍지 않는다

    def _loop(self) -> None:
        while True:
            kind, job_id = self._q.get()
            self.run_one(job_id, kind)

    def start(self) -> None:
        with self.lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, daemon=True, name="sp-worker")
                self._thread.start()

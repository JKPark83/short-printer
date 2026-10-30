"""작업 스레드 1개 + 큐(제작·업로드), 주제 찾기 스레드 1개 + 큐. 같은 작업을 두 번 넣지 않는다.
주제 찾기는 LLM만 써서(Chrome·ffmpeg 안 씀) 제작과 따로 돌아도 부딪치지 않는다.
스케줄 스레드 1개가 30초마다 예정 시각을 본다."""
import logging
import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime

from ..core import pipeline, schedule, trends
from ..core.services import Services
from .store import now, redact, upload_state

log = logging.getLogger(__name__)
TICK = 30   # 초. 스케줄 GRACE(5분)보다 충분히 짧게


class LocalQueue:
    """ports.queue.Queue 구현: 프로세스 안 스레드 둘(제작·업로드 / 주제 찾기).
    채널마다 쓸 구현(Services)은 resolve(channel_id)로 얻는다.
    notify(text)는 스케줄 알림(registry.notify)."""

    def __init__(self, resolve: Callable[[str], Services], notify: Callable[[str], object] = lambda text: None):
        self.resolve = resolve
        self.notify = notify
        self.lock = threading.RLock()   # put_clip이 락 안에서 enqueue를 부른다
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()   # (run|upload, job_id)
        self._tq: queue.Queue[tuple[str, str]] = queue.Queue()   # ("trend", trend_id)
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

    def enqueue_upload(self, job_id: str, again: bool = False, target: str | None = None) -> bool:
        """완성된 작업만, 올리는 중이거나 이미 올린 작업은 빼고 넣는다. target None은 채널 업로드 공급자,
        나머지는 더 올리는 곳(publish.also, 큐 종류 "upload:<target>").
        again이면 이미 올린 작업도 새 영상으로 다시 올린다(주 공급자의 예전 기록은 uploaded_before, 영상은 남는다)."""
        with self.lock:
            job = pipeline.Job.load(job_id)
            data = job.data
            up = pipeline.upload_of(data, target)
            if data["status"] != "done" or up.get("status") in ("queued", "running") \
                    or (up.get("status") == "done" and not again):
                return False
            before = {"uploaded_before": up} if target is None and up.get("status") == "done" else {}
            job.set_upload(target, upload_state("queued"), **before)
        self._q.put(("upload" + (f":{target}" if target else ""), job_id))
        return True

    def redo(self, job_id: str, steps=("thumbnail", "render"), files: dict | None = None, **fields) -> bool:
        """steps만 다시 돈다(상세 화면에서 고치기, 클립 교체). 만들거나 올리는 중이면 막는다.
        files: 손으로 고친 json({파일 이름: 값}, script.json·cues.json).
        fields: job.json에 남길 값(voice·thumb_note 등). steps가 비면 저장만 한다(제목·설명·태그만, 확정 전 대본).
        이미 올린 작업을 다시 만들면 올린 기록을 uploaded_before로 옮겨 고친 영상을 새로 올릴 수 있게 한다
        (예전 영상은 그대로 남는다)."""
        with self.lock:
            job = pipeline.Job.load(job_id)
            data = job.data
            up = data.get("upload") or {}
            if data["status"] not in ("done", "failed", "interrupted", "waiting") or pipeline.uploading(data):
                return False
            if any(s not in data["steps"] for s in steps):   # 쇼츠·롱폼 단계가 다르다: 없는 단계를 만들지 않게
                return False
            for name, value in (files or {}).items():   # 락 안에서: 검사와 쓰기 사이에 작업이 시작되지 않게
                job.put(name, value)
            if not steps:
                job.update(**fields)
                return True
            if up.get("status") == "done":
                fields |= {"upload": None, "uploaded_before": up}
            if done := {k: v for k, v in (data.get("uploads") or {}).items() if v["status"] == "done"}:
                fields |= {"uploads": None, "uploads_before": done}   # 더 올리는 곳도 고친 영상을 새로 올릴 수 있게
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
        self._tq.put(("trend", trend_id))
        return True

    def run_one(self, job_id: str, kind: str = "run") -> None:
        kind, _, target = kind.partition(":")   # "upload:instagram" → 더 올리는 곳
        target = target or None
        if kind == "run":
            with self.lock:   # 대기 중에 취소·삭제됐거나 같은 작업이 두 번 들어왔으면 건너뛴다
                try:
                    job = pipeline.Job.load(job_id)
                except FileNotFoundError:   # 큐에 남은 몫이 작업 스레드를 죽이지 않게
                    return
                if job.data["status"] != "queued":
                    return
                job.update(status="running", cancel=None)
        try:
            rec = (trends.Trend if kind == "trend" else pipeline.Job).load(job_id)
            try:
                sv = self.resolve(rec.data.get("channel") or "")
            except Exception as e:   # 채널 설정이 틀리거나 지워져도 queued에 갇히지 않게 실패로 남긴다
                msg = redact(str(e)) or type(e).__name__
                rec.log(f"채널 설정 실패: {msg}")
                if kind == "upload":
                    rec.set_upload(target, upload_state("failed", error=msg, at=now()))
                else:
                    rec.update(status="failed", error={"step": None, "message": msg}, finished_at=now())
                raise
            if kind == "trend":
                trends.run(rec, sv)
            elif kind == "upload":
                pipeline.publish(rec, sv, target)
            else:
                pipeline.run(rec, sv)
        except Exception:  # noqa: BLE001 — pipeline이 상태·로그(키 가림)에 기록한다
            log.error("작업 실패: %s", job_id)   # 원문 traceback에는 키가 섞일 수 있어 찍지 않는다
        if not target:   # 더 올리는 곳은 사람이 화면에서 눌러 올려 결과도 화면에서 본다(스케줄 알림은 주 공급자만)
            self._after(job_id, kind)

    def _after(self, job_id: str, kind: str) -> None:
        """스케줄 작업이면 다음 일(작업 만들기·업로드·알림). 손으로 만든 작업은 schedule이 그냥 돌아온다."""
        try:
            if kind == "trend":
                schedule.after_trend(trends.Trend.load(job_id), self, self.notify)
            else:
                schedule.after_job(pipeline.Job.load(job_id), kind, self, self.notify)
        except Exception as e:  # noqa: BLE001 — 후속 처리 실패로 작업 스레드가 멈추지 않게
            log.error("스케줄 후속 처리 실패 %s: %s", job_id, redact(str(e)) or type(e).__name__)

    def _loop(self, q: queue.Queue) -> None:
        while True:
            kind, job_id = q.get()
            # ponytail: 롱폼 렌더(수십 분)가 이 하나뿐인 큐를 막아 그동안 쇼츠가 밀린다.
            # 쇼츠가 늦어지면 렌더만 따로 스레드로 돌린다
            self.run_one(job_id, kind)

    def _ticks(self) -> None:
        while True:
            try:
                schedule.tick(self, self.notify, datetime.now().astimezone())
            except Exception as e:  # noqa: BLE001 — 스케줄 폴더를 못 읽어도 스레드는 산다
                log.error("스케줄 확인 실패: %s", redact(str(e)) or type(e).__name__)
            time.sleep(TICK)

    def start(self) -> None:
        with self.lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, args=(self._q,), daemon=True, name="sp-worker")
                self._thread.start()
                threading.Thread(target=self._loop, args=(self._tq,), daemon=True, name="sp-trends").start()
                threading.Thread(target=self._ticks, daemon=True, name="sp-scheduler").start()

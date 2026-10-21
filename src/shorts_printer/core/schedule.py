"""스케줄: 정해진 시각(또는 N시간마다)에 채널 영상 한 편을 만들어 비공개로 올리고 알린다.
시각 계산은 순수 함수, 실행은 Queue·notify를 인자로 받는다. 결정은 docs/plan/schedule.md."""
import logging
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .. import config
from ..infra.store import Record, redact
from ..ports.queue import Queue
from . import channel, trends
from .pipeline import LABELS, Job, in_review
from .trends import Trend

GRACE = timedelta(minutes=5)   # 이보다 늦게 알아챈 시각은 놓친 것으로 본다(사용자 결정: 건너뛰기)
MAX_RUNS = 50
BUSY_JOB = ("draft", "queued", "running", "waiting")
BUSY = ("queued", "running")   # 주제 찾기·업로드
SOURCES = {"trend": "추천", "list": "주제 목록"}
DAYS = "월화수목금토일"
MAX_TIMES = 12
MAX_NAME = 50
MAX_TOPICS = 200
KEYS = ("name", "source", "voice", "when", "keyword", "topics", "enabled")   # 고칠 수 있는 값
LOOKAHEAD = 8   # next_runs가 찾는 날 수
Notify = Callable[[str], object]

log = logging.getLogger(__name__)


def _hhmm(s: str) -> str:
    try:
        return datetime.strptime(s.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError(f"시각은 09:00처럼 적어요: {s}") from None


def _minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


class When(BaseModel):
    """시각 규칙. 검증 실패는 ValueError(pydantic ValidationError) → 화면 400. 한국어 한 줄은 parse_when()으로."""
    kind: Literal["times", "every"]
    times: list[str] = []          # "HH:MM", 정렬·중복 제거. kind=times면 1~12개
    every: int = 6                 # 시간. 1~24
    start: str = "09:00"           # every 창(start <= end)
    end: str = "23:00"
    days: list[int] = Field(default_factory=lambda: list(range(7)))   # 월 0 … 일 6

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        return sorted({_hhmm(t) for t in v if t.strip()})

    @field_validator("start", "end")
    @classmethod
    def _window(cls, v: str) -> str:
        return _hhmm(v)

    @field_validator("days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if not v or any(not 0 <= d <= 6 for d in v):
            raise ValueError("요일을 하나 이상 골라 주세요")
        return sorted(set(v))

    @model_validator(mode="after")
    def _kind(self):
        if self.kind == "times" and not 1 <= len(self.times) <= MAX_TIMES:
            raise ValueError(f"시각을 1~{MAX_TIMES}개 넣어 주세요")
        if self.kind == "every" and not 1 <= self.every <= 24:
            raise ValueError("간격은 1~24시간이에요")
        if self.kind == "every" and self.start > self.end:
            raise ValueError("끝 시각이 시작 시각보다 빨라요")
        return self


def parse_when(value: When | dict) -> When:
    """화면 값 → When. 틀리면 첫 이유 하나만 담은 한국어 ValueError."""
    if isinstance(value, When):
        return value
    try:
        return When(**value)
    except ValidationError as e:
        err = e.errors()[0]
        if err["type"] == "value_error":   # 우리가 던진 한국어 문구
            raise ValueError(err["msg"].removeprefix("Value error, ")) from None
        raise ValueError(f"시각 값이 틀려요: {'.'.join(map(str, err['loc']))}") from None   # 형식 오류는 어느 칸인지만


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _now() -> datetime:
    return datetime.now().astimezone()


def _clean(channel_id: str, d: dict) -> dict:
    """만들기·고치기 값 검사. 틀리면 한국어 ValueError, 채널이 없으면 KeyError."""
    ch = channel.load(channel_id)
    name = d["name"].strip()
    if not name or len(name) > MAX_NAME:
        raise ValueError(f"이름을 1~{MAX_NAME}자로 적어 주세요")
    if d["source"] not in SOURCES:
        raise ValueError("주제 출처는 추천·주제 목록 가운데 하나예요")
    topics = [t.strip()[:200] for t in d["topics"] if t.strip()]
    if d["source"] == "list" and d["enabled"] and not topics:   # 끈 스케줄은 목록이 비어도 고칠 수 있게
        raise ValueError("주제를 한 줄에 하나씩 넣어 주세요")
    if len(topics) > MAX_TOPICS:
        raise ValueError(f"주제는 {MAX_TOPICS}개까지 넣을 수 있어요")
    voice = d["voice"] or ch.tts.default
    if voice not in ch.tts.voices:
        raise ValueError(f"이 채널에 없는 목소리예요: {voice}")
    return {"name": name, "source": d["source"], "keyword": d["keyword"].strip()[:trends.MAX_REQUEST],
            "topics": topics, "voice": voice, "enabled": bool(d["enabled"]), "when": parse_when(d["when"]).model_dump()}


class Schedule(Record):
    KIND = "schedule"
    WHAT = "스케줄"

    @classmethod
    def root(cls) -> Path:
        return config.SCHEDULES_DIR

    @classmethod
    def create(cls, channel: str, name: str, source: str, voice: str, when: When | dict, keyword: str = "",
               topics: Iterable[str] = ()) -> "Schedule":
        """voice가 비면 채널 기본 목소리. last_slot은 지금(지난 시각이 바로 돌지 않게)."""
        fields = _clean(channel, {"name": name, "source": source, "voice": voice, "when": when, "keyword": keyword,
                                  "topics": list(topics), "enabled": True})
        return cls._new((), channel=channel, **fields, last_slot=_iso(_now()), runs=[])

    def change(self, **fields) -> dict:
        """고치기·켜고 끄기(name·source·voice·when·keyword·topics·enabled). 채널은 바꾸지 않는다.
        시각을 바꾸거나 켜면 last_slot을 지금으로. 웹은 q.lock 안에서 부른다(회차 기록과 겹치지 않게)."""
        d = self.data
        new = _clean(d["channel"], {k: d[k] for k in KEYS} | fields)
        if new["when"] != d["when"] or (new["enabled"] and not d["enabled"]):
            new["last_slot"] = _iso(_now())
        return self.update(**new)


# ---------- 시각 ----------

def slots(when: When, day: date, tz: tzinfo | None) -> list[datetime]:
    """그날의 예정 시각들(오름차순). 고르지 않은 요일이면 빈 목록."""
    if day.weekday() not in when.days:
        return []
    if when.kind == "times":
        mins = [_minutes(t) for t in when.times]
    else:
        mins = range(_minutes(when.start), _minutes(when.end) + 1, when.every * 60)
    # ponytail: tz는 now.astimezone()의 고정 오프셋. 서머타임 있는 지역은 바뀌는 날 한 시간 어긋난다(zoneinfo로 바꿀 것)
    return [datetime.combine(day, time(m // 60, m % 60), tz) for m in mins]


def next_runs(when: When, after: datetime, n: int = 5) -> list[datetime]:
    """after 다음 예정 시각 n개(최대 8일 앞까지 찾는다)."""
    out = [s for i in range(LOOKAHEAD + 1) for s in slots(when, after.date() + timedelta(days=i), after.tzinfo)
           if s > after]
    return out[:n]


def _days_text(days: list[int]) -> str:
    named = {(0, 1, 2, 3, 4, 5, 6): "매일", (0, 1, 2, 3, 4): "평일", (5, 6): "주말"}
    return named.get(tuple(days)) or "·".join(DAYS[d] for d in days)


def summary(when: When) -> str:
    """"매일 09:00 · 18:00" / "월·수·금 09:00~23:00 6시간마다"."""
    if when.kind == "times":
        return f"{_days_text(when.days)} {' · '.join(when.times)}"
    return f"{_days_text(when.days)} {when.start}~{when.end} {when.every}시간마다"


def due(data: dict, now: datetime) -> tuple[datetime | None, bool]:
    """(last_slot 뒤 now까지의 마지막 예정 시각, 놓쳤나). 놓친 것 = GRACE보다 늦게 알아챈 것."""
    last = datetime.fromisoformat(data["last_slot"])
    w = When(**data["when"])
    first = max(last.date(), now.date() - timedelta(days=LOOKAHEAD))   # 오래 꺼져 있었어도 며칠만 본다
    past = [s for i in range((now.date() - first).days + 1) for s in slots(w, first + timedelta(days=i), now.tzinfo)
            if last < s <= now]
    if not past:
        return None, False
    return past[-1], now - past[-1] > GRACE


def busy(data: dict) -> bool:
    """마지막 started 회차의 주제 찾기·제작·업로드가 아직 진행 중인가(대기 포함)."""
    run = next((r for r in reversed(data["runs"]) if r["result"] == "started"), None)
    if not run:
        return False
    try:
        if run["job"]:
            d = Job.load(run["job"]).data
            return d["status"] in BUSY_JOB or (d.get("upload") or {}).get("status") in BUSY
        if run["trend"]:
            return Trend.load(run["trend"]).data["status"] in ("draft", *BUSY)
    except FileNotFoundError:   # 작업을 지웠다
        pass
    return False


# ---------- 실행 ----------

def _run(at: datetime, slot: datetime | None, result: str, **fields) -> dict:
    return {"at": _iso(at), "slot": slot and _iso(slot), "result": result, "job": None, "trend": None,
            "topic": None, "note": None} | fields


def _record(s: Schedule, run: dict, **fields) -> None:
    s.update(runs=(s.data["runs"] + [run])[-MAX_RUNS:], **fields)


def _patch(s: Schedule, key: str, value: str, **fields) -> None:
    """key(trend·job)가 value인 회차를 고친다."""
    s.update(runs=[r | fields if r[key] == value else r for r in s.data["runs"]])


def _msg(d: dict, head: str, *lines: str) -> str:
    """알림 글: 첫 줄 [머리] 채널 이름 · 스케줄 이름."""
    try:
        ch = channel.load(d["channel"]).name
    except (KeyError, ValueError):
        ch = d["channel"]
    return "\n".join([f"[{head}] {ch} · {d['name']}", *lines])


def _link(kind: str, rec_id: str) -> str:
    return f"{config.URL}/{kind}/{rec_id}"


def fire(s: Schedule, q: Queue, notify: Notify, at: datetime, slot: datetime | None = None) -> dict:
    """한 회차 시작(정해진 시각이면 slot, [지금 실행]이면 None). 기록한 run을 돌려준다.
    이전 회차가 안 끝났으면 skipped, 주제 목록이 비었으면 failed + 알림 + 스케줄 끄기."""
    with q.lock:
        d = s.data
        fields = {"last_slot": _iso(slot)} if slot else {}
        if busy(d):
            run = _run(at, slot, "skipped", note="이전 회차가 아직 안 끝났어요")
        elif d["source"] == "trend":
            t = Trend.create(d["channel"], d["keyword"])
            t.update(schedule=s.id)
            q.enqueue_trend(t.id)
            run = _run(at, slot, "started", trend=t.id)
        elif d["topics"]:
            topic, *rest = d["topics"]
            job = Job.create(d["channel"], topic, d["voice"], source={"schedule": s.id}, review=True)
            q.enqueue(job.id)
            run = _run(at, slot, "started", job=job.id, topic=topic)
            fields["topics"] = rest
        else:
            run = _run(at, slot, "failed", note="주제 목록이 비어 스케줄을 껐어요")
            fields["enabled"] = False
        _record(s, run, **fields)
    if run["result"] == "failed":   # 알림(네트워크)은 락 밖에서
        notify(_msg(d, "실패", "주제 목록이 비어 스케줄을 껐어요. 주제를 더 넣고 다시 켜세요.",
                    f"스케줄: {_link('schedules', s.id)}"))
    return run


def tick(q: Queue, notify: Notify, now: datetime) -> None:
    """켜진 스케줄 모두: 예정 시각이 지났으면 fire, 늦게 알아챘으면 missed만 기록. 작업 스레드가 30초마다 부른다."""
    for s in Schedule.all():
        try:
            with q.lock:
                d = s.data
                slot, missed = due(d, now) if d["enabled"] else (None, False)
                if slot and missed:
                    _record(s, _run(now, slot, "missed"), last_slot=_iso(slot))
            if slot and not missed:
                fire(s, q, notify, now, slot)
        except Exception as e:   # 스케줄 하나가 틀려도 나머지는 돈다
            log.error("스케줄 %s 실행 실패: %s", s.id, redact(str(e)) or type(e).__name__)


def _schedule(sid: str | None) -> Schedule | None:
    try:
        return Schedule.load(sid) if sid else None
    except FileNotFoundError:   # 스케줄을 지웠으면 이어서 하지 않는다
        return None


def after_trend(trend: Trend, q: Queue, notify: Notify) -> None:
    """주제 찾기가 끝나면 알린다(모든 주제 찾기). 스케줄 주제 찾기는 거기에 더해
    아직 안 만든 첫 추천(다 겹치면 1위)으로 작업을 만들어 넣는다."""
    d = trend.data
    s = _schedule(d.get("schedule"))
    who = s.data if s else {"channel": d["channel"], "name": "직접 찾은 주제"}
    link = f"주제 찾기: {_link('trends', trend.id)}"
    if d["status"] in ("failed", "interrupted"):   # interrupted는 앱이 켜질 때 recover()가 넘긴다
        msg = (d.get("error") or {}).get("message") or \
            ("서버가 꺼져 멈췄어요" if d["status"] == "interrupted" else "알 수 없는 오류")
        if s:
            with q.lock:
                _patch(s, "trend", trend.id, result="failed", note=f"주제 찾기 실패: {msg}")
        if s or d["status"] == "failed":   # 손으로 찾은 것의 중단은 작업과 같이 알리지 않는다
            notify(_msg(who, "실패", f"주제 찾기 실패: {msg}", link))
        return
    if d["status"] != "done":
        return
    picks = trend.doc("picks.json")["picks"]
    tops = [f"{n}. {p['topic']}" for n, p in enumerate(picks[:5], 1)]
    if not s:
        notify(_msg(who, "주제 찾기 완료", *tops, link))
        return
    made = {j.data["topic"] for j in Job.all() if j.data.get("channel") == d["channel"]}
    i = next((i for i, p in enumerate(picks) if p["topic"] not in made), 0)
    p = picks[i]
    job = Job.create(d["channel"], p["topic"], s.data["voice"], brief=trends.brief(trend, p),
                     source={"trend": trend.id, "pick": i, "schedule": s.id}, review=True)
    with q.lock:
        # 실패한 주제 찾기를 다시 돌려 끝난 것이면 회차를 다시 진행 중으로(겹침 막기·배지)
        _patch(s, "trend", trend.id, result="started", note=None, job=job.id, topic=p["topic"])
        q.enqueue(job.id)
    notify(_msg(who, "주제 찾기 완료", *tops, f"→ {i + 1}번 주제로 영상을 만들어요", link))


def _sensitive_wait(job: Job) -> str | None:
    """민감 분야 확인을 기다리면 그 분야. 클립 대기 등 다른 멈춤이면 None."""
    d = job.data
    area = (job.doc("script.json") or {}).get("sensitive")
    if d["status"] != "waiting" or not area or d.get("confirmed") or d["steps"]["footage"]["status"] == "done":
        return None
    return area if channel.load(d["channel"]).sensitive_gate else None


def after_job(job: Job, kind: str, q: Queue, notify: Notify) -> None:
    """완성·실패·검수 대기·민감 대기 → 알림(모든 작업). 스케줄 작업(source.schedule)은 거기에 더해
    완성 → 업로드 넣기, 중단·업로드 완료/실패 → 알림. kind는 큐 종류(run·upload)."""
    d = job.data
    s = _schedule((d.get("source") or {}).get("schedule"))
    title = (job.doc("script.json") or {}).get("title") or d["topic"]
    link = f"작업: {_link('jobs', job.id)}"
    who = s.data if s else {"channel": d["channel"], "name": "직접 만든 작업"}
    then = "영상 제작·업로드까지 이어져요." if s else "영상 제작이 이어져요."   # 손으로 만든 작업은 사람이 올린다
    if kind == "run" and d["status"] == "done":   # 손으로 만든 작업도 영상이 다 되면 알린다
        notify(_msg(who, "제작 완료", title, link))
    elif kind == "run" and d["status"] == "failed":   # 실패도 모든 작업
        err = d.get("error") or {}
        step = LABELS.get(err.get("step"), "")
        notify(_msg(who, "실패", f"제작 실패{f'({step})' if step else ''}: {err.get('message')}", d["topic"], link))
    elif kind == "run" and in_review(d):   # 검수 확정이 민감 확인도 겸하므로 알림은 이것 하나
        area = (job.doc("script.json") or {}).get("sensitive")
        notify(_msg(who, "검수 필요", f"대본을 확인하고 [확인하고 계속]을 누르면 {then}",
                    *filter(None, [area and f"민감 분야({area}) 대본이에요."]), d["topic"], link))
    elif kind == "run" and (area := _sensitive_wait(job)):
        notify(_msg(who, "확인 필요", f"민감 분야({area}) 대본이에요. 대본을 보고 [확인하고 계속]을 누르면 {then}",
                    title, link))
    if not s:
        return
    sd = s.data
    if kind == "upload":
        up = d.get("upload") or {}
        if up.get("status") == "done":
            notify(_msg(sd, "업로드 완료", f"{title} (비공개)", *filter(None, [up.get("note")]),
                        f"스튜디오: https://studio.youtube.com/video/{up['video_id']}/edit", link))
        elif up.get("status") == "failed":
            notify(_msg(sd, "실패", f"업로드 실패: {up.get('error')}", title, link))
        return
    if d["status"] == "done":
        # 처음 완성될 때만 올린다. 올린 뒤 상세 화면에서 고쳐 다시 만든 것(uploaded_before)은 사람이 올린다
        if d.get("upload") is None and not d.get("uploaded_before"):
            q.enqueue_upload(job.id)
    elif d["status"] == "interrupted":   # 앱이 켜질 때 recover()가 넘긴다
        notify(_msg(sd, "실패", "제작 중단: 서버가 꺼져 멈췄어요. 작업 화면에서 다시 시도하세요.", d["topic"], link))

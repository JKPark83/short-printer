from datetime import date, datetime, timedelta, timezone

import pytest

from shorts_printer import config
from shorts_printer.core import pipeline, schedule, trends
from shorts_printer.core.pipeline import Job
from shorts_printer.core.schedule import GRACE, Schedule, When
from shorts_printer.core.trends import Trend
from shorts_printer.infra.store import upload_state
from shorts_printer.infra.worker import LocalQueue

CH = "ko-40sec-facts"
KST = timezone(timedelta(hours=9))
FRI = date(2026, 10, 16)   # 금요일


def at(d: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=KST)


@pytest.fixture
def q():
    return LocalQueue(lambda cid: pytest.fail("스케줄은 넣기만 한다"))


@pytest.fixture
def sent():
    return []


def make(source="list", topics=("커피", "우유"), last="08:00", **when) -> Schedule:
    s = Schedule.create(CH, "아침 상식", source, "", {"kind": "times", "times": ["09:00"]} | when, topics=topics)
    s.update(last_slot=at(FRI, last).isoformat())
    return s


def test_when_normalizes_and_rejects_in_korean():
    w = When(kind="times", times=["18:00", "9:00", "09:00"], days=[4, 0, 0])
    assert (w.times, w.days) == (["09:00", "18:00"], [0, 4])
    for bad, msg in [({"kind": "times", "times": []}, "시각을 1~12개"),
                     ({"kind": "times", "times": ["25:00"]}, "09:00처럼"),
                     ({"kind": "times", "times": ["09:00"], "days": []}, "요일을"),
                     ({"kind": "every", "every": 25}, "1~24시간"),
                     ({"kind": "every", "start": "20:00", "end": "08:00"}, "끝 시각"),
                     ({"kind": "every", "days": ["x"]}, "시각 값이 틀려요: days.0")]:
        with pytest.raises(ValueError, match=msg):
            schedule.parse_when(bad)


def test_slots_next_runs_summary():
    times = When(kind="times", times=["09:00", "18:00"], days=[0, 2, 4])
    assert schedule.slots(times, FRI, KST) == [at(FRI, "09:00"), at(FRI, "18:00")]
    assert schedule.slots(times, FRI + timedelta(days=1), KST) == []   # 토요일
    mon, wed = FRI + timedelta(days=3), FRI + timedelta(days=5)
    assert schedule.next_runs(times, at(FRI, "20:00"), 3) == [at(mon, "09:00"), at(mon, "18:00"), at(wed, "09:00")]
    every = When(kind="every", every=6, start="09:00", end="23:00")
    assert schedule.slots(every, FRI, KST) == [at(FRI, "09:00"), at(FRI, "15:00"), at(FRI, "21:00")]
    assert schedule.summary(times) == "월·수·금 09:00 · 18:00"
    assert schedule.summary(every) == "매일 09:00~23:00 6시간마다"
    assert schedule.summary(When(kind="times", times=["07:30"], days=[0, 1, 2, 3, 4])) == "평일 07:30"


def test_due_skips_missed_after_grace():
    d = {"when": {"kind": "times", "times": ["09:00", "18:00"]}, "last_slot": at(FRI, "08:00").isoformat()}
    assert schedule.due(d, at(FRI, "08:59")) == (None, False)
    assert schedule.due(d, at(FRI, "09:00") + GRACE) == (at(FRI, "09:00"), False)
    assert schedule.due(d, at(FRI, "09:06")) == (at(FRI, "09:00"), True)
    assert schedule.due(d, at(FRI, "18:01")) == (at(FRI, "18:00"), False)   # 09:00은 18:00에 묻힌다
    assert schedule.due(d | {"last_slot": at(FRI, "09:00").isoformat()}, at(FRI, "09:02")) == (None, False)


def test_tick_fires_list_in_order_and_records_missed(q, sent):
    s = make()
    schedule.tick(q, sent.append, at(FRI, "09:01"))
    d = s.data
    run = d["runs"][-1]
    assert run["result"] == "started" and run["topic"] == "커피" and d["topics"] == ["우유"]
    assert d["last_slot"] == at(FRI, "09:00").isoformat()
    job = Job.load(run["job"]).data
    assert job["status"] == "queued" and job["source"] == {"schedule": s.id} and job["voice"] == "PDoCXqBQFGsvfO0hNkEs"
    assert q._q.get_nowait() == ("run", run["job"])
    schedule.tick(q, sent.append, at(FRI, "09:01"))   # 같은 시각은 한 번만
    assert len(s.data["runs"]) == 1

    late = make(last="08:00")
    schedule.tick(q, sent.append, at(FRI, "10:00"))
    d = late.data
    assert d["runs"][-1]["result"] == "missed" and d["topics"] == ["커피", "우유"] and q._q.empty()
    assert d["last_slot"] == at(FRI, "09:00").isoformat() and not sent

    off = make()
    off.update(enabled=False)
    schedule.tick(q, sent.append, at(FRI, "09:01"))
    assert off.data["runs"] == []


def test_fire_trend_marks_trend_and_skips_overlap(q, sent):
    s = make("trend", topics=())
    run = schedule.fire(s, q, sent.append, at(FRI, "09:00"))
    t = Trend.load(run["trend"]).data
    assert t["status"] == "queued" and t["schedule"] == s.id and t["channel"] == CH and run["slot"] is None
    assert schedule.busy(s.data)
    assert schedule.fire(s, q, sent.append, at(FRI, "09:30"))["result"] == "skipped"
    Trend.load(run["trend"]).update(status="failed")
    assert not schedule.busy(s.data)


def test_list_job_busy_until_upload_finishes(q, sent):
    s = make()
    job = Job.load(schedule.fire(s, q, sent.append, at(FRI, "09:00"))["job"])
    for status, upload, busy in [("waiting", None, True), ("done", upload_state("running"), True),
                                 ("done", upload_state("done"), False), ("failed", None, False)]:
        job.update(status=status, upload=upload)
        assert schedule.busy(s.data) is busy


def test_empty_list_disables_and_notifies(q, sent):
    s = make(topics=["커피"])
    schedule.fire(s, q, sent.append, at(FRI, "09:00"))
    Job.load(s.data["runs"][-1]["job"]).update(status="failed")
    run = schedule.fire(s, q, sent.append, at(FRI, "18:00"))
    assert run["result"] == "failed" and not s.data["enabled"]
    assert "[실패] 40초 상식 · 아침 상식" in sent[0] and f"{config.URL}/schedules/{s.id}" in sent[0]


def test_change_validates_and_resets_last_slot():
    s = make(topics=["커피"])
    with pytest.raises(ValueError, match="없는 목소리"):
        s.change(voice="nobody")
    with pytest.raises(ValueError, match="한 줄에 하나씩"):   # 켜진 목록 스케줄은 비울 수 없다
        s.change(topics=[" "])
    assert s.change(name=" 저녁 ")["last_slot"] == at(FRI, "08:00").isoformat()   # 시각을 안 바꾸면 그대로
    d = s.change(enabled=False, topics=[])   # 끈 스케줄은 비워도 된다
    assert (d["name"], d["enabled"], d["topics"]) == ("저녁", False, [])
    s.update(topics=["커피"])
    assert s.change(enabled=True)["last_slot"] != at(FRI, "08:00").isoformat()   # 켜면 지금으로
    s.update(last_slot=at(FRI, "08:00").isoformat())
    d = s.change(when={"kind": "every", "every": 3})
    assert d["when"]["kind"] == "every" and d["last_slot"] != at(FRI, "08:00").isoformat()


def trend_done(s: Schedule, topics: list[str]) -> Trend:
    t = Trend.create(CH)
    t.update(schedule=s.id, status="done")
    t.put("picks.json", {"summary": "", "excluded": [], "picks": [
        {"topic": x, "angle": f"{x} 각도", "format": "잡학·상식", "why_now": "지금", "search_terms": ["a"], "refs": []}
        for x in topics]})
    return t


def test_after_trend_picks_first_unmade_topic(q, sent):
    s = make("trend", topics=())
    Job.create(CH, "커피", "v")   # 이미 만든 주제
    Job.create("other", "우유", "v")   # 다른 채널 주제는 겹쳐도 된다
    t = trend_done(s, ["커피", "우유"])
    s.update(runs=[schedule._run(at(FRI, "09:00"), None, "started", trend=t.id)])
    schedule.after_trend(Trend.load(t.id), q, sent.append)
    run = s.data["runs"][-1]
    job = Job.load(run["job"]).data
    assert run["topic"] == job["topic"] == "우유" and job["status"] == "queued"
    assert job["source"] == {"trend": t.id, "pick": 1, "schedule": s.id} and "우유 각도" in job["brief"]
    Job.create(CH, "우유", "v")
    t2 = trend_done(s, ["커피", "우유"])
    schedule.after_trend(Trend.load(t2.id), q, sent.append)
    assert [j.data["source"] for j in Job.all() if (j.data["source"] or {}).get("trend") == t2.id][0]["pick"] == 0
    assert not sent


def test_after_trend_failure_notifies(q, sent):
    s = make("trend", topics=())
    run = schedule.fire(s, q, sent.append, at(FRI, "09:00"))
    t = Trend.load(run["trend"])
    t.update(status="failed", error={"step": "collect", "message": "할당량을 다 썼어요"})
    schedule.after_trend(t, q, sent.append)
    assert s.data["runs"][-1]["result"] == "failed" and "할당량" in s.data["runs"][-1]["note"]
    assert "주제 찾기 실패: 할당량을 다 썼어요" in sent[0] and f"/trends/{t.id}" in sent[0]


def test_after_job_uploads_and_notifies(q, sent):
    s = make()
    job = Job.load(schedule.fire(s, q, sent.append, at(FRI, "09:00"))["job"])
    q._q.get_nowait()
    job.put("script.json", {"title": "커피의 비밀", "sensitive": None})
    job.update(status="done")
    schedule.after_job(job, "run", q, sent.append)
    assert job.data["upload"]["status"] == "queued" and q._q.get_nowait() == ("upload", job.id) and not sent

    job.update(upload=upload_state("done", video_id="VID"))
    schedule.after_job(job, "upload", q, sent.append)
    assert sent[-1].startswith("[업로드 완료] 40초 상식 · 아침 상식\n커피의 비밀 (비공개)")
    assert "https://studio.youtube.com/video/VID/edit" in sent[-1] and f"{config.URL}/jobs/{job.id}" in sent[-1]

    job.update(upload=upload_state("failed", error="토큰이 없어요"))
    schedule.after_job(job, "upload", q, sent.append)
    assert "업로드 실패: 토큰이 없어요" in sent[-1]

    job.update(upload=None, uploaded_before={"status": "done"})   # 올린 뒤 고쳐 다시 만든 것은 사람이 올린다
    schedule.after_job(job, "run", q, sent.append)
    assert job.data["upload"] is None and q._q.empty()

    job.update(status="failed", error={"step": "voice", "message": "ElevenLabs 401"})
    schedule.after_job(job, "run", q, sent.append)
    assert "제작 실패(음성): ElevenLabs 401" in sent[-1] and len(sent) == 3


def test_after_job_sensitive_wait_only(q, sent):
    s = make()
    job = Job.load(schedule.fire(s, q, sent.append, at(FRI, "09:00"))["job"])
    job.put("script.json", {"title": "약 먹는 법", "sensitive": "건강"})
    job.update(status="waiting")
    schedule.after_job(job, "run", q, sent.append)
    assert sent[-1].startswith("[확인 필요]") and "민감 분야(건강)" in sent[-1]
    job.update(confirmed=True)   # 확인 뒤 클립 대기는 알리지 않는다
    schedule.after_job(job, "run", q, sent.append)
    assert len(sent) == 1


def test_manual_job_is_left_alone(q, sent):
    job = Job.create(CH, "커피", "v")
    for status in ("done", "failed"):
        job.update(status=status)
        schedule.after_job(job, "run", q, sent.append)
    job.update(upload=upload_state("done", video_id="VID"))
    schedule.after_job(job, "upload", q, sent.append)
    assert not sent and q._q.empty() and job.data["upload"]["status"] == "done"


def test_worker_runs_hooks_and_swallows_errors(monkeypatch, sent):
    q = LocalQueue(lambda cid: None, sent.append)
    calls = []

    def boom(*a):
        calls.append(a)
        raise RuntimeError("훅 실패")
    monkeypatch.setattr(pipeline, "run", lambda job, sv: None)
    monkeypatch.setattr(trends, "run", lambda t, sv: None)
    monkeypatch.setattr(schedule, "after_job", boom)
    monkeypatch.setattr(schedule, "after_trend", boom)
    job, t = Job.create(CH, "커피", "v"), Trend.create(CH)
    q.run_one(job.id)   # 훅이 터져도 작업 스레드는 산다
    q.run_one(t.id, "trend")
    assert [(a[0].id, a[-2], a[-1]) for a in calls] == [(job.id, q, sent.append), (t.id, q, sent.append)]
    assert calls[0][1] == "run"



def test_retried_trend_restarts_run_and_interrupted_notifies(q, sent):
    s = make("trend", topics=())
    t = Trend.load(schedule.fire(s, q, sent.append, at(FRI, "09:00"))["trend"])
    t.update(status="interrupted")   # 앱이 켜질 때 recover()가 넘긴다
    schedule.after_trend(t, q, sent.append)
    assert s.data["runs"][-1]["result"] == "failed" and "주제 찾기 실패: 서버가 꺼져 멈췄어요" in sent[-1]
    t.put("picks.json", trend_done(s, ["커피"]).doc("picks.json"))
    t.update(status="done")   # [다시 시도]로 끝났다
    schedule.after_trend(t, q, sent.append)
    run = s.data["runs"][-1]
    assert (run["result"], run["note"], run["topic"]) == ("started", None, "커피") and schedule.busy(s.data)
    assert schedule.fire(s, q, sent.append, at(FRI, "10:00"))["result"] == "skipped"   # 겹치지 않는다
    job = Job.load(run["job"])
    job.update(status="interrupted")
    schedule.after_job(job, "run", q, sent.append)
    assert "제작 중단: 서버가 꺼져 멈췄어요" in sent[-1] and len(sent) == 2

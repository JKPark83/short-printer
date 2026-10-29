import shutil

import pytest
from fastapi.testclient import TestClient

from shorts_printer import config, registry
from shorts_printer.adapters.youtube import YouTube
from shorts_printer.core import trends
from shorts_printer.core.pipeline import Job
from shorts_printer.core.schedule import Schedule
from shorts_printer.core.trends import Trend
from shorts_printer.infra.store import upload_state
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")
CH = "momjob"
VOICE = "LKOcTG4J4tYTPR9DnLeM"
FORM = {"channel": CH, "name": "아침 상식", "source": "list", "voice": VOICE, "keyword": "",
        "topics": "커피\n\n우유 ", "kind": "times", "times": ["18:00", "09:00", ""], "every": "6", "start": "09:00",
        "end": "23:00", "days": ["0", "1", "2", "3", "4"]}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """업로드 토큰(.secrets)을 보지 않게 하고, 앞 테스트가 남긴 채널 쿠키를 비운다."""
    monkeypatch.setattr(YouTube, "ready", lambda self: False)
    client.cookies.clear()


@pytest.fixture(autouse=True)
def ko_only(tmp_path, monkeypatch):
    root = tmp_path / "ko"
    shutil.copytree(config.CHANNELS_DIR / CH, root / CH)
    monkeypatch.setattr(config, "CHANNELS_DIR", root)


@pytest.fixture
def queued(monkeypatch):
    """큐에 넣기·알림을 가짜로(작업 스레드도 진짜 알림도 없다)."""
    got = {"run": [], "trend": [], "notify": []}
    monkeypatch.setattr(web.q, "enqueue", got["run"].append)
    monkeypatch.setattr(web.q, "enqueue_trend", got["trend"].append)
    monkeypatch.setattr(web.q, "notify", got["notify"].append)
    return got


def make(**kw) -> Schedule:
    r = client.post("/schedules", data=FORM | kw, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/schedules", r.text
    return Schedule.all()[-1]


def test_create_cleans_values_and_lists():
    s = make().data
    assert (s["name"], s["topics"], s["enabled"], s["channel"]) == ("아침 상식", ["커피", "우유"], True, CH)
    assert s["when"]["times"] == ["09:00", "18:00"] and s["when"]["days"] == [0, 1, 2, 3, 4]
    html = client.get("/schedules").text
    assert "아침 상식" in html and "평일 09:00 · 18:00" in html and "남은 주제 2개" in html
    assert 'role="switch" aria-checked="true"' in html and "data-sdel=" in html and "confirm(" not in html
    assert 'href="/schedules" aria-current="page"' in html   # 상단 메뉴


def test_empty_state_and_forms():
    html = client.get("/schedules").text
    assert "아직 스케줄이 없어요" in html and "첫 스케줄 만들기" in html
    html = client.get("/schedules/new").text
    assert 'action="/schedules"' in html and 'id="src-trend" name="source" value="trend" checked' in html
    assert 'name="channel" value="momjob"' in html
    assert html.count('class="mono"') == 5   # 서버가 그린 첫 미리 보기 다섯 번
    assert 'name="period"' not in html and "YOUTUBE_API_KEY" not in html
    assert '<textarea' in html and 'name="keyword"' in html and f'maxlength="{trends.MAX_REQUEST}"' in html
    html = client.get("/schedules/new?channel=all").text
    assert "채널을 먼저 골라 주세요" in html and 'id="sched-form"' not in html


@pytest.mark.parametrize(("change", "msg"), [
    ({"name": " "}, "이름을 1~50자"),
    ({"name": "가" * 51}, "이름을 1~50자"),
    ({"topics": ""}, "주제를 한 줄에 하나씩"),
    ({"times": ["", ""]}, "시각을 1~12개"),
    ({"days": []}, "요일을 하나 이상"),
    ({"kind": "every", "every": "30"}, "1~24시간"),
    ({"kind": "every", "start": "22:00", "end": "08:00"}, "끝 시각"),
    ({"voice": "nope"}, "없는 목소리"),
    ({"source": "x"}, "주제 출처"),
    ({"channel": "nope"}, "채널이 없어요"),
])
def test_create_rejects_in_korean(change, msg):
    r = client.post("/schedules", data=FORM | change)
    assert r.status_code == 400 and msg in r.json()["detail"]
    assert Schedule.all() == []


def test_edit_keeps_channel_and_history():
    s = make()
    s.update(runs=[{"at": "2026-10-15T09:00:00+09:00", "slot": None, "result": "missed", "job": None,
                    "trend": None, "topic": None, "note": None}])
    html = client.get(f"/schedules/{s.id}").text
    assert f'action="/api/schedules/{s.id}"' in html and 'type="hidden" name="channel"' not in html and "놓침" in html
    assert 'name="topics" value="커피\n우유"' not in html and "커피\n우유</textarea>" in html
    r = client.post(f"/api/schedules/{s.id}", data=FORM | {"name": "저녁", "source": "trend", "keyword": "우주",
                                                            "kind": "every", "every": "3", "channel": "x"},
                    follow_redirects=False)
    assert r.status_code == 303
    d = s.data
    assert (d["name"], d["source"], d["keyword"], d["channel"], d["when"]["kind"], d["when"]["every"]) == \
        ("저녁", "trend", "우주", CH, "every", 3)
    assert "period" not in d
    assert len(d["runs"]) == 1   # 회차 기록은 그대로
    r = client.post(f"/api/schedules/{s.id}", data=FORM | {"days": ["9"]})
    assert r.status_code == 400 and "요일" in r.json()["detail"]
    assert client.get("/schedules/nope").status_code == 404
    assert client.get("/schedules/..%2Fjobs").status_code == 404


def test_preview_returns_summary_and_next_runs():
    r = client.post("/api/schedules/preview", data=FORM | {"days": ["5", "6"], "times": ["07:30"]})
    j = r.json()
    assert r.status_code == 200 and j["summary"] == "주말 07:30"
    labels = [t["label"][-9:] for t in j["next"]]
    assert set(labels) == {"(토) 07:30", "(일) 07:30"} and 2 <= len(labels) <= 4   # 8일 안의 것만(요일·시각 따라 2~4개)
    assert j["next"][0]["rel"].endswith(("뒤", "곧"))
    r = client.post("/api/schedules/preview", data=FORM | {"kind": "every", "every": "0"})
    assert r.status_code == 400 and "1~24시간" in r.json()["detail"]
    assert Schedule.all() == []   # 저장하지 않는다


def test_toggle_run_delete(queued):
    s = make()
    r = client.post(f"/api/schedules/{s.id}/toggle")
    assert r.json() == {"ok": True, "enabled": False, "msg": "껐어요"} and not s.data["enabled"]
    assert "꺼져 있어요" in client.get("/schedules").text
    assert client.post(f"/api/schedules/{s.id}/toggle").json()["enabled"] is True
    # 지금 실행: 목록 맨 위 주제로 작업을 만들어 넣는다
    j = client.post(f"/api/schedules/{s.id}/run").json()
    assert j["result"] == "started" and "커피" in j["msg"] and len(queued["run"]) == 1
    assert s.data["topics"] == ["우유"] and s.data["runs"][-1]["slot"] is None
    html = client.get("/schedules").text
    assert 'data-active="1"' in html   # 방금 만든 작업이 돌고 있어 목록을 다시 읽는다
    # 앞 회차가 아직 돌고 있으면 건너뛴다
    j = client.post(f"/api/schedules/{s.id}/run").json()
    assert j == {"ok": False, "result": "skipped", "msg": "이전 회차가 아직 안 끝났어요"} and len(queued["run"]) == 1
    # 올라가면 목록에 업로드됨
    Job.load(queued["run"][0]).update(status="done", upload=upload_state("done", video_id="v1"))
    html = client.get(f"/schedules/{s.id}").text
    assert "업로드됨" in html and f'href="/jobs/{queued["run"][0]}"' in html and "건너뜀" in html
    assert "스케줄로 만듦" in client.get(f"/jobs/{queued['run'][0]}").text
    # 지우기: 스케줄만, 작업은 남는다
    assert client.post(f"/api/schedules/{s.id}/delete").json() == {"ok": True}
    assert Schedule.all() == [] and Job.load(queued["run"][0])
    assert client.post(f"/api/schedules/{s.id}/delete").status_code == 404


def test_run_trend_without_youtube_key(queued, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    s = make(source="trend", keyword=" 겨울 위주로\n짧게 ")
    assert s.data["keyword"] == "겨울 위주로\n짧게"
    j = client.post(f"/api/schedules/{s.id}/run").json()
    assert j["result"] == "started" and len(queued["trend"]) == 1
    assert Trend.load(queued["trend"][0]).data["keyword"] == "겨울 위주로\n짧게"
    assert "주제 찾는 중" in client.get("/schedules").text


def test_trend_summary_shows_request_or_default():
    make(name="요청 있음", source="trend", keyword="겨울 위주로")
    make(name="요청 없음", source="trend")
    html = client.get("/schedules").text
    assert "“겨울 위주로”" in html and "기본 기준" in html


def test_toggle_on_with_empty_list_is_rejected(queued):
    s = make(topics="커피")
    client.post(f"/api/schedules/{s.id}/run")
    Job.load(queued["run"][0]).update(status="failed")
    j = client.post(f"/api/schedules/{s.id}/run").json()   # 목록이 비어 꺼진다 + 알림
    assert j["result"] == "failed" and not s.data["enabled"] and len(queued["notify"]) == 1
    r = client.post(f"/api/schedules/{s.id}/toggle")
    assert r.status_code == 400 and "주제를 한 줄에 하나씩" in r.json()["detail"]


def test_notify_test(monkeypatch):
    r = client.post("/api/notify/test")
    assert r.status_code == 400 and "알림 설정이 없어요" in r.json()["detail"]
    sent = []
    monkeypatch.setattr(registry, "notify", lambda text: sent.append(text) or [("Discord", None), ("Telegram", "401")])
    j = client.post("/api/notify/test").json()
    assert j["msg"] == "Discord로 보냈어요 (Telegram: 401)" and "[테스트]" in sent[0]
    monkeypatch.setattr(registry, "notify", lambda text: [("Telegram", "시간 초과")])
    r = client.post("/api/notify/test")
    assert r.status_code == 502 and r.json()["detail"] == "Telegram: 시간 초과"


def test_notify_panel_and_check(monkeypatch):
    html = client.get("/schedules").text
    assert "Discord · 설정 안 됨" in html and "data-notify-test disabled" in html
    assert [c for c in web._checks(CH) if c[1] == "알림"][0][0] == "warn"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/hook")
    html = client.get("/schedules").text
    assert "Discord · 연결됨" in html and "data-notify-test disabled" not in html
    assert ("ok", "알림 · Discord") == web._checks(CH)[-1][:2]


def test_list_filters_by_channel(tmp_path, monkeypatch):
    root = tmp_path / "channels"
    shutil.copytree(config.CHANNELS_DIR / CH, root / CH)
    shutil.copytree(root / CH, root / "en-space-facts")
    monkeypatch.setattr(config, "CHANNELS_DIR", root)
    make(name="한국 채널")
    make(name="영어 채널", channel="en-space-facts")
    ko = client.get("/schedules?channel=momjob").text
    assert "한국 채널" in ko and "영어 채널" not in ko
    every = client.get("/schedules?channel=all").text
    assert "한국 채널" in every and "영어 채널" in every and 'class="badge b-ch"' in every


def test_save_keeps_topics_used_meanwhile_out():
    s = make()
    html = client.get(f"/schedules/{s.id}").text
    assert 'name="topics_base" value="커피\n우유"' in html
    s.update(topics=["우유"])   # 화면을 연 뒤 회차가 "커피"를 썼다
    r = client.post(f"/api/schedules/{s.id}", data=FORM | {"name": "새 이름", "topics": "커피\n우유\n차",
                                                            "topics_base": "커피\n우유"}, follow_redirects=False)
    assert r.status_code == 303 and s.data["topics"] == ["우유", "차"] and s.data["name"] == "새 이름"


def test_new_from_all_channels_picks_back_to_form():
    html = client.get("/schedules/new?channel=all").text
    assert 'class="ch-pick" method="get" action="/schedules/new"' in html
    assert 'class="ch-pick" method="get" action="/schedules"' in client.get("/schedules").text
    assert 'data-idle="30000"' in client.get("/schedules").text   # 저절로 도는 회차를 보려고 쉬는 동안에도 본다


def test_recover_notifies_scheduled_and_view_shows_trend_state(queued):
    s = make(source="trend", topics="")
    t = Trend.create(CH)
    t.update(schedule=s.id, status="running")
    s.update(runs=[{"at": "2026-10-15T09:00:00+09:00", "slot": None, "result": "started", "job": None,
                    "trend": t.id, "topic": None, "note": None}])
    assert web._run_view(s.data["runs"][0])["label"] == "주제 찾는 중"
    job = Job.create(CH, "커피", VOICE, source={"schedule": s.id})
    job.update(status="done", upload=upload_state("running"))
    web.recover()
    assert t.data["status"] == "interrupted" and s.data["runs"][0]["result"] == "failed"
    assert "주제 찾기 실패: 서버가 꺼져 멈췄어요" in queued["notify"][0] and "업로드 실패" in queued["notify"][1]
    s.update(runs=[s.data["runs"][0] | {"result": "started"}])   # after_trend가 못 돈 경우
    assert web._run_view(s.data["runs"][0])["label"] == "중단"


def test_run_view_shows_review_wait():
    s = make()
    job = Job.create(CH, "커피", VOICE, source={"schedule": s.id}, review=True)
    job.update(status="waiting")
    run = {"at": "2026-10-15T09:00:00+09:00", "slot": None, "result": "started", "job": job.id, "trend": None,
           "topic": "커피", "note": None}
    assert web._run_view(run)["label"] == "대본 확인"
    job.update(confirmed=True)   # 확정하면 클립 대기로 돌아간다
    assert web._run_view(run)["label"] == "클립 대기"

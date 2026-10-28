import shutil

import pytest
from fastapi.testclient import TestClient

from shorts_printer import config
from shorts_printer.adapters.youtube import YouTube
from shorts_printer.core import channel, trends
from shorts_printer.core.pipeline import Job
from shorts_printer.core.trends import Trend
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")
VOICE = "LKOcTG4J4tYTPR9DnLeM"
CH = "ko-40sec-facts"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """업로드 토큰(.secrets)을 보지 않게 하고, 앞 테스트가 남긴 채널 쿠키를 비운다."""
    monkeypatch.setattr(YouTube, "ready", lambda self: False)
    client.cookies.clear()


@pytest.fixture(autouse=True)
def ko_only(tmp_path, monkeypatch):
    """실제 channels/에 채널이 늘어도 첫 채널(쿠키 없을 때 기본)이 ko-40sec-facts가 되게 한다."""
    root = tmp_path / "ko"
    shutil.copytree(config.CHANNELS_DIR / CH, root / CH)
    monkeypatch.setattr(config, "CHANNELS_DIR", root)


@pytest.fixture
def queued(monkeypatch):
    got = []
    monkeypatch.setattr(web.q, "enqueue_trend", got.append)
    return got


def pick(i=0, **kw):
    return {"topic": f"정전기 {i}", "angle": "문고리부터", "content": "건조해서 전하가 쌓인다", "format": "잡학·상식",
            "why_now": "겨울이라", "total": 90 - i, "refs": [], "scores": {"fit": 5, "fresh": 4, "safe": 5},
            "search_terms": ["static spark"]} | kw


def done_trend(keyword="겨울", n=10):
    t = Trend.create(CH, keyword)
    t.put("picks.json", {"summary": "겨울 궁금증", "excluded": [], "picks": [pick(i) for i in range(n)]})
    t.update(status="done", steps={"pick": {"status": "done", "engine": "m", "sec": 1.0}})
    return t


def old_trend(status="done"):
    """예전 인기 쇼츠 분석 기록: mode·period·quota, 세 단계, videos.json·analyses.json, refs 있는 picks."""
    t = Trend.create(CH, "자취")
    st = "done" if status == "done" else "failed"
    t.update(status=status, mode="trend", period="3d", quota=101, progress={"done": 3, "total": 3},
             error=None if status == "done" else {"step": "collect", "message": "할당량"},
             steps={s: {"status": st, "engine": "x", "sec": 1.0} for s in ("collect", "analyze", "pick")})
    t.put("videos.json", [{"id": "vid1", "rank": 1, "title": "쇼츠1", "channel": "채널", "duration": 34.0,
                           "views": 123_456, "views_per_hour": 3400.0, "engagement": 0.0123, "age_hours": 30.0,
                           "published_at": "2026-10-12T03:00:00Z", "thumb": "https://i.ytimg.com/vi/vid1/hq.jpg",
                           "url": "https://www.youtube.com/shorts/vid1", "description": ""}])
    t.put("analyses.json", {"vid1": {"status": "ok", "error": None, "shot_count": 9, "avg_shot_sec": 3.8,
                                     "frames": [{"file": "frames/vid1_0.jpg", "t": 1.5}],
                                     "claude": {"hook": "첫 컷에 가격", "footage_desc": "손", "text_overlay": "자막",
                                                "why_popular": "신상이라"}}})
    if status == "done":
        p = pick(topic="라면 끓이는 과학", refs=["vid1", "nope"], scores={"trend": 5, "fit": 4, "fresh": 4, "safe": 5})
        del p["content"]   # 예전 추천에는 내용이 없다
        t.put("picks.json", {"summary": "음식 리뷰가 뜬다", "excluded": [{"video_id": "vid1", "reason": "방송 클립"}],
                             "picks": [p]})
    return t


def test_trends_page_form_and_list():
    html = client.get("/trends").text
    assert "<textarea" in html and f'maxlength="{trends.MAX_REQUEST}"' in html and "추가 요청" in html
    assert "추천 받기" in html and "지난 추천" in html and 'aria-current="page"' in html
    assert 'name="period"' not in html and 'name="mode"' not in html
    assert "YouTube Data API" not in html and "유닛" not in html
    done_trend("겨울 위주로")
    done_trend("")
    html = client.get("/trends").text
    assert "겨울 위주로" in html and "기본 기준" in html and 'data-active="0"' in html


def test_create_trend_with_request_only(queued, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert not hasattr(trends, "ready")   # YouTube 키를 보지 않는다
    request = "겨울철 주제 위주로\n초등학생도 알아들을 소재"
    r = client.post("/trends", data={"keyword": f" {request} ", "channel": CH}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/trends/{queued[0]}"
    d = Trend.load(queued[0]).data
    assert (d["keyword"], d["channel"]) == (request, CH) and "period" not in d and "mode" not in d
    r = client.post("/trends", data={"channel": CH, "period": "30d", "mode": "nope"}, follow_redirects=False)
    assert r.status_code == 303 and Trend.load(queued[1]).data["keyword"] == ""   # 예전 값은 무시한다
    r = client.post("/trends", data={"channel": "all"})   # 전체 채널에서는 시작하지 않는다
    assert r.status_code == 400 and r.json()["detail"] == "채널을 먼저 골라 주세요"
    assert client.post("/trends", data={"channel": "nope"}).status_code == 400 and len(queued) == 2


def test_trend_page_shows_request_criteria_and_picks():
    t = done_trend("겨울 위주로\n초등학생도 알아듣게")
    html = client.get(f"/trends/{t.id}").text
    assert "“겨울 위주로" in html and "초등학생도 알아듣게" in html and "겨울 궁금증" in html
    assert "건조해서 전하가 쌓인다" in html and html.count('class="pick"') == 10
    assert 'id="c-videos"' not in html and 'id="c-analyses"' not in html and "참고 쇼츠" not in html
    assert "화제성" in html and "호기심" in html and "시간당 조회수" not in html and "Claude가 매김" in html
    assert '<span class="mono">25</span>' in html and '<span class="mono">30</span>' in html   # 채널 가중치 그대로
    assert 'name="pick" value="0"' in html and "이 주제로 만들기" in html and f'action="/trends/{t.id}/again"' in html
    assert client.get("/trends/..%2Fx").status_code == 404 and client.get("/trends/nope").status_code == 404


def test_trend_page_before_results():
    t = Trend.create(CH)
    t.update(status="queued")
    html = client.get(f"/trends/{t.id}").text
    assert "기본 기준 추천" in html and "대기열에서 차례를 기다려요" in html and 'data-active="1"' in html
    assert "다시 뽑기" not in html


def test_trend_page_queued_after_failure_says_waiting():
    t = Trend.create(CH)   # 다시 시도 직후: status만 queued, 실패한 단계는 아직 failed
    t.update(status="queued", steps={"pick": {"status": "failed", "engine": None, "sec": 1.0}})
    html = client.get(f"/trends/{t.id}").text
    assert "대기열에서 차례를 기다려요" in html and "이 단계에서 멈췄어요" not in html


def test_trend_api_and_retry(monkeypatch):
    t = Trend.create(CH)
    t.update(status="running", steps={"pick": {"status": "running", "engine": None, "sec": None}})
    d = client.get(f"/api/trends/{t.id}").json()
    assert d["say"] == "선정 진행 중" and d["log"] == []
    t.update(status="failed", error={"step": "pick", "message": "키"},
             steps={"pick": {"status": "failed", "engine": None, "sec": None}})
    assert client.get(f"/api/trends/{t.id}").json()["say"] == "실패: 선정"
    t.update(error={"step": None, "message": "채널"})   # 워커가 채널을 못 읽으면 step 없이 남긴다
    assert client.get(f"/api/trends/{t.id}").json()["say"] == "실패: 채널 설정"
    monkeypatch.setattr(web.q, "enqueue_trend", lambda _id: False)
    r = client.post(f"/api/trends/{done_trend().id}/retry")
    assert r.status_code == 409 and "이미 끝난" in r.text
    monkeypatch.setattr(web.q, "enqueue_trend", lambda _id: True)
    assert client.post(f"/api/trends/{t.id}/retry").json() == {"ok": True}


def test_create_job_from_pick_uses_server_values(monkeypatch):
    queued = []
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    t = done_trend()
    r = client.post("/jobs", data={"trend": t.id, "pick": "0", "voice": VOICE, "topic": "해킹"}, follow_redirects=False)
    assert r.status_code == 303
    d = Job.load(queued[0]).data
    assert (d["topic"], d["source"], d["channel"]) == ("정전기 0", {"trend": t.id, "pick": 0}, CH)
    assert d["brief"] == ("방향: 문고리부터\n내용: 건조해서 전하가 쌓인다\n포맷: 잡학·상식\n"
                          "지금 만들 이유: 겨울이라\n화면 검색어 후보: static spark")
    html = client.get(f"/jobs/{d['id']}").text
    assert "추천 주제에서 만듦" in html and f"/trends/{t.id}#p-0" in html and "문고리부터" in html
    assert client.post("/jobs", data={"trend": t.id, "pick": "10", "voice": VOICE}).status_code == 400
    assert client.post("/jobs", data={"trend": t.id, "voice": VOICE}).status_code == 400
    assert client.post("/jobs", data={"trend": "nope", "pick": "0", "voice": VOICE}).status_code == 404
    assert len(queued) == 1


def test_old_trend_record_still_opens_and_makes_jobs(monkeypatch):
    t = old_trend()
    html = client.get(f"/trends/{t.id}").text
    assert "라면 끓이는 과학" in html and 'name="pick" value="0"' in html
    assert 'id="c-videos"' not in html and "참고 쇼츠" not in html and "/trend-files/" not in html
    assert client.get(f"/api/trends/{t.id}").status_code == 200
    assert "자취" in client.get("/trends").text
    assert "라면 끓이는 과학" in client.get("/").text
    queued = []
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    assert client.post("/jobs", data={"trend": t.id, "pick": "0", "voice": VOICE},
                       follow_redirects=False).status_code == 303
    assert "참고 쇼츠" not in Job.load(queued[0]).data["brief"]
    failed = old_trend("failed")   # 예전 단계(수집)에서 멈춘 기록
    assert "실패: 예전 단계" in client.get(f"/trends/{failed.id}").text
    assert client.get(f"/api/trends/{failed.id}").json()["say"] == "실패: 예전 단계"


def test_dashboard_recommendations():
    html = client.get("/").text
    assert "에서 추천을 받으면 여기에 상위 3개가 떠요" in html and "YouTube Data API" not in html
    t = done_trend()
    html = client.get("/").text
    assert "정전기 0" in html and "추천 보기 · " in html and f'value="{t.id}"' in html
    assert "상위 3개가 떠요" not in html


def test_trends_follow_selected_channel():
    done_trend("겨울")
    Trend.create("en-space-facts", "우주 이야기")   # 다른 채널 기록(채널 폴더는 없어도 목록 거르기는 된다)
    html = client.get("/trends").text
    assert 'name="channel" value="ko-40sec-facts"' in html and "겨울" in html and "우주 이야기" not in html
    html = client.get("/trends?channel=all").text
    assert "우주 이야기" in html and f'b-ch">{channel.load(CH).name}' in html
    assert "채널을 하나 고른 뒤" in html and 'action="/trends"' in html
    assert "정전기 0" in client.get("/?channel=ko-40sec-facts").text


def test_recover_interrupts_running_trend():
    t = Trend.create(CH)
    t.update(status="running")
    web.recover()
    assert t.data["status"] == "interrupted"


def test_again_button(queued):
    t = done_trend("겨울", n=1)
    t.update(status="running")
    assert "다시 뽑기" not in client.get(f"/trends/{t.id}").text   # 아직 안 끝났다
    assert client.post(f"/trends/{t.id}/again").status_code == 409
    t.update(status="done")
    r = client.post(f"/trends/{t.id}/again", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/trends/{queued[0]}"
    d = Trend.load(queued[0]).data
    assert (d["keyword"], d["avoid"]) == ("겨울", ["정전기 0"])
    old = old_trend()   # 예전 기록도 끝났으면 다시 뽑는다
    assert f'action="/trends/{old.id}/again"' in client.get(f"/trends/{old.id}").text
    assert client.post(f"/trends/{old.id}/again", follow_redirects=False).status_code == 303
    assert "mode" not in Trend.load(queued[1]).data

import pytest
from fastapi.testclient import TestClient

from shorts_printer.adapters.youtube import YouTube
from shorts_printer.core import trends
from shorts_printer.core.pipeline import Job
from shorts_printer.core.trends import Trend
from shorts_printer.infra.store import atomic_write_json
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")
VOICE = "LKOcTG4J4tYTPR9DnLeM"
CH = "ko-40sec-facts"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """업로드 토큰(.secrets)을 보지 않게 하고, 앞 테스트가 남긴 채널 쿠키를 비운다."""
    monkeypatch.setattr(YouTube, "ready", lambda self: False)
    client.cookies.clear()


def video(i, **kw):
    return {"id": f"vid{i}", "rank": i, "title": f"쇼츠{i}", "channel": "채널", "published_at": "2026-10-12T03:00:00Z",
            "duration": 34.0, "views": 123_456, "likes": 1000, "comments": 50, "thumb": f"https://i.ytimg.com/vi/vid{i}/hq.jpg",
            "url": f"https://www.youtube.com/shorts/vid{i}", "age_hours": 30.0, "views_per_hour": 3400.0,
            "engagement": 0.0123, "description": ""} | kw


CLAUDE = {"topic": "편의점 신상 리뷰", "format": "음식", "hook": "첫 컷에 가격", "footage_type": "직접 촬영",
          "footage_desc": "손에 든 과자", "narration": "사람 목소리", "text_overlay": "큰 노란 자막",
          "why_popular": "신상이라", "replicable": 3, "replicable_reason": "스톡으로 비슷하게"}


def done_trend(keyword="자취"):
    t = Trend.create(CH, keyword, "3d")
    atomic_write_json(t.dir / "videos.json", [video(1), video(2), video(3)])
    atomic_write_json(t.dir / "analyses.json", {
        "vid1": {"status": "ok", "error": None, "shot_count": 9, "avg_shot_sec": 3.8, "has_transcript": True,
                 "frames": [{"file": "frames/vid1_0.jpg", "t": 1.5}], "claude": CLAUDE},
        "vid2": {"status": "meta_only", "error": "영상을 못 받아", "shot_count": None, "avg_shot_sec": None,
                 "has_transcript": False, "frames": [], "claude": CLAUDE},
        "vid3": {"status": "failed", "error": "Claude 오류", "frames": [], "claude": None}})
    atomic_write_json(t.dir / "picks.json", {"summary": "음식 리뷰가 뜬다",
                                             "excluded": [{"video_id": "vid3", "reason": "방송 클립"}],
                                             "picks": [{"topic": "라면 끓이는 과학", "angle": "물 양부터 의심하게",
                                                        "format": "꿀팁·하우투", "why_now": "라면 쇼츠가 빨리 오른다",
                                                        "total": 82, "refs": ["vid1", "nope"],
                                                        "scores": {"trend": 5, "fit": 4, "fresh": 4, "safe": 5},
                                                        "search_terms": ["ramen boiling"]}]})
    t.update(status="done", quota=101, steps={s: {"status": "done", "engine": "x", "sec": 1.0} for s in trends.STEPS})
    return t


def test_korean_numbers_and_age():
    nums = (None, 950, 3400, 12_345, 123_456, 110_000_000)
    assert [web.kn(n) for n in nums] == ["-", "950", "3.4천", "1.2만", "12만", "1.1억"]
    assert web.kn(9_960) == "1만"   # 반올림해서 단위가 올라가면 위 단위로
    assert (web.ago(5.4), web.ago(30), web.ago(None)) == ("5시간 전", "1일 전", "")


def test_trends_page_states(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: False)
    html = client.get("/trends").text
    assert "아직 분석이 없어요" in html and "YouTube Data API 키가 필요해요" in html and "disabled" in html
    assert 'aria-current="page"' in html and "99번쯤" in html
    monkeypatch.setattr(trends, "ready", lambda: True)
    done_trend()
    html = client.get("/trends").text
    assert "키가 필요해요" not in html and "자취 · 최근 3일" in html and "101유닛" in html and 'data-active="0"' in html


def test_create_trend_validates_and_redirects(monkeypatch):
    queued = []
    monkeypatch.setattr(web.q, "enqueue_trend", queued.append)
    monkeypatch.setattr(trends, "ready", lambda: True)
    assert client.post("/trends", data={"keyword": "가" * 51, "channel": CH}).status_code == 400
    assert client.post("/trends", data={"period": "30d", "channel": CH}).status_code == 400
    r = client.post("/trends", data={"channel": "all"})   # 전체 채널에서는 분석을 시작하지 않는다
    assert r.status_code == 400 and r.json()["detail"] == "채널을 먼저 골라 주세요"
    assert client.post("/trends", data={"channel": "nope"}).status_code == 400
    r = client.post("/trends", data={"keyword": " 요리 ", "period": "7d", "channel": CH}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/trends/{queued[0]}"
    d = Trend.load(queued[0]).data
    assert (d["keyword"], d["period"], d["channel"]) == ("요리", "7d", CH)
    monkeypatch.setattr(trends, "ready", lambda: False)
    assert client.post("/trends", data={"channel": CH}).status_code == 400 and len(queued) == 1


def test_trend_page_shows_process_criteria_and_picks():
    t = done_trend()
    html = client.get(f"/trends/{t.id}").text
    assert "“자취” 인기 쇼츠 분석" in html
    assert 'data-embed="vid1"' in html and "12만회" in html and "3.4천회" in html
    assert "1.2%" in html and "1일 전" in html
    assert f'/trend-files/{t.id}/frames/vid1_0.jpg' in html and "컷 9개 · 평균 3.8초" in html
    assert "썸네일만" in html and "썸네일과 제목·설명·통계만으로" in html and "분석하지 못했어요: Claude 오류" in html
    assert "편의점 신상 리뷰" in html and "직접 촬영" in html
    assert "화제성" in html and "시간당 조회수로 계산" in html and "Claude가 매김" in html
    assert "라면 끓이는 과학" in html and "82<small>/100</small>" in html and 'href="#v-vid1"' in html
    assert 'name="trend" value="' + t.id in html and 'name="pick" value="0"' in html and "이 주제로 만들기" in html
    assert "고르지 않은 영상" in html and "방송 클립" in html and "101 / 10,000유닛" in html
    assert client.get("/trends/..%2Fx").status_code == 404 and client.get("/trends/nope").status_code == 404


def test_trend_page_before_results():
    t = Trend.create(CH)
    t.update(status="queued")
    html = client.get(f"/trends/{t.id}").text
    assert "KR 인기 쇼츠 분석" in html and "40초 상식" in html
    assert "대기열에서 차례를 기다려요" in html and 'data-active="1"' in html
    t.update(status="running", progress={"done": 3, "total": 8},
             steps=t.data["steps"] | {"collect": {"status": "done", "engine": "x", "sec": 2.0},
                                      "analyze": {"status": "running", "engine": None, "sec": None}})
    atomic_write_json(t.dir / "videos.json", [video(1)])
    html = client.get(f"/trends/{t.id}").text
    assert 'aria-valuenow="3"' in html and "분석 중·대기" in html and "분석이 끝나면 Claude가" in html


def test_trend_page_queued_after_failure_says_waiting():
    t = Trend.create(CH)   # 다시 시도 직후: status만 queued, 실패한 단계는 아직 failed
    t.update(status="queued", steps=t.data["steps"] | {"collect": {"status": "failed", "engine": None, "sec": 1.0}})
    html = client.get(f"/trends/{t.id}").text
    assert "대기열에서 차례를 기다려요" in html and "이 단계에서 멈췄어요" not in html


def test_trend_api_and_retry(monkeypatch):
    t = Trend.create(CH)
    t.update(status="running", progress={"done": 3, "total": 8},
             steps=t.data["steps"] | {"analyze": {"status": "running", "engine": None, "sec": None}})
    d = client.get(f"/api/trends/{t.id}").json()
    assert d["say"] == "분석 진행 중 3/8" and d["sig"] == "running:prp:3:0" and d["log"] == []
    t.update(status="failed", error={"step": "analyze", "message": "키"},
             steps=t.data["steps"] | {"analyze": {"status": "failed", "engine": None, "sec": None}})
    assert client.get(f"/api/trends/{t.id}").json()["say"] == "실패: 분석"
    monkeypatch.setattr(web.q, "enqueue_trend", lambda _id: False)
    r = client.post(f"/api/trends/{done_trend().id}/retry")
    assert r.status_code == 409 and "이미 끝난 분석" in r.text
    monkeypatch.setattr(web.q, "enqueue_trend", lambda _id: True)
    assert client.post(f"/api/trends/{t.id}/retry").json() == {"ok": True}


def test_create_job_from_pick_uses_server_values(monkeypatch):
    queued = []
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    t = done_trend()
    r = client.post("/jobs", data={"trend": t.id, "pick": "0", "voice": VOICE, "topic": "해킹"}, follow_redirects=False)
    assert r.status_code == 303
    d = Job.load(queued[0]).data
    assert (d["topic"], d["source"], d["channel"]) == ("라면 끓이는 과학", {"trend": t.id, "pick": 0}, CH)
    # 방향에 근거 쇼츠 분석이 붙는다. 모르는 ref(nope)는 건너뛴다
    assert d["brief"].startswith("방향: 물 양부터 의심하게\n포맷: 꿀팁·하우투\n"
                                 "지금 만들 이유: 라면 쇼츠가 빨리 오른다\n화면 검색어 후보: ramen boiling")
    assert "컷 평균 3.8초" in d["brief"] and "인기 이유 신상이라" in d["brief"] and d["brief"].count("- 참고 쇼츠") == 1
    html = client.get(f"/jobs/{d['id']}").text
    assert "추천 주제에서 만듦" in html and f"/trends/{t.id}#p-0" in html and "물 양부터 의심하게" in html
    assert client.post("/jobs", data={"trend": t.id, "pick": "5", "voice": VOICE}).status_code == 400
    assert client.post("/jobs", data={"trend": t.id, "voice": VOICE}).status_code == 400
    assert client.post("/jobs", data={"trend": "nope", "pick": "0", "voice": VOICE}).status_code == 404
    assert len(queued) == 1


def test_dashboard_recommendations(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: False)
    html = client.get("/").text
    assert "아직 추천이 없어요" in html and "YouTube Data API 키" in html and "주제 찾기용" in html
    t = done_trend()
    html = client.get("/").text
    assert "라면 끓이는 과학" in html and "82" in html and f'value="{t.id}"' in html
    assert "아직 추천이 없어요" not in html


def test_trends_follow_selected_channel(monkeypatch):
    monkeypatch.setattr(trends, "ready", lambda: True)
    done_trend()
    Trend.create("en-space-facts", "space", "3d")   # 다른 채널 분석(채널 폴더는 없어도 목록 거르기는 된다)
    html = client.get("/trends").text
    assert 'name="channel" value="ko-40sec-facts"' in html and "자취" in html and "space" not in html
    assert "KR에서 요즘" in html and "한국어 쇼츠" in html
    html = client.get("/trends?channel=all").text
    assert "space" in html and 'b-ch">40초 상식' in html
    assert "채널을 하나 고른 뒤" in html and 'action="/trends"' in html
    assert "라면 끓이는 과학" in client.get("/?channel=ko-40sec-facts").text


def test_recover_interrupts_running_trend():
    t = Trend.create(CH)
    t.update(status="running")
    web.recover()
    assert t.data["status"] == "interrupted"

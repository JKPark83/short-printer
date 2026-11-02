import pytest
from fastapi.testclient import TestClient
from test_insights import TODAY, FakeAPI, ReviewLLM

from shorts_printer import registry
from shorts_printer.core import insights
from shorts_printer.core.pipeline import Job
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")
CH = "momjob"


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(registry, "analytics", lambda ch: api)
    monkeypatch.setattr(insights, "pacific_today", lambda now=None: TODAY)
    client.cookies.clear()
    return api


def get(path):
    r = client.get(path + ("&" if "?" in path else "?") + f"channel={CH}")
    assert r.status_code == 200
    return r.text


def test_overview_shows_kpis_trend_format_highlights_and_links_the_job():
    job = Job.create(CH, "에이티즈 컴백", "noeul")
    job.update(upload={"status": "done", "video_id": "AAAAAAAAAAA"})
    html = get("/insights")
    assert 'href="/insights"' in html   # 주 메뉴에 성과
    assert "10/03 ~ 10/30" in html and "150" in html and "▲</span> 50.0%" in html
    assert 'class="in-spark"' in html and 'class="before"' in html and "최고 10회" in html   # 추세·앞 기간·최고 날
    assert "conic-gradient(" in html and "일반 영상" in html   # Shorts·일반 도넛
    assert "1천 회당 반응" in html and "in-week" in html   # 하이라이트·요일 리듬(28일)
    assert "요일마다 비슷해요" in html and "월요일화요일" not in html   # 가짜는 매일 10회라 1등 요일이 없다
    assert 'class="in-sticker left"' in html   # 맨 앞 날이 최고면 스티커가 왼쪽 밖으로 나가지 않게
    assert "영상 A" in html and f'href="/jobs/{job.id}"' in html and "미국 태평양 시간" in html


def test_videos_audience_and_video_detail():
    html = get("/insights?tab=videos&sort=views")
    assert "영상 B" in html and "0:45" in html and "page=N2" in html
    assert "기간 조회수" in html and "300" in html and "이 기간 성과가 아직 없어요" in html   # B는 기간 성과 없음
    assert 'aria-current="true">기간 조회수순' in html
    html = get("/insights?tab=audience")
    assert "Shorts 피드" in html and "50.0%" in html and "MYSTERY" in html and "한국" in html
    assert html.count("conic-gradient(") == 3   # 형식·구독 여부·기기는 도넛
    html = get("/insights/videos/AAAAAAAAAAA?days=7")
    assert "구간 유지율" in html and "<polyline points=" in html and "https://youtu.be/AAAAAAAAAAA" in html
    assert "어디서 보러 왔나" in html and "채널 평균보다 +10.0%p" in html   # 영상 50% · 채널 40%


def test_not_connected_and_api_errors_show_a_banner(monkeypatch, fake):
    monkeypatch.setattr(fake, "ready", lambda: False)
    fake.hint = "선택 · 터미널에서 uv run sp youtube-login --channel x"
    assert "YouTube가 연결되지 않았어요" in get("/insights")
    monkeypatch.setattr(fake, "ready", lambda: True)

    def boom(**p):
        raise RuntimeError("채널 성과를 읽을 권한이 없어요.")
    monkeypatch.setattr(fake, "report", boom)
    assert "채널 성과를 읽을 권한이 없어요." in get("/insights")
    assert "이 채널이 올린 영상만" not in get("/insights/videos/AAAAAAAAAAA")
    assert "올바르지 않아요" in get("/insights/videos/bad")


def test_ai_review_button_runs_saves_and_shows_ideas(monkeypatch):
    monkeypatch.setattr(registry, "insight_llm", lambda ch: ReviewLLM())
    assert "분석 받기" in get("/insights")
    r = client.post(f"/insights/review?channel={CH}", data={"days": "28"}, follow_redirects=False)
    assert r.status_code == 303 and "#ai-review" in r.headers["location"]
    html = get("/insights")
    assert "조회가 적어 우연이 커요" in html and "다시 분석" in html and html.count('name="keyword" value="주제 ') == 3

    class Broken(ReviewLLM):
        def ask(self, *a, **k):
            raise RuntimeError("Claude API 키가 없어요.")
    monkeypatch.setattr(registry, "insight_llm", lambda ch: Broken())
    client.post(f"/insights/review?channel={CH}", data={"days": "28"})
    html = get("/insights")
    assert "지난 분석을 받지 못했어요: Claude API 키가 없어요." in html and "조회가 적어 우연이 커요" in html

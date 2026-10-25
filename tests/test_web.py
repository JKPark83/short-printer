import re
import shutil

import pytest
from fastapi.testclient import TestClient

from shorts_printer import config, registry
from shorts_printer.adapters.youtube import YouTube
from shorts_printer.core import channel
from shorts_printer.core.longform import STEPS_LONG
from shorts_printer.core.pipeline import STEPS, Job
from shorts_printer.core.trends import Trend
from shorts_printer.infra import store
from shorts_printer.infra.sqlite import SQLiteStore
from shorts_printer.infra.store import atomic_write_json, upload_state
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")   # with 블록 없이 써서 lifespan(작업 스레드)을 띄우지 않는다
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
def two_channels(tmp_path, monkeypatch):
    """ko-40sec-facts + 목소리가 다른 en-space-facts."""
    root = tmp_path / "channels"
    shutil.copytree(config.CHANNELS_DIR / CH, root / CH)
    en = root / "en-space-facts"
    shutil.copytree(root / CH, en)
    toml = (en / "channel.toml").read_text(encoding="utf-8")
    head, voices = toml.split("[tts.voices]")
    head = re.sub(r'(?m)^name = ".*"', 'name = "Space Facts"', head).replace('language = "ko"', 'language = "en"')
    head = re.sub(r'(?m)^default = ".*"', 'default = "enVoice1"', head)
    head = head.replace("daily_goal = 1", "daily_goal = 2")
    voices = '\nenVoice1 = "Adam"\n\n[video]' + voices.split("[video]", 1)[1]
    (en / "channel.toml").write_text(head + "[tts.voices]" + voices, encoding="utf-8")
    monkeypatch.setattr(config, "CHANNELS_DIR", root)
    return "en-space-facts"


def done_job(channel=CH, voice="LKOcTG4J4tYTPR9DnLeM", topic="커피"):
    job = Job.create(channel, topic, voice)
    job.put("script.json", {"title": "제목", "description": "설명", "tags": ["커피 상식", "카페"],
                            "sentences": ["하나", "둘"], "prompts": ["p1", "p2"], "search_terms": ["coffee", "cup"]})
    job.put("clips.json", [])
    job.put("cues.json", [{"start": 0, "end": 1.4, "text": "하나"}])
    job.update(status="done", duration=21.1, finished_at="2026-10-13T21:00:00+09:00",
               usage={"model": "claude-opus-5-5", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.01},
               steps={s: {"status": "done", "engine": "x", "sec": 1.0} for s in STEPS})
    job.log("완성")
    return job


def test_dashboard_lists_jobs_and_stats():
    assert "아직 작업이 없어요" in client.get("/").text
    done_job()
    html = client.get("/").text
    assert "커피" in html and "$0.01" in html and "0:21" in html and 'data-active="0"' in html


def test_create_validates_and_redirects(monkeypatch):
    queued = []
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    assert client.post("/jobs", data={"topic": "  ", "voice": "elevenlabs", "channel": CH}).status_code == 400
    assert client.post("/jobs", data={"topic": "커피", "voice": "ko-KR-SunHiNeural", "channel": CH}).status_code == 400
    assert client.post("/jobs", data={"topic": "커피", "voice": "elevenlabs"}).status_code == 400   # 채널 없음
    assert client.post("/jobs", data={"topic": "커피", "voice": "elevenlabs", "channel": "all"}).status_code == 400
    r = client.post("/jobs", data={"topic": " 커피 ", "voice": "elevenlabs", "channel": CH}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/jobs/{queued[0]}"
    d = Job.load(queued[0]).data
    assert (d["topic"], d["channel"], d["review"]) == ("커피", CH, True)   # 화면에서 만든 작업은 대본 확인부터
    html = client.get("/").text
    assert html.index(">미스터킴<") < html.index(">미스터최<")   # 첫 칸이 기본값


def test_job_page_api_and_retry_rules():
    job = done_job()
    html = client.get(f"/jobs/{job.id}").text
    assert "#커피상식 #카페" in html and "final.mp4?v=2026-10-13" in html and "그라데이션 배경" in html
    d = client.get(f"/api/jobs/{job.id}").json()
    assert d["sig"] == "done:dddddddd:0:-" and d["say"] == "완성" and d["log"][-1].endswith("완성")
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 409
    assert client.get("/jobs/..%2Fetc").status_code == 404 and client.get("/api/jobs/nope").status_code == 404



def test_cancel_takes_queued_job_out_and_asks_running_job_to_stop():
    job = done_job()
    assert client.post(f"/api/jobs/{job.id}/cancel").status_code == 409   # 완성된 건 취소할 게 없다
    job.update(status="queued")
    assert 'data-retry="cancel"' in client.get(f"/jobs/{job.id}").text
    assert client.post(f"/api/jobs/{job.id}/cancel").json() == {"ok": True}
    web.q.run_one(job.id)   # 큐에 남은 몫은 건너뛴다
    d = job.data
    assert d["status"] == "interrupted" and d["cancel"]
    assert client.get(f"/api/jobs/{job.id}").json()["sig"].endswith(":취소")
    html = client.get(f"/jobs/{job.id}").text
    assert "취소했어요" in html and "data-retry>" in html and 'data-retry="cancel"' not in html
    job.update(status="running", cancel=None)
    client.post(f"/api/jobs/{job.id}/cancel")
    assert job.data["status"] == "running" and "취소하는 중이에요" in client.get(f"/jobs/{job.id}").text

def test_job_page_shows_facts_refs_unverified_and_description_preview():
    job = done_job()
    job.edit("script.json", lambda s: s | {"sentences": ["물은 100도", "2배 비싸다"], "fact_ids": [["F1"], []],
                                           "prompts_ko": ["끓는 냄비", "가격 비교"]})
    job.put("facts.json", {"facts": [
        {"id": "F1", "text": "물은 100도에서 끓는다", "url": "https://a.go.kr/1", "title": "", "site": "a.go.kr",
         "kind": "official", "retrieved_at": "2026-10-16T09:00:00+09:00"},
        {"id": "F2", "text": "값이 올랐다", "url": "https://news.kr/2", "title": "", "site": "news.kr",
         "kind": "news", "retrieved_at": "2026-10-16T09:00:00+09:00"}]})
    html = client.get(f"/jobs/{job.id}").text
    assert 'id="fact-F1"' in html and "물은 100도에서 끓는다" in html and "2026-10-16 확인" in html
    assert 'class="chip chip-news">보도<' in html and 'href="#fact-F1">F1<' in html
    assert "근거 없는 문장 1개" in html and "2번 문장" in html and 'class="unv"' in html
    assert "설명란 미리보기" in html and '<pre class="desc-preview">설명\n\n출처\nhttps://a.go.kr/1\n\n' in html
    job.update(status="waiting", review=True)   # 확정 전: 영어 프롬프트 아래 한국어 한 줄
    assert '<p class="prompt-ko" lang="ko">끓는 냄비</p>' in client.get(f"/jobs/{job.id}").text


def test_lifespan_migrates_legacy_folder(tmp_path, monkeypatch):
    """예전 폴더(job.json·script.json·log.txt)만 있는 작업도 켤 때 DB로 옮겨져 화면에 뜬다."""
    job = done_job()
    for name in ("script.json", "clips.json", "cues.json"):
        atomic_write_json(job.dir / name, job.doc(name))
    atomic_write_json(job.dir / "job.json", job.data)
    (job.dir / "log.txt").write_text("12:00:00 예전 로그\n", encoding="utf-8")
    new = SQLiteStore(tmp_path / "new.db")   # 빈 DB로 켠다
    monkeypatch.setattr(store, "_STORE", new)
    monkeypatch.setattr(web.q, "start", lambda: None)
    with TestClient(web.app, base_url="http://127.0.0.1") as c:   # lifespan을 돌린다
        html = c.get(f"/jobs/{job.id}").text
    new.close()
    assert "예전 로그" in html and "#커피상식 #카페" in html and (job.dir / "log.txt").exists()   # 원본은 남는다


def test_recover_marks_running_jobs_interrupted():
    job = Job.create(CH, "커피", "LKOcTG4J4tYTPR9DnLeM")
    job.step("script", status="done")
    job.step("footage", status="running")
    job.update(status="running")
    (job.dir / "final.tmp.mp4").write_bytes(b"x")
    web.recover()
    d = job.data
    assert d["status"] == "interrupted" and d["steps"]["footage"]["status"] == "pending"
    assert d["steps"]["script"]["status"] == "done" and not (job.dir / "final.tmp.mp4").exists()
    assert "실패: " not in web.say(d) and web.say(d) == "중단"
    waiting = Job.create(CH, "차", "ko-KR-SunHiNeural")
    waiting.update(status="waiting")
    web.recover()
    assert waiting.data["status"] == "waiting"   # 사람을 기다리는 작업은 서버가 꺼져도 그대로


def test_unknown_model_cost_keeps_pages_up():
    job = done_job()
    job.update(usage=job.data["usage"] | {"cost_usd": None})   # 가격표에 없는 모델
    assert client.get("/").status_code == 200 and client.get(f"/jobs/{job.id}").status_code == 200


def test_rejects_cross_site_post_and_foreign_host(monkeypatch):
    monkeypatch.setattr(web.q, "enqueue", lambda _id: True)
    form = {"topic": "커피", "voice": "elevenlabs", "channel": CH}
    assert client.post("/jobs", data=form, headers={"Origin": "http://localhost:3000"}).status_code == 403
    for origin in ("http://127.0.0.1", "https://127.0.0.1"):   # tailscale serve: 브라우저는 https, 앱은 http로 받는다
        r = client.post("/jobs", data=form, headers={"Origin": origin}, follow_redirects=False)
        assert r.status_code == 303
    assert client.get("/", headers={"Host": "evil.example:8765"}).status_code == 400


def test_upload_endpoint_rules(monkeypatch):
    job = done_job()
    assert client.post(f"/api/jobs/{job.id}/upload").status_code == 400
    assert f"uv run sp youtube-login --channel {CH}" in client.get(f"/jobs/{job.id}").text
    monkeypatch.setattr(YouTube, "ready", lambda self: True)
    assert "승인하고 YouTube에 올리기" in client.get(f"/jobs/{job.id}").text
    draft = Job.create(CH, "차", "ko-KR-SunHiNeural")
    r = client.post(f"/api/jobs/{draft.id}/upload")
    assert r.status_code == 409 and r.json()["detail"] == "완성된 영상만 올릴 수 있어요"
    assert client.post(f"/api/jobs/{job.id}/upload").json() == {"ok": True}
    assert web.q._q.get_nowait() == ("upload", job.id)
    r = client.post(f"/api/jobs/{job.id}/upload")
    assert r.status_code == 409 and r.json()["detail"] == "이미 올리는 중이에요"
    d = client.get(f"/api/jobs/{job.id}").json()
    assert d["sig"].endswith(":queued") and d["say"] == "YouTube에 올리는 중"
    assert 'data-active="1"' in client.get(f"/jobs/{job.id}").text   # 열자마자 폴링한다
    job.update(upload=upload_state("done", video_id="VID"))
    assert client.post(f"/api/jobs/{job.id}/upload").json()["detail"] == "이미 올렸어요"
    assert "studio.youtube.com/video/VID/edit" in client.get(f"/jobs/{job.id}").text
    # 다시 올리기: 새 영상으로 올리고 예전 기록은 uploaded_before에 남긴다
    assert "data-again" in client.get(f"/jobs/{job.id}").text
    assert client.post(f"/api/jobs/{job.id}/upload?again=true").json() == {"ok": True}
    assert web.q._q.get_nowait() == ("upload", job.id)
    d = job.data
    assert d["upload"]["status"] == "queued" and d["uploaded_before"]["video_id"] == "VID"


def test_recover_fails_interrupted_upload(monkeypatch):
    job = done_job()
    job.update(upload=upload_state("running"))
    web.recover()
    d = job.data
    assert d["status"] == "done" and d["upload"]["status"] == "failed" and "스튜디오" in d["upload"]["error"]
    assert web.say(d) == "YouTube 업로드 실패"
    monkeypatch.setattr(YouTube, "ready", lambda self: True)   # 실패 뒤 [다시 올리기]
    html = client.get(f"/jobs/{job.id}").text
    assert "다시 올리기" in html and "스튜디오에서 먼저 확인" in html
    assert client.post(f"/api/jobs/{job.id}/upload").json() == {"ok": True}
    assert web.q._q.get_nowait() == ("upload", job.id)


MP4 = b"\0\0\0\x18ftypmp42" + b"x" * 16   # ftyp 머리만 있는 가짜(디코드 검증은 가짜 ffmpeg)


def scene_job(status="waiting", done=("script",)):
    job = Job.create(CH, "커피", "LKOcTG4J4tYTPR9DnLeM")
    job.put("script.json", {"title": "t", "description": "d", "tags": [],
                                                "sentences": ["하나", "둘"], "prompts": ["p1", "p2"]})
    steps = {s: {"status": "done", "engine": "x", "sec": 1.0} for s in done}
    job.update(status=status, steps=job.data["steps"] | steps)
    return job


def test_clip_upload_waits_then_enqueues(monkeypatch):
    job = scene_job()
    html = client.get(f"/jobs/{job.id}").text
    assert "p1" in html and "프롬프트 복사" in html and "클립 대기" in html and "클립 0/2" in html
    assert client.get(f"/api/jobs/{job.id}").json()["say"] == "클립 대기"
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    enqueued = []
    monkeypatch.setattr(web.q, "enqueue", enqueued.append)
    url = f"/api/jobs/{job.id}/clips"
    assert client.post(f"{url}/2", content=MP4).status_code == 404
    assert client.post(f"{url}/0", content=MP4, headers={"origin": "http://evil.com"}).status_code == 403
    assert client.post(f"{url}/0", content=b"not a video at all").status_code == 400
    monkeypatch.setattr(web, "MAX_CLIP", 10)
    assert client.post(f"{url}/0", content=MP4).status_code == 413
    monkeypatch.setattr(web, "MAX_CLIP", 1000)
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad")))
    assert client.post(f"{url}/0", content=MP4).status_code == 400
    assert not list((job.dir / "clips").glob("*.tmp.mp4"))   # 실패한 임시 파일은 남지 않는다
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    assert client.post(f"{url}/0", content=MP4).json() == {"ok": True}
    assert (job.dir / "clips" / "clip0.mp4").read_bytes() == MP4 and enqueued == []
    assert job.doc("clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"}]
    assert "클립 1/2" in client.get(f"/jobs/{job.id}").text
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and enqueued == [job.id]
    job.update(status="queued")
    assert client.post(f"{url}/0", content=MP4).status_code == 409


def test_sensitive_banner_and_confirm(monkeypatch):
    job = scene_job()
    job.put("script.json", job.doc("script.json") | {"sensitive": "금융·투자"})
    assert "민감 분야(금융·투자)" in client.get(f"/jobs/{job.id}").text
    enqueued = []
    monkeypatch.setattr(web.q, "enqueue", lambda i: enqueued.append(i) or True)
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True}
    assert enqueued == [job.id] and job.data["confirmed"] is True
    assert "민감 분야" not in client.get(f"/jobs/{job.id}").text


def test_review_edit_keeps_long_styled_prompts():
    """저장된 프롬프트엔 채널 스타일 머리말이 붙어 1000자를 넘기도 한다: 그대로 다시 보내도 저장돼야 한다."""
    job = scene_job()
    job.update(review=True)
    url, form = f"/api/jobs/{job.id}/edit", {"title": "t", "sentences": ["하나", "둘"], "voice": "elevenlabs"}
    assert client.post(url, data=form | {"prompts": ["x" * 2001, "p2"]}).status_code == 400
    assert client.post(url, data=form | {"prompts": ["x" * 1500, "p2"]}).status_code == 200
    assert job.doc("script.json")["prompts"][0] == "x" * 1500 and web.q._q.get_nowait() == ("run", job.id)


def test_review_edit_saves_and_confirm_starts(monkeypatch):
    job = scene_job()
    job.put("script.json", job.doc("script.json") | {"prompts_ko": ["가", "나"]})
    job.update(review=True)
    html = client.get(f"/jobs/{job.id}").text
    assert "대본·음성·자막을 확인해 주세요" in html and "대본 확인" in html and "대본을 확정하면 시작해요" in html
    assert 'name="prompts"' in html and "클립 바꾸기" not in html
    assert client.get("/").text.count("대본 확인")
    enqueued = []
    monkeypatch.setattr(web.q, "enqueue", lambda i: enqueued.append(i) or True)
    url = f"/api/jobs/{job.id}/edit"
    form = {"title": "t", "description": "d", "sentences": ["하나", "셋"], "prompts": ["p1", "p3"],
            "voice": "elevenlabs"}
    assert client.post(url, data=form | {"prompts": ["p1"]}).status_code == 400
    assert client.post(url, data=form).status_code == 200
    s, d = job.doc("script.json"), job.data
    assert s["sentences"] == ["하나", "셋"] and s["prompts"] == ["p1", "p3"] and d["voice"] == "elevenlabs"
    assert s["prompts_ko"] == ["가", ""]   # 바꾼 프롬프트의 한국어 풀이는 낡아서 비운다
    assert d["status"] == "queued" and d["steps"]["voice"]["status"] == "pending"   # 음성·자막만 다시
    assert d["steps"]["render"]["status"] == "pending" and web.q._q.get_nowait() == ("run", job.id)
    job.update(status="waiting")
    assert client.post(url, data=form | {"title": "t2"}).status_code == 200 and web.q._q.empty()   # 제목만이면 저장만
    rev = client.post(f"/api/jobs/{job.id}/script/revise", data={"note": "더 짧게"}).json()
    assert "다시 확인" in rev["msg"] and job.data["status"] == "queued"
    web.q._q.get_nowait()
    assert client.post(f"/api/jobs/{job.id}/confirm").status_code == 409   # 고치는 중엔 확정 못 한다
    job.update(status="waiting")
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True} and enqueued == [job.id]
    assert client.post(url, data=form).status_code == 409   # 확정 뒤엔 장면 프롬프트를 못 고친다


def test_confirm_redoes_draft_voice():
    """초안 음성으로 확인했으면 확정할 때 음성·자막을 다시 해 채널 TTS로 한 번 읽고, 음성 확정에서 다시 멈춘다."""
    job = scene_job(done=("script", "voice", "subtitles"))
    job.update(review=True, voice_draft=True)
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True}
    d = job.data
    assert d["confirmed"] is True and d["voice_ok"] is False
    assert d["status"] == "queued" and web.q._q.get_nowait() == ("run", job.id)
    assert d["steps"]["voice"]["status"] == d["steps"]["subtitles"]["status"] == "pending"

    steps = d["steps"] | {s: {"status": "done", "engine": "ElevenLabs", "sec": 1} for s in ("voice", "subtitles")}
    job.update(status="waiting", steps=steps, voice_draft=False)   # 채널 TTS로 다 읽고 영상 소스 앞에서 멈춘 뒤
    html = client.get(f"/jobs/{job.id}").text
    assert "음성 확정하고 영상 만들기" in html and "음성 다시 만들기" in html
    assert client.post(f"/api/jobs/{job.id}/voice/redo").json() == {"ok": True}   # 마음에 안 들면 다시 읽는다
    assert web.q._q.get_nowait() == ("run", job.id) and job.data["steps"]["voice"]["status"] == "pending"
    job.update(status="waiting", steps=steps)
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True}
    assert job.data["voice_ok"] is True and job.data["steps"]["voice"]["status"] == "done"   # 음성은 두고 영상으로
    assert web.q._q.get_nowait() == ("run", job.id)
    assert client.post(f"/api/jobs/{job.id}/voice/redo").status_code == 409



def test_review_job_can_redo_channel_voice():
    """초안 없이 처음부터 채널 TTS로 읽은 작업: 대본 확인 중에도 음성을 다시 만들 수 있고, 확정하면 바로 영상으로."""
    job = scene_job(done=("script", "voice", "subtitles"))
    job.update(review=True, status="waiting")
    assert "음성 다시 만들기" in client.get(f"/jobs/{job.id}").text
    assert client.post(f"/api/jobs/{job.id}/voice/redo").json() == {"ok": True}
    assert web.q._q.get_nowait() == ("run", job.id) and job.data["steps"]["voice"]["status"] == "pending"
    job.update(status="waiting", steps=job.data["steps"] | {s: {"status": "done"} for s in ("voice", "subtitles")})
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True}
    assert job.data["confirmed"] is True and "voice_ok" not in job.data
    assert web.q._q.get_nowait() == ("run", job.id)

def test_clip_replace_after_done_rerenders_only(monkeypatch):
    job = scene_job("done", STEPS)
    (job.dir / "clips").mkdir()
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    job.put("clips.json", [{"file": f"clip{i}.mp4", "source": "Google Flow"} for i in (0, 1)])
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(web.q, "redo", lambda j, steps: seen.append(steps) or True)
    assert "클립 바꾸기" in client.get(f"/jobs/{job.id}").text   # 완성 뒤에도 장면마다 바꿀 수 있다
    url = f"/api/jobs/{job.id}/clips"
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and seen == [("render",)]
    assert client.post(f"{url}/0", content=MP4).status_code == 200 and seen[-1] == ("thumbnail", "render")
    assert [c["source"] for c in job.doc("clips.json")] == ["직접 올림", "직접 올림"]
    job.update(status="failed")
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and len(seen) == 3
    job.update(upload=upload_state("running"))
    assert client.post(f"{url}/1", content=MP4).status_code == 409   # 올리는 중


def test_checks_list_providers():
    labels = [c[1] for c in web._checks(CH)]
    assert labels[0] == "Claude API 키" and "영상 · Google Flow(자동) (이 채널)" in labels
    assert "음성 · ElevenLabs" in labels
    research = next(c for c in web._checks(CH) if c[1] == "조사 · Claude 조사")
    assert "[research] domains" not in research[2]   # 채널에 허용 사이트가 있다
    assert "YouTube 업로드" in labels and labels == [c[1] for c in web._checks("all")]   # 전체는 첫 채널
    assert "YouTube Data API 키" not in labels   # 주제 찾기는 YouTube 키를 쓰지 않는다
    html = client.get("/").text   # 대시보드 카드가 아니라 상단바의 점 하나 + 펼침
    assert 'popovertarget="env-pop"' in html and "Claude API 키" in html and 'id="h-env"' not in html


def test_script_edit_direct_and_revise():
    job = scene_job("done", STEPS)
    url = f"/api/jobs/{job.id}/edit"
    html = client.get(f"/jobs/{job.id}").text
    assert 'id="script-edit"' in html and 'id="savebar"' in html and 'form="edit"' in html
    form = {"title": "t", "description": "d", "tags": "", "sentences": ["하나", "둘"]}
    # 제목·태그만: 저장만, 다시 돌지 않는다
    assert client.post(url, data=form | {"tags": "#커피, , 카페"}).json()["msg"] == "저장했어요"
    assert job.doc("script.json")["tags"] == ["커피", "카페"] and job.data["status"] == "done"
    assert client.post(url, data=form | {"sentences": ["하나"]}).status_code == 400   # 장면 수가 다르면
    assert client.post(url, data=form | {"sentences": ["하나", " "]}).status_code == 400
    # 문장을 바꾸면 음성부터(클립·썸네일은 그대로)
    assert client.post(url, data=form | {"sentences": ["하나", "셋"]}).status_code == 200
    d = job.data
    assert job.doc("script.json")["sentences"] == ["하나", "셋"] and d["status"] == "queued"
    assert [s for s in STEPS if d["steps"][s]["status"] == "pending"] == ["voice", "subtitles", "render"]
    assert web.q._q.get_nowait() == ("run", job.id)
    assert client.post(url, data=form).status_code == 409   # 만드는 중
    job.update(status="done")
    rev = f"/api/jobs/{job.id}/script/revise"
    assert client.post(rev, data={"note": " "}).status_code == 400
    assert client.post(rev, data={"note": "더 짧게"}).status_code == 200
    d = job.data
    assert d["script_note"] == "더 짧게" and d["steps"]["script"]["status"] == "pending"
    assert d["steps"]["footage"]["status"] == "done"
    assert d["steps"]["proofread"]["status"] == "pending"   # 고친 대본도 다시 검수한다
    assert web.q._q.get_nowait() == ("run", job.id)
    # 처음부터 다시 쓰기: 클립을 만든 뒤에는 막는다(장면이 어긋난다)
    job.update(status="done")
    assert client.post(f"/api/jobs/{job.id}/script/rewrite").status_code == 409
    assert 'id="script-rewrite"' not in client.get(f"/jobs/{job.id}").text
    # 목소리만 바꿔도 음성부터 다시. 모르는 목소리는 거절
    job.update(status="done")
    assert client.post(url, data=form | {"voice": "nope"}).status_code == 400
    assert client.post(url, data=form | {"voice": "elevenlabs"}).status_code == 200
    d = job.data
    assert d["voice"] == "elevenlabs" and d["status"] == "queued" and d["steps"]["voice"]["status"] == "pending"
    assert web.q._q.get_nowait() == ("run", job.id)
    job.update(status="done", upload=upload_state("running"))
    assert "올리는 중" in client.post(url, data=form).json()["detail"]
    # 이미 올린 작업도 고칠 수 있다. 다시 만들면 올린 기록을 옮겨 새로 올릴 수 있게
    job.update(upload=upload_state("done", video_id="old"))
    assert client.post(url, data=form).json()["msg"] == "저장했어요" and job.data["upload"]["status"] == "done"
    msg = client.post(url, data=form | {"voice": "LKOcTG4J4tYTPR9DnLeM"}).json()["msg"]
    assert msg == "저장했어요. 음성·자막·렌더를 다시 해요"
    d = job.data
    assert d["upload"] is None and d["uploaded_before"]["video_id"] == "old"
    assert web.q._q.get_nowait() == ("run", job.id)


def test_edit_subtitle_line_breaks_redoes_voice_and_keeps_them():
    job = scene_job("done", STEPS)
    job.put("script.json", job.doc("script.json") | {"sentences": ["가나다. 라마 바사", "둘"]})
    job.put("timing.json", [{"text": "가나다. 라마 바사", "start": 0, "end": 2}, {"text": "둘", "start": 2, "end": 3}])
    job.put("cues.json", [{"start": 0, "end": 1, "text": "가나다."}, {"start": 1, "end": 2, "text": "라마 바사"},
                          {"start": 2, "end": 3, "text": "둘"}])
    form = {"title": "t", "description": "d", "tags": "", "sentences": ["가나다. 라마 바사", "둘"]}
    # 낱말은 그대로 줄만 옮겨도 음성부터 다시 하고, 고친 줄은 자막 단계가 쓰게 남긴다
    r = client.post(f"/api/jobs/{job.id}/edit", data=form | {"cues": ["가나다. 라마", "바사", "둘"]}).json()
    assert r["msg"] == "저장했어요. 음성·자막·렌더를 다시 해요"
    assert job.data["cue_hand"] == [["가나다. 라마", "바사"], ["둘"]]
    assert job.doc("script.json")["sentences"] == ["가나다. 라마 바사", "둘"]
    assert [s for s in STEPS if job.data["steps"][s]["status"] == "pending"] == ["voice", "subtitles", "render"]
    web.q._q.get_nowait()
    # 대본 확정 전에도 음성은 다시 녹음한다(렌더만 확정 뒤로 미룬다)
    job.update(status="waiting", review=True)
    r = client.post(f"/api/jobs/{job.id}/edit", data=form | {"cues": ["가나다. 라", "마 바사", "둘"]}).json()
    assert r["msg"] == "저장했어요. 음성·자막를 다시 해요"
    assert job.data["cue_hand"] == [["가나다. 라", "마 바사"], ["둘"]]
    web.q._q.get_nowait()
    # 예전에 줄을 합쳐 나눈 줄 수와 달라진 문장이 있어도, 지금 자막 줄 수대로 묶어 글자를 고칠 수 있다
    job.update(status="waiting", cue_hand=[["가나다. 라마 바사"], ["둘"]])
    job.put("cues.json", [{"start": 0, "end": 2, "text": "가나다. 라마 바사"}, {"start": 2, "end": 3, "text": "둘"}])
    r = client.post(f"/api/jobs/{job.id}/edit", data=form | {"cues": ["가나다. 라마 아자", "둘"]}).json()
    assert r["msg"] == "저장했어요. 음성·자막를 다시 해요"
    assert job.data["cue_hand"] == [["가나다. 라마 아자"], ["둘"]]
    assert job.doc("script.json")["sentences"] == ["가나다. 라마 아자", "둘"]
    web.q._q.get_nowait()


def test_edit_checks_only_changed_sentences_against_channel_length():
    job = scene_job("done", STEPS)
    cap = channel.load("ko-40sec-facts").script.sentence[1] * 2   # ko 채널 문장 한도의 두 배
    long = "가" * (cap + 10)   # 한도를 넘는 예전 문장
    job.put("script.json", job.doc("script.json") | {"sentences": ["하나", long]})
    url, form = f"/api/jobs/{job.id}/edit", {"title": "t", "description": "d", "tags": ""}
    assert client.post(url, data=form | {"sentences": ["하나", long]}).status_code == 200   # 안 바꾼 문장은 통과
    r = client.post(url, data=form | {"sentences": ["가" * (cap + 1), long]})
    assert r.status_code == 400 and f"{cap}자" in r.json()["detail"]


def test_edit_subtitles_and_thumbnail_by_hand(monkeypatch):
    job = scene_job("done", STEPS)
    job.put("cues.json", [{"start": 0, "end": 1, "text": "하나"},
                                              {"start": 1, "end": 2, "text": "둘"}])
    job.put("thumb.json", {"lines": ["물 양", "비밀"], "accent": "비밀", "position": "top",
                                               "usage": None, "texts": []})
    (job.dir / "thumbnail.jpg").write_bytes(b"x")
    html = client.get(f"/jobs/{job.id}").text
    assert 'name="cues" form="edit"' in html and 'name="thumb" form="edit"' in html and "data-sample" in html
    url, form = f"/api/jobs/{job.id}/edit", {"title": "t", "description": "d", "tags": "", "sentences": ["하나", "둘"]}
    edit = form | {"cues": ["하나", "둘"], "thumb": ["물 양", "비밀"], "accent": "비밀"}
    assert client.post(url, data=edit).json()["msg"] == "저장했어요"   # 그대로면 저장만
    assert client.post(url, data=edit | {"cues": ["하나"]}).status_code == 400
    # 자막 줄 → 그 문장을 고친 줄대로 바꾸고 음성부터 다시(목소리가 고친 자막대로 읽게)
    r = client.post(url, data=edit | {"cues": ["하나!", "둘"]}).json()["msg"]
    assert r == "저장했어요. 음성·자막·렌더를 다시 해요" and job.doc("script.json")["sentences"] == ["하나!", "둘"]
    assert [s for s in STEPS if job.data["steps"][s]["status"] == "pending"] == ["voice", "subtitles", "render"]
    web.q._q.get_nowait()
    job.update(status="done")
    # 썸네일 문구 → 썸네일·렌더, 문구에 없는 강조는 뺀다
    job.update(status="done")
    assert client.post(url, data=edit | {"thumb": ["가" * 16, ""]}).status_code == 400
    assert client.post(url, data=edit | {"thumb": ["물 550ml", ""], "accent": "비밀"}).status_code == 200
    d = job.data
    assert d["thumb_hand"] == {"lines": ["물 550ml"], "accent": ""} and d["steps"]["thumbnail"]["status"] == "pending"
    web.q._q.get_nowait()
    # 미리 듣기: 아는 목소리만, 한 번 만든 견본은 다시 부르지 않는다
    calls = []
    monkeypatch.setattr(config, "ROOT", job.dir)

    class FakeTTS:
        label, hint = "가짜", ""

        def ready(self):
            return True

        def speak(self, v, text, out):
            calls.append(v)
            out.write_bytes(b"mp3")

    monkeypatch.setitem(registry.TTSES, "elevenlabs", FakeTTS())
    assert f'data-channel="{CH}"' in html
    assert client.get(f"/api/channels/{CH}/voices/nope/sample").status_code == 404
    assert client.get("/api/channels/nope/voices/elevenlabs/sample").status_code == 404
    for _ in range(2):
        assert client.get(f"/api/channels/{CH}/voices/elevenlabs/sample").content == b"mp3"
    assert calls == ["elevenlabs"]


def test_dashboard_marks_uploaded():
    job = done_job()
    assert "미업로드" in client.get("/").text
    job.update(upload=upload_state("done", video_id="v"))
    html = client.get("/").text
    assert "업로드됨" in html and "is-up" in html and "미업로드" not in html


def test_delete_job_removes_folder_but_not_while_running():
    job = done_job()
    assert 'data-delete="' + job.id in client.get("/").text
    assert client.post(f"/api/jobs/{job.id}/delete").json() == {"ok": True}
    assert not job.dir.exists() and client.post(f"/api/jobs/{job.id}/delete").status_code == 404
    busy = done_job()
    busy.update(status="running")
    assert client.post(f"/api/jobs/{busy.id}/delete").status_code == 409 and busy.dir.exists()
    busy.update(status="done", upload=upload_state("running"))
    assert client.post(f"/api/jobs/{busy.id}/delete").status_code == 409
    assert 'data-delete="' + busy.id not in client.get("/").text


def test_channel_cookie_selects_and_filters(two_channels):
    done_job(topic="커피")
    done_job(two_channels, "enVoice1", topic="Mars")
    html = client.get("/").text   # 쿠키가 없으면 첫 채널(이름순)
    assert "커피" not in html and "Mars" in html and "<small> / 2</small>" in html
    r = client.get(f"/?channel={CH}")
    assert r.cookies.get("sp_channel") == CH and "Mars" not in r.text and "<small> / 1</small>" in r.text
    html = client.get("/").text   # 쿠키로 기억한다
    assert "커피" in html and "Mars" not in html
    html = client.get("/?channel=all").text   # 전체: 둘 다, 채널 이름 배지, 목표는 합
    assert "커피" in html and "Mars" in html and 'b-ch">Space Facts' in html and "<small> / 3</small>" in html
    assert client.get("/?channel=nope").status_code == 404
    assert client.cookies.get("sp_channel") == "all"   # 모르는 채널은 쿠키를 바꾸지 않는다


def test_new_job_form_follows_channel(two_channels, monkeypatch):
    queued = []
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    html = client.get(f"/?channel={two_channels}").text
    assert f'name="channel" value="{two_channels}"' in html and ">Adam<" in html and "미스터킴" not in html
    html = client.get(f"/?channel={CH}").text
    assert ">미스터킴<" in html and ">Adam<" not in html
    form = {"topic": "x", "voice": "LKOcTG4J4tYTPR9DnLeM", "channel": two_channels}
    assert client.post("/jobs", data=form).status_code == 400   # 다른 채널 목소리는 거절
    r = client.post("/jobs", data=form | {"voice": "enVoice1"}, follow_redirects=False)
    assert r.status_code == 303 and Job.load(queued[0]).data["channel"] == two_channels
    assert "Space Facts · Adam" in client.get(f"/jobs/{queued[0]}").text   # 작업 화면 목소리도 그 채널 것


def test_broken_channel_keeps_pages_up(two_channels):
    toml = config.CHANNELS_DIR / two_channels / "channel.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace("daily_goal = 2", 'daily_goal = "x"'), encoding="utf-8")
    t = Trend.create(two_channels)
    t.update(status="done")
    for path in ("/", "/trends", f"/?channel={two_channels}", f"/trends?channel={two_channels}", "/?channel=all"):
        assert client.get(path).status_code == 200, path
    assert "채널 설정" in client.get(f"/?channel={two_channels}").text


def test_all_channels_view_hides_form(two_channels):
    html = client.get("/?channel=all").text
    assert 'id="new"' not in html and "채널을 하나 고른 뒤" in html
    assert 'value="all" selected' in html and 'for="ch-sel"' in html


def test_translate_saves_ko_shows_it_and_marks_stale(two_channels, monkeypatch):
    from types import SimpleNamespace

    from shorts_printer.core import script
    job = done_job(two_channels, voice="enVoice1")
    assert "한국어로 옮기기" in client.get(f"/jobs/{job.id}").text
    assert "한국어로 옮기기" not in client.get(f"/jobs/{done_job().id}").text   # 한국어 채널엔 없다
    out = script.Translation(title="한글 제목", description="d", tags=[], sentences=["하나", "둘"], thumb=[],
                             cues=["하나 뜻"], notes=["어색한 곳"])
    usage = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.02}
    llm = SimpleNamespace(label="Claude", ask=lambda *a, **kw: (out, usage))
    with monkeypatch.context() as m:   # 화면의 환경 점검은 진짜 services를 쓴다
        m.setattr(registry, "services", lambda cid: SimpleNamespace(llm=llm, script_llm=llm,
                                                                    channel=channel.load(cid)))
        assert client.post(f"/api/jobs/{job.id}/translate").json()["msg"] == "한국어로 옮겼어요"
    html = client.get(f"/jobs/{job.id}").text
    assert "한글 제목" in html and "어색한 곳" in html and "다시 옮기기" in html and "바뀌었어요" not in html
    assert "(하나 뜻)" in html   # 자막 줄마다 괄호로
    assert web.job_cost(job.data) == 0.03
    job.put("cues.json", [{"start": 0, "end": 1.4, "text": "바뀐 자막"}])
    assert "(하나 뜻)" not in client.get(f"/jobs/{job.id}").text
    job.edit("script.json", lambda s: s | {"title": "new"})
    assert "바뀌었어요" in client.get(f"/jobs/{job.id}").text


def test_job_cost_adds_research_and_page_shows_step():
    job = done_job()
    job.update(research_usage={"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.05})
    assert web.job_cost(job.data) == 0.06
    assert "자료 조사" in client.get(f"/jobs/{job.id}").text


def test_credits_shows_shorts_left(monkeypatch):
    """장면 11개·문장 56~63자 → 한 편 ElevenLabs 654자, Flow 132크레딧. 적은 쪽이 편수를 정한다."""
    from shorts_printer.adapters.elevenlabs import ElevenLabs
    from shorts_printer.adapters.flow_auto import FlowAuto
    monkeypatch.setattr(web, "_left_cache", {})
    monkeypatch.delenv("ANTHROPIC_ADMIN_API_KEY", raising=False)   # Claude 줄은 설정이 없으면 안 뜬다
    monkeypatch.setattr(FlowAuto, "ready", lambda self: True)
    monkeypatch.setattr(ElevenLabs, "credits", lambda self: 6540)
    monkeypatch.setattr(FlowAuto, "credits", lambda self: 5883)
    assert 'data-src="/credits"' in client.get("/").text   # 대시보드는 자리만 두고 바로 그린다
    html = client.get("/credits").text
    assert "6,540" in html and "편당 654 · 10편" in html and "편당 132 · 44편" in html
    assert "약 <strong>10편</strong>" in html and "ElevenLabs가 먼저" in html

    def broken(self):
        raise RuntimeError("전용 Chrome이 꺼져 있어요")
    monkeypatch.setattr(web, "_left_cache", {})
    monkeypatch.setattr(FlowAuto, "credits", broken)
    html = client.get("/credits").text
    assert "전용 Chrome이 꺼져 있어요" in html and "만들 수 있어요" not in html   # 하나라도 모르면 편수를 말하지 않는다


def test_credits_shows_claude_balance_from_cost_report(monkeypatch):
    """$50에서 비용 보고서 두 쪽(150.5 + 49.5센트)을 빼 $48.00. 최근 작업 평균 $0.01이라 4,800편."""
    import io
    import json

    from shorts_printer.adapters import claude
    from shorts_printer.adapters.elevenlabs import ElevenLabs
    from shorts_printer.adapters.flow_auto import FlowAuto
    monkeypatch.setattr(web, "_left_cache", {})
    monkeypatch.setattr(FlowAuto, "ready", lambda self: True)
    monkeypatch.setattr(ElevenLabs, "credits", lambda self: 654_000_000)
    monkeypatch.setattr(FlowAuto, "credits", lambda self: 132_000_000)
    monkeypatch.setenv("ANTHROPIC_ADMIN_API_KEY", "sk-ant-admin01-x")
    monkeypatch.setattr(config, "CLAUDE_CREDIT_USD", "50")
    monkeypatch.setattr(config, "CLAUDE_CREDIT_SINCE", "2026-10-01")
    urls = []

    def urlopen(req, timeout):
        urls.append(req.full_url)
        last = "page=p2" in req.full_url
        return io.BytesIO(json.dumps({"data": [{"results": [{"amount": "49.5" if last else "150.5"}]}, {"results": []}],
                                      "has_more": not last, "next_page": None if last else "p2"}).encode())
    monkeypatch.setattr(claude, "urlopen", urlopen)
    done_job()
    html = client.get("/credits").text
    assert "starting_at=2026-10-01T00%3A00%3A00Z" in urls[0] and len(urls) == 2
    assert "$48.00" in html and "편당 $0.01 · 4800편" in html and "Claude가 먼저" in html


def test_sig_and_say_follow_long_job_steps():
    job = Job.create(CH, "주제", "v", long=True)
    job.step("map", status="running")
    d = job.data
    assert web.sig(d).split(":")[1] == "".join(st["status"][0] for st in d["steps"].values())
    assert web.say(d) == f"{web.LABELS['map']} 진행 중"


# ── 롱폼 작업 화면
LONG_DONE = ("research", "script", "proofread")


@pytest.fixture
def two_clips(monkeypatch):
    """클립 한도 2개인 채널(기본 8개는 장면 5개로는 한도에 닿지 않는다)."""
    load = channel.load
    monkeypatch.setattr(channel, "load", lambda cid: (c := load(cid)).model_copy(
        update={"long": c.long.model_copy(update={"max_clips": 2})}))


def long_job(status="waiting", done=LONG_DONE, kinds=("map", "clip", "map", "map", "map"), **fields):
    """장 2개·장면 5개 롱폼 작업. 장면 1은 clip, 장면 2는 map이지만 clip_prompt가 있다(클립 한도 2)."""
    job = Job.create(CH, "6.25 전쟁", "LKOcTG4J4tYTPR9DnLeM", long=True)
    scenes = [{"narration": f"내레이션{i}", "kind": k, "beat": "", "visual": f"보임{i}", "fact_ids": [],
               "clip_prompt": f"prompt{i}" if k == "clip" or i == 2 else "",
               "clip_prompt_ko": f"뜻{i}" if k == "clip" or i == 2 else "", "chapter": 0 if i < 3 else 1}
              for i, k in enumerate(kinds)]
    job.put("script.json", {"title": "전쟁의 시작", "description": "설명", "tags": ["역사"], "thumb": ["첫 줄"],
                            "sensitive": "", "chapters": [{"title": "남침", "first": 0}, {"title": "반격", "first": 3}],
                            "scenes": scenes, "notes": [], "sentences": [s["narration"] for s in scenes],
                            "fact_ids": [[] for _ in scenes]})
    job.put("proofread.json", {"pass": 80, "max": {"사실": 40}, "rounds": [
        {"total": 90, "scores": {"사실": 36}, "passed": True, "issues": []}]})
    steps = {s: {"status": "done", "engine": "x", "sec": 1.0} for s in done}
    job.update(status=status, steps=job.data["steps"] | steps, **fields)
    return job


def drain():
    while not web.q._q.empty():
        web.q._q.get_nowait()


def test_long_script_gate_page_and_approve(two_clips, monkeypatch):
    monkeypatch.setattr(registry.VIDEOS["flow-auto"], "ready", lambda: True)   # 쇼츠 채널 CH라 9:16 720p 판
    job = long_job()
    assert not web.in_review(job.data) and not web.in_voice_review(job.data)
    html = client.get(f"/jobs/{job.id}").text
    assert "대본 승인 대기" in html and 'data-retry="approve/script"' in html and "1장. 남침" in html
    assert "뜻1" in html and "보임3" in html and "검수 90점 · 통과" in html and "클립 1/2" in html
    assert "대본 25자 · 클립 1개 × 12크레딧" in html   # 승인 전 비용 어림(내레이션 5자 × 5)
    assert 'data-post="scenes/1/kind"' in html and 'data-post="script/revise"' in html
    assert "대본 승인 대기" in client.get("/").text
    url = f"/api/jobs/{job.id}/approve"
    assert client.post(f"{url}/draft").status_code == 409 and client.post(f"{url}/clips").status_code == 409
    assert client.post(f"{url}/script").status_code == 200
    d = Job.load(job.id).data
    assert d["script_ok"] and d["status"] == "queued" and web.q._q.get_nowait() == ("run", job.id)
    assert client.post(f"{url}/script").status_code == 409   # 이미 승인


def test_long_scene_kind_toggle_keeps_clip_limit(two_clips):
    job = long_job(kinds=("clip", "clip", "map", "map", "map"))
    url = f"/api/jobs/{job.id}/scenes"
    r = client.post(f"{url}/2/kind", data={"kind": "clip"})
    assert r.status_code == 400 and "2개까지" in r.json()["detail"]
    r = client.post(f"{url}/3/kind", data={"kind": "clip"})
    assert r.status_code == 400 and "고쳐 줘" in r.json()["detail"]
    assert client.post(f"{url}/9/kind", data={"kind": "map"}).status_code == 404
    assert client.post(f"{url}/1/kind", data={"kind": "photo"}).status_code == 400
    assert client.post(f"{url}/1/kind", data={"kind": "map"}).status_code == 200
    assert client.post(f"{url}/2/kind", data={"kind": "clip"}).status_code == 200
    assert [s["kind"] for s in job.doc("script.json")["scenes"]] == ["clip", "map", "clip", "map", "map"]
    assert Job.load(job.id).data["status"] == "waiting" and web.q._q.empty()   # 저장만
    job.update(script_ok=True, steps=job.data["steps"] | {"voice": {"status": "done", "engine": "x", "sec": 1.0}})
    assert client.post(f"{url}/1/kind", data={"kind": "clip"}).status_code == 409   # 승인 뒤엔 못 바꾼다


def test_long_script_revise_and_rewrite_only_before_voice():
    job = long_job()
    r = client.post(f"/api/jobs/{job.id}/script/revise", data={"note": "더 짧게"})
    assert r.status_code == 200
    d = Job.load(job.id).data
    assert d["script_note"] == "더 짧게" and d["steps"]["script"]["status"] == "pending"
    assert d["steps"]["research"]["status"] == "done" and "voice" in d["steps"] and "subtitles" not in d["steps"]
    drain()
    job = long_job(done=(*LONG_DONE, "voice"), script_ok=True, status="failed")
    assert client.post(f"/api/jobs/{job.id}/script/revise", data={"note": "x"}).status_code == 409
    assert client.post(f"/api/jobs/{job.id}/script/rewrite").status_code == 409
    job = long_job()
    assert client.post(f"/api/jobs/{job.id}/script/rewrite").status_code == 200
    assert Job.load(job.id).data["steps"]["proofread"]["status"] == "pending"
    drain()


def test_long_clips_gate_and_put_clip(monkeypatch):
    job = long_job(done=(*LONG_DONE, "voice", "plan", "map"), script_ok=True)
    html = client.get(f"/jobs/{job.id}").text
    assert "클립 대기" in html and "16:9" in html and 'data-copy="prompt1"' in html and 'data-clip="1"' in html
    assert 'data-clip="0"' not in html
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    enqueued, redone = [], []
    monkeypatch.setattr(web.q, "enqueue", lambda i: enqueued.append(i) or True)
    monkeypatch.setattr(web.q, "redo", lambda i, steps, **k: redone.append(steps) or True)
    url = f"/api/jobs/{job.id}/clips"
    assert client.post(f"{url}/0", content=MP4).status_code == 400   # 지도 장면
    assert client.post(f"{url}/1", content=MP4).status_code == 200
    assert enqueued == [job.id] and (job.dir / "clips" / "clip1.mp4").exists()
    job.update(draft_ok=True, steps=job.data["steps"] | {k: {"status": "done", "engine": "x", "sec": 1.0}
                                                         for k in ("clips", "draft")})
    assert client.post(f"{url}/1", content=MP4).status_code == 200
    assert redone == [("draft", "render", "final")]
    job.update(steps=job.data["steps"] | {"voice": {"status": "pending", "engine": None, "sec": None}})
    assert client.post(f"{url}/1", content=MP4).status_code == 409   # 음성 전(대본이 아직 바뀔 수 있다)


def test_long_draft_gate_approve_and_revise():
    job = long_job(done=(*LONG_DONE, "voice", "plan", "map", "clips", "draft"), script_ok=True, draft_ok=False)
    job.put("draft.json", {"check": {"lint": {"errors": 0, "warnings": 2}}, "snapshots": [
        {"chapter": 0, "title": "남침", "at": 2.9, "file": "draft/ch0.jpg"}]})
    job.put("film.json", {"total": 65.2, "end_start": 58.0})
    html = client.get(f"/jobs/{job.id}").text
    assert "초안 승인 대기" in html and f'src="/files/{job.id}/draft/ch0.jpg' in html
    assert "1:05" in html and "경고 2" in html and 'data-post="draft/revise"' in html
    assert client.post(f"/api/jobs/{job.id}/draft/revise", data={"note": " "}).status_code == 400
    r = client.post(f"/api/jobs/{job.id}/draft/revise", data={"note": "2장 더 확대"})
    assert r.status_code == 200
    d = Job.load(job.id).data
    assert d["draft_note"] == "2장 더 확대" and [d["steps"][k]["status"] for k in ("voice", "plan", "map", "draft")] \
        == ["done", "pending", "pending", "pending"]
    drain()
    job.update(status="waiting", steps=job.data["steps"] | {k: {"status": "done", "engine": "x", "sec": 1.0}
                                                            for k in ("plan", "map", "draft")})
    assert client.post(f"/api/jobs/{job.id}/approve/draft").status_code == 200
    assert Job.load(job.id).data["draft_ok"] and web.q._q.get_nowait() == ("run", job.id)
    assert client.post(f"/api/jobs/{job.id}/draft/revise", data={"note": "x"}).status_code == 409


def test_long_done_page_shows_final_checks():
    job = long_job(status="done", done=STEPS_LONG, script_ok=True, draft_ok=True, duration=65.0)
    job.put("final.json", {"duration": 65.0, "expected": 65.2, "lufs": -16.2, "true_peak": -1.5, "silences": [],
                           "cue_end": 60.0, "issues": []})
    job.put("credits.json", ["내레이션 ElevenLabs", "지도 Esri"])
    (job.dir / "captions.srt").write_text("1\n", encoding="utf-8")
    html = client.get(f"/jobs/{job.id}").text
    assert "final.mp4" in html and "captions.srt" in html and "통과" in html and "-16.2 LUFS" in html
    assert "지도 Esri" in html and "force-ssl" not in html and 'id="upload-box"' in html   # 자막은 영상에 구웠다
    assert "설명\n\n내레이션 ElevenLabs" in html   # 설명란에 크레딧
    job.put("final.json", job.doc("final.json") | {"issues": ["음량 -12 LUFS"]})
    assert "음량 -12 LUFS" in client.get(f"/jobs/{job.id}").text


def test_shorts_only_endpoints_reject_long_jobs():
    job = long_job(status="done", done=("research", "script", "proofread", "voice"), script_ok=True)
    for path in ("confirm", "voice/redo", "thumbnail", "edit", "translate"):
        r = client.post(f"/api/jobs/{job.id}/{path}", data={"title": "t"})
        assert r.status_code == 409 and r.json()["detail"] == web.SHORTS_ONLY, path


def test_redo_rejects_steps_the_job_does_not_have():
    long, short = long_job(status="done"), scene_job(status="done")
    assert not web.q.redo(long.id, ("footage",)) and not web.q.redo(short.id, ("plan",))
    assert Job.load(long.id).data["status"] == "done" and web.q._q.empty()
    with pytest.raises(web.HTTPException) as e:
        web._redo(short.id, ("plan",))
    assert e.value.status_code == 409


def test_long_clip_upload_only_after_voice():
    """음성 전(대본 승인 뒤 음성 실패)엔 대본을 다시 고칠 수 있어 클립을 받지 않는다(다른 장면에 묶인다)."""
    job = long_job(status="failed", script_ok=True, error={"step": "voice", "message": "한도"})
    assert 'data-clip="1"' not in client.get(f"/jobs/{job.id}").text
    assert client.post(f"/api/jobs/{job.id}/clips/1", content=MP4).status_code == 409


def test_long_refused_clip_scene_turns_into_map():
    """거절로 멈춘 클립 장면은 음성 뒤에도 지도로 바꿔 지도 계획부터 다시 한다."""
    job = long_job(status="failed", done=(*LONG_DONE, "voice", "plan", "map"), script_ok=True,
                   refused=[{"i": 1, "reason": "정책"}], error={"step": "clips", "message": "거절"})
    html = client.get(f"/jobs/{job.id}").text
    assert 'data-post="scenes/1/kind"' in html and "지도로 바꾸기" in html
    url = f"/api/jobs/{job.id}/scenes"
    assert client.post(f"{url}/2/kind", data={"kind": "clip"}).status_code == 409   # 음성 뒤엔 지도로만
    assert client.post(f"{url}/0/kind", data={"kind": "map"}).status_code == 400   # 이미 지도
    assert client.post(f"{url}/1/kind", data={"kind": "map"}).status_code == 200
    d = Job.load(job.id).data
    assert job.doc("script.json")["scenes"][1]["kind"] == "map" and d["refused"] is None and d["draft_note"]
    assert [d["steps"][k]["status"] for k in ("voice", "plan", "map", "clips")] == ["done", "pending", "pending",
                                                                                   "pending"]
    assert web.q._q.get_nowait() == ("run", job.id)
    job = long_job(status="done", done=STEPS_LONG, script_ok=True, draft_ok=True)
    assert client.post(f"/api/jobs/{job.id}/scenes/1/kind", data={"kind": "map"}).status_code == 409   # 초안 뒤


def test_long_kind_toggle_only_where_it_can_succeed(two_clips):
    job = long_job(kinds=("clip", "clip", "map", "map", "map"))   # 클립 2/2: 지도 → 클립은 한도에 걸린다
    html = client.get(f"/jobs/{job.id}").text
    assert 'data-post="scenes/1/kind"' in html and 'data-post="scenes/2/kind"' not in html
    job = long_job(kinds=("map",) * 5)   # 한도가 남으면 프롬프트 있는 장면(2)만
    html = client.get(f"/jobs/{job.id}").text
    assert 'data-post="scenes/2/kind"' in html and 'data-post="scenes/3/kind"' not in html


def test_long_upload_button_waits_for_final(monkeypatch):
    monkeypatch.setattr(YouTube, "ready", lambda self: True)
    job = long_job(status="running", done=STEPS_LONG[:-1], script_ok=True, draft_ok=True)
    job.step("final", status="running")
    html = client.get(f"/jobs/{job.id}").text
    assert 'id="upload-box"' not in html and "최종 검수가 끝나면 올릴 수 있어요" in html
    (job.dir / "final.mp4").write_bytes(b"x")
    html = client.get(f"/jobs/{job.id}").text
    assert f"final.mp4?v={(job.dir / 'final.mp4').stat().st_mtime_ns}" in html   # finished_at이 비어도 캐시를 깬다


def test_draft_snapshots_bust_cache_by_file():
    job = long_job(done=(*LONG_DONE, "voice", "plan", "map", "clips", "draft"), script_ok=True, draft_ok=False)
    snap = {"chapter": 0, "title": "남침", "at": 2.9, "file": "draft/a.png"}
    job.put("draft.json", {"check": {}, "snapshots": [snap]})
    (job.dir / "draft").mkdir()
    (job.dir / "draft" / "a.png").write_bytes(b"png")
    assert f"draft/a.png?v={(job.dir / 'draft' / 'a.png').stat().st_mtime_ns}" in client.get(f"/jobs/{job.id}").text


def test_say_survives_channel_setting_failure():
    job = done_job()
    job.update(status="failed", error={"step": None, "message": "채널 설정이 틀렸어요"})
    r = client.get(f"/api/jobs/{job.id}")
    assert r.status_code == 200 and r.json()["say"] == "실패: 채널 설정"


def test_dashboard_dots_follow_step_order_not_stored_order():
    job = done_job()
    job.update(steps=dict(reversed(job.data["steps"].items())))   # 예전 작업: 나중에 생긴 단계가 뒤에 붙었다
    long = long_job()
    html = client.get("/").text
    for j, order in ((job, STEPS), (long, STEPS_LONG)):
        label = ", ".join(f"{web.LABELS[s]} {web.STATE[j.data['steps'][s]['status']]}" for s in order)
        assert f'aria-label="{label}"' in html


def test_long_voice_pick_before_voice_only():
    job = long_job()
    html = client.get(f"/jobs/{job.id}").text
    assert 'data-sample="lv-voice"' in html and 'data-post="voice"' in html
    url = f"/api/jobs/{job.id}/voice"
    assert client.post(url, data={"voice": "없는목소리"}).status_code == 400
    key = next(k for k in web._channel(CH).tts.voices if k != job.data["voice"])
    assert client.post(url, data={"voice": key}).status_code == 200 and Job.load(job.id).data["voice"] == key
    job = long_job(status="done", done=STEPS_LONG, script_ok=True, draft_ok=True)
    assert client.post(f"/api/jobs/{job.id}/voice", data={"voice": key}).status_code == 409
    assert "voice/s00.mp3" in client.get(f"/jobs/{job.id}").text   # 음성 뒤엔 장면마다 들어 본다


def test_long_thumb_edit_saves_and_redraws_only_after_render(monkeypatch):
    drawn = []
    monkeypatch.setattr(web.longform, "thumbnail", lambda job: drawn.append(job.doc("script.json")["thumb"]))
    job = long_job()
    assert 'data-post="thumb"' in client.get(f"/jobs/{job.id}").text
    url = f"/api/jobs/{job.id}/thumb"
    assert client.post(url, data={"thumb": ["가" * 17]}).status_code == 400
    assert client.post(url, data={"thumb": ["압록강까지 갔는데", "왜 다시 38선?"]}).status_code == 200
    assert job.doc("script.json")["thumb"] == ["압록강까지 갔는데", "왜 다시 38선?"] and not drawn   # 렌더 전: 저장만
    job = long_job(status="done", done=STEPS_LONG, script_ok=True, draft_ok=True)
    (job.dir / "thumbnail.jpg").write_bytes(b"JPG")
    html = client.get(f"/jobs/{job.id}").text
    assert html.count('data-post="thumb"') == 1 and html.index('class="thumb-wide"') < html.index('data-post="thumb"')
    assert client.post(f"/api/jobs/{job.id}/thumb", data={"thumb": ["새 글자", ""]}).status_code == 200
    assert drawn == [["새 글자"]]

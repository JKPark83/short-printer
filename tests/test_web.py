import shutil

from fastapi.testclient import TestClient

from shorts_printer import config, worker, youtube
from shorts_printer.jobs import STEPS, Job, atomic_write_json, read_json, upload_state
from shorts_printer.web import app as web

client = TestClient(web.app, base_url="http://127.0.0.1")   # with 블록 없이 써서 lifespan(작업 스레드)을 띄우지 않는다


def done_job():
    job = Job.create("커피", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", {"title": "제목", "description": "설명", "tags": ["커피 상식", "카페"],
                                                "sentences": ["하나", "둘"], "prompts": ["p1", "p2"],
                                                "search_terms": ["coffee", "cup"]})
    atomic_write_json(job.dir / "clips.json", [])
    atomic_write_json(job.dir / "cues.json", [{"start": 0, "end": 1.4, "text": "하나"}])
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
    monkeypatch.setattr(worker, "enqueue", queued.append)
    assert client.post("/jobs", data={"topic": "  ", "voice": "ko-KR-SunHiNeural"}).status_code == 400
    assert client.post("/jobs", data={"topic": "커피", "voice": "nope"}).status_code == 400
    r = client.post("/jobs", data={"topic": " 커피 ", "voice": "ko-KR-InJoonNeural"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/jobs/{queued[0]}"
    assert Job.load(queued[0]).data["topic"] == "커피"
    # macOS say 목소리는 say가 있을 때만 목록에 있다
    r = client.post("/jobs", data={"topic": "커피", "voice": "Yuna"}, follow_redirects=False)
    assert r.status_code == (303 if shutil.which("say") else 400)


def test_job_page_api_and_retry_rules():
    job = done_job()
    html = client.get(f"/jobs/{job.id}").text
    assert "#커피상식 #카페" in html and "final.mp4?v=2026-10-13" in html and "그라데이션 배경" in html
    d = client.get(f"/api/jobs/{job.id}").json()
    assert d["sig"] == "done:dddddd:0:-" and d["say"] == "완성" and d["log"][-1].endswith("완성")
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 409
    assert client.get("/jobs/..%2Fetc").status_code == 404 and client.get("/api/jobs/nope").status_code == 404


def test_recover_marks_running_jobs_interrupted():
    job = Job.create("커피", "ko-KR-SunHiNeural")
    job.step("script", status="done")
    job.step("footage", status="running")
    job.update(status="running")
    (job.dir / "final.tmp.mp4").write_bytes(b"x")
    web.recover()
    d = job.data
    assert d["status"] == "interrupted" and d["steps"]["footage"]["status"] == "pending"
    assert d["steps"]["script"]["status"] == "done" and not (job.dir / "final.tmp.mp4").exists()
    assert "실패: " not in web.say(d) and web.say(d) == "중단"
    waiting = Job.create("차", "ko-KR-SunHiNeural")
    waiting.update(status="waiting")
    web.recover()
    assert waiting.data["status"] == "waiting"   # 사람을 기다리는 작업은 서버가 꺼져도 그대로


def test_unknown_model_cost_keeps_pages_up():
    job = done_job()
    job.update(usage=job.data["usage"] | {"cost_usd": None})   # 가격표에 없는 모델
    assert client.get("/").status_code == 200 and client.get(f"/jobs/{job.id}").status_code == 200


def test_rejects_cross_site_post_and_foreign_host(monkeypatch):
    monkeypatch.setattr(worker, "enqueue", lambda _id: True)
    form = {"topic": "커피", "voice": "ko-KR-SunHiNeural"}
    assert client.post("/jobs", data=form, headers={"Origin": "http://localhost:3000"}).status_code == 403
    assert client.post("/jobs", data=form, headers={"Origin": "http://127.0.0.1"}, follow_redirects=False).status_code == 303
    # tailscale serve: 브라우저는 https, 앱은 http로 받는다
    assert client.post("/jobs", data=form, headers={"Origin": "https://127.0.0.1"}, follow_redirects=False).status_code == 303
    assert client.get("/", headers={"Host": "evil.example:8765"}).status_code == 400


def test_upload_endpoint_rules(monkeypatch):
    job = done_job()
    monkeypatch.setattr(youtube, "ready", lambda: False)
    assert client.post(f"/api/jobs/{job.id}/upload").status_code == 400
    assert "uv run sp youtube-login" in client.get(f"/jobs/{job.id}").text
    monkeypatch.setattr(youtube, "ready", lambda: True)
    assert "승인하고 YouTube에 올리기" in client.get(f"/jobs/{job.id}").text
    draft = Job.create("차", "ko-KR-SunHiNeural")
    r = client.post(f"/api/jobs/{draft.id}/upload")
    assert r.status_code == 409 and r.json()["detail"] == "완성된 영상만 올릴 수 있어요"
    assert client.post(f"/api/jobs/{job.id}/upload").json() == {"ok": True}
    assert worker._q.get_nowait() == ("upload", job.id)
    r = client.post(f"/api/jobs/{job.id}/upload")
    assert r.status_code == 409 and r.json()["detail"] == "이미 올리는 중이에요"
    d = client.get(f"/api/jobs/{job.id}").json()
    assert d["sig"].endswith(":queued") and d["say"] == "YouTube에 올리는 중"
    assert 'data-active="1"' in client.get(f"/jobs/{job.id}").text   # 열자마자 폴링한다
    job.update(upload=upload_state("done", video_id="VID"))
    assert client.post(f"/api/jobs/{job.id}/upload").json()["detail"] == "이미 올렸어요"
    assert "studio.youtube.com/video/VID/edit" in client.get(f"/jobs/{job.id}").text


def test_recover_fails_interrupted_upload(monkeypatch):
    job = done_job()
    job.update(upload=upload_state("running"))
    web.recover()
    d = job.data
    assert d["status"] == "done" and d["upload"]["status"] == "failed" and "스튜디오" in d["upload"]["error"]
    assert web.say(d) == "YouTube 업로드 실패"
    monkeypatch.setattr(youtube, "ready", lambda: True)   # 실패 뒤 [다시 올리기]
    html = client.get(f"/jobs/{job.id}").text
    assert "다시 올리기" in html and "스튜디오에서 먼저 확인" in html
    assert client.post(f"/api/jobs/{job.id}/upload").json() == {"ok": True}
    assert worker._q.get_nowait() == ("upload", job.id)


MP4 = b"\0\0\0\x18ftypmp42" + b"x" * 16   # ftyp 머리만 있는 가짜(디코드 검증은 가짜 ffmpeg)


def scene_job(status="waiting", done=("script",)):
    job = Job.create("커피", "ko-KR-SunHiNeural")
    atomic_write_json(job.dir / "script.json", {"title": "t", "description": "d", "tags": [],
                                                "sentences": ["하나", "둘"], "prompts": ["p1", "p2"]})
    job.update(status=status, steps=job.data["steps"] | {s: {"status": "done", "engine": "x", "sec": 1.0} for s in done})
    return job


def test_clip_upload_waits_then_enqueues(monkeypatch):
    job = scene_job()
    html = client.get(f"/jobs/{job.id}").text
    assert "p1" in html and "프롬프트 복사" in html and "클립 대기" in html and "클립 0/2" in html
    assert client.get(f"/api/jobs/{job.id}").json()["say"] == "클립 대기"
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    enqueued = []
    monkeypatch.setattr(worker, "enqueue", enqueued.append)
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
    assert read_json(job.dir / "clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"}]
    assert "클립 1/2" in client.get(f"/jobs/{job.id}").text
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and enqueued == [job.id]
    job.update(status="queued")
    assert client.post(f"{url}/0", content=MP4).status_code == 409


def test_clip_replace_after_done_rerenders_only(monkeypatch):
    job = scene_job("done", STEPS)
    (job.dir / "clips").mkdir()
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    atomic_write_json(job.dir / "clips.json", [{"file": f"clip{i}.mp4", "source": "Google Flow"} for i in (0, 1)])
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(worker, "redo", lambda j, steps: seen.append(steps) or True)
    assert "클립 바꾸기" in client.get(f"/jobs/{job.id}").text   # 완성 뒤에도 장면마다 바꿀 수 있다
    url = f"/api/jobs/{job.id}/clips"
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and seen == [("render",)]
    assert client.post(f"{url}/0", content=MP4).status_code == 200 and seen[-1] == ("thumbnail", "render")
    assert [c["source"] for c in read_json(job.dir / "clips.json")] == ["직접 올림", "직접 올림"]
    job.update(status="failed")
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and len(seen) == 3
    job.update(upload=upload_state("done"))
    assert client.post(f"{url}/1", content=MP4).status_code == 409


def test_checks_list_providers(monkeypatch):
    monkeypatch.setattr(config, "VIDEO", "flow")
    checks = web._checks()
    labels = [c[1] for c in checks]
    assert labels[0] == "Claude API 키" and "영상 · Google Flow (기본)" in labels and "음성 · edge-tts" in labels


def test_script_edit_direct_and_revise():
    job = scene_job("done", STEPS)
    url = f"/api/jobs/{job.id}/script"
    assert 'id="script-edit"' in client.get(f"/jobs/{job.id}").text
    form = {"title": "t", "description": "d", "tags": "", "sentences": ["하나", "둘"]}
    # 제목·태그만: 저장만, 다시 돌지 않는다
    assert client.post(url, data=form | {"tags": "#커피, , 카페"}).json()["msg"] == "저장했어요"
    assert read_json(job.dir / "script.json")["tags"] == ["커피", "카페"] and job.data["status"] == "done"
    assert client.post(url, data=form | {"sentences": ["하나"]}).status_code == 400   # 장면 수가 다르면
    assert client.post(url, data=form | {"sentences": ["하나", " "]}).status_code == 400
    # 문장을 바꾸면 음성부터(클립·썸네일은 그대로)
    assert client.post(url, data=form | {"sentences": ["하나", "셋"]}).status_code == 200
    d = job.data
    assert read_json(job.dir / "script.json")["sentences"] == ["하나", "셋"] and d["status"] == "queued"
    assert [s for s in STEPS if d["steps"][s]["status"] == "pending"] == ["voice", "subtitles", "render"]
    assert worker._q.get_nowait() == ("run", job.id)
    assert client.post(url, data=form).status_code == 409   # 만드는 중
    job.update(status="done")
    assert client.post(f"{url}/revise", data={"note": " "}).status_code == 400
    assert client.post(f"{url}/revise", data={"note": "더 짧게"}).status_code == 200
    d = job.data
    assert d["script_note"] == "더 짧게" and d["steps"]["script"]["status"] == "pending" and d["steps"]["footage"]["status"] == "done"
    assert worker._q.get_nowait() == ("run", job.id)
    job.update(status="done", upload=upload_state("done"))
    assert "대본" in client.post(url, data=form).json()["detail"]

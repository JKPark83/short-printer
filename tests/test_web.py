import shutil

import pytest
from fastapi.testclient import TestClient

from shorts_printer import config, registry
from shorts_printer.adapters.youtube import YouTube
from shorts_printer.core.pipeline import STEPS, Job
from shorts_printer.core.trends import Trend
from shorts_printer.infra.store import atomic_write_json, read_json, upload_state
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
    head = head.replace('name = "40초 상식"', 'name = "Space Facts"').replace('language = "ko"', 'language = "en"')
    head = head.replace('default = "LKOcTG4J4tYTPR9DnLeM"', 'default = "enVoice1"')
    head = head.replace("daily_goal = 3", "daily_goal = 2")
    voices = '\nenVoice1 = "Adam"\n\n[video]' + voices.split("[video]", 1)[1]
    (en / "channel.toml").write_text(head + "[tts.voices]" + voices, encoding="utf-8")
    monkeypatch.setattr(config, "CHANNELS_DIR", root)
    return "en-space-facts"


def done_job(channel=CH, voice="LKOcTG4J4tYTPR9DnLeM", topic="커피"):
    job = Job.create(channel, topic, voice)
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
    monkeypatch.setattr(web.q, "enqueue", queued.append)
    assert client.post("/jobs", data={"topic": "  ", "voice": "elevenlabs", "channel": CH}).status_code == 400
    assert client.post("/jobs", data={"topic": "커피", "voice": "ko-KR-SunHiNeural", "channel": CH}).status_code == 400
    assert client.post("/jobs", data={"topic": "커피", "voice": "elevenlabs"}).status_code == 400   # 채널 없음
    assert client.post("/jobs", data={"topic": "커피", "voice": "elevenlabs", "channel": "all"}).status_code == 400
    r = client.post("/jobs", data={"topic": " 커피 ", "voice": "elevenlabs", "channel": CH}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/jobs/{queued[0]}"
    assert (Job.load(queued[0]).data["topic"], Job.load(queued[0]).data["channel"]) == ("커피", CH)
    html = client.get("/").text
    assert html.index(">미스터킴<") < html.index(">미스터최<")   # 첫 칸이 기본값


def test_job_page_api_and_retry_rules():
    job = done_job()
    html = client.get(f"/jobs/{job.id}").text
    assert "#커피상식 #카페" in html and "final.mp4?v=2026-10-13" in html and "그라데이션 배경" in html
    d = client.get(f"/api/jobs/{job.id}").json()
    assert d["sig"] == "done:dddddd:0:-" and d["say"] == "완성" and d["log"][-1].endswith("완성")
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 409
    assert client.get("/jobs/..%2Fetc").status_code == 404 and client.get("/api/jobs/nope").status_code == 404


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
    atomic_write_json(job.dir / "script.json", {"title": "t", "description": "d", "tags": [],
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
    assert read_json(job.dir / "clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"}]
    assert "클립 1/2" in client.get(f"/jobs/{job.id}").text
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and enqueued == [job.id]
    job.update(status="queued")
    assert client.post(f"{url}/0", content=MP4).status_code == 409


def test_sensitive_banner_and_confirm(monkeypatch):
    job = scene_job()
    atomic_write_json(job.dir / "script.json", read_json(job.dir / "script.json") | {"sensitive": "금융·투자"})
    assert "민감 분야(금융·투자)" in client.get(f"/jobs/{job.id}").text
    enqueued = []
    monkeypatch.setattr(web.q, "enqueue", lambda i: enqueued.append(i) or True)
    assert client.post(f"/api/jobs/{job.id}/confirm").json() == {"ok": True}
    assert enqueued == [job.id] and job.data["confirmed"] is True
    assert "민감 분야" not in client.get(f"/jobs/{job.id}").text


def test_clip_replace_after_done_rerenders_only(monkeypatch):
    job = scene_job("done", STEPS)
    (job.dir / "clips").mkdir()
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    atomic_write_json(job.dir / "clips.json", [{"file": f"clip{i}.mp4", "source": "Google Flow"} for i in (0, 1)])
    monkeypatch.setattr(web.ffmpeg, "run", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(web.q, "redo", lambda j, steps: seen.append(steps) or True)
    assert "클립 바꾸기" in client.get(f"/jobs/{job.id}").text   # 완성 뒤에도 장면마다 바꿀 수 있다
    url = f"/api/jobs/{job.id}/clips"
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and seen == [("render",)]
    assert client.post(f"{url}/0", content=MP4).status_code == 200 and seen[-1] == ("thumbnail", "render")
    assert [c["source"] for c in read_json(job.dir / "clips.json")] == ["직접 올림", "직접 올림"]
    job.update(status="failed")
    assert client.post(f"{url}/1", content=MP4).status_code == 200 and len(seen) == 3
    job.update(upload=upload_state("running"))
    assert client.post(f"{url}/1", content=MP4).status_code == 409   # 올리는 중


def test_checks_list_providers():
    labels = [c[1] for c in web._checks(CH)]
    assert labels[0] == "Claude API 키" and "영상 · Google Flow(자동) (이 채널)" in labels
    assert "음성 · ElevenLabs" in labels
    assert "YouTube 업로드" in labels and labels == [c[1] for c in web._checks("all")]   # 전체는 첫 채널
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
    assert read_json(job.dir / "script.json")["tags"] == ["커피", "카페"] and job.data["status"] == "done"
    assert client.post(url, data=form | {"sentences": ["하나"]}).status_code == 400   # 장면 수가 다르면
    assert client.post(url, data=form | {"sentences": ["하나", " "]}).status_code == 400
    # 문장을 바꾸면 음성부터(클립·썸네일은 그대로)
    assert client.post(url, data=form | {"sentences": ["하나", "셋"]}).status_code == 200
    d = job.data
    assert read_json(job.dir / "script.json")["sentences"] == ["하나", "셋"] and d["status"] == "queued"
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
    assert web.q._q.get_nowait() == ("run", job.id)
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


def test_edit_checks_only_changed_sentences_against_channel_length():
    job = scene_job("done", STEPS)
    long = "가" * 120   # ko 채널 한도(55자의 두 배)를 넘는 예전 문장
    atomic_write_json(job.dir / "script.json", read_json(job.dir / "script.json") | {"sentences": ["하나", long]})
    url, form = f"/api/jobs/{job.id}/edit", {"title": "t", "description": "d", "tags": ""}
    assert client.post(url, data=form | {"sentences": ["하나", long]}).status_code == 200   # 안 바꾼 문장은 통과
    r = client.post(url, data=form | {"sentences": ["가" * 111, long]})
    assert r.status_code == 400 and "110자" in r.json()["detail"]


def test_edit_subtitles_and_thumbnail_by_hand(monkeypatch):
    job = scene_job("done", STEPS)
    atomic_write_json(job.dir / "cues.json", [{"start": 0, "end": 1, "text": "하나"},
                                              {"start": 1, "end": 2, "text": "둘"}])
    atomic_write_json(job.dir / "thumb.json", {"lines": ["물 양", "비밀"], "accent": "비밀", "position": "top",
                                               "usage": None, "texts": []})
    (job.dir / "thumbnail.jpg").write_bytes(b"x")
    html = client.get(f"/jobs/{job.id}").text
    assert 'name="cues" form="edit"' in html and 'name="thumb" form="edit"' in html and "data-sample" in html
    url, form = f"/api/jobs/{job.id}/edit", {"title": "t", "description": "d", "tags": "", "sentences": ["하나", "둘"]}
    edit = form | {"cues": ["하나", "둘"], "thumb": ["물 양", "비밀"], "accent": "비밀"}
    assert client.post(url, data=edit).json()["msg"] == "저장했어요"   # 그대로면 저장만
    assert client.post(url, data=edit | {"cues": ["하나"]}).status_code == 400
    # 자막 줄만 → 렌더만(시각은 그대로)
    assert client.post(url, data=edit | {"cues": ["하나!", "둘"]}).json()["msg"] == "저장했어요. 렌더를 다시 해요"
    assert read_json(job.dir / "cues.json")[0] == {"start": 0, "end": 1, "text": "하나!"}
    assert [s for s in STEPS if job.data["steps"][s]["status"] == "pending"] == ["render"]
    web.q._q.get_nowait()
    # 썸네일 문구 → 썸네일·렌더, 문구에 없는 강조는 뺀다
    job.update(status="done")
    assert client.post(url, data=edit | {"thumb": ["가" * 13, ""]}).status_code == 400
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
    assert r.cookies.get("sp_channel") == CH and "Mars" not in r.text and "<small> / 3</small>" in r.text
    html = client.get("/").text   # 쿠키로 기억한다
    assert "커피" in html and "Mars" not in html
    html = client.get("/?channel=all").text   # 전체: 둘 다, 채널 이름 배지, 목표는 합
    assert "커피" in html and "Mars" in html and 'b-ch">Space Facts' in html and "<small> / 5</small>" in html
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

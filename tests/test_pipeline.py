from dataclasses import replace
from types import SimpleNamespace

import pytest

from shorts_printer import registry
from shorts_printer.adapters import flow_auto
from shorts_printer.adapters.flow import Flow
from shorts_printer.adapters.splitters.ko import Korean
from shorts_printer.core import channel, pipeline, scenes, trends
from shorts_printer.core import script as script_mod
from shorts_printer.core.channel import ResearchCfg
from shorts_printer.core.pipeline import STEPS, Job
from shorts_printer.core.services import Services
from shorts_printer.infra import store
from shorts_printer.infra.worker import LocalQueue

CH = "ko-40sec-facts"


class Publisher:
    label, hint, private = "가짜올림", "", True

    def __init__(self, fail_thumb=False):
        self.sent, self.thumbs, self.fail_thumb = [], [], fail_thumb

    def ready(self):
        return True

    def upload(self, path, meta, log):
        self.sent.append((path.name, meta))
        return "VID"

    def set_thumbnail(self, video_id, path):
        if self.fail_thumb:
            raise RuntimeError("forbidden")
        self.thumbs.append((video_id, path.name))

    def link(self, video_id):
        return f"https://v/{video_id}"


def services(**kw) -> Services:
    """작은 가짜로 묶은 Services. 쓰지 않는 공급자는 None."""
    return Services(**{"channel": channel.load(CH), "llm": None, "tts": None, "video": Flow(),
                       "publisher": Publisher(), "splitter": Korean(), "research": None} | kw)


def stub_steps(monkeypatch, fail=None):
    ran = []

    def make(name):
        def step(job, sv):
            ran.append(name)
            if name == fail:
                raise RuntimeError("일부러 sk-ant-SECRET 실패")
            return f"{name}-engine"
        return step

    monkeypatch.setattr(pipeline, "RUN", {s: make(s) for s in STEPS})
    return ran


def test_failure_is_recorded_redacted_then_retry_resumes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    job = Job.create(CH, "주제", "ko-KR-SunHiNeural")
    assert job.data["channel"] == CH
    ran = stub_steps(monkeypatch, fail="voice")
    with pytest.raises(RuntimeError):
        pipeline.run(job, services())
    d = job.data
    assert d["status"] == "failed" and d["error"]["step"] == "voice"
    assert "SECRET" not in d["error"]["message"] and "SECRET" not in "\n".join(job.tail())
    assert [d["steps"][s]["status"] for s in STEPS] == ["done", "done", "done", "failed", "pending", "pending",
                                                        "pending", "pending"]

    ran = stub_steps(monkeypatch)
    pipeline.run(job, services())
    assert ran == ["voice", "subtitles", "footage", "thumbnail", "render"]   # 끝난 단계는 건너뛴다
    d = job.data
    assert d["status"] == "done" and d["error"] is None and d["steps"]["render"]["engine"] == "render-engine"


def scene_job(*done, ch=CH):
    """문장 2개짜리 대본·음성 시각이 있는 작업."""
    job = Job.create(ch, "주제", "ko-KR-SunHiNeural")
    job.put("script.json", {"sentences": ["하나", "둘"], "prompts": ["p1", "p2"],
                                                "search_terms": ["cat", "dog"]})
    job.put("timing.json", [{"start": 0, "end": 1.2}, {"start": 1.3, "end": 2.5}])
    for s in done + (("research", "proofread") if "script" in done else ()):   # 대본이 있으면 조사·검수는 끝났다
        job.step(s, status="done")
    return job


def test_review_job_waits_for_confirmed_script(monkeypatch):
    job = scene_job("script")
    job.update(review=True)
    ran = stub_steps(monkeypatch)
    monkeypatch.setitem(pipeline.RUN, "footage", pipeline.step_footage)
    pipeline.run(job, services())   # 대본·음성·자막까지 돌고 영상 소스(크레딧) 앞에서 멈춘다
    assert ran == ["voice", "subtitles"] and job.data["status"] == "waiting"
    assert pipeline.in_review(job.data)
    job.update(confirmed=True)
    assert not pipeline.in_review(job.data)
    assert not pipeline.in_review(Job.create(CH, "주제", "v").data | {"status": "waiting"})   # 스케줄·CLI는 안 멈춘다
    job.update(voice_ok=False)   # 초안 음성을 확정해 채널 TTS로 다시 읽었으면 음성 확정 전까지 영상을 만들지 않는다
    pipeline.run(job, services())
    assert job.data["status"] == "waiting" and pipeline.in_voice_review(job.data)


def footage_only(monkeypatch):
    ran = stub_steps(monkeypatch)
    monkeypatch.setitem(pipeline.RUN, "footage", pipeline.step_footage)
    return ran


def test_footage_waits_for_clips_then_resumes(monkeypatch):
    job = scene_job("script", "voice", "subtitles")
    ran = footage_only(monkeypatch)
    pipeline.run(job, services())
    d = job.data
    assert d["status"] == "waiting" and d["steps"]["footage"]["status"] == "pending"
    assert ran == [] and d["error"] is None
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    pipeline.run(job, services())
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"


def sensitive_job():
    job = scene_job("script", "voice", "subtitles")
    job.put("script.json", job.doc("script.json") | {"sensitive": "건강·의료"})
    (job.dir / "clips").mkdir()
    for i in (0, 1):
        (job.dir / "clips" / f"clip{i}.mp4").write_bytes(b"x")
    return job


def test_sensitive_script_waits_for_confirm_before_footage(monkeypatch):
    job = sensitive_job()
    ran = footage_only(monkeypatch)
    pipeline.run(job, services())
    assert job.data["status"] == "waiting" and ran == [] and "민감 분야(건강·의료)" in "\n".join(job.tail())
    job.update(confirmed=True)
    pipeline.run(job, services())
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"
    assert job.doc("clips.json") == [{"file": "clip0.mp4", "source": "직접 올림"},
                                                 {"file": "clip1.mp4", "source": "직접 올림"}]


def test_sensitive_gate_off_skips_the_wait(monkeypatch):
    job = sensitive_job()
    ran = footage_only(monkeypatch)
    pipeline.run(job, services(channel=channel.load(CH).model_copy(update={"sensitive_gate": False})))
    assert ran == ["thumbnail", "render"] and job.data["status"] == "done"


def test_auto_provider_fills_what_it_can_then_waits():
    class Fake:
        label, hint = "Fake", ""

        def __init__(self):
            self.calls = []

        def ready(self):
            return True

        def make(self, todo, out, log):
            self.calls.append([s["i"] for s in todo])
            if todo and todo[0]["i"] == 0:
                (out / "clip0.mp4").write_bytes(b"x")
                yield {"file": "clip0.mp4", "source": "Fake", "sec": todo[0]["sec"]}

    fake = Fake()
    sv = services(video=fake)
    job = scene_job("script", "voice", "subtitles")
    with pytest.raises(pipeline.Wait):
        pipeline.step_footage(job, sv)
    sec = pytest.approx(1.3, abs=0.04)
    assert job.doc("clips.json") == [{"file": "clip0.mp4", "source": "Fake", "sec": sec}]
    (job.dir / "clips" / "clip1.mp4").write_bytes(b"x")
    scenes.set_clip(job, {"file": "clip1.mp4", "source": "직접 올림"})
    assert pipeline.step_footage(job, sv) == "Fake 2개"
    assert fake.calls == [[0, 1], []]   # 있는 장면은 다시 안 만든다
    assert [c["source"] for c in job.doc("clips.json")] == ["Fake", "직접 올림"]



def test_cancel_stops_after_current_clip_and_retry_resumes(monkeypatch):
    """취소는 받은 장면까지 남기고 다음 장면을 넣지 않는다(이미 쓴 크레딧을 버리지 않게). 다시 돌리면 이어서."""
    job = scene_job("script", "voice", "subtitles")
    ran = footage_only(monkeypatch)
    made = []

    class Fake:
        label = "Fake"
        press = True

        def ready(self):
            return True

        def make(self, todo, out, log):
            for s in todo:
                made.append(s["i"])
                (out / s["file"]).write_bytes(b"x")
                if self.press:   # 첫 장면을 만드는 중에 취소를 눌렀다
                    job.update(cancel=True)
                yield {"file": s["file"], "source": "Fake"}

    sv = services(video=Fake())
    pipeline.run(job, sv)
    d = job.data
    assert made == [0] and d["status"] == "interrupted" and d["steps"]["footage"]["status"] == "pending"
    assert [c["file"] for c in job.doc("clips.json")] == ["clip0.mp4"] and ran == []
    pipeline.run(job, sv)   # 취소가 남아 있으면 단계 앞에서 바로 멈춘다
    assert made == [0] and job.data["status"] == "interrupted"
    job.update(cancel=None)   # 다시 시도하면 작업 스레드가 지운다
    sv.video.press = False
    pipeline.run(job, sv)
    assert made == [0, 1] and job.data["status"] == "done" and ran == ["thumbnail", "render"]

def test_flow_auto_without_chrome_falls_back_to_flow(monkeypatch):
    ch = channel.load(CH)
    ch = ch.model_copy(update={"video": ch.video.model_copy(update={"provider": "flow-auto"})})
    monkeypatch.setattr(flow_auto, "CHROME", "/nope")   # Chrome이 없는 기계면 Flow(직접 올림)
    assert registry.video(ch)[0] == "flow"


def test_redact_hides_any_api_key_by_suffix(monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "sd-SECRET-123")
    assert store.redact("x sd-SECRET-123 y") == "x *** y"
    monkeypatch.setenv("SHORT_API_KEY", "ab")
    assert "ab" in store.redact("ab")   # 짧은 값은 가리지 않는다


def test_redo_steps():
    q = LocalQueue(lambda cid: pytest.fail("넣기만 하면 Services를 찾지 않는다"))
    job = scene_job(*STEPS)
    job.update(status="failed")
    assert q.redo(job.id, ("render",))
    d = Job.load(job.id).data
    assert d["status"] == "queued" and d["steps"]["render"]["status"] == "pending"
    assert d["steps"]["thumbnail"]["status"] == "done"
    assert q._q.get_nowait() == ("run", job.id)


def test_trend_queue_is_separate_from_jobs():
    """주제 찾기는 따로 줄을 서서 영상 제작이 도는 동안에도 돈다."""
    q = LocalQueue(lambda cid: pytest.fail("넣기만 하면 Services를 찾지 않는다"))
    job, t = Job.create("ch", "주제", "v"), trends.Trend.create("ch")
    assert q.enqueue(job.id) and q.enqueue_trend(t.id)
    assert q._q.get_nowait() == ("run", job.id) and q._q.empty()
    assert q._tq.get_nowait() == ("trend", t.id)


def test_queue_resolves_services_by_job_channel(monkeypatch):
    seen, got = [], []
    q = LocalQueue(lambda cid: seen.append(cid) or SimpleNamespace(cid=cid))
    monkeypatch.setattr(pipeline, "run", lambda job, sv: got.append(("run", job.id, sv.cid)))
    monkeypatch.setattr(pipeline, "publish", lambda job, sv, target=None: got.append(("upload", job.id, sv.cid)))
    monkeypatch.setattr(trends, "run", lambda t, sv: got.append(("trend", t.id, sv.cid)))
    a, b, t = Job.create("ch-a", "주제", "v"), Job.create("ch-b", "주제", "v"), trends.Trend.create("ch-c")
    a.update(status="queued")   # 제작은 큐에 넣은 것만 돈다
    q.run_one(a.id)
    q.run_one(b.id, "upload")
    q.run_one(t.id, "trend")
    assert seen == ["ch-a", "ch-b", "ch-c"]
    assert got == [("run", a.id, "ch-a"), ("upload", b.id, "ch-b"), ("trend", t.id, "ch-c")]


def test_queue_marks_failed_when_channel_cannot_resolve():
    def resolve(cid):
        raise KeyError("채널이 없어요")
    q = LocalQueue(resolve)
    a, b, t = Job.create("gone", "주제", "v"), Job.create("gone", "주제", "v"), trends.Trend.create("gone")
    a.update(status="queued")
    q.run_one(a.id)
    q.run_one(b.id, "upload")
    q.run_one(t.id, "trend")
    assert Job.load(a.id).data["status"] == "failed" and "채널이 없어요" in Job.load(a.id).data["error"]["message"]
    assert Job.load(b.id).data["upload"]["status"] == "failed"
    assert trends.Trend.load(t.id).data["status"] == "failed"
    assert q.enqueue(a.id) and q.enqueue_trend(t.id)   # queued에 갇히지 않아 다시 넣을 수 있다


def test_script_step_passes_brief_and_recent_titles_of_same_channel(monkeypatch):
    job = Job.create(CH, "주제", "ko-KR-SunHiNeural", brief="질문으로 시작", source={"trend": "t1", "pick": 0})
    assert job.data["brief"] == "질문으로 시작" and job.data["source"] == {"trend": "t1", "pick": 0}
    seen = []

    def write(llm, ch, topic, brief=None, recent=(), facts=(), **kw):
        seen.append((ch.id, topic, brief, recent, facts))
        raise RuntimeError("여기까지만")
    monkeypatch.setattr(pipeline.script, "write", write)
    with pytest.raises(RuntimeError):
        pipeline.step_script(job, services())
    for cid, title in ((CH, "라면의 진짜 이유"), ("en-other", "Other channel title")):
        other = Job.create(cid, "예전", "v")
        other.put("script.json", {"title": title, "sentences": ["x"]})
    fact = {"id": "F1", "text": "가", "url": "https://a.go.kr/1", "kind": "official"}
    job.put("facts.json", {"queries": [], "facts": [fact]})   # 자료 조사 결과를 대본에 넘긴다
    with pytest.raises(RuntimeError):
        pipeline.step_script(job, services())
    assert seen == [(CH, "주제", "질문으로 시작", [], []), (CH, "주제", "질문으로 시작", ["라면의 진짜 이유"], [fact])]


def test_script_step_passes_unverified_claims_from_research_notes(monkeypatch):
    """조사 메모의 "확인 못 함:" 줄을 주장만 떼어 대본 쓰기에 넘긴다(여러 줄이 한 메모에 붙어 와도)."""
    job = Job.create(CH, "주제", "v")
    job.put("facts.json", {"queries": [], "facts": [], "notes": [
        "검색 'x': 9건", "(반론 있음)\n확인 못 함: 수학 손짓(2001)\n확인 못 함: 손을 묶으면(1996)",
        "확인 못 함: 수학 손짓(2001)"]})
    seen = []

    def write(*a, unverified=(), **kw):
        seen.append(unverified)
        raise RuntimeError("여기까지만")
    monkeypatch.setattr(pipeline.script, "write", write)
    with pytest.raises(RuntimeError):
        pipeline.step_script(job, services())
    assert seen == [["수학 손짓(2001)", "손을 묶으면(1996)"]]


def test_script_step_revises_when_note(monkeypatch):
    job = scene_job(*STEPS)
    job.update(script_note="더 짧게", usage={"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01})
    monkeypatch.setattr(pipeline.script, "write", lambda *a: pytest.fail("새로 쓰면 장면이 바뀐다"))
    monkeypatch.setattr(pipeline.script, "revise", lambda llm, ch, s, note, **kw: (
        s | {"sentences": ["짧게", "둘"]}, {"model": "m", "input_tokens": 2, "output_tokens": 2, "cost_usd": 0.02}))
    assert pipeline.step_script(job, services()) == "m"
    assert job.doc("script.json")["prompts"] == ["p1", "p2"] and job.data["usage"]["cost_usd"] == 0.03


def test_publish_uses_channel_publisher():
    job = scene_job(*STEPS)
    meta = {"title": "제목", "description": "설명", "tags": ["a"]}
    job.put("script.json", meta | {"sentences": ["x"]})
    (job.dir / "thumbnail.jpg").write_bytes(b"JPG")
    sv = services()
    pipeline.publish(job, sv)
    footer = "\n\n" + channel.load(CH).publish.footer
    assert sv.publisher.sent == [("final.mp4", meta | {"description": "설명" + footer})]
    assert sv.publisher.thumbs == [("VID", "thumbnail.jpg")]
    up = job.data["upload"]
    assert up["status"] == "done" and up["video_id"] == "VID" and up["note"] is None
    assert "가짜올림 업로드 완료: VID (비공개)" in "\n".join(job.tail())

    sv = replace(sv, publisher=Publisher(fail_thumb=True))   # 썸네일 실패는 업로드를 실패로 두지 않는다
    pipeline.publish(job, sv)
    up = job.data["upload"]
    assert up["status"] == "done" and "forbidden" in up["note"] and "가짜올림에서" in up["note"]


def test_extra_target_keeps_its_own_state_and_schedule_uploads_only_primary(monkeypatch):
    job = scene_job(*STEPS)
    job.put("script.json", {"title": "제목", "description": "설명", "tags": [], "sentences": ["x"]})
    job.update(status="done")
    extra = Publisher()
    extra.label, extra.private = "인스타", False
    sv = services(also={"instagram": extra})
    q = LocalQueue(lambda cid: sv)
    assert q.enqueue_upload(job.id, target="instagram") and q._q.get_nowait() == ("upload:instagram", job.id)
    assert not q.enqueue_upload(job.id, target="instagram")   # 올리는 중이면 다시 못 넣는다
    after = []
    monkeypatch.setattr(q, "_after", lambda *a: after.append(a))
    q.run_one(job.id, "upload:instagram")
    d = job.data
    assert d["upload"] is None and extra.sent and not sv.publisher.sent
    up = d["uploads"]["instagram"]
    assert up["status"] == "done" and up["video_id"] == "VID" and up["url"] == "https://v/VID"
    tail = "\n".join(job.tail())
    assert after == [] and "인스타 업로드 완료: VID" in tail and "(비공개)" not in tail   # 공개라 붙이지 않는다

    assert q.redo(job.id) and job.data["uploads"] is None   # 다시 만들면 더 올린 기록도 옮긴다
    assert job.data["uploads_before"]["instagram"]["video_id"] == "VID"


def test_publish_appends_channel_footer_to_description():
    job = scene_job(*STEPS)
    s = {"title": "제목", "description": "설명\n", "tags": [], "sentences": ["x"]}
    job.put("script.json", s)
    ch = channel.load(CH)
    sv = services(channel=ch.model_copy(update={"publish": ch.publish.model_copy(update={"footer": "※AI 이미지"})}))
    pipeline.publish(job, sv)
    assert sv.publisher.sent[0][1]["description"] == "설명\n\n※AI 이미지"


def test_description_lists_used_sources_in_order_and_fits_5000_bytes():
    job = scene_job(*STEPS)
    job.put("script.json", {"title": "t", "description": "설명\n", "tags": [], "sentences": ["a", "b", "c"],
                            "fact_ids": [["F2"], ["F1", "F2"], ["F9"]]})
    job.put("facts.json", {"facts": [{"id": f"F{i}", "url": f"https://a.go.kr/{i}"} for i in (1, 2, 3)]})
    ch = channel.load(CH)

    def with_(**kw):
        return ch.model_copy(update={"publish": ch.publish.model_copy(update=kw)})

    # 쓴 것만, 등장 순, 중복 없이. 쓰지 않은 F3·시트에 없는 F9는 빠진다
    assert pipeline.description(job, with_(sources_heading="출처", footer="※AI")) == \
        "설명\n\n출처\nhttps://a.go.kr/2\nhttps://a.go.kr/1\n\n※AI"
    assert pipeline.description(job, with_(sources_heading="", footer="")) == "설명"
    job.edit("script.json", lambda s: s | {"description": "가" * 1653})   # 4959바이트: URL 하나만 들어간다
    out = pipeline.description(job, with_(sources_heading="출처", footer=""))
    assert out.endswith("출처\nhttps://a.go.kr/2") and len(out.encode()) <= 5000
    job.put("facts.json", None)
    job.edit("script.json", lambda s: s | {"description": "설명"})
    assert pipeline.description(job, with_(sources_heading="출처", footer="※AI")) == "설명\n\n※AI"   # 예전 작업


def test_publish_sends_description_with_sources():
    job = scene_job(*STEPS)
    job.put("script.json", {"title": "t", "description": "설명", "tags": [], "sentences": ["a"], "fact_ids": [["F1"]]})
    job.put("facts.json", {"facts": [{"id": "F1", "url": "https://a.go.kr/1"}]})
    ch = channel.load(CH)
    sv = services(channel=ch.model_copy(update={"publish": ch.publish.model_copy(update={"sources_heading": "출처"})}))
    pipeline.publish(job, sv)
    assert sv.publisher.sent[0][1]["description"] == pipeline.description(job, sv.channel) == \
        "설명\n\n출처\nhttps://a.go.kr/1\n\n" + ch.publish.footer


def test_flow_auto_retries_failed_scene_once_after_delay(monkeypatch, tmp_path):
    """실패는 5분 뒤 한 번만 더, 정책 거절은 다시 하지 않는다. 끝내 못 만든 장면이 있으면 실패로 던진다."""
    from unittest.mock import MagicMock

    import playwright.sync_api

    fa = flow_auto
    monkeypatch.setattr(fa, "open_chrome", lambda: None)
    monkeypatch.setattr(fa, "_settings", lambda page, aspect, quality: None)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", MagicMock())
    slept = []
    monkeypatch.setattr(fa.time, "sleep", slept.append)
    tries = []

    def gen(page, prompt, path):   # 장면 a는 계속, b는 처음 한 번만 실패, d는 거절
        tries.append(prompt)
        if prompt == "d":
            raise fa.Refused("미성년자 정책")
        if prompt == "a" or (prompt == "b" and tries.count("b") == 1):
            raise RuntimeError("화면이 바뀜")
        path.write_bytes(prompt.encode())

    monkeypatch.setattr(fa, "_generate", gen)
    todo = [{"i": i, "prompt": p, "file": f"{p}.mp4"} for i, p in enumerate("abcd")]
    logs, got = [], []
    with pytest.raises(RuntimeError, match="장면 1, 4을 못 만들었어요") as e:
        for c in fa.FlowAuto().make(todo, tmp_path, logs.append):
            got.append(c["file"])
    assert e.value.scenes == {3: "미성년자 정책"}   # 거절 사유는 core가 프롬프트를 고치도록 넘긴다
    assert tries == ["a", "b", "c", "d", "a", "b"]   # 실패한 장면만 딱 한 번 더, 거절된 d는 빼고
    assert got == ["c.mp4", "b.mp4"] and len(slept) == 2 and 0 < slept[0] <= fa.RETRY_AFTER
    assert "장면 4 거절됨(미성년자 정책)" in logs[4]
    assert "다시 해도 못 만듦" in logs[-2] and "다시 시도해 완료" in logs[-1]


def test_flow_auto_never_resubmits_lost_and_drops_duplicate_clip(monkeypatch, tmp_path):
    """넣었는데 못 받은 장면은 다시 넣지 않고(두 번 과금) 끝에 자리로 받는다. 앞 장면과 같은 파일을 받으면 버린다."""
    from unittest.mock import MagicMock

    import playwright.sync_api

    fa = flow_auto
    monkeypatch.setattr(fa, "open_chrome", lambda: None)
    monkeypatch.setattr(fa, "_settings", lambda page, aspect, quality: None)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", MagicMock())
    monkeypatch.setattr(fa.time, "sleep", lambda s: None)
    tries = []

    def gen(page, prompt, path):
        tries.append(prompt)
        if prompt == "b":
            raise fa.Lost("TimeoutError", 1)
        path.write_bytes(b"same")   # 타일을 잘못 짚으면 앞 장면 영상이 또 받아진다

    refetched = []

    def refetch(page, pos, path):
        refetched.append(pos)
        path.write_bytes(b"lost")
    monkeypatch.setattr(fa, "_generate", gen)
    monkeypatch.setattr(fa, "_refetch", refetch)
    todo = [{"i": i, "prompt": p, "file": f"{p}.mp4"} for i, p in enumerate("abc")]
    got = []
    with pytest.raises(RuntimeError, match="장면 3을 못 만들었어요"):
        for c in fa.FlowAuto().make(todo, tmp_path, lambda line: None):
            got.append(c["file"])
    assert tries == ["a", "b", "c"] and refetched == [1]
    assert got == ["a.mp4", "b.mp4"] and not (tmp_path / "c.mp4").exists()


def test_translate_only_non_korean_when_source_changed_and_never_fails_job(monkeypatch):
    calls = []

    def translate(llm, ch, s, thumb, cues):
        calls.append(list(cues))
        if s["sentences"][0] == "망가짐":
            raise RuntimeError("일부러")
        return {"src": pipeline.script.ko_source(s, thumb), "cues": list(cues), "ko": {}}, {
            "model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01}
    monkeypatch.setattr(pipeline.script, "translate", translate)
    job = scene_job()
    job.put("script.json", {"title": "t", "description": "d", "tags": [], "sentences": ["a", "b"]})
    pipeline.translate(job, services())
    assert calls == []   # 한국어 채널은 옮기지 않는다
    ja = services(channel=channel.load(CH).model_copy(update={"language": "ja"}))
    pipeline.translate(job, ja)
    pipeline.translate(job, ja)   # 원문 그대로면 다시 부르지 않는다
    job.put("cues.json", [{"start": 0, "end": 1, "text": "あ"}])
    pipeline.translate(job, ja)
    assert calls == [[], ["あ"]] and job.data["ko_usage"]["cost_usd"] == 0.02
    job.edit("script.json", lambda s: s | {"sentences": ["망가짐", "b"]})
    pipeline.translate(job, ja)
    assert any("한국어 뜻 실패: 일부러" in line for line in job.tail())


def test_old_job_without_research_step_is_filled_from_script(db):
    for status in ("done", "pending"):
        job = Job.create(CH, "주제", "v")
        old = {k: v for k, v in job.data["steps"].items() if k != "research"}
        old["script"]["status"] = status
        db.edit("job", job.id, lambda d, old=old: d | {"steps": old})
        assert job.data["steps"]["research"]["status"] == status


def test_step_research_saves_facts_and_usage():
    calls = []

    def gather(system, text, **kw):
        calls.append(text)
        return ([{"text": "가", "url": "https://kdca.go.kr/a", "title": "t", "published": "", "retrieved_at": "x"}],
                {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01})

    ch = channel.load(CH).model_copy(update={"research": ResearchCfg(domains=["kdca.go.kr"])})
    rs = SimpleNamespace(gather=gather)
    job = Job.create(CH, "독감", "v", brief="주장")
    assert pipeline.step_research(job, services(channel=ch, research=rs)) == "m"
    assert job.doc("facts.json")["facts"][0]["id"] == "F1" and job.data["research_usage"]["cost_usd"] == 0.01
    assert "주장" in calls[0] and "사실 1개" in job.tail()[-1]


def test_step_research_without_facts_keeps_notes_and_usage():
    def gather(system, text, **kw):
        note = {"text": "확인 못 함: 요금", "url": "", "title": "", "published": "", "retrieved_at": ""}
        return ([note], {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01})

    ch = channel.load(CH).model_copy(update={"research": ResearchCfg(domains=["kdca.go.kr"])})
    job = Job.create(CH, "독감", "v")
    with pytest.raises(RuntimeError, match="출처가 붙은 사실을 하나도"):
        pipeline.step_research(job, services(channel=ch, research=SimpleNamespace(gather=gather)))
    # 왜 못 찾았는지 남는다: 메모는 로그에, 비용은 usage에
    assert job.doc("facts.json")["notes"] == ["확인 못 함: 요금"]
    assert job.data["research_usage"]["cost_usd"] == 0.01 and "조사 메모: 확인 못 함" in job.tail()[-1]


def test_proofread_step_only_reviews_and_passes_with_small_issues_left(monkeypatch):
    ja = channel.load(CH).model_copy(update={"language": "ja"})
    monkeypatch.setattr(pipeline, "translate", lambda job, sv: None)
    usage = {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01}
    monkeypatch.setattr(pipeline.script, "write", lambda *a, **kw: (script_mod.Script(
        title="t1", description="d", tags=["a"], sensitive="",
        scenes=[script_mod.Scene(sentence=t, prompt=p) for t, p in zip("一二三", "pqr", strict=True)]), usage))
    monkeypatch.setattr(pipeline.script, "revise", lambda *a, **kw: pytest.fail("검수는 고치지 않는다"))
    verdict = script_mod.Verdict(issues=[script_mod.Issue(scene=3, kind="문장", severity="작음",
                                                          problem="새 흠", fix="x")])
    monkeypatch.setattr(pipeline.script, "proofread", lambda *a, **kw: (verdict, usage))
    job = Job.create(CH, "주제", "v")
    sv = services(channel=ja)
    pipeline.step_script(job, sv)
    assert pipeline.step_proofread(job, sv) == "m"
    s = job.doc("script.json")
    # 대본은 한 글자도 안 바뀐다
    assert s["title"] == "t1" and s["sentences"] == ["一", "二", "三"] and s["prompts"] == ["p", "q", "r"]
    assert job.data["usage"]["cost_usd"] == 0.02   # 쓰기 1 + 검수 1
    assert not job.data.get("review")
    logs = "\n".join(job.tail())
    assert "통과 97점(주제·제목 15/15, 흐름 25/25, 사실 20/20, 문장 12/15" in logs and "남은 지적 1개" in logs
    pr = job.doc("proofread.json")
    assert pr["pass"] == 70 and [r["total"] for r in pr["rounds"]] == [97] and pr["rounds"][0]["passed"]
    assert pr["rounds"][0]["issues"] == [{"kind": "문장", "severity": "작음", "text": "장면 3「三」: 새 흠 → x"}]


def test_failed_proofread_keeps_the_script_and_waits_for_a_human(monkeypatch):
    usage = {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": None}
    monkeypatch.setattr(pipeline.script, "write", lambda *a, **kw: (script_mod.Script(
        title="t", description="d", tags=["a"], sensitive="",
        scenes=[script_mod.Scene(sentence=t, prompt=p) for t, p in zip("가나다", "pqr", strict=True)]), usage))
    monkeypatch.setattr(pipeline.script, "revise", lambda *a, **kw: pytest.fail("검수는 고치지 않는다"))
    bad = script_mod.Verdict(issues=[script_mod.Issue(scene=1, kind="사실", severity="큼",
                                                      problem="반전이 아님", fix="가2")])
    monkeypatch.setattr(pipeline.script, "proofread", lambda *a, **kw: (bad, usage))
    job = Job.create(CH, "주제", "v")
    sv = services()
    pipeline.step_script(job, sv)
    pipeline.step_proofread(job, sv)   # 떨어져도 실패하지 않는다
    assert job.doc("script.json")["sentences"] == ["가", "나", "다"]   # 한 글자도 안 고친다
    # 장면을 만들기 전에 사람 확인으로 멈추고, 지적은 로그에 남는다
    assert job.data["review"] is True and not job.doc("proofread.json")["rounds"][0]["passed"]
    last = job.tail()[-1]
    assert "불통과" in last and "장면 1「가」: 반전이 아님 → 가2" in last and "검수는 고치지 않아요" in last
    # 완성 뒤 고치기(script_note)에서 떨어지면 지적만 남기고 확정 대기로 돌리지 않는다
    job.update(review=False, script_note="더 짧게")
    pipeline.step_proofread(job, sv)
    assert not job.data["review"] and "검수는 고치지 않아요" not in job.tail()[-1]


def test_old_job_without_proofread_step_is_filled_from_script(db):
    job = Job.create(CH, "주제", "v")
    old = {k: v for k, v in job.data["steps"].items() if k != "proofread"}
    old["script"]["status"] = "done"
    db.edit("job", job.id, lambda d: d | {"steps": old})
    assert job.data["steps"]["proofread"]["status"] == "done"


def test_refused_scene_is_recorded_then_reprompted_on_retry(monkeypatch):
    """정책 거절은 장면별 사유로 남기고, 다시 시도하면 클립이 없는 거절 장면만 프롬프트를 고쳐 넣는다."""
    from shorts_printer.ports.video import Refused

    sent = []

    class Video:
        label = "가짜영상"

        def make(self, todo, out, log):
            sent.append([s["prompt"] for s in todo])
            if len(sent) == 1:
                (out / "clip0.mp4").write_bytes(b"x")
                yield {"file": "clip0.mp4", "source": self.label}
                raise Refused("장면 2 거절", {1: "미성년자 정책"})
            for s in todo:
                (out / s["file"]).write_bytes(b"y")
                yield {"file": s["file"], "source": self.label}

    asked = []

    def reprompt(llm, ch, prompt, reason):
        asked.append((prompt, reason))
        return script_mod.Reprompt(cause="아이로 읽힘", prompt="p2 adult", prompt_ko="어른"), {
            "model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.01}
    monkeypatch.setattr(pipeline.script, "reprompt", reprompt)
    job = scene_job("script", "voice", "subtitles")
    sv = services(video=Video())
    with pytest.raises(Refused):
        pipeline.step_footage(job, sv)
    assert job.data["refused"] == [{"i": 1, "reason": "미성년자 정책"}]
    pipeline.step_footage(job, sv)
    assert asked == [("p2", "미성년자 정책")] and sent[1] == ["p2 adult"]
    assert job.doc("script.json")["prompts"] == ["p1", "p2 adult"] and job.data["refused"] is None


def test_flow_auto_fetches_submitted_scene_from_old_project_before_generating(monkeypatch, tmp_path):
    """넣었지만 못 받은 장면(clip.task)은 다시 넣지 않고 지난 프로젝트에서 받는다. 못 찾으면 새로 만든다."""
    import json
    from unittest.mock import MagicMock

    import playwright.sync_api

    fa = flow_auto
    monkeypatch.setattr(fa, "open_chrome", lambda: None)
    monkeypatch.setattr(fa, "_settings", lambda page, aspect, quality: None)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", MagicMock())
    made, fetched = [], []

    def gen(page, prompt, path):
        made.append(prompt)
        path.write_bytes(prompt.encode())

    def refetch(page, pos, path):
        fetched.append(pos)
        if pos == 9:
            raise TimeoutError("타일 없음")
        path.write_bytes(b"old")
        path.with_suffix(".task").unlink()
    monkeypatch.setattr(fa, "_generate", gen)
    monkeypatch.setattr(fa, "_refetch", refetch)
    for i, pos in ((0, 2), (1, 9)):
        (tmp_path / f"clip{i}.task").write_text(json.dumps({"url": "https://flow/project/old", "pos": pos}))
    todo = [{"i": i, "prompt": p, "file": f"clip{i}.mp4"} for i, p in enumerate("abc")]
    got = [c["file"] for c in fa.FlowAuto().make(todo, tmp_path, lambda line: None)]
    assert fetched == [2, 9] and made == ["b", "c"]   # a는 받기만, b는 못 찾아 새로
    assert got == ["clip0.mp4", "clip1.mp4", "clip2.mp4"] and not list(tmp_path.glob("*.task"))

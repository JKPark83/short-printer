from dataclasses import replace

import pytest
from test_pipeline import CH, Publisher, services

from shorts_printer import registry
from shorts_printer.core import channel, longform, pipeline
from shorts_printer.core.longform import STEPS_LONG
from shorts_printer.core.pipeline import Job
from shorts_printer.ports.video import Refused

LONG = channel.load(CH).model_copy(update={"format": "long"})


@pytest.fixture(autouse=True)
def npx(monkeypatch):
    """Node가 없는 기계에서도 돈다. 없을 때는 test_run_stops_before_paid_steps_without_npx가 본다."""
    monkeypatch.setattr(longform.hyperframes, "ready", lambda: True)


def long_job(*done: str) -> Job:
    job = Job.create(CH, "주제", LONG.tts.default, long=True)
    for s in done:
        job.step(s, status="done")
    return job


def test_clock_gaps_turn_and_end_card():
    starts, end_start, total = longform.clock([2, 3, 4], ["", "turn", ""])
    assert starts == [1.4, 4.8, 8.6]   # 1.4 + 2 + 1.4(turn 앞), 4.8 + 3 + 0.8
    assert (end_start, total) == (13.35, 19.95)


def test_create_long_steps_and_fix_adds_no_short_steps():
    job = long_job()
    assert job.data["format"] == "long" and tuple(job.data["steps"]) == STEPS_LONG
    assert not {"thumbnail", "subtitles", "footage"} & job.data["steps"].keys()   # _fix가 쇼츠 단계를 넣지 않는다
    assert tuple(Job.create(CH, "주제", "v").data["steps"]) == pipeline.STEPS


def test_run_dispatches_long_and_waits_for_script_approval():
    job = long_job("research", "script", "proofread")
    pipeline.run(job, services(channel=LONG))   # TTS가 None이어도 승인 전엔 읽지 않는다
    assert job.data["status"] == "waiting" and job.data["steps"]["voice"]["status"] == "pending"
    assert "음성 대기: 대본을 확인하고 승인해 주세요" in "\n".join(job.tail())


def test_run_stops_before_paid_steps_without_npx(monkeypatch):
    monkeypatch.setattr(longform.hyperframes, "ready", lambda: False)
    monkeypatch.setitem(longform.RUN, "research", lambda job, sv: pytest.fail("돈 드는 조사를 부르면 안 된다"))
    job = long_job()
    with pytest.raises(RuntimeError, match="Node.js 22 이상"):
        pipeline.run(job, services(channel=LONG))
    assert job.data["status"] == "failed" and job.data["error"]["step"] == "research"   # 작업 화면에 남는다
    assert "Node.js" in job.data["error"]["message"]


def test_render_srt_uses_twice_splitter_limit_unless_channel_sets_it(monkeypatch):
    limits = []
    monkeypatch.setattr(longform.hyperframes, "render", lambda project, out, log: out)
    monkeypatch.setattr(longform.hyperframes, "snapshot", lambda project, at, out: [out / "x.png"])
    monkeypatch.setattr(longform.ffmpeg, "text_card", lambda *a: None)
    monkeypatch.setattr(longform.ffmpeg, "duration", lambda p: 10.0)
    monkeypatch.setattr(longform.subtitles, "cues", lambda timing, sp, limit: limits.append(limit) or [])
    job = long_job()
    job.update(draft_ok=True)
    job.put("film.json", {"total": 10.0, "credits": []})
    job.put("timing.json", [{"start": 1.4}])
    job.put("script.json", {"title": "t", "scenes": [{"beat": ""}]})
    sv = services(channel=LONG)
    longform.step_render(job, sv)
    style = LONG.style.model_copy(update={"subtitle_limit": 30})
    longform.step_render(job, services(channel=LONG.model_copy(update={"style": style})))
    assert limits == [2 * sv.splitter.limit, 30]


def test_render_waits_for_draft_approval():
    job = long_job(*STEPS_LONG[:8])
    pipeline.run(job, services(channel=LONG))
    assert job.data["status"] == "waiting" and job.data["steps"]["render"]["status"] == "pending"
    assert "렌더 대기: 초안을 확인하고 승인해 주세요" in "\n".join(job.tail())


class TTS:
    label, hint = "가짜음성", ""

    def __init__(self):
        self.calls = []

    def ready(self):
        return True

    def speak(self, voice, text, out):
        self.calls.append(text)
        out.write_bytes(b"MP3")
        return out, [{"text": "첫", "start": 0.0}, {"text": "낱말", "start": 0.5}] if text == "가 나" else None


def test_voice_reads_each_scene_once_and_rereads_only_changed(monkeypatch):
    monkeypatch.setattr(longform.ffmpeg, "duration", lambda p: 2.0)
    job = long_job()
    job.update(script_ok=True)
    job.put("script.json", {"scenes": [{"narration": "가 나", "beat": ""}, {"narration": "다라 마", "beat": "turn"}]})
    sv = services(channel=LONG, tts=TTS())
    assert longform.step_voice(job, sv) == "가짜음성"
    t = job.doc("timing.json")
    assert [(x["start"], x["end"], x["file"]) for x in t] == [(1.4, 3.4, "voice/s00.mp3"), (4.8, 6.8, "voice/s01.mp3")]
    assert t[0]["words"] == [{"text": "첫", "start": 1.4}, {"text": "낱말", "start": 1.9}]   # 절대 초
    assert t[1]["words"] == [{"text": "다라", "start": 4.8}, {"text": "마", "start": 6.133}]   # 글자 비례 어림

    longform.step_voice(job, sv)   # 다시 시도: 다시 읽지 않는다
    assert sv.tts.calls == ["가 나", "다라 마"]
    job.edit("script.json", lambda s: s | {"scenes": [s["scenes"][0], {"narration": "바뀐 글", "beat": ""}]})
    longform.step_voice(job, sv)
    assert sv.tts.calls == ["가 나", "다라 마", "바뀐 글"]
    assert job.doc("timing.json")[0]["words"][1]["start"] == 1.9   # 캐시한 낱말 시각을 그대로 쓴다


def test_description_keeps_credits_and_drops_urls_first():
    job = long_job()
    job.put("script.json", {"title": "t", "description": "가" * 1640, "tags": [], "sentences": ["a"],
                            "fact_ids": [["F1", "F2"]]})
    job.put("facts.json", {"facts": [{"id": f"F{i}", "url": f"https://a.go.kr/{i}"} for i in (1, 2)]})
    job.put("credits.json", ["내레이션 가짜", "음악 곡"])
    ch = LONG.model_copy(update={"publish": LONG.publish.model_copy(update={"sources_heading": "출처",
                                                                           "footer": "※AI"})})
    out = pipeline.description(job, ch)
    assert out.endswith("출처\nhttps://a.go.kr/1\n\n내레이션 가짜\n음악 곡\n\n※AI") and len(out.encode()) <= 5000


class CaptionPublisher(Publisher):
    def __init__(self, fail=False):
        super().__init__()
        self.captions, self.fail = [], fail

    def set_captions(self, video_id, srt, language):
        if self.fail:
            raise RuntimeError("quota")
        self.captions.append((video_id, srt.name, language))


@pytest.mark.parametrize("fail", [False, True])
def test_publish_sets_captions_and_failure_is_only_a_note(fail):
    job = long_job(*STEPS_LONG)
    job.put("script.json", {"title": "t", "description": "d", "tags": [], "sentences": ["a"]})
    (job.dir / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\na\n")
    sv = services(channel=LONG, publisher=CaptionPublisher(fail))
    pipeline.publish(job, sv)
    up = job.data["upload"]
    assert up["status"] == "done"
    if fail:
        assert sv.publisher.captions == [] and "자막은 못 올렸어요(quota)" in up["note"]
    else:
        assert sv.publisher.captions == [("VID", "captions.srt", "ko")] and up["note"] is None
    pipeline.publish(job, replace(sv, publisher=Publisher()))   # set_captions가 없는 공급자는 건너뛴다
    assert job.data["upload"]["note"] is None


def test_registry_falls_back_to_16x9_flow_for_long_channel(monkeypatch):
    monkeypatch.setattr(registry.VIDEOS["flow-auto-16x9"], "ready", lambda: False)
    monkeypatch.setattr(registry.VIDEOS["flow-auto"], "ready", lambda: False)
    ch = LONG.model_copy(update={"video": LONG.video.model_copy(update={"provider": "flow-auto-16x9"})})
    assert registry.video(ch)[0] == "flow-16x9"
    short = channel.load(CH)
    assert registry.video(short.model_copy(update={"video": short.video.model_copy(
        update={"provider": "flow-auto"})}))[0] == "flow"


def test_draft_builds_film_project_and_stops_on_check_errors(monkeypatch, tmp_path):
    hf = longform.hyperframes
    report = {"ok": True, "lint": {"errorCount": 0, "warningCount": 1, "findings": []}, "saved": {}}
    monkeypatch.setattr(hf, "init", lambda project, title: project.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(hf, "check", lambda project: report)

    def snapshot(project, at, out):
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"at-{t:g}s.png" for t in at]
    monkeypatch.setattr(hf, "snapshot", snapshot)
    monkeypatch.setattr(longform.ffmpeg, "duration", lambda p: 1.5)   # 음성(2초)보다 짧게 올린 클립
    (tmp_path / "m.mp3").write_bytes(b"M")
    monkeypatch.setattr(longform.media, "fetch_music", lambda title, url: tmp_path / "m.mp3")
    monkeypatch.setattr(longform.sound, "track", lambda p, credit: {"file": "m.mp3", "duration": 200.0,
                                                                     "credit": credit, "head": 0, "tail": 0})
    job = long_job()
    job.put("script.json", {"title": "A&B <C>", "thumb": ["가"], "chapters": [{"title": "1장", "first": 0}],
                            "scenes": [{"narration": "서울 새벽", "kind": "map", "beat": ""},
                                       {"narration": "끝", "kind": "clip", "beat": "turn"}]})
    job.put("timing.json", [
        {"text": "서울 새벽", "start": 1.4, "end": 3.4, "file": "voice/s00.mp3", "duration": 2.0,
         "words": [{"text": "서울", "start": 1.4}, {"text": "새벽", "start": 2.4}]},
        {"text": "끝", "start": 4.8, "end": 6.8, "file": "voice/s01.mp3", "duration": 2.0,
         "words": [{"text": "끝", "start": 4.8}]}])
    seoul = {"name": "서울", "lng": 127.0, "lat": 37.5}
    job.put("plan.json", {"world": {"box": [124, 40, 131, 33], "zoom": 7, "detail": [125, 39, 130, 34], "land": [],
                                    "border": [], "border_box": None, "side": "north", "places": {"seoul": seoul},
                                    "states": {"L0": [[124.5, 38], [130.5, 38]]}},
                          "scenes": [{"scene": 0, "camera": {"place": "seoul", "lng": 0, "lat": 0, "scale": 0.5},
                                      "front": "L0", "labels": [{"place": "seoul", "at": "서울"}], "arrows": [],
                                      "date": None, "flashes": [{"place": "seoul", "at": "새벽"}]},
                                     {"scene": 1, "camera": None, "front": "", "labels": [], "arrows": [],
                                      "date": None, "flashes": []}]})
    job.put("tiles.json", {"z": 7, "x0": 108, "y0": 48, "width": 1536, "height": 1280})
    job.put("geo.json", {"crop": [0, 0, 100, 100], "land": "", "border": ""})
    for f in ("voice/s00.mp3", "voice/s01.mp3", "clips/clip1.mp4"):
        (job.dir / f).parent.mkdir(parents=True, exist_ok=True)
        (job.dir / f).write_bytes(b"x")
    job.update(draft_ok=True)
    sv = services(channel=LONG, tts=TTS())

    assert longform.step_draft(job, sv) == "HyperFrames 14초"
    film = job.doc("film.json")
    project = job.dir / "film"
    assert (film["total"], film["end_start"]) == (14.15, 7.55)
    assert film["clips"] == [{"id": "c01", "src": "assets/clips/clip1.mp4", "start": 4.8, "duration": 1.5}]
    assert film["title"] == "A&amp;B &lt;C&gt;"   # film.build는 이스케이프하지 않는다
    assert [v["src"] for v in film["voices"]] == ["assets/voice/s00.mp3", "assets/voice/s01.mp3"]
    assert film["credits"][:2] == ["내레이션 가짜음성", film["map_credit"]] and film["credits"][2] == "음악 " + \
        longform.sound.tables()[1][LONG.long.music][0]["credit"]
    assert all((project / "assets" / s[1]).exists() for s in film["sounds"])   # 음악·효과음을 프로젝트로 복사
    assert (project / "index.html").exists() and (project / "assets/clips/clip1.mp4").exists()
    shots = job.doc("draft.json")["snapshots"]
    assert shots == [{"chapter": 0, "title": "1장", "at": 2.9, "file": "draft/at-2.9s.png"}]
    assert job.data["draft_ok"] is False   # 초안이 바뀌면 다시 승인받는다
    assert film["subtitle"] == "가"   # 끝 화면 부제는 썸네일 첫 줄(장 제목 아님)

    job.edit("timing.json", lambda t: [t[0] | {"duration": 5.0}, t[1]])   # 긴 장면은 가운데(지명 글씨가 뜬 뒤)
    job.edit("script.json", lambda s: s | {"thumb": ["A&B <C>"]})   # 제목과 같은 썸네일 줄은 부제로 안 쓴다
    longform.step_draft(job, sv)
    assert job.doc("draft.json")["snapshots"][0]["at"] == 3.9 and job.doc("film.json")["subtitle"] == ""

    report["lint"] = {"errorCount": 1, "findings": [{"severity": "error", "message": "겹침"}]}
    with pytest.raises(RuntimeError, match="초안 검사 오류: 겹침"):
        longform.step_draft(job, sv)

    bad = LONG.model_copy(update={"long": LONG.long.model_copy(update={"music": "없는분위기"})})
    with pytest.raises(RuntimeError, match="모르는 음악 분위기예요"):
        longform.step_draft(job, services(channel=bad, tts=TTS()))


def test_voice_keeps_scene_state_in_db_not_files(monkeypatch):
    monkeypatch.setattr(longform.ffmpeg, "duration", lambda p: 2.0)
    job = long_job()
    job.update(script_ok=True)
    job.put("script.json", {"scenes": [{"narration": "가 나", "beat": ""}]})
    longform.step_voice(job, services(channel=LONG, tts=TTS()))
    assert job.doc("voice.json")[0]["text"] == "가 나" and not list((job.dir / "voice").glob("*.json"))


def test_clips_refused_stops_with_reason_and_success_clears_it():
    class Video:
        label, hint, refuse = "가짜영상", "", True

        def ready(self):
            return True

        def make(self, todo, out, log):
            if self.refuse:
                raise Refused("거절", {t["i"]: "정책" for t in todo})
            for t in todo:
                (out / t["file"]).write_bytes(b"x")
                yield {"file": t["file"], "source": "가짜영상"}

    job = long_job()
    job.put("script.json", {"scenes": [{"narration": "a", "kind": "map"},
                                       {"narration": "b", "kind": "clip", "clip_prompt": "p"}]})
    job.put("timing.json", [{"duration": 2.0}, {"duration": 3.0}])
    sv = services(channel=LONG, video=Video())
    with pytest.raises(RuntimeError, match="장면 2 클립을 거절했어요"):
        longform.step_clips(job, sv)
    assert job.data["refused"] == [{"i": 1, "reason": "정책"}]
    sv.video.refuse = False
    assert longform.step_clips(job, sv) == "가짜영상 1개" and job.data["refused"] is None


def test_create_follows_channel_format(monkeypatch):
    monkeypatch.setattr(pipeline, "load_channel", lambda cid: LONG)
    assert Job.create(CH, "주제", "v").data["format"] == "long"   # 화면·스케줄·CLI가 long을 안 넘겨도


def test_registry_uses_16x9_twin_of_ready_provider(monkeypatch):
    monkeypatch.setattr(registry.VIDEOS["flow-auto-16x9"], "ready", lambda: True)
    ch = LONG.model_copy(update={"video": LONG.video.model_copy(update={"provider": "flow-auto"})})
    assert registry.video(ch)[0] == "flow-auto-16x9"


def test_final_ignores_quiet_end_card_but_flags_body_silence(monkeypatch):
    job = long_job()
    job.put("film.json", {"total": 20.0, "end_start": 13.4})
    job.put("cues.json", [{"end": 12.6}])
    monkeypatch.setattr(longform.ffmpeg, "duration", lambda p: 20.0)
    monkeypatch.setattr(longform.ffmpeg, "loudness", lambda p: {"lufs": -16, "true_peak": -1.5})
    monkeypatch.setattr(longform.ffmpeg, "silences", lambda p, min_s: [(2.0, 6.0), (12.9, 20.0)])
    assert longform.step_final(job, services(channel=LONG)) == "지적 1개"   # 끝 화면(13.4~) 무음은 0.5초만 남아 빠진다
    assert job.doc("final.json")["silences"] == [[2.0, 6.0]]

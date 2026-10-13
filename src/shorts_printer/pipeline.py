"""다섯 단계를 차례로 돌린다. 끝난 단계는 건너뛰어, 다시 시도하면 실패한 단계부터 이어서 한다."""
import time

from . import footage, render, script, subtitles, thumbnail, voice, youtube
from .jobs import LABELS, STEPS, Job, atomic_write_json, now, read_json, redact, upload_state


def step_script(job: Job) -> str:
    s, usage = script.write(job.data["topic"], job.data.get("brief"))   # 예전 job.json엔 brief가 없다
    atomic_write_json(job.dir / "script.json", s.model_dump())
    job.update(usage=usage)
    job.log(f"제목: {s.title} · 문장 {len(s.sentences)}개 · 검색어 {', '.join(s.search_terms)}")
    return usage["model"]


def step_footage(job: Job) -> str:
    note, src = None, footage.source()
    if src:
        clips = footage.fetch(src, read_json(job.dir / "script.json")["search_terms"], job.dir / "clips", job.log)
        if not clips:
            note = f"{src}에서 맞는 영상을 못 찾아 그라데이션 배경으로 만들어요"
    else:
        clips, note = [], "영상 소스 키(PIXABAY_API_KEY 또는 PEXELS_API_KEY)가 없어 그라데이션 배경으로 만들어요"
    atomic_write_json(job.dir / "clips.json", clips)
    if note:
        job.log(note)
        if note not in job.data["notices"]:
            job.update(notices=job.data["notices"] + [note])
    return f"{src.lower()} {len(clips)}개" if clips else "그라데이션"


def step_voice(job: Job) -> str:
    engine = voice.synth(read_json(job.dir / "script.json")["sentences"], job.data["voice"], job.dir, job.log)
    want = "ElevenLabs" if job.data["voice"] == "elevenlabs" else "edge-tts"
    if engine != want:
        note = f"{want}가 안 돼 {'macOS 기본 목소리(Yuna)' if engine == 'macOS say' else engine}로 읽었어요"
        if note not in job.data["notices"]:
            job.update(notices=job.data["notices"] + [note])
    return engine


def step_subtitles(job: Job) -> str:
    cues = subtitles.cues(read_json(job.dir / "timing.json"))
    subtitles.write_ass(job.dir / "subs.ass", cues)
    atomic_write_json(job.dir / "cues.json", cues)
    return f"ASS {len(cues)}줄"


def step_thumbnail(job: Job) -> str:
    """썸네일 스킬대로 문구·사진을 정해 thumbnail.jpg를 만든다. 렌더가 이걸 영상 첫 0.5초에 넣는다."""
    clips = [c["file"] for c in read_json(job.dir / "clips.json", [])]
    taken = {t["photo"]["id"] for j in Job.all() if j.id != job.id and (t := read_json(j.dir / "thumb.json")) and t["photo"]}
    t = thumbnail.make(job.dir, read_json(job.dir / "script.json"), job.data["topic"], job.log, taken)
    t["background"] = render.thumbnail(job.dir, t["lines"], t["accent"], t["position"], clips[0] if clips else None)
    atomic_write_json(job.dir / "thumb.json", t)
    job.update(thumb_usage=t["usage"])
    if not t["photo"]:
        note = f"썸네일에 맞는 Pixabay 사진을 못 찾아 {t['background']} 배경으로 만들었어요"
        job.log(note)
        if note not in job.data["notices"]:
            job.update(notices=job.data["notices"] + [note])
    return "pixabay 사진" if t["photo"] else t["background"]


def step_render(job: Job) -> str:
    clips = [c["file"] for c in read_json(job.dir / "clips.json", [])]
    voice_sec = read_json(job.dir / "timing.json")[-1]["end"]
    t = read_json(job.dir / "thumb.json")   # 위 띠 제목은 썸네일 훅 문구. 없으면(예전 작업) 대본 제목
    title = (t["lines"], t["accent"]) if t else ([read_json(job.dir / "script.json")["title"]], "")
    job.update(duration=render.render(job.dir, clips, voice_sec, title))
    return "ffmpeg"


RUN = {"script": step_script, "footage": step_footage, "voice": step_voice,
       "subtitles": step_subtitles, "thumbnail": step_thumbnail, "render": step_render}


def run_steps(rec, steps, labels: dict, run: dict, done_msg: str) -> None:
    """steps를 차례로. 끝난 단계는 건너뛰고, 실패하면 status=failed·error를 남기고 다시 던진다. 작업과 주제 찾기가 같이 쓴다."""
    rec.update(status="running", error=None, finished_at=None)
    for name in steps:
        if rec.data["steps"][name]["status"] == "done":
            continue
        rec.step(name, status="running", engine=None, sec=None)
        rec.log(f"{labels[name]} 시작")
        t0 = time.monotonic()
        try:
            engine = run[name](rec)
        except BaseException as e:   # Ctrl+C도 실패로 남겨 다시 시도할 수 있게
            msg = redact(str(e)) or type(e).__name__
            rec.step(name, status="failed", sec=round(time.monotonic() - t0, 1))
            rec.log(f"{labels[name]} 실패: {msg}")
            rec.update(status="failed", error={"step": name, "message": msg}, finished_at=now())
            raise
        sec = round(time.monotonic() - t0, 1)
        rec.step(name, status="done", engine=engine, sec=sec)
        rec.log(f"{labels[name]} 완료 ({sec}s, {engine})")
    rec.update(status="done", finished_at=now())
    rec.log(done_msg)


def run(job: Job) -> None:
    run_steps(job, STEPS, LABELS, RUN, "완성")


def publish(job: Job) -> None:
    """완성 영상을 YouTube에 비공개로 올린다. 실패하면 failed로 남겨 다시 올릴 수 있게 한다."""
    job.update(upload=upload_state("running"))
    job.log("YouTube 업로드 시작")
    try:
        video_id = youtube.upload(job.dir / "final.mp4", read_json(job.dir / "script.json"))
    except BaseException as e:   # Ctrl+C도 실패로 남긴다
        msg = redact(str(e)) or type(e).__name__
        job.update(upload=upload_state("failed", error=msg, at=now()))
        job.log(f"YouTube 업로드 실패: {msg}")
        raise
    job.log(f"YouTube 업로드 완료: https://youtu.be/{video_id} (비공개)")
    note, thumb = None, job.dir / "thumbnail.jpg"
    if thumb.exists():
        # 영상은 이미 올라갔으니 썸네일 실패로 업로드를 failed로 두지 않는다(다시 올리면 중복된다)
        try:
            youtube.set_thumbnail(video_id, thumb)
            job.log("썸네일 설정 완료")
        except Exception as e:
            note = f"썸네일은 못 붙였어요({redact(str(e)) or type(e).__name__}). YouTube 스튜디오에서 thumbnail.jpg를 직접 올리세요."
            job.log(note)
    job.update(upload=upload_state("done", video_id=video_id, at=now(), note=note))

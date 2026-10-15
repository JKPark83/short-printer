"""여섯 단계를 차례로 돌린다. 끝난 단계는 건너뛰어, 다시 시도하면 실패한 단계부터 이어서 한다.
빠진 장면 클립이 있으면 waiting으로 멈춘다."""
import time
from typing import ClassVar

from ..infra.store import Record, now, redact, upload_state
from ..ports.llm import add_usage
from . import render, scenes, script, subtitles, thumbnail, voice
from .services import Services

STEPS = ("script", "voice", "subtitles", "footage", "thumbnail", "render")   # 사람을 기다리는 영상 소스는 뒤로
LABELS = {"script": "대본", "footage": "영상 소스", "voice": "음성", "subtitles": "자막", "thumbnail": "썸네일",
          "render": "렌더"}


class Job(Record):
    EXTRA: ClassVar[dict] = {"upload": None, "duration": None}

    @staticmethod
    def _fix(d: dict) -> dict:
        # 썸네일 단계가 생기기 전 job.json: 렌더까지 끝났으면 옛 방식 썸네일이 있으니 done으로 본다
        d["steps"].setdefault("thumbnail", {"status": "done" if d["steps"]["render"]["status"] == "done" else "pending",
                                            "engine": None, "sec": None})
        return d

    @classmethod
    def create(cls, channel: str, topic: str, voice: str, brief: str | None = None,
               source: dict | None = None) -> "Job":
        """brief: 대본에 넘길 참고 방향, source: 추천 주제에서 만들었으면 {"trend", "pick"}."""
        return cls._new(STEPS, channel=channel, topic=topic, voice=voice, brief=brief, source=source)


class Wait(Exception):
    """사람 손이 필요해 멈춘다(클립 올리기). 실패가 아니다."""


def missing_clips(job: Job) -> list[int]:
    """아직 안 올라온 장면 번호(0부터). 장면 = 대본 문장."""
    n = len(job.doc("script.json")["sentences"])
    return [i for i in range(n) if not (job.dir / "clips" / f"clip{i}.mp4").exists()]


def step_script(job: Job, sv: Services) -> str:
    if note := job.data.get("script_note"):   # 완성 뒤 고치기(/script/revise만 이 단계를 되돌린다)
        s, usage = script.revise(sv.llm, sv.channel, job.doc("script.json"), note)
        job.put("script.json", s)
        job.update(usage=add_usage(job.data["usage"], usage))
        job.log(f"대본 고침: {note}")
        return usage["model"]
    # 최근 제목은 같은 채널 안에서만 피한다
    recent = [t for j in Job.all() if j.id != job.id and j.data.get("channel") == sv.channel.id
              and (t := (j.doc("script.json") or {}).get("title"))][-15:]
    # 예전 job.json엔 brief가 없다
    s, usage = script.write(sv.llm, sv.channel, job.data["topic"], job.data.get("brief"), recent)
    job.put("script.json", s.flat())
    job.update(usage=usage)
    job.log(f"제목: {s.title} · 장면 {len(s.scenes)}개")
    if s.sensitive and sv.channel.sensitive_gate:
        job.log(f"민감 분야({s.sensitive}): 대본을 확인한 뒤 [확인하고 계속]을 눌러야 장면을 만들어요")
    return usage["model"]


def step_footage(job: Job, sv: Services) -> str:
    """장면마다 클립 하나. 공급자가 만들 수 있는 건 만들고, 빠진 장면은 사람이 올릴 때까지 waiting.
    채널이 sensitive_gate를 켰으면 민감 분야 대본은 사람이 확인(confirmed)하기 전엔 크레딧을 쓰지 않고 멈춘다."""
    area = job.doc("script.json").get("sensitive")
    if sv.channel.sensitive_gate and area and not job.data.get("confirmed"):
        raise Wait(f"민감 분야({area}) 대본 확인")
    p = sv.video
    d = job.dir / "clips"
    d.mkdir(exist_ok=True)
    todo = scenes.scenes(job.doc("script.json"), job.doc("timing.json"))
    for c in p.make([s for s in todo if not (d / s["file"]).exists()], d, job.log):
        scenes.set_clip(job, c)   # 하나씩 기록: 중간에 실패해도 만든 장면은 남는다
    if miss := missing_clips(job):
        raise Wait(f"장면 클립 {len(todo) - len(miss)}/{len(todo)}개")
    got = {c["file"]: c for c in job.doc("clips.json", [])}
    # 장면 순서로 다시 쓴다. 기록 없이 파일만 있는 장면(손으로 넣은 파일)은 직접 올림으로
    job.put("clips.json", [got.get(s["file"], {"file": s["file"], "source": "직접 올림"}) for s in todo])
    return f"{p.label} {len(todo)}개"


def step_voice(job: Job, sv: Services) -> str:
    engine, timing = voice.synth(sv.tts, sv.channel, job.doc("script.json")["sentences"], job.data["voice"],
                                 job.dir, job.log)
    job.put("timing.json", timing)
    return engine


def step_subtitles(job: Job, sv: Services) -> str:
    cues = subtitles.cues(job.doc("timing.json"), sv.splitter,
                          sv.channel.style.subtitle_limit or sv.splitter.limit)
    job.put("cues.json", cues)   # subs.ass는 렌더가 쓴다(상세 화면에서 고친 자막도 들어가게)
    return f"ASS {len(cues)}줄"


def step_thumbnail(job: Job, sv: Services) -> str:
    """채널 thumbnail.md대로 문구를 정해 thumbnail.jpg를 만든다. 배경은 첫 장면 클립.
    문구는 렌더가 위 띠 제목으로도 쓴다.
    상세 화면에서 문구를 손으로 고쳤으면(thumb_hand) LLM 없이 그 문구로 만든다."""
    clips = [c["file"] for c in job.doc("clips.json", [])]
    old = job.doc("thumb.json") or {}
    if hand := job.data.get("thumb_hand"):
        t = old | hand | {"position": old.get("position", "top"), "usage": old.get("usage"), "note": "",
                          "texts": old.get("texts", []) + [" / ".join(hand["lines"])]}
        job.log(f"썸네일 문구(직접 고침): {' / '.join(hand['lines'])}")
    else:
        t = thumbnail.make(sv.llm, sv.channel, old.get("texts", []), job.doc("script.json"), job.data["topic"],
                           job.log, job.data.get("thumb_note") or "")
    t["background"] = render.thumbnail(job.dir, t["lines"], t["accent"], t["position"], sv.channel, sv.splitter,
                                       clips[0] if clips else None)
    job.put("thumb.json", t)
    job.update(thumb_usage=t["usage"], thumb_hand=None)
    return t["background"]


def step_render(job: Job, sv: Services) -> str:
    clips = [c["file"] for c in job.doc("clips.json", [])]
    timing = job.doc("timing.json")
    t = job.doc("thumb.json")   # 위 띠 제목은 썸네일 훅 문구. 없으면(예전 작업) 대본 제목
    title = (t["lines"], t["accent"]) if t else ([job.doc("script.json")["title"]], "")
    if cues := job.doc("cues.json"):   # 없으면(아주 예전 작업) 있던 subs.ass 그대로
        subtitles.write_ass(job.dir / "subs.ass", cues, sv.channel.font, render.LAYOUTS[sv.channel.style.layout].sub)
    job.update(duration=render.render(job.dir, clips, timing[-1]["end"], sv.channel, sv.splitter, title,
                                      [t["start"] for t in timing]))
    return "ffmpeg"


RUN = {"script": step_script, "footage": step_footage, "voice": step_voice,
       "subtitles": step_subtitles, "thumbnail": step_thumbnail, "render": step_render}


def run_steps(rec, steps, labels: dict, run: dict, done_msg: str) -> None:
    """steps를 차례로. 끝난 단계는 건너뛰고, 실패하면 status=failed·error를 남기고 다시 던진다.
    작업과 주제 찾기가 같이 쓴다."""
    rec.update(status="running", error=None, finished_at=None)
    for name in steps:
        if rec.data["steps"][name]["status"] == "done":
            continue
        rec.step(name, status="running", engine=None, sec=None)
        rec.log(f"{labels[name]} 시작")
        t0 = time.monotonic()
        try:
            engine = run[name](rec)
        except Wait as w:   # 클립 대기: 실패가 아니라 멈춤. 클립이 다 오면 다시 큐에 넣는다
            rec.step(name, status="pending")
            rec.log(f"{labels[name]} 대기: {w}")
            rec.update(status="waiting")
            return
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


def run(job: Job, sv: Services) -> None:
    run_steps(job, STEPS, LABELS, {k: lambda rec, f=f: f(rec, sv) for k, f in RUN.items()}, "완성")


def publish(job: Job, sv: Services) -> None:
    """완성 영상을 채널 업로드 공급자로 비공개로 올린다. 실패하면 failed로 남겨 다시 올릴 수 있게 한다.
    대체 경로(스튜디오 화면 등)는 공급자 안에서 고른다."""
    p = sv.publisher
    job.update(upload=upload_state("running"))
    job.log(f"{p.label} 업로드 시작")
    s = job.doc("script.json")
    meta = {k: s[k] for k in ("title", "description", "tags")}
    if foot := sv.channel.publish.footer:   # 스튜디오 대체 업로드도 같은 meta를 쓴다
        meta["description"] = f"{meta['description'].rstrip()}\n\n{foot}"
    try:
        video_id = p.upload(job.dir / "final.mp4", meta, job.log)
    except BaseException as e:   # Ctrl+C도 실패로 남긴다
        msg = redact(str(e)) or type(e).__name__
        job.update(upload=upload_state("failed", error=msg, at=now()))
        job.log(f"{p.label} 업로드 실패: {msg}")
        raise
    job.log(f"{p.label} 업로드 완료: {video_id} (비공개)")
    note, thumb = None, job.dir / "thumbnail.jpg"
    if thumb.exists():
        # 영상은 이미 올라갔으니 썸네일 실패로 업로드를 failed로 두지 않는다(다시 올리면 중복된다)
        try:
            p.set_thumbnail(video_id, thumb)
            job.log("썸네일 설정 완료")
        except Exception as e:
            note = (f"썸네일은 못 붙였어요({redact(str(e)) or type(e).__name__}). "
                    f"{p.label}에서 thumbnail.jpg를 직접 올리세요.")
            job.log(note)
    job.update(upload=upload_state("done", video_id=video_id, at=now(), note=note))

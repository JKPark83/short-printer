"""여덟 단계를 차례로 돌린다. 끝난 단계는 건너뛰어, 다시 시도하면 실패한 단계부터 이어서 한다.
화면에서 만든 작업은 대본·음성·자막 뒤 확정 전까지, 빠진 장면 클립이 있으면 영상 소스에서 waiting으로 멈춘다."""
import time
from typing import ClassVar

from ..infra.store import Record, now, redact, upload_state
from ..ports.llm import add_usage
from . import render, research, scenes, script, subtitles, thumbnail, voice
from .channel import Channel
from .services import Services

# 사람을 기다리는 영상 소스는 뒤로
STEPS = ("research", "script", "proofread", "voice", "subtitles", "footage", "thumbnail", "render")
LABELS = {"research": "자료 조사", "script": "대본", "proofread": "대본 검수", "footage": "영상 소스",
          "voice": "음성", "subtitles": "자막", "thumbnail": "썸네일", "render": "렌더"}


class Job(Record):
    EXTRA: ClassVar[dict] = {"upload": None, "duration": None}

    @staticmethod
    def _fix(d: dict) -> dict:
        # 썸네일 단계가 생기기 전 job.json: 렌더까지 끝났으면 옛 방식 썸네일이 있으니 done으로 본다
        d["steps"].setdefault("thumbnail", {"status": "done" if d["steps"]["render"]["status"] == "done" else "pending",
                                            "engine": None, "sec": None})
        # 자료 조사 단계가 생기기 전 작업: 대본이 이미 있으면 조사 없이 그대로 연다
        d["steps"].setdefault("research", {"status": "done" if d["steps"]["script"]["status"] == "done" else "pending",
                                           "engine": None, "sec": None})
        # 원어민 검수 단계가 생기기 전 작업: 대본이 있으면 검수 없이 그대로 쓴다
        d["steps"].setdefault("proofread", {"status": "done" if d["steps"]["script"]["status"] == "done" else "pending",
                                            "engine": None, "sec": None})
        return d

    @classmethod
    def create(cls, channel: str, topic: str, voice: str, brief: str | None = None,
               source: dict | None = None, review: bool = False) -> "Job":
        """brief: 대본에 넘길 참고 방향, source: 추천 주제에서 만들었으면 {"trend", "pick"}.
        review: 사람이 대본·음성·자막을 확정(confirmed)해야 영상 소스부터 만든다
        (화면에서 만든 작업. 스케줄·CLI는 끝까지 돈다)."""
        return cls._new(STEPS, channel=channel, topic=topic, voice=voice, brief=brief, source=source, review=review)


class Wait(Exception):
    """사람 손이 필요해 멈춘다(클립 올리기). 실패가 아니다."""


class Canceled(Exception):
    """운영자가 취소했다(cancel). 단계 사이·장면 클립 사이에서만 멈춰 이미 넣은 영상 크레딧을 버리지 않는다."""


def in_review(data: dict) -> bool:
    """대본·음성·자막을 사람이 확정하기를 기다리는 중."""
    return data["status"] == "waiting" and bool(data.get("review")) and not data.get("confirmed")


def in_voice_review(data: dict) -> bool:
    """대본 확정 뒤 채널 TTS로 다시 읽은 음성을 사람이 확정하기를 기다리는 중.
    voice_ok는 초안 음성을 확정할 때만 False로 생긴다(예전 작업·처음부터 채널 TTS로 읽은 작업은 없다)."""
    return data["status"] == "waiting" and data.get("voice_ok") is False


def missing_clips(job: Job) -> list[int]:
    """아직 안 올라온 장면 번호(0부터). 장면 = 대본 문장."""
    n = len(job.doc("script.json")["sentences"])
    return [i for i in range(n) if not (job.dir / "clips" / f"clip{i}.mp4").exists()]


def step_research(job: Job, sv: Services) -> str:
    facts, usage = research.gather(sv.research, sv.channel, job.data["topic"], job.data.get("brief"))
    job.put("facts.json", facts)
    job.update(research_usage=usage)
    for n in facts["notes"]:
        job.log(f"조사 메모: {n[:200]}")
    if not facts["facts"]:
        raise RuntimeError("출처가 붙은 사실을 하나도 찾지 못했어요. "
                           "로그의 조사 메모를 보고 허용 사이트를 더하거나 주제를 바꿔 주세요.")
    job.log(f"사실 {len(facts['facts'])}개")
    return usage["model"]


def _unverified(notes: list[str]) -> list[str]:
    """조사 메모에서 "확인 못 함: <주장>" 줄의 주장만. 한 메모에 여러 줄이 붙어 오기도 해서 줄마다 본다."""
    return list(dict.fromkeys(c for n in notes for x in n.splitlines()
                              if x.strip().startswith("확인 못 함:") and (c := x.split(":", 1)[1].strip())))


def step_script(job: Job, sv: Services) -> str:
    research_doc = job.doc("facts.json") or {}   # 예전 작업엔 없다
    facts = research_doc.get("facts", [])
    if note := job.data.get("script_note"):   # 완성 뒤 고치기(/script/revise만 이 단계를 되돌린다)
        draft = job.data.get("review") and not job.data.get("confirmed")   # 확정 전: 장면 프롬프트도 고친다
        s, usage = script.revise(sv.llm, sv.channel, job.doc("script.json"), note, draft=bool(draft),
                                  facts=facts)
        job.put("script.json", s)
        job.update(usage=add_usage(job.data["usage"], usage))
        job.log(f"대본 고침: {note}")
        translate(job, sv)
        return usage["model"]
    s, usage = script.write(sv.llm, sv.channel, job.data["topic"], job.data.get("brief"), _recent(job, sv), facts=facts,
                            unverified=_unverified(research_doc.get("notes", [])))
    job.put("script.json", s.flat())
    job.update(usage=add_usage(job.data.get("usage"), usage))
    job.log(f"제목: {s.title} · 장면 {len(s.scenes)}개")
    if s.sensitive and sv.channel.sensitive_gate:
        job.log(f"민감 분야({s.sensitive}): 대본을 확인한 뒤 [확인하고 계속]을 눌러야 장면을 만들어요")
    translate(job, sv)
    return usage["model"]


def _recent(job: Job, sv: Services) -> list[str]:
    """최근 제목은 같은 채널 안에서만 피한다."""
    return [t for j in Job.all() if j.id != job.id and j.data.get("channel") == sv.channel.id
            and (t := (j.doc("script.json") or {}).get("title"))][-15:]


def step_proofread(job: Job, sv: Services) -> str:
    """대본을 원어민 편집자 눈으로 검수만 한다. 지적마다 분야·무게로 깎아 100점 만점 70점(script.PASS) 이상이고
    흐름이 바닥(script.FLOOR) 위면 통과.
    고치지는 않는다: 모델이 고치면 새 문장에서 새 흠이 생기고 앞뒤가 다시 어긋난다.
    떨어지면 지적을 남기고 사람 확인으로 멈춘다(운영자가 읽고 고치거나 그대로 확정한다)."""
    facts = (job.doc("facts.json") or {}).get("facts", [])
    s = job.doc("script.json")
    verdict, usage = script.proofread(sv.llm, sv.channel, s, sv.splitter,
                                      sv.channel.style.subtitle_limit or sv.splitter.limit, facts=facts,
                                      topic=job.data["topic"])
    job.update(usage=add_usage(job.data["usage"], usage))
    feedback = verdict.lines(s["sentences"])
    # 화면이 분야별 점수를 보여 준다(rounds는 검수가 한 번뿐이어도 옛 작업과 같은 꼴로 둔다)
    job.put("proofread.json", {"pass": script.PASS, "max": script.SCORES, "rounds": [
        {"total": verdict.total, "scores": verdict.scores(), "passed": verdict.passed,
         "issues": [{"kind": i.kind, "severity": i.severity, "text": x}
                    for i, x in zip(verdict.issues, feedback, strict=True)]}]})
    if verdict.passed:
        job.log(f"통과 {verdict.summary()}" +
                (f", 남은 지적 {len(feedback)}개:\n" + "\n".join(feedback) if feedback else ""))
    elif job.data.get("script_note"):   # 완성 뒤 고치기: 클립이 이미 있어 확정을 기다리게 하지 않는다
        job.log(f"불통과 {verdict.summary()}, 지적 {len(feedback)}개:\n" + "\n".join(feedback))
    else:
        job.update(review=True)   # 확정 전엔 장면 영상을 만들지 않는다(스케줄 작업도 여기서 멈춘다)
        job.log(f"불통과 {verdict.summary()}, 지적 {len(feedback)}개:\n" + "\n".join(feedback) +
                "\n검수는 고치지 않아요. 위 지적을 보고 대본을 고치거나 그대로 확정해 주세요")
    translate(job, sv)
    return usage["model"]


def translate(job: Job, sv: Services) -> None:
    """한국어가 아닌 채널: 운영자가 확인하도록 대본·썸네일 문구·자막에 한국어 뜻을 붙인다(ko.json).
    원문이 그대로면 다시 부르지 않는다. 확인용이라 실패해도 작업은 이어 간다(상세 화면에서 다시 옮긴다)."""
    if sv.channel.language == "ko":
        return
    s, thumb, ko = job.doc("script.json"), job.doc("thumb.json"), job.doc("ko.json")
    cues = [c["text"] for c in job.doc("cues.json") or []]
    if ko and ko["src"] == script.ko_source(s, thumb) and ko["cues"] == cues:
        return
    try:
        ko, usage = script.translate(sv.llm, sv.channel, s, thumb, cues)
    except Exception as e:
        job.log(f"한국어 뜻 실패: {redact(str(e)) or type(e).__name__}")
        return
    job.put("ko.json", ko)
    job.update(ko_usage=add_usage(job.data.get("ko_usage"), usage))


def step_footage(job: Job, sv: Services) -> str:
    """장면마다 클립 하나. 공급자가 만들 수 있는 건 만들고, 빠진 장면은 사람이 올릴 때까지 waiting.
    채널이 sensitive_gate를 켰으면 민감 분야 대본은 사람이 확인(confirmed)하기 전엔 크레딧을 쓰지 않고 멈춘다."""
    if job.data.get("review") and not job.data.get("confirmed"):   # 영상 크레딧이 가장 비싸 먼저 확정받는다
        raise Wait("대본 확정")
    if job.data.get("voice_ok") is False:   # 실제 음성을 들어 보고 확정해야 영상 크레딧을 쓴다
        raise Wait("음성 확정")
    area = job.doc("script.json").get("sensitive")
    if sv.channel.sensitive_gate and area and not job.data.get("confirmed"):
        raise Wait(f"민감 분야({area}) 대본 확인")
    p = sv.video
    d = job.dir / "clips"
    d.mkdir(exist_ok=True)
    todo = scenes.scenes(job.doc("script.json"), job.doc("timing.json"))
    for c in p.make([s for s in todo if not (d / s["file"]).exists()], d, job.log):
        scenes.set_clip(job, c)   # 하나씩 기록: 중간에 실패해도 만든 장면은 남는다
        if job.data.get("cancel"):   # 받은 장면까지 남기고 다음 장면은 넣지 않는다
            raise Canceled
    if miss := missing_clips(job):
        raise Wait(f"장면 클립 {len(todo) - len(miss)}/{len(todo)}개")
    got = {c["file"]: c for c in job.doc("clips.json", [])}
    # 장면 순서로 다시 쓴다. 기록 없이 파일만 있는 장면(손으로 넣은 파일)은 직접 올림으로
    job.put("clips.json", [got.get(s["file"], {"file": s["file"], "source": "직접 올림"}) for s in todo])
    return f"{p.label} {len(todo)}개"


def step_voice(job: Job, sv: Services) -> str:
    sentences = job.doc("script.json")["sentences"]
    engine, timing = voice.synth(sv.tts, sv.channel, sentences, job.data["voice"], job.dir, job.log)
    job.update(voice_draft=False)   # 예전 초안 음성 작업도 채널 TTS로 다시 읽으면 초안 표시를 지운다
    job.put("timing.json", timing)
    return engine


def step_subtitles(job: Job, sv: Services) -> str:
    cues = subtitles.cues(job.doc("timing.json"), sv.splitter,   # 손으로 고친 줄(cue_hand)은 그대로 쓴다
                          sv.channel.style.subtitle_limit or sv.splitter.limit, job.data.get("cue_hand"))
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
    # 따옴표 낱말(표시 라벨)은 "no voices"를 적어도 영상 모델이 읽어 버려서, 그 장면은 클립 소리를 통째로 뺀다
    mute = {i for i, p in enumerate(job.doc("script.json").get("prompts", [])) if '"' in p}
    job.update(duration=render.render(job.dir, clips, timing[-1]["end"], sv.channel, sv.splitter, title,
                                      [t["start"] for t in timing], mute))
    translate(job, sv)   # 자막·썸네일 문구는 대본 뒤에 생기고, 무엇을 고쳐도 렌더는 다시 돈다
    return "ffmpeg"


RUN = {"research": step_research, "script": step_script, "proofread": step_proofread, "footage": step_footage,
       "voice": step_voice,
       "subtitles": step_subtitles, "thumbnail": step_thumbnail, "render": step_render}


def run_steps(rec, steps, labels: dict, run: dict, done_msg: str) -> None:
    """steps를 차례로. 끝난 단계는 건너뛰고, 실패하면 status=failed·error를 남기고 다시 던진다.
    작업과 주제 찾기가 같이 쓴다."""
    rec.update(status="running", error=None, finished_at=None)
    for name in steps:
        if rec.data["steps"][name]["status"] == "done":
            continue
        t0 = time.monotonic()
        try:
            if rec.data.get("cancel"):
                raise Canceled
            rec.step(name, status="running", engine=None, sec=None)
            rec.log(f"{labels[name]} 시작")
            engine = run[name](rec)
        except Canceled:   # 실패가 아니라 중단. [다시 시도]하면 이 단계부터 이어서
            rec.step(name, status="pending")
            rec.log(f"취소: {labels[name]} 전에 멈췄어요")
            rec.update(status="interrupted")
            return
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


MAX_DESC = 5000   # YouTube 설명란 한도(UTF-8 바이트)


def description(job: Job, ch: Channel) -> str:
    """올릴 설명란: LLM 설명 / 출처 머리말 + 대본이 쓴 사실의 URL(등장 순) / footer. 업로드와 검수 화면이 같이 쓴다.
    넘치면 URL을 뒤에서부터 뺀다. 어댑터가 뒤를 자르면 footer(AI 표시)가 잘리기 때문이다."""
    s = job.doc("script.json")
    urls = {f["id"]: f["url"] for f in (job.doc("facts.json") or {}).get("facts", [])}
    used = list(dict.fromkeys(urls[i] for ids in s.get("fact_ids") or [] for i in ids if i in urls))
    head, foot = ch.publish.sources_heading, ch.publish.footer

    def join(xs: list[str]) -> str:
        src = "\n".join([head, *xs]) if head and xs else ""
        return "\n\n".join(x for x in (s["description"].rstrip(), src, foot) if x)

    out = join(used)
    while len(out.encode()) > MAX_DESC and used:
        used.pop()
        out = join(used)
    return out   # 그래도 넘으면 어댑터가 자른다


def publish(job: Job, sv: Services) -> None:
    """완성 영상을 채널 업로드 공급자로 비공개로 올린다. 실패하면 failed로 남겨 다시 올릴 수 있게 한다.
    대체 경로(스튜디오 화면 등)는 공급자 안에서 고른다."""
    p = sv.publisher
    job.update(upload=upload_state("running"))
    job.log(f"{p.label} 업로드 시작")
    s = job.doc("script.json")
    meta = {k: s[k] for k in ("title", "description", "tags")} | {"description": description(job, sv.channel)}
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

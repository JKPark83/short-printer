"""롱폼(16:9 지도 역사 영상) 열 단계(docs/plan/longform.md). 쇼츠와 같은 run_steps로 돌고, 끝난 단계는 건너뛴다.
사람 승인 두 번: 대본(script_ok) 전엔 음성을 읽지 않고, 초안(draft_ok) 전엔 렌더하지 않는다."""
import html
import shutil
from pathlib import Path

from ..infra import ffmpeg, hyperframes, maptiles, media
from ..ports.llm import add_usage
from ..ports.video import Refused
from . import film, longscript, mapplan, scenes, script, sound, subtitles, voice
from .pipeline import Canceled, Job, Wait, _recent, _unverified, run_steps, step_research
from .services import Services

STEPS_LONG = ("research", "script", "proofread", "voice", "plan", "map", "clips", "draft", "render", "final")
LABELS_LONG = {"research": "자료 조사", "script": "대본", "proofread": "대본 검수", "voice": "음성",
               "plan": "지도 계획", "map": "지도 이미지", "clips": "장면 클립", "draft": "초안", "render": "렌더",
               "final": "최종 검수"}
S0, GAP, TURN_GAP = 1.4, 0.8, 1.4   # 첫 장면 전, 장면 사이, turn 장면 앞 쉼(초)
END_PAD, END_CARD = 0.75, 6.6   # 마지막 장면 끝 → 끝 화면, 끝 화면 길이(초)
CLIP_MAX = 8   # Flow 클립 길이(초)
INK, BG = "#F3EFE7", "#2b2a27"
LOCALES = {"ko": "ko-KR", "ja": "ja-JP", "en": "en-US"}
FONT = "assets/fonts/Pretendard-ExtraBold.woff2"   # hyperframes.init이 프로젝트에 넣는다
LUFS, LUFS_TOL, PEAK, LEN_TOL, QUIET = -16, 1, -1, 1.5, 3
# ponytail: 롱폼 자막(16:9 화면 아래 한 줄)은 쇼츠 자막 덩어리의 두 배. 언어마다 맞는 값은 쓰다가 정한다
CAP_SCALE = 2


def gate(data: dict) -> str | None:
    """롱폼 작업이 사람을 기다리는 까닭: script(대본 승인)·clips(장면 클립)·draft(초안 승인). 아니면 None."""
    if data.get("format") != "long" or data["status"] != "waiting":
        return None
    st = {k: v["status"] for k, v in data["steps"].items()}
    if st["voice"] != "done" and not data.get("script_ok"):
        return "script"
    if st["draft"] == "done" and not data.get("draft_ok"):
        return "draft"
    return "clips" if st["clips"] != "done" else None


def missing_clips(job: Job) -> list[int]:
    """clip 장면 중 아직 클립 파일이 없는 장면 번호(0부터). 쇼츠의 pipeline.missing_clips는 모든 문장을 센다."""
    s = job.doc("script.json")
    return [i for i, sc in enumerate(s["scenes"])
            if sc["kind"] == "clip" and not (job.dir / "clips" / f"clip{i}.mp4").exists()]


def clock(durs: list[float], beats: list[str]) -> tuple[list[float], float, float]:
    """장면 음성 길이 → (장면 시작들, 끝 화면 시작, 영상 끝)."""
    starts, t = [], S0
    for i, (d, b) in enumerate(zip(durs, beats, strict=True)):
        if i:
            t += TURN_GAP if b == "turn" else GAP
        starts.append(round(t, 3))
        t += d
    end_start = round(t + END_PAD, 3)
    return starts, end_start, round(end_start + END_CARD, 3)


def _beats(s: dict) -> list[str]:
    return [sc.get("beat") or "" for sc in s["scenes"]]


def _even(text: str, start: float, dur: float) -> list[dict]:
    """낱말 시각이 없는 TTS: 글자 수에 비례해 나눈다."""
    out, t, n = [], start, max(1, len("".join(text.split())))
    for w in text.split():
        out.append({"text": w, "start": round(t, 3)})
        t += dur * len(w) / n
    return out


def _copy(src: Path, dst: Path) -> None:
    """src가 더 새로우면 dst로 복사한다(tmp에 쓰고 바꾼다)."""
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copyfile(src, tmp)
    tmp.replace(dst)


def step_script(job: Job, sv: Services) -> str:
    research_doc = job.doc("facts.json") or {}
    facts, llm = research_doc.get("facts", []), sv.script_llm or sv.llm
    if note := job.data.get("script_note"):
        s, usage = longscript.revise(llm, sv.channel, job.doc("script.json"), note, facts)
        job.log(f"대본 고침: {note}")
    else:
        s, usage = longscript.write(llm, sv.channel, job.data["topic"], job.data.get("brief"), _recent(job, sv),
                                    facts, _unverified(research_doc.get("notes", [])))
    for n in s["notes"]:
        job.log(f"대본 메모: {n}")
    job.put("script.json", s)
    # 대본이 바뀌면 지난 승인은 무효
    job.update(usage=add_usage(job.data.get("usage"), usage), script_note=None, script_ok=False)
    job.log(f"제목: {s['title']} · 장 {len(s['chapters'])}개 · 장면 {len(s['scenes'])}개")
    return usage["model"] if usage else llm.label


def step_proofread(job: Job, sv: Services) -> str:
    """검수만 한다. 떨어져도 멈추지 않는다: 어차피 사람이 대본을 승인해야 음성으로 간다."""
    s = job.doc("script.json")
    verdict, usage = longscript.proofread(sv.script_llm or sv.llm, sv.channel, s,
                                          (job.doc("facts.json") or {}).get("facts", []), job.data["topic"])
    job.update(usage=add_usage(job.data.get("usage"), usage))
    feedback = verdict.lines(s["sentences"])
    job.put("proofread.json", {"pass": script.PASS, "max": script.SCORES, "rounds": [
        {"total": verdict.total, "scores": verdict.scores(), "passed": verdict.passed,
         "issues": [{"kind": i.kind, "severity": i.severity, "text": x}
                    for i, x in zip(verdict.issues, feedback, strict=True)]}]})
    job.log(f"{'통과' if verdict.passed else '불통과'} {verdict.summary()}, 지적 {len(feedback)}개"
            + ("\n" + "\n".join(feedback) if feedback else ""))
    return usage["model"] if usage else "검수"


def step_voice(job: Job, sv: Services) -> str:
    """장면마다 mp3 하나. 글·목소리가 그대로인 장면은 다시 읽지 않는다(다시 시도해도 두 번 과금하지 않게)."""
    if not job.data.get("script_ok"):
        raise Wait("대본을 확인하고 승인해 주세요")
    ch, key = sv.channel, job.data["voice"]
    if key not in ch.tts.voices:
        raise RuntimeError(f"더는 쓰지 않는 목소리({key})예요. 작업 화면에서 다른 목소리를 골라 주세요")
    voice._check(sv.tts)
    s = job.doc("script.json")
    out = job.dir / "voice"
    out.mkdir(parents=True, exist_ok=True)
    texts, durs, metas = [sc["narration"] for sc in s["scenes"]], [], []
    old = job.doc("voice.json") or []   # 장면마다 {text, voice, words}
    for i, text in enumerate(texts):
        mp3, m = out / f"s{i:02d}.mp3", old[i] if i < len(old) else {}
        if not (mp3.exists() and m.get("text") == text and m.get("voice") == key):
            src, ws = sv.tts.speak(key, text, mp3)
            if src != mp3:   # mp3가 아닌 공급자
                ffmpeg.run(["-i", src, "-c:a", "libmp3lame", "-q:a", 2, mp3])
            m = {"text": text, "voice": key, "words": ws}
            job.put("voice.json", [*metas, m, *old[i + 1:]])   # 바로 남겨 중간에 멈춰도 다시 읽지 않는다
            job.log(f"음성 {i + 1}/{len(texts)}")
        durs.append(round(ffmpeg.duration(mp3), 3))
        metas.append(m)
    job.put("voice.json", metas)
    words = [m["words"] for m in metas]
    starts, end_start, total = clock(durs, _beats(s))
    job.put("timing.json", [
        {"text": t, "start": a, "end": round(a + d, 3), "file": f"voice/s{i:02d}.mp3", "duration": d,
         "words": [{"text": x["text"], "start": round(a + x["start"], 3)} for x in ws] if ws else _even(t, a, d)}
        for i, (t, a, d, ws) in enumerate(zip(texts, starts, durs, words, strict=True))])
    job.log(f"음성 {sum(durs):.0f}초 · 영상 {total:.0f}초 예상")
    return sv.tts.label


def step_plan(job: Job, sv: Services) -> str:
    facts = (job.doc("facts.json") or {}).get("facts", [])
    s = job.doc("script.json")
    plan, usage = mapplan.plan(sv.llm, sv.channel, s, job.doc("timing.json"), facts,
                               note=job.data.get("draft_note") or "", old=job.doc("plan.json"))
    plan["photos"], u = mapplan.photos(sv.llm, sv.channel, s)
    usage = add_usage(usage, u)
    job.put("plan.json", plan)
    job.update(usage=add_usage(job.data.get("usage"), usage), draft_note=None)
    return usage["model"] if usage else sv.llm.label


def step_map(job: Job, sv: Services) -> str:
    """지도 타일을 받아 wide.jpg·detail.jpg와 잘라 쓸 땅·국경 path를 만든다. 지도 값이 그대로면 다시 받지 않는다."""
    w = job.doc("plan.json")["world"]
    key = {k: w[k] for k in ("box", "zoom", "detail", "land", "border", "border_box")}
    build, out = job.dir / "film" / "build", job.dir / "film" / "assets" / "map"
    files = [build / "esri_raw.jpg", out / "wide.jpg", out / "detail.jpg"]
    if job.data.get("map_key") == key and job.doc("tiles.json") and all(f.exists() for f in files):
        return "그대로"
    tiles = maptiles.fetch(w["box"], w["zoom"], build, job.log)
    crop = maptiles.images(files[0], tiles, w["detail"] or w["box"], out)["crop"]
    job.put("tiles.json", tiles)
    job.put("geo.json", {"crop": crop} | maptiles.geo(w["land"], w["border"], tiles, w["border_box"]))
    job.update(map_key=key)
    return f"Esri z{w['zoom']}"


def step_clips(job: Job, sv: Services) -> str:
    """clip 장면만 영상 공급자로. 빠진 클립은 사람이 올릴 때까지 waiting(pipeline.step_footage와 같은 규칙)."""
    s, timing = job.doc("script.json"), job.doc("timing.json")
    todo = [{"i": i, "file": f"clip{i}.mp4", "sentence": sc["narration"], "prompt": sc["clip_prompt"],
             "sec": min(CLIP_MAX, t["duration"])}
            for i, (sc, t) in enumerate(zip(s["scenes"], timing, strict=True)) if sc["kind"] == "clip"]
    if not todo:
        return "없음"
    # ponytail: 거절된 장면 프롬프트를 고치는 reprompt는 쇼츠만. 롱폼은 그 장면을 지도로 바꾸거나 클립을 직접 넣는다
    d = job.dir / "clips"
    d.mkdir(parents=True, exist_ok=True)
    try:
        for c in sv.video.make([x for x in todo if not (d / x["file"]).exists()], d, job.log):
            scenes.set_clip(job, c)
            if job.data.get("cancel"):
                raise Canceled
    except Refused as e:   # 같은 프롬프트는 또 거절된다: 사람이 고치거나 직접 넣어야 한다
        job.update(refused=[{"i": i, "reason": r} for i, r in sorted(e.scenes.items())])
        raise RuntimeError(f"영상 공급자가 장면 {', '.join(str(i + 1) for i in sorted(e.scenes))} 클립을 거절했어요. "
                           "장면 클립 칸에서 [지도로 바꾸기]를 누르거나 클립을 직접 올려 주세요") from e
    if miss := [x for x in todo if not (d / x["file"]).exists()]:
        raise Wait(f"장면 클립 {len(miss)}개를 기다려요")
    job.update(refused=None)
    return f"{sv.video.label} {len(todo)}개"


def step_draft(job: Job, sv: Services) -> str:
    """film.json → HyperFrames 프로젝트(film/) → check → 장마다 스냅샷 한 장. 사람이 보고 draft_ok를 준다."""
    ch, s, timing, plan = sv.channel, job.doc("script.json"), job.doc("timing.json"), job.doc("plan.json")
    project, beats = job.dir / "film", _beats(s)
    S = [t["start"] for t in timing]
    _, end_start, total = clock([t["duration"] for t in timing], beats)
    hyperframes.init(project, s["title"])
    for t in timing:
        _copy(job.dir / t["file"], project / "assets" / t["file"])
    voices = [{"id": f"vo-{i + 1:02d}", "src": f"assets/{t['file']}", "start": t["start"], "duration": t["duration"]}
              for i, t in enumerate(timing)]
    clips = []
    for i, sc in enumerate(s["scenes"]):
        if sc["kind"] == "clip":
            _copy(job.dir / "clips" / f"clip{i}.mp4", project / "assets" / "clips" / f"clip{i}.mp4")
            clips.append({"id": f"c{i:02d}", "src": f"assets/clips/clip{i}.mp4", "start": S[i],   # 짧게 올린 클립
                          "duration": round(min(CLIP_MAX, timing[i]["duration"],
                                                ffmpeg.duration(job.dir / "clips" / f"clip{i}.mp4")), 3)})
    got = {}   # 기록 사진: 하나 못 받아도 영상은 만든다
    for ph in plan.get("photos") or []:
        dst = job.dir / "photos" / f"p{ph['scene']}.jpg"
        try:
            info = media.fetch_photo(ph["query"], dst)
        except RuntimeError as e:
            job.log(f"사진을 건너뛰었어요: {e}")
            continue
        if not info:
            job.log(f"퍼블릭 도메인 사진을 못 찾아 건너뛰었어요({ph['query']})")
            continue
        _copy(dst, project / "assets" / "photos" / dst.name)
        got[ph["scene"]] = info | {"file": dst.name}
        job.log(f"사진 장면 {ph['scene'] + 1}: {info['title']} ({info['license']}) {info['url']}")
    parts = mapplan.film_parts(plan, s, timing, end_start, ch.style.accent, INK, got)
    for w in parts.pop("warnings"):
        job.log(f"지도 계획 고침: {w}")
    lib, table = sound.tables()
    if ch.long.music not in table:
        raise RuntimeError(f"모르는 음악 분위기예요: [long] music = {ch.long.music} (가능: {', '.join(table)})")
    m = table[ch.long.music][0]
    path = media.fetch_music(m["title"], m["url"])
    music = sound.track(path, m["credit"])
    _copy(path, project / "assets" / music["file"])
    sounds = sound.place(total=total, end_start=end_start, cam=parts["cam"],
                         turns=[S[i] for i, b in enumerate(beats) if b == "turn"],
                         hits=[x[0] for x in parts["flashes"]],
                         final=next((S[i] for i, b in enumerate(beats) if b == "final"), None),
                         photos=[p[3] for p in parts["photos"]], music=music, lib=lib)
    for name in {x[1] for x in sounds} - {music["file"]}:
        _copy(sound.ASSETS / name, project / "assets" / name)
    # 자막은 영상에 굽는다: YouTube CC는 기본으로 꺼져 있어 대부분 못 본다
    cues = subtitles.cues(timing, sv.splitter, ch.style.subtitle_limit or CAP_SCALE * sv.splitter.limit)
    job.put("cues.json", cues)
    credits = [f"내레이션 {sv.tts.label}", parts["map_credit"],
               *(["사진 Wikimedia Commons(퍼블릭 도메인)"] if parts["photos"] else []),
               *sound.credits(lib, {Path(f).stem for _, f, *_ in sounds}, music)]
    sub = (s.get("thumb") or [""])[0]   # 끝 화면 부제: 썸네일 첫 줄. 장 제목("6월 25일 새벽")은 어색하다
    # film.build는 글을 이스케이프하지 않는다(mapplan 글은 film_parts가 이미 걸렀다)
    data = parts | {"title": html.escape(s["title"]),
                    "subtitle": html.escape(sub if sub != s["title"] else ""),
                    "lang": ch.language, "locale": LOCALES.get(ch.language, ch.language), "size": list(mapplan.SIZE),
                    "ink": INK, "accent": ch.style.accent, "bg": BG, "total": total, "end_start": end_start,
                    "tiles": job.doc("tiles.json"), "geo": job.doc("geo.json"), "voices": voices, "clips": clips,
                    "captions": [[c["start"], c["end"], html.escape(c["text"])] for c in cues],
                    "sounds": sounds, "credits": credits, "panels": [], "notes": []}
    job.put("film.json", data)
    film.build(data, project)
    report = hyperframes.check(project)
    summary = {k: {"errors": v.get("errorCount", 0), "warnings": v.get("warningCount", 0)}
               for k, v in report.items() if isinstance(v, dict) and "errorCount" in v}
    if any(v["errors"] for v in summary.values()):
        msgs = [x["message"] for v in report.values() if isinstance(v, dict)
                for x in v.get("findings", []) if x.get("severity") == "error"]
        raise RuntimeError("초안 검사 오류: " + " / ".join(
            msgs[:3] or [f"{k} {v['errors']}개" for k, v in summary.items() if v["errors"]]))
    # 장 첫 장면 가운데: 지명 글씨가 다 뜬 뒤라 사람이 글씨를 볼 수 있다
    # 사진은 다 뜬 뒤 한 장씩: 사진이 그 장면과 맞는지 사람이 본다
    want = [{"chapter": k, "title": c["title"],
             "at": round(S[c["first"]] + max(1.5, timing[c["first"]]["duration"] / 2), 2)}
            for k, c in enumerate(s["chapters"])]
    want += [{"chapter": None, "title": f"사진 · {p[2]}", "at": round(p[3] + 1.0, 2)} for p in parts["photos"]]
    want.sort(key=lambda x: x["at"])
    shots = hyperframes.snapshot(project, [x["at"] for x in want], job.dir / "draft")
    job.put("draft.json", {"check": summary, "snapshots": [
        x | {"file": f"draft/{p.name}"} for x, p in zip(want, shots, strict=True)]})
    job.update(draft_ok=False)   # 초안이 바뀌면 다시 본다
    return f"HyperFrames {total:.0f}초"


def step_render(job: Job, sv: Services) -> str:
    """final.mp4 · thumbnail.jpg(1280x720) · credits.json. 자막은 초안에서 영상에 구웠다."""
    if not job.data.get("draft_ok"):
        raise Wait("초안을 확인하고 승인해 주세요")
    f, timing = job.doc("film.json"), job.doc("timing.json")
    project, video = job.dir / "film", job.dir / "final.mp4"
    hyperframes.render(project, video, job.log)
    # 예전 작업의 SRT: 남아 있으면 업로드가 CC로 또 붙여 자막이 겹친다
    (job.dir / "captions.srt").unlink(missing_ok=True)
    s = job.doc("script.json")
    # 썸네일은 turn 장면 앞 쉼에서 찍는다: 그 사이엔 구운 자막이 없다
    at = next((t["start"] - TURN_GAP / 2 for t, b in zip(timing, _beats(s), strict=True) if b == "turn"),
              f["total"] / 3)
    shot = hyperframes.snapshot(project, [round(at, 2)], job.dir / "draft")[0]
    ffmpeg.text_card(shot, s.get("thumb") or [s["title"]], project / FONT, job.dir / "thumbnail.jpg")
    job.put("credits.json", f["credits"])
    job.update(duration=round(ffmpeg.duration(video), 2))
    return "HyperFrames"


def step_final(job: Job, sv: Services) -> str:
    """길이·음량·무음·자막 끝을 재서 final.json에 남긴다. 지적은 로그로만(실패하지 않는다)."""
    f, video = job.doc("film.json"), job.dir / "final.mp4"
    dur, loud = ffmpeg.duration(video), ffmpeg.loudness(video)
    # 끝 화면은 음악만 작게 깔려 늘 무음으로 잡히므로 끝 화면 앞까지만 잘라 잰다
    cut = [(a, min(b, f["end_start"])) for a, b in ffmpeg.silences(video, min_s=QUIET)]
    quiet = [(round(a, 2), round(b, 2)) for a, b in cut if b - a >= QUIET]
    cue_end = max((c["end"] for c in job.doc("cues.json") or []), default=0)
    issues = []
    if abs(dur - f["total"]) > LEN_TOL:
        issues.append(f"길이 {dur:.1f}초, 예상 {f['total']:.1f}초")
    if abs(loud["lufs"] - LUFS) > LUFS_TOL:
        issues.append(f"음량 {loud['lufs']} LUFS(목표 {LUFS}±{LUFS_TOL})")
    if loud["true_peak"] > PEAK:
        issues.append(f"true peak {loud['true_peak']} dBTP(목표 {PEAK} 이하)")
    issues += [f"{a}~{b}초 무음" for a, b in quiet]
    if cue_end > dur:
        issues.append(f"자막이 영상 끝({dur:.1f}초) 뒤 {cue_end:.1f}초까지 가요")
    job.put("final.json", {"duration": dur, "expected": f["total"], "lufs": loud["lufs"],
                           "true_peak": loud["true_peak"], "silences": quiet, "cue_end": cue_end, "issues": issues})
    for x in issues:
        job.log(f"최종 검수: {x}")
    return "통과" if not issues else f"지적 {len(issues)}개"


RUN = {"research": step_research, "script": step_script, "proofread": step_proofread, "voice": step_voice,
       "plan": step_plan, "map": step_map, "clips": step_clips, "draft": step_draft, "render": step_render,
       "final": step_final}


def _step(f, sv: Services):
    def go(rec: Job) -> str:
        # 단계마다 먼저 본다: 조사·LLM·음성에 돈을 쓴 뒤 초안에서 Node가 없어 멈추지 않게.
        # run_steps 안에서 던져야 실패가 작업에 남는다(밖에서 던지면 상태가 running에 갇힌다)
        if not hyperframes.ready():
            raise RuntimeError("Node.js 22 이상(npx)을 찾지 못했어요. 롱폼 초안·렌더에 필요해요")
        return f(rec, sv)
    return go


def run(job: Job, sv: Services) -> None:
    run_steps(job, STEPS_LONG, LABELS_LONG, {k: _step(f, sv) for k, f in RUN.items()},
              "완성 · 최종 검수 뒤 업로드를 눌러 주세요")

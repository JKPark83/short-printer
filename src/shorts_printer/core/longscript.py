"""롱폼 대본: 목차(장 5~8개) → 장마다 장면 → script.json(docs/plan/longform.md 3·4단계).
장면은 지도(map)가 기본이고 일부만 Flow 클립(clip). clip 비율 상한은 모델이 아니라 코드가 지킨다.
지시문 = prompts/long_*.md + 채널 script.md·video_style.md. 길이는 channel.toml [long] minutes."""
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from ..ports.llm import LLM, add_usage
from . import prompts, script
from .channel import Channel
from .script import Issue, Verdict

Beat = Literal["", "turn", "hit", "final"]
RATE = {"chars": 7.0, "words": 2.6}   # 초당 낭독 길이(글자는 띄어쓰기 빼고)
SCENE_SEC = (8, 14)   # 장면 하나 낭독 길이(초)
AVG_SCENE = 11   # 장면 하나 + 쉼(초). 8분 ≈ 44장면, 12분 ≈ 65장면


class Chapter(BaseModel):
    title: str = Field(description="장 제목(짧게)")
    summary: str = Field(description="이 장에서 일어나는 일과 지도에서 움직이는 것 2~3문장")
    scenes: int = Field(description="이 장의 장면 수")
    fact_ids: list[str] = Field(default_factory=list, description="이 장이 쓸 사실 시트 ID")
    beats: list[Literal["turn", "hit", "final"]] = Field(default_factory=list,
                                                        description="이 장에 둘 박자(없으면 비운다)")


class Outline(BaseModel):
    title: str = Field(description="영상 제목. 60자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 3~5문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 10~15개, # 없이")
    thumb: list[str] = Field(description="썸네일 큰 글자 1~2줄")
    sensitive: str = Field(description="지금의 정치 논쟁에 닿으면 그 분야 이름(정치 등). 역사 서술만이면 빈 문자열")
    spine: str = Field(description="첫 장이 여는 물음과 마지막 장면의 답 한 줄")
    chapters: list[Chapter] = Field(description="장 목록, 시간 순서")


class Scene(BaseModel):
    narration: str = Field(description="장면 하나의 내레이션(문장 1~3개)")
    kind: Literal["map", "clip"] = Field(description="map: 지도 장면, clip: AI 영상 클립")
    beat: Beat = Field("", description="turn·hit·final 또는 빈 문자열")
    visual: str = Field(description="지도나 클립이 보여 줄 것 한국어 한 줄(어디·무엇이 움직이나·뜨는 지명)")
    fact_ids: list[str] = Field(default_factory=list, description="이 장면이 기댄 사실 시트 ID")
    clip_prompt: str = Field("", description="clip이면 영어 영상 생성 프롬프트(머리말 없이), map이면 빈 문자열")
    clip_prompt_ko: str = Field("", description="clip_prompt를 한국어로 짧게, map이면 빈 문자열")


class Scenes(BaseModel):
    scenes: list[Scene] = Field(description="이 장의 장면, 읽는 순서")


class Edit(Scene):
    scene: int = Field(description="고친 장면 번호(1부터)")


class Revision(BaseModel):
    title: str = Field(description="영상 제목. 바꾸지 않으면 그대로")
    description: str = Field(description="영상 설명. 바꾸지 않으면 그대로")
    tags: list[str] = Field(description="검색 태그. 바꾸지 않으면 그대로")
    thumb: list[str] = Field(description="썸네일 큰 글자 1~2줄. 바꾸지 않으면 그대로")
    scenes: list[Edit] = Field(default_factory=list, description="바꾼 장면만. 안 바꾼 장면은 넣지 않는다")


def _size(ch: Channel, t: str) -> int:
    return len("".join(t.split())) if ch.script.unit == "chars" else len(t.split())


def estimate_seconds(ch: Channel, sentences: Sequence[str]) -> float:
    """대본 길이로 어림한 영상 길이(초): 낭독 + 앞뒤 약 8초 + 장면 사이 0.8초."""
    return sum(_size(ch, t) for t in sentences) / RATE[ch.script.unit] + 8 + 0.8 * len(sentences)


def values(ch: Channel) -> dict:
    """long_* 지시문의 ${이름} 값. 길이는 [long] minutes에서 센다."""
    lo, hi = ch.long.minutes
    rate = RATE[ch.script.unit]
    n_lo, n_hi = round(lo * 60 / AVG_SCENE), round(hi * 60 / AVG_SCENE)
    return dict(lang=ch.lang_name, minutes_lo=lo, minutes_hi=hi, scenes_lo=n_lo, scenes_hi=n_hi,
                unit=script.UNITS[ch.script.unit], scene_lo=round(SCENE_SEC[0] * rate),
                scene_hi=round(SCENE_SEC[1] * rate), total_lo=round((lo * 60 - 8 - 0.8 * n_lo) * rate),
                total_hi=round((hi * 60 - 8 - 0.8 * n_hi) * rate), clip_pct=round(ch.long.clip_ratio * 100),
                channel_script=ch.text("script.md"), channel_video=ch.video_rules())


def _clean(ch: Channel, sc: dict) -> dict:
    """map은 프롬프트를 비우고, 프롬프트 없는 clip은 만들 수 없어 map으로. clip엔 채널 머리말을 붙인다."""
    p = sc["clip_prompt"].strip()
    if sc["kind"] != "clip" or not p:
        return sc | {"kind": "map", "clip_prompt": "", "clip_prompt_ko": ""}
    style = ch.video.style
    return sc | {"clip_prompt": f"{style} {p}" if style and not p.startswith(style) else p}


def cap_clips(ch: Channel, scenes: list[dict], prefer: Sequence[int] = ()) -> list[str]:
    """clip이 [long] clip_ratio를 넘으면 넘친 만큼 map으로 바꾼다(제자리에서).
    고친 장면 → 장의 첫 clip → 앞쪽 순으로 남긴다."""
    clips = [i for i, s in enumerate(scenes) if s["kind"] == "clip"]
    room = int(ch.long.clip_ratio * len(scenes))
    if len(clips) <= room:
        return []
    firsts = {next(i for i in clips if scenes[i]["chapter"] == c) for c in {scenes[i]["chapter"] for i in clips}}
    drop = sorted(sorted(clips, key=lambda i: (i not in prefer, i not in firsts, i))[room:])
    for i in drop:
        scenes[i] |= {"kind": "map", "clip_prompt": "", "clip_prompt_ko": ""}
    nums = ", ".join(str(i + 1) for i in drop)
    return [f"clip 장면 {len(clips)}개가 상한 {room}개를 넘어 장면 {nums}을 map으로 바꿨다"]


def _flat(head: dict, chapters: list[dict], scenes: list[dict], notes: list[str]) -> dict:
    return head | {"chapters": chapters, "scenes": scenes, "notes": notes,
                   "sentences": [s["narration"] for s in scenes], "fact_ids": [s["fact_ids"] for s in scenes]}


def _request(ch: Channel, topic: str, brief: str | None, recent: Sequence[str], unverified: Sequence[str]) -> str:
    text = f"주제: {topic}"
    if brief:
        text += f"\n\n참고(추천 주제 방향). 방향·내용은 따르되 문장을 베끼지 않는다:\n{brief}"
    if unverified:
        text += ("\n\n조사에서 확인하지 못한 주장(사실 시트에 같은 내용이 없으면 쓰지 않는다):\n"
                 + "\n".join(f"- {c}" for c in unverified))
    text += f"\n\n채널 분야: {ch.concept}. 이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다."
    if recent:
        text += "\n\n최근 제목(이 틀을 피한다):\n" + "\n".join(f"- {t}" for t in recent)
    return text


def _toc(o: Outline) -> str:
    return "\n".join(f"{k}. {c.title} (장면 {c.scenes}개, 박자 {', '.join(c.beats) or '없음'}, "
                     f"근거 {', '.join(c.fact_ids) or '없음'}): {c.summary}" for k, c in enumerate(o.chapters, 1))


def write(llm: LLM, ch: Channel, topic: str, brief: str | None = None, recent: Sequence[str] = (),
          facts: Sequence[dict] = (), unverified: Sequence[str] = ()) -> tuple[dict, dict | None]:
    """목차 한 번 + 장마다 한 번. 장을 쓸 때 목차와 앞 장 내레이션을 같이 줘 이어지게 한다.
    돌려주는 dict는 script.json 롱폼 꼴(docs/plan/longform.md). notes: 코드가 바꾼 것."""
    v = values(ch)
    sheet = "\n\n" + script.sheet_block(facts) if facts else ""
    refusal = f"{llm.label}가 이 주제로는 목차를 쓰지 않았어요. 주제를 바꿔 보세요."
    outline, usage = llm.ask(prompts.render("long_outline", **v), _request(ch, topic, brief, recent, unverified)
                             + sheet, Outline, refusal=refusal, what="목차")
    if not outline.chapters:
        raise RuntimeError("목차를 받지 못했어요(장이 비었어요).")
    scenes: list[dict] = []
    chapters: list[dict] = []
    for k, c in enumerate(outline.chapters):
        before = "\n".join(f"{i}. {s['narration']}" for i, s in enumerate(scenes, 1)) or "(첫 장)"
        text = (f"주제: {topic}\n제목: {outline.title}\n줄기: {outline.spine}\n\n목차:\n{_toc(outline)}\n\n"
                f"지금 쓸 장: {k + 1}. {c.title}. 장면 약 {c.scenes}개, 박자 {', '.join(c.beats) or '없음'}\n\n"
                f"앞 장 내레이션:\n{before}{sheet}")
        out, u = llm.ask(prompts.render("long_scenes", **v), text, Scenes, what=f"{k + 1}장 장면",
                         refusal=f"{llm.label}가 {k + 1}장 장면을 쓰지 않았어요. 주제를 바꿔 보세요.")
        usage = add_usage(usage, u)
        if not out.scenes:
            raise RuntimeError(f"{k + 1}장 장면을 받지 못했어요(장면이 비었어요).")
        chapters.append({"title": c.title, "first": len(scenes)})
        scenes += [_clean(ch, s.model_dump() | {"chapter": k}) for s in out.scenes]
    head = outline.model_dump(include={"title", "description", "tags", "sensitive", "thumb"})
    return _flat(head, chapters, scenes, cap_clips(ch, scenes)), usage


def _listing(ch: Channel, s: dict) -> str:
    """장 머리 + 장면마다 [종류/박자] 내레이션, 화면, 근거. 클립 프롬프트는 머리말을 뺀다(모든 장면에 같다)."""
    heads = {c["first"]: f"## {k}장. {c['title']}" for k, c in enumerate(s["chapters"], 1)}
    lines = []
    for i, sc in enumerate(s["scenes"]):
        if i in heads:
            lines.append(heads[i])
        p = sc["clip_prompt"].removeprefix(ch.video.style).strip()
        lines.append(f"{i + 1}. [{sc['kind']}{'/' + sc['beat'] if sc['beat'] else ''}] {sc['narration']}"
                     f"\n   (화면: {sc['visual']}" + (f" / 클립: {p}" if p else "") + ")"
                     + (f"\n   (근거: {', '.join(sc['fact_ids'])})" if sc["fact_ids"] else ""))
    return "\n".join(lines)


def checks(ch: Channel, s: dict, facts: Sequence[dict]) -> list[Issue]:
    """모델이 세지 못하는 것: clip 비율, 전체 길이, 근거 없는 숫자·날짜."""
    out = []
    n, clips = len(s["scenes"]), sum(sc["kind"] == "clip" for sc in s["scenes"])
    if clips > (room := int(ch.long.clip_ratio * n)):
        out.append(Issue(scene=0, kind="화면", severity="큼", problem=f"clip 장면이 {clips}개라 상한 {room}개를 넘음",
                         fix=f"clip 장면 {clips - room}개를 map으로 바꾼다"))
    lo, hi = ch.long.minutes
    if not lo * 60 <= (sec := estimate_seconds(ch, s["sentences"])) <= hi * 60:
        out.append(Issue(scene=0, kind="낭독·자막", severity="큼",
                         problem=f"어림 길이 {int(sec // 60)}분 {int(sec % 60)}초라 {lo}~{hi}분을 벗어남",
                         fix=f"장면을 {'덜어' if sec > hi * 60 else '더해'} {lo}~{hi}분 안으로 맞춘다"))
    out += [Issue(scene=i + 1, kind="사실", severity="큼", problem="숫자·날짜가 있는데 근거(fact_ids)가 없거나 틀림",
                  fix="사실 시트의 번호를 달거나 숫자를 뺀다") for i in script.unverified(s, list(facts))]
    return out


def proofread(llm: LLM, ch: Channel, s: dict, facts: Sequence[dict] = (), topic: str = "") -> tuple[Verdict, dict]:
    """롱폼 대본 검수. 모델 채점(날짜 순서·사실 출처·화면과 내레이션·흐름) + 코드 점검(checks).
    고치지 않는다. 떨어지면 호출한 쪽이 지적을 남기고 사람 확인으로 멈춘다."""
    text = ((f"주제: {topic}\n" if topic else "") + f"제목: {s['title']}\n설명: {s['description']}\n"
            f"장면 {len(s['scenes'])}개:\n{_listing(ch, s)}")
    if facts:
        text += "\n\n" + script.sheet_block(facts)
    verdict, usage = llm.ask(prompts.render("long_proofread", **values(ch)), text, Verdict,
                             refusal=f"{llm.label}가 이 대본을 검수하지 않았어요.", what="검수 결과")
    return Verdict(issues=verdict.issues + checks(ch, s, facts)), usage


def revise(llm: LLM, ch: Channel, s: dict, note: str, facts: Sequence[dict] = ()) -> tuple[dict, dict]:
    """사람이 적은 요청대로 고친다. 모델은 바꾼 장면만 돌려주고 나머지 장면은 그대로 둔다. 장면 수·장은 그대로."""
    # ponytail: 장면 더하기·빼기는 안 한다. 필요하면 Edit에 op를 두고 chapters의 first를 다시 센다
    text = (f"제목: {s['title']}\n설명: {s['description']}\n태그: {', '.join(s['tags'])}\n"
            f"썸네일: {' / '.join(s.get('thumb') or [])}\n장면 {len(s['scenes'])}개:\n{_listing(ch, s)}"
            f"\n\n사용자 수정 요청: {note}")
    if facts:
        text += "\n\n" + script.sheet_block(facts)
    out, usage = llm.ask(prompts.render("long_scenes", **values(ch)) + "\n\n" + prompts.render("long_revise"), text,
                         Revision, refusal=f"{llm.label}가 이 요청으로는 대본을 고치지 않았어요. 요청을 바꿔 보세요.",
                         what="고친 대본")
    scenes = [dict(sc) for sc in s["scenes"]]
    if bad := [e.scene for e in out.scenes if not 1 <= e.scene <= len(scenes)]:
        raise RuntimeError(f"고친 장면 번호가 맞지 않아요({', '.join(map(str, bad))}). 다시 시도하세요.")
    for e in out.scenes:
        scenes[e.scene - 1] = _clean(ch, e.model_dump(exclude={"scene"}) | {"chapter": scenes[e.scene - 1]["chapter"]})
    notes = cap_clips(ch, scenes, prefer=[e.scene - 1 for e in out.scenes])
    return s | _flat(out.model_dump(exclude={"scenes"}), s["chapters"], scenes, notes), usage

"""1단계 대본: LLM으로 주제 하나에서 제목·설명·태그와 장면(문장·영상 프롬프트)을 한 번에 받는다
(MoneyPrinter의 gpt.py 역할).
지시문 = prompts/script.md(공통) + 채널 script.md·video_style.md. 장면 수·문장 길이·영상 머리말은 channel.toml."""
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from ..ports.llm import LLM
from ..ports.splitter import Splitter
from . import prompts, research
from .channel import Channel
from .subtitles import SENTENCE_END


class Scene(BaseModel):
    # 문장보다 먼저 받는다: 앞 장면과의 관계를 정하고 쓰면 접속어·반전이 내용과 어긋나지 않는다(저장하지 않는다)
    link: str = Field("", description="쓰기 전에 정하는 앞 장면과의 관계 한 줄(규칙은 지시문의 장면 잇기)")
    sentence: str = Field(description="장면 하나의 내레이션(짧은 문장 1~2개)")
    prompt: str = Field(description="이 장면 동안 보일 한 장면의 영어 영상 생성 프롬프트, 스타일 머리말 없이")
    fact_ids: list[str] = Field(default_factory=list,
                                description="이 문장이 근거로 삼은 사실 시트 ID(F1 등). 숫자·사실이 있는 문장은 비우지 않는다")
    prompt_ko: str = Field("", description="prompt를 한국어로 짧게. 검수용")


class Script(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    scenes: list[Scene] = Field(description="장면 목록. 장면 하나 = 문장 하나, 읽는 순서")
    sensitive: str = Field(
        description="진단·치료·약·식품 효능·투자·법률 조언이 들어가거나 정치 주제면 그 분야 이름(건강·의료, 법률, 금융·투자, 정치). "
        "몸의 원리 설명만이면 빈 문자열"
    )

    def flat(self) -> dict:
        """script.json 형식: 장면을 같은 개수의 배열들로 푼다(다른 단계는 sentences를 읽는다).
        예전 script.json엔 fact_ids·prompts_ko가 없으니 읽는 곳은 .get으로 읽는다."""
        return self.model_dump(exclude={"scenes"}) | {
            "sentences": [s.sentence for s in self.scenes], "prompts": [s.prompt for s in self.scenes],
            "fact_ids": [s.fact_ids for s in self.scenes], "prompts_ko": [s.prompt_ko for s in self.scenes]}


UNITS = {"chars": "자", "words": "단어"}


def system(ch: Channel) -> str:
    """채널 대본 지시문. 글 파일은 부를 때마다 읽어 고치면 바로 반영된다."""
    c = ch.script
    lo, hi = c.sentence
    return prompts.render("script", lang=ch.lang_name, duration=c.duration, scenes=c.scenes, lo=lo, hi=hi,
                          unit=UNITS[c.unit], total_lo=lo * c.scenes, total_hi=hi * c.scenes,
                          channel_script=ch.text("script.md"), channel_video=ch.text("video_style.md"))


class Revision(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    sentences: list[str] = Field(description="장면마다 내레이션(짧은 문장 1~2개). 받은 장면과 같은 개수, 같은 순서")


class Draft(Revision):
    prompts: list[str] = Field(description="장면마다 영어 영상 생성 프롬프트, 스타일 머리말 없이. 받은 장면과 같은 개수")
    fact_ids: list[list[str]] = Field(default_factory=list,
                                      description="장면마다 근거로 삼은 사실 시트 ID 목록. 받은 장면과 같은 개수")
    prompts_ko: list[str] = Field(default_factory=list, description="장면마다 prompt를 한국어로 짧게. 검수용")


def _fit(xs, n: int, empty) -> list:
    """장면 수와 길이가 맞으면 그대로, 아니면(예전 대본·모델이 빼먹음) 빈 값 n개."""
    return list(xs) if len(xs or []) == n else [empty() for _ in range(n)]


def keep_ko(old: dict, shots: list[str]) -> list[str]:
    """영어 프롬프트가 그대로인 장면만 한국어 풀이를 잇는다. 바뀐 장면은 낡은 풀이라 비운다."""
    n = len(shots)
    return [k if a == b else "" for k, a, b in
            zip(_fit(old.get("prompts_ko"), n, str), _fit(old.get("prompts"), n, str), shots, strict=True)]


def sheet_block(facts: Sequence[dict]) -> str:
    """user 메시지 끝에 붙일 사실 시트. 사실이 없으면(예전 작업) 빈 글."""
    return "사실 시트(이것만 사실로 쓴다):\n" + research.sheet(list(facts)) if facts else ""


def unverified(s: dict, facts: list[dict]) -> list[int]:
    """숫자가 든 문장인데 근거(fact_ids)가 없거나 시트에 없는 ID를 가리키는 장면 번호(0부터). 검수 화면에만 띄운다."""
    # ponytail: 한자 숫자(三つ)·고유명사는 못 잡는다. 사람 검수가 맡는다.
    ids = {f["id"] for f in facts}
    refs = _fit(s.get("fact_ids"), len(s["sentences"]), list)
    return [i for i, (t, r) in enumerate(zip(s["sentences"], refs, strict=True))
            if re.search("[0-9０-９]", t) and (not r or not set(r) <= ids)]


def revise(llm: LLM, ch: Channel, s: dict, note: str, draft: bool = False,
           facts: Sequence[dict] = ()) -> tuple[dict, dict]:
    """대본(script.json)을 요청대로 고친다. 장면 수는 그대로.
    draft: 확정 전(장면 영상이 아직 없다)이라 영상 프롬프트도 문장에 맞춰 고친다. 아니면 프롬프트는 그대로.
    facts: 자료 조사 사실. 대본을 쓸 때와 같은 시트를 붙인다."""
    n = len(s["sentences"])
    shots = _fit(s.get("prompts"), n, str)   # 예전 대본엔 없다
    refs = _fit(s.get("fact_ids"), n, list)
    scenes = "\n".join(f"{i}. {t}" + (f"\n   (화면: {p})" if p else "") + (f"\n   (근거: {', '.join(r)})" if r else "")
                       for i, (t, p, r) in enumerate(zip(s["sentences"], shots, refs, strict=True), 1))
    text = (f"제목: {s['title']}\n설명: {s['description']}\n태그: {', '.join(s['tags'])}\n장면 {n}개:\n{scenes}"
            f"\n\n사용자 수정 요청: {note}")
    if facts:
        text += "\n\n" + sheet_block(facts)
    refusal = f"{llm.label}가 이 요청으로는 대본을 고치지 않았어요. 요청을 바꿔 보세요."
    out, usage = llm.ask(system(ch) + "\n\n" + prompts.render("script_revise_draft" if draft else "script_revise"),
                         text, Draft if draft else Revision, refusal=refusal, what="고친 대본")
    new = out.model_dump()
    for key in ("sentences", "prompts") if draft else ("sentences",):
        new[key] = [x.strip() for x in new[key]]
        if len(new[key]) != n or not all(new[key]):
            raise RuntimeError(f"고친 대본의 장면 수가 맞지 않아요({len(new[key])}/{n}개). 다시 시도하세요.")
    if draft:   # 모델이 빼먹거나 개수가 틀리면 예전 근거·풀이를 잇는다(비우면 안 바꾼 장면까지 근거 없음으로 뜬다)
        if len(new["fact_ids"]) != n:
            new["fact_ids"] = refs
        if len(new["prompts_ko"]) != n:
            new["prompts_ko"] = keep_ko(s, new["prompts"])
        if style := ch.video.style:   # write처럼 머리말을 붙인다. 받은 프롬프트를 그대로 돌려준 장면엔 이미 있다
            new["prompts"] = [p if p.startswith(style) else f"{style} {p}" for p in new["prompts"]]
    else:   # 문장만 바뀌어 근거는 그대로 잇는다
        new["fact_ids"] = refs
    return s | new, usage


class Translation(BaseModel):
    title: str = Field(description="제목 한국어")
    description: str = Field(description="설명 한국어")
    tags: list[str] = Field(description="태그 한국어. 받은 것과 같은 개수, 같은 순서")
    sentences: list[str] = Field(description="문장 한국어. 받은 것과 같은 개수, 같은 순서")
    thumb: list[str] = Field(description="썸네일 문구 줄 한국어. 받은 것과 같은 개수")
    cues: list[str] = Field(description="자막 줄 한국어. 받은 것과 같은 개수, 같은 순서. 받지 않았으면 빈 목록")
    notes: list[str] = Field(description="원문에서 어색하거나 틀렸거나 오해를 살 만한 곳. 없으면 빈 목록")


def ko_source(s: dict, thumb: dict | None) -> dict:
    """옮길 원문. 웹이 저장된 번역과 견줘 대본·썸네일 문구를 고친 뒤인지 본다."""
    return {k: s[k] for k in ("title", "description", "tags", "sentences")} | {
        "thumb": (thumb or {}).get("lines", [])}


def translate(llm: LLM, ch: Channel, s: dict, thumb: dict | None,
              cues: Sequence[str] = ()) -> tuple[dict, dict]:
    """한국어가 아닌 채널의 대본·썸네일 문구·자막 줄을 운영자가 확인하도록 한국어로 옮긴다.
    {"src": 원문, "cues": 자막 원문, "ko": 번역}. 자막은 음성 단계 뒤에 생겨 src와 따로 견준다."""
    src = ko_source(s, thumb)
    text = "\n".join([f"제목: {src['title']}", f"설명: {src['description']}", f"태그: {', '.join(src['tags'])}",
                      f"문장 {len(src['sentences'])}개:", *(f"{i}. {t}" for i, t in enumerate(src["sentences"], 1)),
                      f"썸네일 문구 {len(src['thumb'])}줄:", *src["thumb"],
                      f"자막 {len(cues)}줄:", *(f"{i}. {t}" for i, t in enumerate(cues, 1))])
    out, usage = llm.ask(prompts.render("translate", lang=ch.lang_name), text, Translation,
                         refusal=f"{llm.label}가 이 대본을 옮기지 않았어요.", what="번역")
    if len(out.sentences) != len(src["sentences"]):
        raise RuntimeError(f"번역의 문장 수가 맞지 않아요({len(out.sentences)}/{len(src['sentences'])}개). 다시 시도하세요.")
    if len(out.cues) != len(cues):
        raise RuntimeError(f"번역의 자막 줄 수가 맞지 않아요({len(out.cues)}/{len(cues)}줄). 다시 시도하세요.")
    return {"src": src, "cues": list(cues), "ko": out.model_dump()}, usage


class Issue(BaseModel):
    scene: int = Field(description="장면 번호(1부터). 제목·설명·태그는 0")
    problem: str = Field(description="어느 표현이 무슨 뜻이고 왜 어색한지 한 줄. 반드시 한국어(확인하는 사람은 한국인)")
    fix: str = Field(description="고친 문장(대본 언어)과 괄호 안에 그 뜻을 한국어로 짧게")


class Verdict(BaseModel):
    passed: bool = Field(description="시청자에게 내보내도 되면 true")
    issues: list[Issue] = Field(default_factory=list, description="고칠 곳. passed가 true면 비운다")

    def lines(self, sentences: Sequence[str]) -> list[str]:
        """로그에 남기고 다시 쓰기에 넘기는 꼴. 원문을 같이 적어 장면 번호 없이도 무엇을 고칠지 알게 한다."""
        return [f"장면 {i.scene}" + (f"「{sentences[i.scene - 1]}」" if 0 < i.scene <= len(sentences) else "")
                + f": {i.problem} → {i.fix}" for i in self.issues]


FIX_NOTE = ("검수 지적이다. 지적받은 장면(0은 제목·설명)을 fix를 따라 고치고 괄호 안 한국어 뜻은 넣지 않는다. "
            "고친 문장이 바로 앞뒤 장면과 이어지지 않으면 그 앞뒤 장면까지만 같이 고친다. "
            "그 밖의 장면은 한 글자도 바꾸지 않는다:\n")


def proofread(llm: LLM, ch: Channel, s: dict, splitter: Splitter, limit: int,
              facts: Sequence[dict] = ()) -> tuple[Verdict, dict]:
    """대본(script.json 꼴)이 그 말로 자연스러운지, 자막으로 끊었을 때 잘 읽히는지 검수한다.
    문장마다 따로가 아니라 앞 문장들에 비춰 흐름부터 본다. 사실 시트를 붙여 고칠 말이 사실을 벗어나지 않게 한다.
    문장마다 자막 단계와 같은 규칙으로 끊은 자리를 " / "로 보여 준다(끊는 규칙은 못 고치니 문장을 고치게).
    통과하지 못하면 호출한 쪽이 FIX_NOTE + Verdict.lines()를 revise()로 넘겨 지적한 곳만 고친다."""
    def cut(t: str) -> str:
        return " / ".join(p for part in SENTENCE_END.split(t) if part.strip() for p in splitter.chunks(part, limit))
    scenes = "\n".join(f"{i}. {cut(t)}" for i, t in enumerate(s["sentences"], 1))
    text = f"제목: {s['title']}\n설명: {s['description']}\n장면 {len(s['sentences'])}개(자막 끊는 자리는 /):\n{scenes}"
    if facts:
        text += "\n\n" + sheet_block(facts)
    name = "script_proofread_ko" if ch.language == "ko" else "script_proofread"
    verdict, usage = llm.ask(prompts.render(name, lang=ch.lang_name, limit=limit), text, Verdict,
                             refusal=f"{llm.label}가 이 대본을 검수하지 않았어요.", what="검수 결과")
    if long := too_long(ch, s["sentences"]):
        verdict = Verdict(passed=False, issues=verdict.issues + long)
    return verdict, usage


def too_long(ch: Channel, sentences: Sequence[str]) -> list[Issue]:
    """한 장면 최대 길이를 넘는 장면. 모델은 글자 수를 세지 못해 지시문만으론 넘치므로 코드가 재서 검수 지적으로 넘긴다.
    짧은 장면은 클립 안에 끝나니 넘긴다."""
    hi, u = ch.script.sentence[1], UNITS[ch.script.unit]
    size = len if ch.script.unit == "chars" else (lambda t: len(t.split()))
    return [Issue(scene=i, problem=f"{n}{u}라 한 장면 {hi}{u}를 넘어 장면 클립보다 길게 읽힘",
                  fix=f"뜻과 고정 멘트는 그대로 두고 군더더기를 덜어 {hi}{u} 안으로 줄인 문장")
            for i, t in enumerate(sentences, 1) if (n := size(t)) > hi]


def write(llm: LLM, ch: Channel, topic: str, brief: str | None = None, recent: Sequence[str] = (),
          facts: Sequence[dict] = ()) -> tuple[Script, dict]:
    """brief: 추천 주제에서 왔으면 훅·전개 방향 참고. recent: 최근 작업 제목(같은 틀을 피한다).
    facts: 자료 조사 사실(facts.json의 facts). 대본은 이 시트의 사실만 쓴다."""
    text = f"주제: {topic}"
    if brief:
        text += f"\n\n참고(추천 주제 방향). 방향·내용은 따르되 문장을 베끼지 않는다:\n{brief}"
    text += f"\n\n채널 분야: {ch.concept}. 이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다."
    if recent:
        text += "\n\n최근 제목(이 틀을 피한다):\n" + "\n".join(f"- {t}" for t in recent)
    if facts:
        text += "\n\n" + sheet_block(facts)
    refusal = f"{llm.label}가 이 주제로는 대본을 쓰지 않았어요. 주제를 바꿔 보세요."
    script, usage = llm.ask(system(ch), text, Script, refusal=refusal, what="대본")
    if not script.scenes:
        raise RuntimeError("대본을 받지 못했어요(문장이 비었어요).")
    # 장면마다 LLM이 화풍을 달리 쓰면 영상이 들쭉날쭉해서 채널 머리말을 코드로 붙인다
    if style := ch.video.style:
        script = script.model_copy(update={"scenes": [s.model_copy(update={"prompt": f"{style} {s.prompt}"})
                                                      for s in script.scenes]})
    return script, usage

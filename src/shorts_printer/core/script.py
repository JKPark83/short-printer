"""1단계 대본: LLM으로 주제 하나에서 제목·설명·태그와 장면(문장·영상 프롬프트)을 한 번에 받는다
(MoneyPrinter의 gpt.py 역할).
지시문 = prompts/script.md(공통) + 채널 script.md·video_style.md. 장면 수·문장 길이·영상 머리말은 channel.toml."""
from collections.abc import Sequence

from pydantic import BaseModel, Field

from ..ports.llm import LLM
from . import prompts
from .channel import Channel


class Scene(BaseModel):
    sentence: str = Field(description="내레이션 한 문장")
    prompt: str = Field(description="이 문장 동안 보일 한 장면의 영어 영상 생성 프롬프트, 스타일 머리말 없이")


class Script(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    scenes: list[Scene] = Field(description="장면 목록. 장면 하나 = 문장 하나, 읽는 순서")
    sensitive: str = Field(description="건강·의료, 법률, 금융·투자, 정치 주제면 그 분야 이름. 아니면 빈 문자열")

    def flat(self) -> dict:
        """script.json 형식: 장면을 같은 개수의 배열 셋으로 푼다(다른 단계는 sentences를 읽는다)."""
        return self.model_dump(exclude={"scenes"}) | {
            "sentences": [s.sentence for s in self.scenes], "prompts": [s.prompt for s in self.scenes]}


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
    sentences: list[str] = Field(description="장면마다 내레이션 한 문장. 받은 장면과 같은 개수, 같은 순서")


def revise(llm: LLM, ch: Channel, s: dict, note: str) -> tuple[dict, dict]:
    """완성된 대본(script.json)을 요청대로 고친다. 장면 수와 영상 프롬프트는 그대로."""
    n = len(s["sentences"])
    shots = s.get("prompts") if len(s.get("prompts") or []) == n else [""] * n   # 예전 대본엔 없다
    scenes = "\n".join(f"{i}. {t}" + (f"\n   (화면: {p})" if p else "")
                       for i, (t, p) in enumerate(zip(s["sentences"], shots, strict=True), 1))
    text = (f"제목: {s['title']}\n설명: {s['description']}\n태그: {', '.join(s['tags'])}\n장면 {n}개:\n{scenes}"
            f"\n\n사용자 수정 요청: {note}")
    refusal = f"{llm.label}가 이 요청으로는 대본을 고치지 않았어요. 요청을 바꿔 보세요."
    out, usage = llm.ask(system(ch) + "\n\n" + prompts.render("script_revise"), text, Revision,
                         refusal=refusal, what="고친 대본")
    sentences = [x.strip() for x in out.sentences]
    if len(sentences) != n or not all(sentences):
        raise RuntimeError(f"고친 대본의 장면 수가 맞지 않아요({len(sentences)}/{n}개). 다시 시도하세요.")
    return s | out.model_dump() | {"sentences": sentences}, usage


def write(llm: LLM, ch: Channel, topic: str, brief: str | None = None,
          recent: Sequence[str] = ()) -> tuple[Script, dict]:
    """brief: 추천 주제에서 왔으면 훅·전개 방향 참고. recent: 최근 작업 제목(같은 틀을 피한다)."""
    text = f"주제: {topic}"
    if brief:
        text += f"\n\n참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:\n{brief}"
    text += f"\n\n채널 분야: {ch.concept}. 이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다."
    if recent:
        text += "\n\n최근 제목(이 틀을 피한다):\n" + "\n".join(f"- {t}" for t in recent)
    refusal = f"{llm.label}가 이 주제로는 대본을 쓰지 않았어요. 주제를 바꿔 보세요."
    script, usage = llm.ask(system(ch), text, Script, refusal=refusal, what="대본")
    if not script.scenes:
        raise RuntimeError("대본을 받지 못했어요(문장이 비었어요).")
    # 장면마다 LLM이 화풍을 달리 쓰면 영상이 들쭉날쭉해서 채널 머리말을 코드로 붙인다
    if style := ch.video.style:
        script = script.model_copy(update={"scenes": [s.model_copy(update={"prompt": f"{style} {s.prompt}"})
                                                      for s in script.scenes]})
    return script, usage

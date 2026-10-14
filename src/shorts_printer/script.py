"""1단계 대본: Claude API로 주제 하나에서 제목·설명·태그와 장면(문장·영상 프롬프트·스톡 검색어)을 한 번에 받는다(MoneyPrinter의 gpt.py 역할)."""
import anthropic
from pydantic import BaseModel, Field

from . import config


class Scene(BaseModel):
    sentence: str = Field(description="내레이션 한 문장, 48~55자")
    prompt: str = Field(description="이 문장 동안 보일 한 장면의 영어 영상 생성 프롬프트, 60~90단어, 스타일 머리말 없이")
    term: str = Field(description="같은 장면을 스톡 영상에서 찾을 구체적인 영어 명사구 2~4단어")


class Script(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    scenes: list[Scene] = Field(description="장면 7개. 장면 하나 = 문장 하나, 읽는 순서")
    sensitive: str = Field(description="건강·의료, 법률, 금융·투자, 정치 주제면 그 분야 이름. 아니면 빈 문자열")

    def flat(self) -> dict:
        """script.json 형식: 장면을 같은 개수의 배열 셋으로 푼다(다른 단계는 sentences를 읽는다)."""
        return self.model_dump(exclude={"scenes"}) | {
            "sentences": [s.sentence for s in self.scenes], "prompts": [s.prompt for s in self.scenes],
            "search_terms": [s.term for s in self.scenes]}


# 모든 장면 프롬프트 앞에 붙는 화풍. 장면마다 Claude가 화풍을 달리 쓰면 영상이 들쭉날쭉해서 코드로 고정한다
STYLE = ("Stylized 3D animated explainer, clean CGI visualization like an architecture documentary, "
         "smooth matte materials, soft even daylight, warm muted colors, same art style in every shot.")

SYSTEM = """너는 유튜브 쇼츠·릴스·틱톡용 한국어 내레이션 대본을 쓴다. 대본은 TTS가 그대로 읽고, 자막으로 화면에 뜬다. 장면 하나가 문장 하나이고, 장면 영상은 prompt로 AI 영상 생성 서비스가 만들거나 term으로 스톡 영상에서 찾는다.

- 읽었을 때 40~50초 길이. 장면은 정확히 7개, 문장마다 48~55자(모두 합쳐 350~380자). 장면마다 생성 비용이 들어 장면 수를 늘리지 않고, 장면 클립이 8초라 한 문장이 55자를 넘지 않게 한다.
- 첫 문장은 3초 안에 계속 보게 만드는 훅이다. 질문이나 의외의 사실로 시작한다.
- 말하듯 자연스러운 존댓말로 쓴다. TTS가 기호까지 읽으므로 문장에 이모지·해시태그·괄호·특수기호를 넣지 않는다.
- 숫자와 사실은 널리 확인된 것만 쓴다. 확실하지 않으면 일반론으로 말한다.
- 마지막 문장은 구독·댓글 요청이 아니라 정보의 마무리나 반전이다. 영상이 반복 재생될 때 첫 문장으로 자연스럽게 이어지게 쓴다.
- 제목은 질문형, 숫자형, 반전형, 비교형, 경고형 가운데 하나로 쓴다. 최근 제목이 주어지면 그 끝맺음과 틀(예: "~진짜 이유")을 피한다.
- prompt는 그 문장을 읽는 약 6~7초 동안 보일 한 장면을 영어 한 단락(60~90단어)으로 쓴다.
- 화풍은 실사가 아니라 건축·과학 해설 채널 같은 깔끔한 3D 애니메이션이다. 앱이 모든 prompt 앞에 같은 스타일 머리말을 붙이므로 prompt에 화풍·조명·카메라 품질 문구(photoreal, cinematic 등)를 쓰지 않는다. 사람은 얼굴을 단순화한 3D 캐릭터로 쓴다.
- 생성 서비스는 앞 프롬프트를 기억하지 않으므로 주인공·장소·시대·옷차림을 매번 다시 적어 장면이 이어지게 한다.
- 핵심 피사체와 동작은 화면 가운데, 앞 5초 안에 둔다. 영상의 양옆과 뒷부분은 잘릴 수 있다. 카메라 움직임은 하나만 쓴다(예: slow push-in, sideways truck).
- 눈에 안 보이는 원리나 수치는 숫자 대신 단면도(cutaway)와 빨간 선·화살표로 보여 준다.
- prompt는 항상 "No on-screen text, no numbers, no logos."로 끝낸다. 실존 인물의 얼굴, 브랜드, 화면비 문구는 넣지 않는다.
- term은 같은 장면을 스톡 영상에서 찾을 구체적인 영어 명사구다(예: "city night traffic", "coffee pouring"). "success" 같은 추상어는 피한다."""

# 백만 토큰당 달러(입력, 출력). 모르는 모델이면 비용을 비워 둔다.
PRICES = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10), "claude-haiku-4-5": (1, 5)}
NO_KEY = "Claude API 키가 없어요. .env에 ANTHROPIC_API_KEY를 넣고 서버를 다시 켜세요."


def cost(model: str, inp: int, out: int) -> float | None:
    price = next((p for k, p in PRICES.items() if model.startswith(k)), None)
    return round((inp * price[0] + out * price[1]) / 1e6, 4) if price else None


def add_usage(a: dict | None, b: dict | None) -> dict | None:
    """Claude 호출 사용량을 쌓는다. 비용을 모르는 모델이 섞이면 비용은 None."""
    if not a or not b:
        return a or b
    cost = None if a["cost_usd"] is None or b["cost_usd"] is None else round(a["cost_usd"] + b["cost_usd"], 4)
    return {"model": b["model"], "input_tokens": a["input_tokens"] + b["input_tokens"],
            "output_tokens": a["output_tokens"] + b["output_tokens"], "cost_usd": cost}


def ask(system: str, content, output_format, refusal: str, what: str):
    """Claude 한 번 부르고 (구조화 결과, 사용량)을 돌려준다. 대본과 주제 찾기가 같이 쓴다. 오류는 한국어 RuntimeError로."""
    # 안전 분류기가 거절하면 서버가 대체 모델로 다시 돌린다. haiku는 대상이 아니라 뺀다.
    extra = {} if "haiku" in config.CLAUDE_MODEL else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = anthropic.Anthropic().beta.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=output_format,
            **extra,
        )
    except TypeError as e:   # 키가 아예 없으면 SDK가 요청 직전에 TypeError를 낸다
        if "authentication" not in str(e):
            raise
        raise RuntimeError(NO_KEY) from None
    except anthropic.AuthenticationError:
        raise RuntimeError("Claude API 키가 맞지 않아요. .env의 ANTHROPIC_API_KEY를 확인하세요.") from None
    except anthropic.RateLimitError:
        raise RuntimeError("Claude API 요청 한도에 걸렸어요. 잠시 뒤 다시 시도하세요.") from None
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API 오류({e.status_code}): {e.message}") from None
    except anthropic.APIConnectionError:
        raise RuntimeError("Claude API에 연결하지 못했어요. 네트워크를 확인하세요.") from None
    if resp.stop_reason == "refusal":
        raise RuntimeError(refusal)
    if resp.parsed_output is None:
        raise RuntimeError(f"{what}을 받지 못했어요(stop_reason={resp.stop_reason}).")
    u = resp.usage
    # ponytail: 대체 모델이 돌았으면 응답 모델 값으로 한 번에 계산한다. 정확한 단계별 비용은 usage.iterations를 보면 된다.
    return resp.parsed_output, {"model": resp.model, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                                "cost_usd": cost(resp.model, u.input_tokens, u.output_tokens)}


class Revision(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    sentences: list[str] = Field(description="장면마다 내레이션 한 문장. 받은 장면과 같은 개수, 같은 순서")


REVISE = """

## 지금 할 일
이미 만든 대본을 사용자 요청대로 고친다. 장면 영상은 이미 만들어져 있으니 장면 수와 순서를 그대로 두고, 문장이 그 장면 화면과 어긋나지 않게 한다. 요청과 관계없는 문장·제목·설명·태그는 그대로 둔다. 위 규칙과 요청이 부딪히면 요청을 따른다."""


def revise(s: dict, note: str) -> tuple[dict, dict]:
    """완성된 대본(script.json)을 요청대로 고친다. 장면 수와 영상 프롬프트는 그대로."""
    n = len(s["sentences"])
    prompts = s.get("prompts") if len(s.get("prompts") or []) == n else [""] * n   # 예전 대본엔 없다
    scenes = "\n".join(f"{i}. {t}" + (f"\n   (화면: {p})" if p else "")
                       for i, (t, p) in enumerate(zip(s["sentences"], prompts), 1))
    text = (f"제목: {s['title']}\n설명: {s['description']}\n태그: {', '.join(s['tags'])}\n장면 {n}개:\n{scenes}"
            f"\n\n사용자 수정 요청: {note}")
    out, usage = ask(SYSTEM + REVISE, text, Revision, "Claude가 이 요청으로는 대본을 고치지 않았어요. 요청을 바꿔 보세요.", "고친 대본")
    sentences = [x.strip() for x in out.sentences]
    if len(sentences) != n or not all(sentences):
        raise RuntimeError(f"고친 대본의 장면 수가 맞지 않아요({len(sentences)}/{n}개). 다시 시도하세요.")
    return s | out.model_dump() | {"sentences": sentences}, usage


def write(topic: str, brief: str | None = None, recent: list[str] = ()) -> tuple[Script, dict]:
    """brief: 추천 주제에서 왔으면 훅·전개 방향 참고. recent: 최근 작업 제목(같은 틀을 피한다)."""
    text = f"주제: {topic}" + (f"\n\n참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:\n{brief}" if brief else "")
    if config.CHANNEL:
        text += f"\n\n채널 분야: {config.CHANNEL}. 이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다."
    if recent:
        text += "\n\n최근 제목(이 틀을 피한다):\n" + "\n".join(f"- {t}" for t in recent)
    script, usage = ask(SYSTEM, text, Script, "Claude가 이 주제로는 대본을 쓰지 않았어요. 주제를 바꿔 보세요.", "대본")
    if not script.scenes:
        raise RuntimeError("대본을 받지 못했어요(문장이 비었어요).")
    scenes = [s.model_copy(update={"prompt": f"{STYLE} {s.prompt}"}) for s in script.scenes]
    return script.model_copy(update={"scenes": scenes}), usage

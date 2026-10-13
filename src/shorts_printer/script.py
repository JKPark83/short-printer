"""1단계 대본: Claude API로 주제 하나에서 제목·설명·태그·문장·영어 검색어를 한 번에 받는다(MoneyPrinter의 gpt.py 역할)."""
import anthropic
from pydantic import BaseModel, Field

from . import config


class Script(BaseModel):
    title: str = Field(description="쇼츠 제목. 40자 이내, 해시태그 없이")
    description: str = Field(description="영상 설명 2~3문장, 끝에 해시태그 3개")
    tags: list[str] = Field(description="검색 태그 5~10개, # 없이")
    sentences: list[str] = Field(description="내레이션 문장 6~10개, 문장마다 45자 이내")
    search_terms: list[str] = Field(description="Pexels 세로 영상 검색용 영어 키워드 3~5개, 문장 흐름 순서")


SYSTEM = """너는 유튜브 쇼츠·릴스·틱톡용 한국어 내레이션 대본을 쓴다. 대본은 TTS가 그대로 읽고, 자막으로 화면에 뜨고, 영어 검색어로 찾은 무료 스톡 영상이 배경으로 깔린다.

- 읽었을 때 30~45초 길이. 문장 6~10개, 문장마다 45자 이내.
- 첫 문장은 3초 안에 계속 보게 만드는 훅이다. 질문이나 의외의 사실로 시작한다.
- 말하듯 자연스러운 존댓말로 쓴다. TTS가 기호까지 읽으므로 문장에 이모지·해시태그·괄호·특수기호를 넣지 않는다.
- 숫자와 사실은 널리 확인된 것만 쓴다. 확실하지 않으면 일반론으로 말한다.
- 마지막 문장은 구독이나 댓글을 자연스럽게 부르는 한마디다.
- search_terms는 Pexels에서 세로 영상이 잘 나오는 구체적인 영어 명사구다(예: "city night traffic", "coffee pouring"). "success" 같은 추상어는 피한다."""

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


def write(topic: str, brief: str | None = None) -> tuple[Script, dict]:
    """brief: 추천 주제에서 왔으면 훅·전개 방향 참고."""
    text = f"주제: {topic}" + (f"\n\n참고(최근 인기 쇼츠 분석에서 나온 방향): {brief}" if brief else "")
    script, usage = ask(SYSTEM, text, Script, "Claude가 이 주제로는 대본을 쓰지 않았어요. 주제를 바꿔 보세요.", "대본")
    if not script.sentences:
        raise RuntimeError("대본을 받지 못했어요(문장이 비었어요).")
    return script, usage

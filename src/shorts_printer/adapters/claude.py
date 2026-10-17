"""LLM 구현: Claude API. 대본·썸네일·주제 찾기가 같이 쓴다."""
import base64
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import anthropic
import pydantic

from .. import config

# 백만 토큰당 달러(입력, 출력). 모르는 모델이면 비용을 비워 둔다.
PRICES = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10), "claude-haiku-4-5": (1, 5)}
SEARCH_USD = 0.01   # 웹 검색 한 번
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
NO_KEY = "Claude API 키가 없어요. .env에 ANTHROPIC_API_KEY를 넣고 서버를 다시 켜세요."
BLOCKED = re.compile(r"not accessible to our user agent: \[([^\]]*)\]")


def cost(model: str, inp: int, out: int) -> float | None:
    price = next((p for k, p in PRICES.items() if model.startswith(k)), None)
    return round((inp * price[0] + out * price[1]) / 1e6, 4) if price else None


# 안전 분류기가 거절하면 서버가 대체 모델로 다시 돌린다
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


@contextmanager
def errors() -> Iterator[None]:
    """SDK 오류를 한국어 RuntimeError로. 대본·조사가 같이 쓴다."""
    try:
        yield
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
    except pydantic.ValidationError:   # 구조화 출력이라 모양이 틀리는 건 응답이 max_tokens에서 끊겼을 때뿐이다
        raise RuntimeError("Claude 응답이 너무 길어 중간에 끊겼어요. 다시 시도하세요.") from None


def with_sites(request, tools: list[dict] | None):
    """request(tools)를 부른다. 크롤러를 막는 사이트가 allowed_domains에 있으면 서버가 400으로 목록을 알려 주니,
    그 사이트만 빼고 한 번 더 부른다. (응답, 실제로 쓴 tools)."""
    try:
        return request(tools), tools
    except anthropic.BadRequestError as e:
        m = BLOCKED.search(str(e))
        if not m or not tools:
            raise
        bad = set(re.findall(r"'([^']+)'", m.group(1)))
        tools = [t | {"allowed_domains": [d for d in t["allowed_domains"] if d not in bad]} if "allowed_domains" in t
                 else t for t in tools]
        return request(tools), tools


def _image(img: bytes | str) -> dict:
    """JPEG 바이트는 base64로, 문자열은 URL로."""
    if isinstance(img, str):
        return {"type": "image", "source": {"type": "url", "url": img}}
    data = base64.standard_b64encode(img).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def stream(**kw):
    """스트리밍으로 부른다. 비스트리밍은 SDK가 max_tokens를 2만 남짓으로 막는다(10분 넘을 요청)."""
    with anthropic.Anthropic().beta.messages.stream(**kw) as s:
        return s.get_final_message()


class Claude:
    label = "Claude"

    @property
    def model(self) -> str:
        return config.CLAUDE_MODEL   # 테스트가 바꾸므로 부를 때마다 읽는다

    @property
    def hint(self) -> str:
        return self.model if self.ready() else ".env에 ANTHROPIC_API_KEY를 넣어 주세요"

    def ready(self) -> bool:
        return bool(config.secret("ANTHROPIC_API_KEY") or config.secret("ANTHROPIC_AUTH_TOKEN"))

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        return cost(self.model, input_tokens, output_tokens)

    def ask(self, system: str, text: str, schema, *, refusal: str, what: str, images: Sequence[bytes | str] = (),
            web: bool | Sequence[str] = False):
        """Claude 한 번 부르고 (구조화 결과, 사용량)을 돌려준다. 오류는 한국어 RuntimeError로."""
        model = self.model
        content = [*map(_image, images), {"type": "text", "text": text}] if images else text
        extra = FALLBACK
        # True면 어디서나, 사이트 목록이면 그 안에서만 검색한다
        tools = [WEB_SEARCH if isinstance(web, bool) else WEB_SEARCH | {"allowed_domains": list(web)}] if web else None
        messages = [{"role": "user", "content": content}]
        inp = out = searches = 0
        with errors():
            for _ in range(4):   # 검색이 길면 서버가 pause_turn으로 멈춘다. 그대로 돌려보내면 이어 간다
                resp, tools = with_sites(lambda t: stream(
                    model=model,
                    # 생각 토큰도 여기서 빠진다. 대본은 생각만 1만 토큰을 넘기도 한다
                    max_tokens=128000,   # Opus 5.5 상한
                    system=system,
                    messages=messages,
                    output_format=schema,
                    **(extra | {"tools": t} if t else extra),
                ), tools)
                u = resp.usage
                inp, out = inp + u.input_tokens, out + u.output_tokens
                searches += (u.server_tool_use.web_search_requests or 0) if u.server_tool_use else 0
                if resp.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            raise RuntimeError(refusal)
        if resp.parsed_output is None:
            raise RuntimeError(f"{what}을 받지 못했어요(stop_reason={resp.stop_reason}).")
        # ponytail: 대체 모델이 돌았으면 응답 모델 값으로 한 번에 계산한다.
        # 정확한 단계별 비용은 usage.iterations를 보면 된다.
        usd = cost(resp.model, inp, out)
        return resp.parsed_output, {"model": resp.model, "input_tokens": inp, "output_tokens": out,
                                    "cost_usd": None if usd is None else round(usd + searches * SEARCH_USD, 4)}

"""LLM 포트: 지시문과 글(그림)을 주면 정해진 pydantic 모양으로 답한다."""
from collections.abc import Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLM(Protocol):
    label: str   # 화면 이름
    model: str   # 지금 쓰는 모델 이름
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    def ask(self, system: str, text: str, schema: type[T], *, refusal: str, what: str,
            images: Sequence[bytes | str] = (), web: bool = False) -> tuple[T, dict]:
        """(구조화 결과, 사용량). images는 JPEG 바이트 또는 URL, 글 앞에 붙는다.
        web=True면 답하기 전에 인터넷을 검색해도 된다(검색 비용은 cost_usd에 더한다).
        거절하면 RuntimeError(refusal), 결과가 없으면 RuntimeError(f"{what}을 받지 못했어요…").
        오류는 모두 한국어 RuntimeError.
        사용량 = {"model", "input_tokens", "output_tokens", "cost_usd"(모르면 None)}."""

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        """지금 모델로 이만큼 쓰면 드는 달러. 모르면 None."""


def add_usage(a: dict | None, b: dict | None) -> dict | None:
    """사용량을 쌓는다. 비용을 모르는 호출이 섞이면 비용은 None."""
    if not a or not b:
        return a or b
    cost = None if a["cost_usd"] is None or b["cost_usd"] is None else round(a["cost_usd"] + b["cost_usd"], 4)
    return {"model": b["model"], "input_tokens": a["input_tokens"] + b["input_tokens"],
            "output_tokens": a["output_tokens"] + b["output_tokens"], "cost_usd": cost}

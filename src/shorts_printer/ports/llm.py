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

    # 선택: credits() -> int | None: 남은 크레딧(센트). 셀 설정이 없으면 None, 못 읽으면 한국어 RuntimeError.
    # 있으면 대시보드에 남은 금액·최근 작업 평균 비용으로 만들 수 있는 편수가 뜬다

    def ask(self, system: str, text: str, schema: type[T], *, refusal: str, what: str,
            images: Sequence[bytes | str] = (), web: bool | Sequence[str] = False) -> tuple[T, dict]:
        """(구조화 결과, 사용량). images는 JPEG 바이트 또는 URL, 글 앞에 붙는다.
        web=True면 답하기 전에 인터넷을 검색해도 된다(검색 비용은 cost_usd에 더한다).
        web에 사이트 목록을 주면 그 사이트 안에서만 검색한다.
        거절하면 RuntimeError(refusal), 결과가 없으면 RuntimeError(f"{what}을 받지 못했어요…").
        오류는 모두 한국어 RuntimeError.
        사용량 = {"model", "input_tokens", "output_tokens", "cost_usd"(모르면 None)}.
        input_tokens는 캐시에 쓰고 읽은 입력까지 더한 값이고, cost_usd만 캐시 단가로 셌다.
        그래서 저장된 사용량을 cost()로 다시 세면 캐시 읽기가 정가로 잡힌다(다시 세지 말고 cost_usd를 쓴다)."""

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        """지금 모델로 이만큼 쓰면 드는 달러(입력은 모두 정가로 센다). 모르면 None."""


class Cached(str):
    """앞부분(head)이 다른 호출과 같은 지시문. 그냥 문자열로 쓰이고(다른 공급자는 몰라도 된다), Claude만 head 끝에
    캐시 위치를 둔다. 같은 앞부분으로 5분 안에 거듭 부르는 곳(롱폼 장마다·지도 장마다·롱폼 고쳐 쓰기)에만 쓴다.
    한 번만 부르는 지시문에 쓰면 캐시 쓰기(입력의 1.25배)만 하고 읽지 못해 오히려 비싸다."""
    head: str

    def __new__(cls, head: str, tail: str = "") -> "Cached":
        s = super().__new__(cls, f"{head}\n\n{tail}" if tail else head)
        s.head = head
        return s


def add_usage(a: dict | None, b: dict | None) -> dict | None:
    """사용량을 쌓는다. 비용을 모르는 호출이 섞이면 비용은 None."""
    if not a or not b:
        return a or b
    cost = None if a["cost_usd"] is None or b["cost_usd"] is None else round(a["cost_usd"] + b["cost_usd"], 4)
    return {"model": b["model"], "input_tokens": a["input_tokens"] + b["input_tokens"],
            "output_tokens": a["output_tokens"] + b["output_tokens"], "cost_usd": cost}

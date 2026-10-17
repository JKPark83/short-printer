"""자료 조사 포트: 주제를 주면 정해진 사이트에서 찾아 출처가 붙은 사실 문장을 돌려준다.
LLM.ask와 따로 둔 까닭: 구조화 출력과 인용은 한 호출에 같이 쓸 수 없다."""
from typing import Protocol


class Researcher(Protocol):
    label: str   # 화면 이름
    hint: str    # 환경 점검 한 줄

    def ready(self) -> bool: ...

    def gather(self, system: str, text: str, *, domains: list[str], queries: int,
               max_pages: int) -> tuple[list[dict], dict]:
        """문장을 [{"text", "url", "title", "published", "retrieved_at"}]로 돌려준다. 인용이 붙은 문장은 url이 있고,
        인용 없는 문장("확인 못 함: …" 같은 메모)은 url이 ""다.
        쓴 양은 usage({"model", "input_tokens", "output_tokens", "cost_usd"(모르면 None)})로 돌려준다.
        domains 밖은 검색·열람하지 않는다(빈 목록이면 제한 없음). queries는 검색 수, max_pages는 열어 볼 쪽 수 상한.
        오류는 한국어 RuntimeError. 키 값은 메시지에 넣지 않는다."""

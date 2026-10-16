"""자료 조사 구현: Claude web_search·web_fetch에 인용을 켜고, 인용이 붙은 문장만 사실로 모은다."""
import anthropic

from .. import config
from .claude import SEARCH_USD, cost, errors, fallback, with_sites

REFUSAL = "Claude가 이 주제의 조사를 거절했어요. 주제를 바꿔 보세요."


def _source(c, fetched: list[dict]) -> dict | None:
    """인용 하나가 가리키는 페이지 {"url", "title", "retrieved_at"}. 정할 수 없으면 None."""
    if c.type == "web_search_result_location":
        return {"url": c.url, "title": getattr(c, "title", None) or "", "retrieved_at": ""}
    if c.type != "char_location" or not fetched:
        return None
    # char_location은 web_fetch로 연 문서 순번을 가리킨다. 범위 밖이면 제목으로, 그래도 없으면 마지막 문서
    i = getattr(c, "document_index", None)
    if isinstance(i, int) and 0 <= i < len(fetched):
        return fetched[i]
    title = getattr(c, "document_title", None)
    return next((f for f in fetched if title and f["title"] == title), fetched[-1])


def parse(contents: list) -> list[dict]:
    """응답들의 content(차례대로)에서 인용 있는 text만 사실로. 인용 없는 text("확인 못 함: …" 등)는 버린다."""
    fetched, facts = [], []
    for block in (b for content in contents for b in content):
        if block.type == "web_fetch_tool_result" and getattr(block.content, "type", None) == "web_fetch_result":
            r = block.content
            fetched.append({"url": r.url, "title": getattr(r.content, "title", None) or "",
                            "retrieved_at": getattr(r, "retrieved_at", None) or ""})
        elif block.type == "text" and getattr(block, "citations", None) and (text := block.text.strip()):
            src = next((s for c in block.citations if (s := _source(c, fetched))), None)
            if src:
                facts.append({"text": text, "url": src["url"], "title": src["title"], "published": "",
                              "retrieved_at": src["retrieved_at"]})
    return facts


class ClaudeResearch:
    label = "Claude 조사"

    @property
    def model(self) -> str:
        return config.CLAUDE_MODEL   # 테스트가 바꾸므로 부를 때마다 읽는다

    @property
    def hint(self) -> str:
        return f"{self.model} 웹 검색·열람" if self.ready() else ".env에 ANTHROPIC_API_KEY를 넣어 주세요"

    def ready(self) -> bool:
        return bool(config.secret("ANTHROPIC_API_KEY") or config.secret("ANTHROPIC_AUTH_TOKEN"))

    def gather(self, system: str, text: str, *, domains: list[str], queries: int,
               max_pages: int) -> tuple[list[dict], dict]:
        model = self.model
        # 인용은 구조화 출력(output_format)과 같이 못 쓰니 글로 받아 인용 블록을 읽는다
        tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": queries, "allowed_domains": domains},
            {"type": "web_fetch_20260309", "name": "web_fetch", "max_uses": max_pages, "allowed_domains": domains,
             "citations": {"enabled": True}, "max_content_tokens": 8000, "use_cache": False},
        ]
        messages = [{"role": "user", "content": text}]
        contents, inp, out, searches = [], 0, 0, 0
        with errors():
            for _ in range(4):   # 검색이 길면 서버가 pause_turn으로 멈춘다. 그대로 돌려보내면 이어 간다
                resp, tools = with_sites(lambda t: anthropic.Anthropic().beta.messages.create(
                    model=model, max_tokens=8000, system=system, messages=messages, tools=t, **fallback(model)), tools)
                u = resp.usage
                inp, out = inp + u.input_tokens, out + u.output_tokens
                searches += (u.server_tool_use.web_search_requests or 0) if u.server_tool_use else 0
                contents.append(resp.content)
                if resp.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            raise RuntimeError(REFUSAL)
        usd = cost(resp.model, inp, out)   # web_fetch는 토큰 말고 따로 안 받는다
        return parse(contents), {"model": resp.model, "input_tokens": inp, "output_tokens": out,
                                 "cost_usd": None if usd is None else round(usd + searches * SEARCH_USD, 4)}

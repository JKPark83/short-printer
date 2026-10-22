"""자료 조사 구현: Claude web_search·web_fetch에 인용을 켜고, 인용이 붙은 문장만 사실로 모은다."""
import re

from .. import config
from .claude import FALLBACK, SEARCH_USD, cost, errors, stream, with_sites

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


def _note(text: str) -> dict:
    return {"text": text, "url": "", "title": "", "published": "", "retrieved_at": ""}


def _norm(text: str) -> str:
    return " ".join(text.split())


def _verbatim(text: str, cites) -> bool:
    """인용 조각이 다른 언어 원문을 그대로 옮긴 것인지. 그렇다면 사실 문장이 아니라 quote로 뺀다.
    사실 문장은 한국어로 쓰므로 한글이 든 조각은 문장 일부(원문 구절·숫자 인용)라 그대로 둔다."""
    t = _norm(text)
    if re.search("[가-힣]", t):
        return False
    return any(t and (t in (c := _norm(getattr(x, "cited_text", None) or "")) or (c and c in t)) for x in cites)


def parse(contents: list) -> list[dict]:
    """응답들의 content(차례대로)에서 인용 있는 줄은 사실로, 인용 없는 줄("확인 못 함: …" 등)은 url 없는 메모로.
    도구 호출 수와 도구 오류도 메모로 남겨, 못 찾았을 때 검색이 막힌 건지 자료가 없는 건지 알 수 있게 한다.
    인용을 켜면 text 블록이 인용 경계에서 쪼개져 "한국어 문장 / 원문 조각(인용) / (근거 꼬리표)"로 온다.
    그래서 줄바꿈까지 블록을 이어 사실 한 줄로 합치고, 원문을 그대로 옮긴 인용 조각은 문장에서 빼 quote에 둔다."""
    fetched, facts, calls, errs = [], [], {}, []   # errs: 검색어마다 결과 수와 도구 오류(왜 못 찾았는지)
    n = {"web_search": 0, "web_fetch": 0}
    line, quotes, src = [], [], None   # 지금 모으는 줄: 문장 조각, 원문 인용 조각, 첫 출처

    def flush():
        nonlocal line, quotes, src
        text = _norm("".join(line))
        # 문장이 꼬리표·구두점뿐이면(인용 조각이 곧 사실 문장) 인용 조각을 문장에 둔다
        if quotes and not re.sub(r"\([^)]*\)|[\s.,]", "", text):
            text, quotes = _norm(" ".join([*quotes, text])), []
        if text and src:
            q = {"quote": " … ".join(quotes)} if quotes else {}
            facts.append({"text": text, "url": src["url"], "title": src["title"], "published": "",
                          "retrieved_at": src["retrieved_at"]} | q)
        elif text:   # 왜 못 찾았는지 화면에 보여 주려고 남긴다
            facts.append(_note(text))
        line, quotes, src = [], [], None

    for block in (b for content in contents for b in [*content, None]):   # None: 응답 끝에서 줄을 닫는다
        if block is None or block.type != "text":
            flush()
        if block is None:
            continue
        if block.type == "server_tool_use":
            calls[block.id] = block.input.get("query") or block.input.get("url") or ""
        elif block.type in ("web_search_tool_result", "web_fetch_tool_result"):
            tool = block.type.removesuffix("_tool_result")
            n[tool] += 1
            c = block.content
            code = getattr(c, "error_code", None) if "error" in (getattr(c, "type", None) or "") else None
            if code:
                what = "검색" if tool == "web_search" else "열람"
                errs.append(f"{what} '{calls.get(block.tool_use_id, '')}' 오류: {code}")
            elif tool == "web_search":
                errs.append(f"검색 '{calls.get(block.tool_use_id, '')}': {len(c) if isinstance(c, list) else 0}건")
            elif tool == "web_fetch" and getattr(c, "type", None) == "web_fetch_result":
                fetched.append({"url": c.url, "title": getattr(c.content, "title", None) or "",
                                "retrieved_at": getattr(c, "retrieved_at", None) or ""})
        elif block.type == "text":
            cites = getattr(block, "citations", None) or ()
            s = next((s for c in cites if (s := _source(c, fetched))), None)
            for i, part in enumerate(block.text.split("\n")):
                if i:   # 줄이 바뀌면 앞 줄을 닫는다
                    flush()
                if s and _verbatim(part, cites):
                    quotes.append(_norm(part))
                else:
                    line.append(part)
                if part.strip():
                    src = src or s
    summary = _note(f"도구: 검색 {n['web_search']}번, 열람 {n['web_fetch']}쪽")
    return [summary, *map(_note, errs), *facts]


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
        where = {"allowed_domains": domains} if domains else {}   # 빈 목록 = 제한 없음
        # web_fetch는 기본 버전(20250910)을 쓴다. 동적 필터링 버전(20260209 이후)은 코드 실행 안에서 페이지를 열어
        # 인용(citation)이 붙지 않아 사실이 전부 메모로 떨어진다. 대신 max_content_tokens로 길이를 막는다
        tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": queries} | where,
            {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": max_pages,
             "citations": {"enabled": True}, "max_content_tokens": 8000} | where,
        ]
        messages = [{"role": "user", "content": text}]
        contents, inp, out, searches = [], 0, 0, 0
        with errors():
            for _ in range(4):   # 검색이 길면 서버가 pause_turn으로 멈춘다. 그대로 돌려보내면 이어 간다
                resp, tools = with_sites(lambda t: stream(   # Opus 5.5 상한. 스트리밍이라야 SDK가 막지 않는다
                    model=model, max_tokens=128000, system=system, messages=messages, tools=t, **FALLBACK), tools)
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

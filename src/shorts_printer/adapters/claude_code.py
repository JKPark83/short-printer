"""LLM·자료 조사 구현: Claude Code CLI(`claude -p`). API 키 대신 Claude 구독 사용량으로 돈다.
대본(script.llm)·주제 찾기(trends.llm)·자료 조사(research.provider)에 쓴다."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pydantic
from pydantic import BaseModel

from .. import config
from ..infra.store import redact

CLI = shutil.which("claude") or str(Path.home() / ".claude/local/claude")   # 셸 alias는 서버에서 안 보인다
TIMEOUT = 1200   # 대본은 생각이 길어 몇 분씩 걸린다
# 프로젝트·사용자 설정(CLAUDE.md·훅·MCP·스킬)을 읽지 않고 답만 받는다. 도구는 웹 검색 때 WebSearch만 켠다
FLAGS = ["--output-format", "json", "--setting-sources", "", "--strict-mcp-config",
         "--disable-slash-commands", "--no-session-persistence"]
WEB = "필요하면 답하기 전에 WebSearch로 찾는다. 검색은 {n}번까지만 한다."   # 기본 5: Claude WEB_SEARCH max_uses와 같게
RESEARCH_TIMEOUT = 1800   # 하위 에이전트까지 돌리는 조사는 오래 걸린다
# PreToolUse 훅: 모델이 WebSearch에 무엇을 넣든 allowed_domains를 허용 사이트로 덮어쓴다(API처럼 강제)
HOOK = ("import json,sys; i=json.load(sys.stdin)['tool_input']; i.pop('blocked_domains', None); "
        "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow', "
        "'updatedInput': i | {'allowed_domains': %s}}}))")


def _only(domains: Sequence[str]) -> str:
    """--settings 값: WebSearch마다 HOOK을 돌린다."""
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(HOOK % json.dumps(list(domains)))}"
    hook = {"matcher": "WebSearch", "hooks": [{"type": "command", "command": cmd}]}
    return json.dumps({"hooks": {"PreToolUse": [hook]}})


class ClaudeCode:
    label = "Claude Code"

    def __init__(self, effort: str | None = None):
        self._effort = effort   # 비우면 .env CLAUDE_CODE_EFFORT. 주제 찾기는 medium(high는 20분씩 걸렸다)

    @property
    def effort(self) -> str:
        return self._effort or config.CLAUDE_CODE_EFFORT

    @property
    def model(self) -> str:
        return config.CLAUDE_CODE_MODEL

    @property
    def hint(self) -> str:
        if not self.ready():
            return "Claude Code를 설치하고 claude 로그인(구독)을 해 주세요"
        return f"{self.model} · {self.effort}"

    def ready(self) -> bool:
        return Path(CLI).exists()

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        return 0.0   # 구독 사용량이라 따로 들지 않는다

    def ask(self, system: str, text: str, schema, *, refusal: str, what: str, images: Sequence[bytes | str] = (),
            web: bool | Sequence[str] = False, searches: int = 5, pages: int = 0, agents: dict | None = None,
            timeout: int = TIMEOUT):
        """pages를 주면 WebFetch도 켠다. agents({이름: {description, prompt, tools}})를 주면 Agent 도구로
        하위 에이전트를 띄울 수 있다(딥리서치). 둘 다 web이 있을 때만."""
        # ponytail: 그림은 안 넘긴다(대본·주제 찾기는 안 쓴다). 썸네일에 쓰려면 stream-json 입력으로 넓힌다
        if images:
            raise RuntimeError("Claude Code 공급자는 그림을 못 받아요. 채널 llm은 claude로 두세요")
        tools = ["--tools", ""]
        if web:   # -p에는 묻는 사람이 없어 allowedTools로 미리 허락해야 검색한다
            names = ",".join(["WebSearch", *(["WebFetch"] if pages else []), *(["Agent"] if agents else [])])
            tools = ["--tools", names, "--allowedTools", names]
            system += "\n\n" + WEB.format(n=searches)
            if pages:
                system += f" 페이지는 WebFetch로 {pages}쪽까지만 연다."
            if agents:
                tools += ["--agents", json.dumps(agents, ensure_ascii=False)]
            if not isinstance(web, bool):   # 사이트 제한 CLI 옵션이 없어 훅으로 건다(--setting-sources ""여도 돈다)
                tools += ["--settings", _only(web)]
                system += f" 검색 결과는 다음 사이트(하위 도메인 포함)에서만 나온다: {', '.join(web)}."
        cmd = [CLI, "-p", *FLAGS, *tools, "--model", self.model, "--effort", self.effort,
               "--system-prompt", system, "--json-schema", json.dumps(schema.model_json_schema())]
        # API 키가 환경에 있으면 CLI가 구독 대신 API로 과금한다(.env를 os.environ에 읽어 둔다)
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=timeout, env=env,
                               cwd=tempfile.gettempdir())   # 이 프로젝트의 CLAUDE.md를 읽지 않게
        except FileNotFoundError:
            raise RuntimeError(self.hint) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude Code가 {timeout // 60}분 안에 답하지 않았어요. 다시 시도하세요.") from None
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            msg = redact((r.stderr or r.stdout).strip()[-300:])
            raise RuntimeError(f"Claude Code 실행 실패: {msg}") from None
        if out.get("is_error"):   # 구독 한도·로그인 만료도 여기로 온다
            raise RuntimeError(f"Claude Code 오류: {redact(str(out.get('result')))[:300]}")
        if out.get("stop_reason") == "refusal":
            raise RuntimeError(refusal)
        if out.get("structured_output") is None:
            raise RuntimeError(f"{what}을 받지 못했어요(stop_reason={out.get('stop_reason')}).")
        try:
            parsed = schema.model_validate(out["structured_output"])
        except pydantic.ValidationError:
            raise RuntimeError(f"{what} 모양이 틀렸어요. 다시 시도하세요.") from None
        u = out.get("usage") or {}
        inp = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        return parsed, {"model": self.model, "input_tokens": inp, "output_tokens": u.get("output_tokens") or 0,
                        "cost_usd": 0.0}


# 자료 조사: API의 citation이 없어 모델이 적은 URL을 믿는다.
# 대신 하위 에이전트를 병렬로 띄워 주장마다 깊게 찾는다(딥리서치)
RESEARCH = ("이 환경에는 citation 기능이 없다. 지시문의 열람·web_fetch는 WebFetch 도구로 한다. "
            "먼저 확인할 주장을 2~4묶음으로 나눠 researcher 하위 에이전트를 Agent 도구로 한꺼번에(병렬로) 띄워 맡기고, "
            "돌아온 사실을 합친다. 모자란 것만 직접 더 찾는다. "
            "사실은 검색 결과나 연 페이지에 적힌 것만 쓰고, url 칸에 그 페이지의 URL을 적는 것이 인용이다. "
            "숫자·조건은 적힌 그대로 옮긴다. title은 페이지 제목, published는 게시일(YYYY-MM-DD, 모르면 빈 칸). "
            "quote는 적지 않는다(WebFetch가 요약해 주어 원문이 아니다). "
            "확인 못 한 주장·막힌 검색은 facts가 아니라 notes에 적는다.")
RESEARCHER = ("너는 자료 조사원이다. 맡은 주장을 WebSearch로 찾고 쓸 페이지는 WebFetch로 열어 본문에서 확인한다. "
              "확인된 사실마다 한국어 한 문장과 그 페이지 URL·제목·게시일을 적어 돌려주고, "
              "못 찾은 주장은 그렇다고 적는다. "
              "숫자·조건은 페이지에 적힌 그대로 옮기고 출처가 쓴 강도보다 세게 말하지 않는다.")


class _Fact(BaseModel):
    text: str
    url: str = ""
    title: str = ""
    published: str = ""


class _Found(BaseModel):
    facts: list[_Fact]
    notes: list[str] = []


def _note(text: str) -> dict:
    return {"text": text, "url": "", "title": "", "published": "", "retrieved_at": ""}


class ClaudeCodeResearch:
    label = "Claude Code 조사"

    @property
    def hint(self) -> str:
        if not Path(CLI).exists():
            return "Claude Code를 설치하고 claude 로그인(구독)을 해 주세요"
        return (f"{config.CLAUDE_CODE_MODEL} · {config.CLAUDE_CODE_RESEARCH_EFFORT} "
                "하위 에이전트 검색·열람(본문 대조 안 함)")

    def ready(self) -> bool:
        return Path(CLI).exists()

    def gather(self, system: str, text: str, *, domains: list[str], queries: int,
               max_pages: int) -> tuple[list[dict], dict]:
        where = f" 검색·열람은 다음 사이트(하위 도메인 포함) 안에서만 한다: {', '.join(domains)}." if domains else ""
        agents = {"researcher": {"description": "주장 묶음 하나를 웹에서 확인해 출처 있는 사실로 돌려준다",
                                 "prompt": RESEARCHER + where, "tools": ["WebSearch", "WebFetch"]}}
        found, usage = ClaudeCode(config.CLAUDE_CODE_RESEARCH_EFFORT).ask(
            system + "\n\n" + RESEARCH, text, _Found, refusal="Claude Code가 이 주제의 조사를 거절했어요.",
            what="조사 결과", web=domains or True, searches=queries, pages=max_pages, agents=agents,
            timeout=RESEARCH_TIMEOUT)
        facts, notes, out = [], list(found.notes), 0
        today = date.today().isoformat()
        for f in (f for f in found.facts if f.text.strip()):
            host = (urlsplit(f.url).hostname or "").removeprefix("www.")
            if not host:
                notes.append(f.text)   # 주소 없는 사실은 확인 안 된 메모로
            elif domains and not any(host == d or host.endswith("." + d) for d in domains):
                out += 1   # 허용 사이트 밖은 코드가 버린다
            else:
                facts.append({"text": f.text, "url": f.url, "title": f.title, "published": f.published,
                              "retrieved_at": today})
        summary = f"Claude Code 조사: 출처 있는 사실 {len(facts)}개" + (f", 범위 밖 출처 {out}건 뺌" if out else "")
        return [_note(summary), *map(_note, notes), *facts], usage

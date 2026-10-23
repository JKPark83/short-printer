"""LLM 구현: Claude Code CLI(`claude -p`). API 키 대신 Claude 구독 사용량으로 돈다. 대본(script.llm)에 쓴다."""
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pydantic

from .. import config
from ..infra.store import redact

CLI = shutil.which("claude") or str(Path.home() / ".claude/local/claude")   # 셸 alias는 서버에서 안 보인다
TIMEOUT = 1200   # 대본은 생각이 길어 몇 분씩 걸린다
# 프로젝트·사용자 설정(CLAUDE.md·훅·MCP·스킬)을 읽지 않고 도구 없이 답만 받는다
FLAGS = ["--output-format", "json", "--tools", "", "--setting-sources", "", "--strict-mcp-config",
         "--disable-slash-commands", "--no-session-persistence"]


class ClaudeCode:
    label = "Claude Code"

    @property
    def model(self) -> str:
        return config.CLAUDE_CODE_MODEL

    @property
    def hint(self) -> str:
        if not self.ready():
            return "Claude Code를 설치하고 claude 로그인(구독)을 해 주세요"
        return f"{self.model} · {config.CLAUDE_CODE_EFFORT}"

    def ready(self) -> bool:
        return Path(CLI).exists()

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        return 0.0   # 구독 사용량이라 따로 들지 않는다

    def ask(self, system: str, text: str, schema, *, refusal: str, what: str, images: Sequence[bytes | str] = (),
            web: bool | Sequence[str] = False):
        # ponytail: 그림·웹 검색은 안 넘긴다(대본은 안 쓴다). 썸네일·주제 찾기에 쓰려면 --tools WebSearch 등으로 넓힌다
        if images or web:
            raise RuntimeError("Claude Code 공급자는 그림·웹 검색을 못 해요. 채널 llm은 claude로 두세요")
        cmd = [CLI, "-p", *FLAGS, "--model", self.model, "--effort", config.CLAUDE_CODE_EFFORT,
               "--system-prompt", system, "--json-schema", json.dumps(schema.model_json_schema())]
        # API 키가 환경에 있으면 CLI가 구독 대신 API로 과금한다(.env를 os.environ에 읽어 둔다)
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=TIMEOUT, env=env,
                               cwd=tempfile.gettempdir())   # 이 프로젝트의 CLAUDE.md를 읽지 않게
        except FileNotFoundError:
            raise RuntimeError(self.hint) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude Code가 {TIMEOUT // 60}분 안에 답하지 않았어요. 다시 시도하세요.") from None
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

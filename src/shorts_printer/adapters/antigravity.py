"""LLM·자료 조사 구현: Antigravity CLI(`agy -p`). API 키 대신 Google 로그인 구독으로 돈다.
system 플래그가 없어 지시문을 프롬프트 맨 앞에 넣는다. 아래 짧은 규칙 문구는 공급자 차이(도구 이름·인용 방식)를
흡수하는 접착제라 prompts/가 아니라 여기 둔다."""
import contextlib
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pydantic
from pydantic import BaseModel

from .. import config
from ..infra.store import redact

CLI = shutil.which("agy") or str(Path.home() / ".local/bin/agy")   # 서버 PATH에 ~/.local/bin이 없을 수 있다
TIMEOUT = 1200   # 대본은 생각이 길어 몇 분씩 걸린다
RESEARCH_TIMEOUT = 1800   # 조사는 다른 agy와 함께 돌 때 13분까지 걸렸다
MAX_PROMPT = 900_000   # 프롬프트를 인자 하나로 넘겨 ARG_MAX(1MB)에 걸린다. stdin은 stream-json만 받는다
HINT = "Antigravity CLI(agy)를 설치하고 로그인해 주세요"
NO_SHELL = "터미널 명령은 실행하지 않는다(이 환경에서는 거부된다). 파일도 만들거나 고치지 않는다."
NO_WEB = "검색·도구를 쓰지 말고 바로 답한다."
# Claude WEB_SEARCH max_uses와 같게. 없으면 30번 넘게 검색하다 시간이 다 된다
WEB = "필요하면 답하기 전에 웹을 검색한다. 웹 검색은 5번까지만 한다."
# ponytail: headless agy에는 페이지 읽기 도구가 없어 사실이 검색 결과 요약에서만 온다. 페이지 본문과 맞는지는
# 확인하지 않는다(quote 15개 중 2개만 본문에 있었다). 읽기 도구를 --settings로 열 수 있으면 web_fetch 규칙을 되살린다
RESEARCH = ("이 환경에는 citation 기능도 페이지 읽기 도구(web_fetch)도 없다. 지시문의 열람·web_fetch 규칙은 건너뛴다. "
            "사실은 검색 결과 요약에 적힌 것만 쓰고, url 칸에 그 요약이 가리키는 검색 결과의 URL을 적는 것이 인용이다. "
            "숫자·조건은 요약에 적힌 그대로 옮긴다. title은 페이지 제목, published는 게시일(YYYY-MM-DD, 모르면 빈 칸). "
            "quote는 적지 않는다(요약은 원문이 아니다). "
            "요약에서 확인 못 한 주장·막힌 검색은 facts가 아니라 notes에 적는다.")


def _obj(word: str) -> str:
    """목적격 조사: 받침이 있으면 을, 없으면 를."""
    c = ord(word[-1]) - 0xAC00 if word else -1
    return "을" if 0 <= c < 11172 and c % 28 else "를"


# ponytail: 사이트 제한은 지시문으로만 건다(agy에 허용 도메인 설정이 없다). ask의 답은 코드로 거르지 않는다
def _sites(domains: Sequence[str]) -> str:
    return (f"웹 검색·열람은 다음 사이트(하위 도메인 포함) 안에서만 한다: {', '.join(domains)}. "
            "그 밖의 결과는 쓰지 않는다.")


def _parse(stdout: str) -> dict | None:
    """stdout의 마지막 JSON 줄. 도구가 막히면 앞에 "jetski: …" 경고 줄이 섞인다."""
    for line in reversed(stdout.splitlines()):
        if line.startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                return json.loads(line)
    return None


def _run(system: str, text: str, rules: list[str], schema: dict, what: str,
         timeout: int = TIMEOUT) -> tuple[dict, dict]:
    """agy를 한 번 부른다. (structured_output, 사용량)."""
    prompt = (f"[지시문]\n{system}\n[지시문 끝]\n\n[실행 규칙]\n" + "\n".join([*rules, NO_SHELL])
              + f"\n\n[요청]\n{text}")
    if (size := len(prompt.encode())) > MAX_PROMPT:
        raise RuntimeError(f"Antigravity에 넘길 글이 너무 길어요({size // 1000}KB). 참고 글을 줄여 주세요.")
    model, effort = config.ANTIGRAVITY_MODEL, config.ANTIGRAVITY_EFFORT
    cmd = [CLI, "--output-format", "json", "--disable-slash-commands", "--model", model,
           *(["--effort", effort] if effort else []), "--json-schema", json.dumps(schema),
           "--print-timeout", f"{timeout}s", f"-p={prompt}"]   # -p 뒤에 띄우면 다음 플래그를 프롬프트로 못 읽는다
    late = f"Antigravity가 {timeout // 60}분 안에 답하지 않았어요. 다시 시도하세요."
    # 빈 임시 폴더에서 돌려 이 프로젝트의 GEMINI.md·AGENTS.md를 읽지 않고, 호출마다 깨끗하게
    # ponytail: agy에 기록 끄기 플래그가 없어 대화가 ~/.gemini/antigravity-cli/{conversations,brain}에 쌓인다.
    # 디스크가 문제되면 응답의 conversation_id로 그 폴더를 지운다
    with tempfile.TemporaryDirectory() as cwd:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60, cwd=cwd)
        except FileNotFoundError:
            raise RuntimeError(HINT) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(late) from None
        except (ValueError, OSError) as e:   # 인자에 NUL 바이트, E2BIG 등
            raise RuntimeError(f"Antigravity를 실행하지 못했어요: {type(e).__name__}") from None
    out = _parse(r.stdout)
    # agy가 먼저 끊으면 영어 중단 문구나 빈·덜 된 답을 준다. 모양 맞는 답이 왔으면 그대로 쓴다
    if "print timeout" in (r.stderr or "") and (out or {}).get("structured_output") is None:
        raise RuntimeError(late)
    if out is None:
        msg = redact((r.stderr or r.stdout).strip()[-300:])
        raise RuntimeError(f"Antigravity 실행 실패: {msg}")
    if out.get("status") != "SUCCESS":   # 로그인 만료·한도도 여기로 온다
        msg = redact(str(out.get("error") or out.get("response") or out.get("status")))[:300]
        raise RuntimeError(f"Antigravity 오류: {msg}")
    data = out.get("structured_output")
    if data is None:
        if denied := out.get("denied_actions"):   # headless라 권한을 물을 수 없어 저절로 거부된다
            names = ", ".join(str(d.get("display_name") or d.get("action")) for d in denied)
            raise RuntimeError(f"Antigravity가 허용되지 않은 도구({names})를 쓰려다 멈췄어요. 다시 시도하세요.")
        said = redact(str(out.get("response") or "")).strip()[:100]
        raise RuntimeError(f"{what}{_obj(what)} 받지 못했어요(빈 응답이거나 모양 없는 답: {said or '없음'}).")
    u = out.get("usage") or {}
    return data, {"model": model, "input_tokens": (u.get("input_tokens") or 0) + (u.get("cache_read_tokens") or 0),
                  "output_tokens": (u.get("output_tokens") or 0) + (u.get("thinking_tokens") or 0), "cost_usd": 0.0}


class Antigravity:
    label = "Antigravity"

    @property
    def model(self) -> str:
        return config.ANTIGRAVITY_MODEL

    @property
    def hint(self) -> str:
        if not self.ready():
            return HINT
        return self.model + (f" · {config.ANTIGRAVITY_EFFORT}" if config.ANTIGRAVITY_EFFORT else "")

    def ready(self) -> bool:
        return Path(CLI).exists()

    def cost(self, input_tokens: int, output_tokens: int) -> float | None:
        return 0.0   # 구독 사용량이라 따로 들지 않는다

    def ask(self, system: str, text: str, schema, *, refusal: str, what: str, images: Sequence[bytes | str] = (),
            web: bool | Sequence[str] = False):
        # ponytail: 그림은 안 넘긴다(core가 안 쓴다). 쓰려면 임시 폴더에 jpg를 쓰고 view_file로 열라고 적는다
        if images:
            raise RuntimeError("Antigravity 공급자는 그림을 못 받아요. 채널 llm은 claude로 두세요")
        # ponytail: 거절 신호가 출력에 없어 refusal은 쓰지 않는다. 거절도 "받지 못했어요"로 뜬다
        rules = [NO_WEB] if not web else [WEB] if web is True else [WEB, _sites(web)]
        data, usage = _run(system, text, rules, schema.model_json_schema(), what)
        try:
            return schema.model_validate(data), usage
        except pydantic.ValidationError:
            raise RuntimeError(f"{what} 모양이 틀렸어요. 다시 시도하세요.") from None


class _Fact(BaseModel):
    text: str
    url: str = ""
    title: str = ""
    published: str = ""


class _Found(BaseModel):
    facts: list[_Fact]
    notes: list[str] = []


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None   # 따라가지 않고 HTTPError로 Location을 읽는다


def _resolve(url: str) -> str:
    """검색 근거 주소(vertexaisearch 리다이렉트)를 실제 페이지 주소로. 못 풀면 그대로(허용 사이트 검사에서 빠진다)."""
    if urlsplit(url).hostname != "vertexaisearch.cloud.google.com":
        return url
    try:
        urllib.request.build_opener(_NoFollow).open(urllib.request.Request(url, method="HEAD"), timeout=10)
    except urllib.error.HTTPError as e:
        return e.headers.get("Location") or url
    except OSError:
        pass
    return url


def _note(text: str) -> dict:
    return {"text": text, "url": "", "title": "", "published": "", "retrieved_at": ""}


class AntigravityResearch:
    label = "Antigravity 조사"

    @property
    def hint(self) -> str:
        return f"{config.ANTIGRAVITY_MODEL} 웹 검색(요약만, 페이지 본문 대조 안 함)" if self.ready() else HINT

    def ready(self) -> bool:
        return Path(CLI).exists()

    def gather(self, system: str, text: str, *, domains: list[str], queries: int,
               max_pages: int) -> tuple[list[dict], dict]:
        rules = [RESEARCH, f"검색은 {queries}번까지만 한다."]   # 열 도구가 없어 max_pages는 쓰지 않는다
        rules += [_sites(domains)] if domains else []
        data, usage = _run(system, text, rules, _Found.model_json_schema(), "조사 결과", RESEARCH_TIMEOUT)
        try:
            found = _Found.model_validate(data)
        except pydantic.ValidationError:
            raise RuntimeError("조사 결과 모양이 틀렸어요. 다시 시도하세요.") from None
        # 인용을 서버가 붙여 주지 않아 모델이 적은 url을 믿는다. 허용 사이트 밖은 코드로 거른다
        facts, notes, out = [], list(found.notes), 0
        today = date.today().isoformat()
        for f in (f for f in found.facts if f.text.strip()):
            f.url = _resolve(f.url) if f.url else f.url   # 웹 검색 결과는 구글 리다이렉트 주소로 온다
            host = (urlsplit(f.url).hostname or "").removeprefix("www.")
            if not host:
                notes.append(f.text)   # 주소 없는 사실은 확인 안 된 메모로
            elif domains and not any(host == d or host.endswith("." + d) for d in domains):
                out += 1
            else:
                facts.append({"text": f.text, "url": f.url, "title": f.title, "published": f.published,
                              "retrieved_at": today})   # quote는 검색 요약이라 원문인 척 내보내지 않는다
        summary = f"Antigravity 조사: 출처 있는 사실 {len(facts)}개" + (f", 범위 밖 출처 {out}건 뺌" if out else "")
        return [_note(summary), *map(_note, notes), *facts], usage

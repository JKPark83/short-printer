"""자료 조사: 채널이 허용한 사이트에서 사실과 출처를 모아 facts.json 모양으로. 대본은 이 사실만 쓴다(다음 단계)."""
from datetime import datetime
from urllib.parse import urlsplit

from ..ports.research import Researcher
from . import prompts
from .channel import LANGS, Channel

MAX_FACTS = 12


def system(ch: Channel) -> str:
    langs = ch.research.languages or [ch.language]
    return prompts.render("research", today=datetime.now().astimezone().date().isoformat(),
                          search_langs=", ".join(LANGS.get(c, c) for c in langs), max_facts=MAX_FACTS,
                          news_sites=", ".join(ch.research.news) or "없음")


def _site(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.")


def sites(ch: Channel) -> list[str]:
    """채널이 허용한 검색 사이트(공식 + 보도). 조사와 주제 찾기가 같은 목록을 쓴다."""
    return list(dict.fromkeys(ch.research.domains + ch.research.news))


def gather(rs: Researcher, ch: Channel, topic: str, brief: str | None) -> tuple[dict, dict]:
    """(facts.json 문서, 사용량). 사실마다 F1부터 번호, 사이트, 공식/보도 구분을 붙인다."""
    r = ch.research
    domains = sites(ch)
    if not domains:
        raise RuntimeError("채널에 조사 사이트([research] domains)가 없어요. channel.toml에 허용 사이트를 넣어 주세요.")
    text = f"주제: {topic}" + (f"\n\n확인할 주장·참고:\n{brief}" if brief else "")
    raw, usage = rs.gather(system(ch), text, domains=domains, queries=r.queries_per_topic, max_pages=r.max_pages)
    uniq: dict[str, dict] = {}
    for f in raw:
        uniq.setdefault(f["text"], f)   # 같은 문장은 첫 것만
    at = datetime.now().astimezone().isoformat(timespec="seconds")
    facts = []
    for i, f in enumerate(uniq.values(), 1):
        site = _site(f["url"])
        news = any(site == n or site.endswith("." + n) for n in r.news)
        facts.append({"id": f"F{i}", "text": f["text"], "url": f["url"], "title": f.get("title") or "", "site": site,
                      "kind": "news" if news else "official", "published": f.get("published") or "",
                      "retrieved_at": f.get("retrieved_at") or at})
    if not facts:
        raise RuntimeError("자료를 찾지 못했어요. 주제를 바꾸거나 다시 시도해 주세요.")
    # 어댑터가 검색어를 돌려주지 않아 비워 둔다(문서 모양은 맞춘다)
    return {"queries": [], "facts": facts}, usage


def sheet(facts: list[dict]) -> str:
    """대본에 넘길 사실 시트. 토큰을 아끼려고 URL은 뺀다. 보도는 끝에 표시해 공식 자료와 구별한다."""
    return "\n".join(f"{f['id']}. {f['text']}" + (" (보도)" if f["kind"] == "news" and "보도" not in f["text"] else "")
                     for f in facts)

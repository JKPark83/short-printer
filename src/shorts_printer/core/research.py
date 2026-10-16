"""자료 조사: 채널이 허용한 사이트에서 사실과 출처를 모아 facts.json 모양으로. 대본은 이 사실만 쓴다(다음 단계)."""
from datetime import datetime
from urllib.parse import urlsplit

from ..ports.research import Researcher
from . import prompts
from .channel import LANGS, Channel

MAX_FACTS = 12


def system(ch: Channel) -> str:
    langs = ch.research.languages or [ch.language]
    # 어디까지 검색하는지: open이면 블로그·일반 웹 규칙(research_open.md)을 덧붙이고, 아니면 앱이 사이트를 막는다
    scope = prompts.render("research_open", sites=", ".join(ch.research.domains) or "없음") if ch.research.open else ""
    return prompts.render("research", today=datetime.now().astimezone().date().isoformat(),
                          search_langs=", ".join(LANGS.get(c, c) for c in langs), max_facts=MAX_FACTS,
                          news_sites=", ".join(ch.research.news) or "없음", scope=scope,
                          queries=ch.research.queries_per_topic, max_pages=ch.research.max_pages)


def _site(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.")


def sites(ch: Channel) -> list[str]:
    """채널이 허용한 검색 사이트(공식 + 보도). 조사와 주제 찾기가 같은 목록을 쓴다. open이면 제한이 없으니 빈 목록."""
    return [] if ch.research.open else list(dict.fromkeys(ch.research.domains + ch.research.news))


def _kind(site: str, news: list[str], domains: list[str]) -> str:
    """보도·공식·그 밖(open일 때 블로그 등)."""
    def within(hosts):
        return any(site == h or site.endswith("." + h) for h in hosts)
    return "news" if within(news) else "official" if within(domains) else "web"


def gather(rs: Researcher, ch: Channel, topic: str, brief: str | None) -> tuple[dict, dict]:
    """(facts.json 문서, 사용량). 사실마다 F1부터 번호, 사이트, 공식/보도 구분을 붙인다.
    인용 없는 문장은 notes에 둔다(못 찾은 이유가 거기 적혀 있다). 사실이 없어도 돌려준다: 멈출지는 부른 쪽이 정한다."""
    r = ch.research
    domains = sites(ch)
    if not domains and not r.open:
        raise RuntimeError("채널에 조사 사이트([research] domains)가 없어요. channel.toml에 허용 사이트를 넣어 주세요.")
    text = f"주제: {topic}" + (f"\n\n확인할 주장·참고:\n{brief}" if brief else "")
    raw, usage = rs.gather(system(ch), text, domains=domains, queries=r.queries_per_topic, max_pages=r.max_pages)
    uniq: dict[str, dict] = {}
    notes = list(dict.fromkeys(f["text"] for f in raw if not f["url"]))
    for f in (f for f in raw if f["url"]):
        uniq.setdefault(f["text"], f)   # 같은 문장은 첫 것만
    at = datetime.now().astimezone().isoformat(timespec="seconds")
    facts = []
    for i, f in enumerate(uniq.values(), 1):
        site = _site(f["url"])
        facts.append({"id": f"F{i}", "text": f["text"], "url": f["url"], "title": f.get("title") or "", "site": site,
                      "kind": _kind(site, r.news, r.domains), "published": f.get("published") or "",
                      "retrieved_at": f.get("retrieved_at") or at})
    # 어댑터가 검색어를 돌려주지 않아 비워 둔다(문서 모양은 맞춘다)
    return {"queries": [], "facts": facts, "notes": notes}, usage


def sheet(facts: list[dict]) -> str:
    """대본에 넘길 사실 시트. 토큰을 아끼려고 URL은 뺀다. 보도·웹은 끝에 표시해 공식 자료와 구별한다."""
    mark = {"news": " (보도)", "web": " (웹)"}
    return "\n".join(f"{f['id']}. {f['text']}" + ("" if "보도" in f["text"] else mark.get(f["kind"], ""))
                     for f in facts)

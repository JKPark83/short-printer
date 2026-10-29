"""주제 찾기: 채널 기본 추천 기준(prompts/trend_idea.md + 채널 ideas.md·trends.md)으로 LLM이 웹을 찾아
주제 IDEA_N개를 고른다. 사용자가 적은 추가 요청이 있으면 기본 기준에 더해 따른다.
인기 쇼츠 참고(popular)를 켜면 채널 검색어(trends.keywords)로 최근 뜨는 쇼츠를 YouTube Data API로 모아
시간당 조회수 순으로 함께 넘긴다. 해외 검색어(trends.abroad)가 있으면 지난 ABROAD_DAYS일 영어 쇼츠도
누적 조회수 순으로 덧붙인다. 롱폼 채널(format long)은 4~20분 영상을 모으고 prompts/long_trend_idea.md를 쓴다.
롱폼 추천 하나는 시리즈로 나눌 수 있다(series): 같은 선정 단계가 prompts/long_series.md로 편 목록을 고른다.
단계는 선정 하나. 작업(Job)과 같은 규칙으로 실패하면 다시 시도할 수 있다."""
import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from .. import config
from ..infra.store import Record
from ..ports.llm import add_usage
from . import prompts, research
from .channel import Channel
from .pipeline import Job, run_steps
from .services import Services

STEPS = ("pick",)
LABELS = {"pick": "선정"}
IDEA_N = 10          # 추천 수
SERIES = (2, 6)      # 시리즈 편 수 [최소, 최대]
MAX_REQUEST = 1000   # 추가 요청 최대 글자
POPULAR_N = 15       # 지시문에 넣을 인기 쇼츠 수
POPULAR_DAYS = 7     # 인기 쇼츠를 찾을 기간
ABROAD_N = 10        # 지시문에 넣을 해외 인기 쇼츠 수
ABROAD_DAYS = 365    # 해외 인기 쇼츠를 찾을 기간. 터진 소재는 오래 쌓인 조회수로 본다
ABROAD_LANG = "en"
MAX_SEC = 180        # 쇼츠 최대 길이
SAME = 0.6           # 띄어쓰기·문장부호를 뺀 글자 닮음 비율. 이 이상이면 말만 바꾼 같은 주제로 본다
# 나이 구간(시간 이하, 이름). 갓 올린 쇼츠일수록 시간당 조회수가 부풀어 같은 구간끼리만 순위를 매긴다
AGES = ((24, "24시간 안"), (72, "1~3일"), (POPULAR_DAYS * 24, "3~7일"))
CRITERIA = {
    "trend": ("화제성", "지금 사람들이 이 소재를 보고 찾고 있나(요즘 뜨는 쇼츠·최근 화제)"),
    "curious": ("호기심", "듣자마자 답이 궁금하고, 알고 나면 남에게 말하고 싶은가"),
    "fit": ("제작 적합도", "우리 제작 방식으로 만들 수 있나"),
    "fresh": ("차별화", "이미 만든 주제·흔한 영상과 겹치지 않고 새 각도가 있나"),
    "safe": ("안전성", "저작권·민감 주제 위험이 낮나"),
}

API = "https://www.googleapis.com/youtube/v3/"
NO_KEY = "YouTube API 키가 없어요. .env에 YOUTUBE_API_KEY를 넣고 서버를 다시 켜세요."
QUOTA = "YouTube API 오늘 할당량을 다 썼어요. 태평양 시간 자정(한국 오후 4~5시)에 다시 채워져요."
REGIONS = {"ko": "KR", "ja": "JP", "en": "US"}
# 언어마다 제목·설명에 있어야 할 글자. 여기 없는 언어는 글자로 거르지 않는다(relevanceLanguage만)
SCRIPTS = {"ko": re.compile("[가-힣]"), "ja": re.compile("[\u3040-\u30ff\u4e00-\u9fff]")}

Format = Literal["잡학·상식", "썰·사연", "명언·동기부여", "순위·리스트", "뉴스·이슈", "꿀팁·하우투", "유머·밈",
                 "음식", "일상·브이로그", "게임", "음악·댄스", "동물", "기타"]


class Trend(Record):
    KIND = "trend"
    WHAT = "추천"

    @classmethod
    def root(cls) -> Path:
        return config.TRENDS_DIR

    @classmethod
    def create(cls, channel: str, keyword: str = "", *, popular: bool = False, series: dict | None = None) -> "Trend":
        """keyword는 사용자 추가 요청(자유 글). 예전 기록·스케줄과 맞추려고 저장 키 이름은 keyword 그대로 둔다.
        popular면 요즘 인기 쇼츠를 모아 주제 고르기에 함께 넘긴다.
        series = {"topic", "brief"}면 새 주제 대신 그 추천 하나를 시리즈 편으로 나눈다."""
        return cls._new(STEPS, channel=channel, keyword=keyword.strip()[:MAX_REQUEST], popular=popular, series=series)

    def again(self) -> "Trend":
        """같은 채널·추가 요청으로 다시 뽑는 새 기록. 앞서 나온 주제(이어진 기록 포함, 최근 50개)는 피하게 넘긴다."""
        shown = self.data.get("avoid", []) + [p["topic"] for p in (self.doc("picks.json") or {}).get("picks", [])]
        t = Trend.create(self.data["channel"], self.data["keyword"], popular=self.data.get("popular", False),
                         series=self.data.get("series"))
        t.update(avoid=shown[-50:])
        return t


# ---------- 인기 쇼츠 ----------

def iso_seconds(s: str) -> float:
    """ISO 8601 길이(PT1M5S, P0D 등)를 초로."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", s or "")
    if not m:
        return 0.0
    d, h, mi, sec = (float(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def _api(path: str, **params) -> dict:
    url = f"{API}{path}?{urlencode(params | {'key': config.secret('YOUTUBE_API_KEY')})}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "shorts-printer/0.1"}), timeout=30) as r:
            return json.load(r)
    except HTTPError as e:
        try:
            reason = json.loads(e.read())["error"]["errors"][0]["reason"]
        except Exception:  # noqa: BLE001 — 본문이 json이 아니면 상태 코드만 쓴다
            reason = str(e.code)
        if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            raise RuntimeError(QUOTA) from None
        if e.code in (400, 403):
            raise RuntimeError(f"YouTube API 키가 맞지 않거나 YouTube Data API v3가 사용 설정되지 않았어요({reason}). "
                               "Google Cloud 콘솔에서 확인하세요.") from None
        raise RuntimeError(f"YouTube API 오류({e.code}, {reason})") from None
    except URLError:
        raise RuntimeError("YouTube API에 연결하지 못했어요. 네트워크를 확인하세요.") from None


def _long(ch: Channel) -> bool:
    # channel.format이 없던 예전 Channel도 숏폼으로 본다
    return getattr(ch, "format", "short") == "long"


def _kind(ch: Channel) -> str:
    return "영상" if _long(ch) else "쇼츠"


def rank(items: list[dict], now: datetime, language: str, long: bool = False) -> list[dict]:
    """videos.list 결과를 거른다(숏폼은 180초 이하, 제목·설명에 그 언어 글자) → 시간당 조회수 내림차순."""
    out, script, top = [], SCRIPTS.get(language), float("inf") if long else MAX_SEC
    for it in items:
        sn, st = it["snippet"], it.get("statistics", {})
        dur = iso_seconds(it.get("contentDetails", {}).get("duration"))
        if not 0 < dur <= top or script and not script.search(sn["title"] + sn.get("description", "")):
            continue
        views = int(st.get("viewCount", 0))   # 숨긴 값은 0
        age = max((now - datetime.fromisoformat(sn["publishedAt"])).total_seconds() / 3600, 1)
        out.append({"id": it["id"], "title": sn["title"], "channel": sn["channelTitle"], "channel_id": sn["channelId"],
                    "views": views,
                    "views_per_hour": round(views / age), "hours": round(age),
                    "url": f"https://www.youtube.com/{'watch?v=' if long else 'shorts/'}{it['id']}",
                    "description": sn.get("description", "")[:200]})
    out.sort(key=lambda v: v["views_per_hour"], reverse=True)
    seen = Counter()
    for v in out:
        v["age"] = next((name for h, name in AGES if v["hours"] <= h), AGES[-1][1])
        seen[v["age"]] += 1
        v["age_rank"] = seen[v["age"]]
    for v in out:
        v["age_n"] = seen[v["age"]]
    return out


def _subs(ids: list[str]) -> dict[str, int]:
    """채널 ID → 구독자 수. 숨겼거나 0인 채널은 뺀다. 할당량 1."""
    items = _api("channels", part="statistics", id=",".join(ids)).get("items", []) if ids else []
    return {c["id"]: n for c in items if not (st := c["statistics"]).get("hiddenSubscriberCount")
            and (n := int(st.get("subscriberCount", 0)))}


def _search(ch: Channel, keywords: list[str], language: str, days: int) -> list[dict]:
    """검색어로 최근 days일 쇼츠(롱폼 채널은 4~20분 영상)를 조회수 순으로 찾아 rank를 거친 목록. 할당량 101."""
    now = datetime.now(UTC)
    q = {"part": "snippet", "type": "video", "videoDuration": "medium" if _long(ch) else "short",   # medium = 4~20분
         "order": "viewCount", "maxResults": 50,
         "relevanceLanguage": language, "q": " | ".join(keywords),   # | 는 YouTube 검색의 OR
         "publishedAfter": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if region := REGIONS.get(language):
        q["regionCode"] = region
    ids = [it["id"]["videoId"] for it in _api("search", **q).get("items", [])]
    items = _api("videos", part="snippet,contentDetails,statistics", id=",".join(ids)).get("items", []) if ids else []
    return rank(items, now, language, _long(ch))


def _with_subs(top: list[dict]) -> list[dict]:
    """구독자 대비 배수(per_sub)를 붙여 큰 채널의 평소 성적과 작은 채널의 대박을 가른다. 할당량 1."""
    subs = _subs(sorted({v["channel_id"] for v in top}))
    for v in top:
        if n := subs.get(v["channel_id"]):
            v["per_sub"] = round(v["views"] / n, 2)
    return top


def popular_videos(ch: Channel) -> list[dict]:
    """채널 검색어로 최근 POPULAR_DAYS일 쇼츠(롱폼 채널은 4~20분 영상)를 조회수 순으로 찾아
    시간당 조회수 상위 POPULAR_N개.
    검색어가 없으면 지역 전체 인기(드라마·아이돌)가 모여 채널과 상관없는 주제가 나와 막는다. 할당량은 102."""
    if not config.secret("YOUTUBE_API_KEY"):
        raise RuntimeError(NO_KEY)
    if not ch.trends.keywords:
        raise RuntimeError(f"채널 channel.toml의 [trends] keywords에 인기 {_kind(ch)} 검색어를 넣어 주세요.")
    return _with_subs(_search(ch, ch.trends.keywords, ch.language, POPULAR_DAYS)[:POPULAR_N])


def abroad_videos(ch: Channel) -> list[dict]:
    """해외 검색어(trends.abroad)로 지난 ABROAD_DAYS일 영어 쇼츠를 누적 조회수 상위 ABROAD_N개(abroad 표시).
    지금 화제가 아니라 소재 힘(해외에서 터진 물음)의 근거다. 할당량은 102."""
    found = sorted(_search(ch, ch.trends.abroad, ABROAD_LANG, ABROAD_DAYS), key=lambda v: v["views"], reverse=True)
    return [v | {"abroad": True} for v in _with_subs(found[:ABROAD_N])]


def _age(v: dict) -> str:
    """나이·구간 순위·구독자 대비 배수. 예전 기록에는 없는 값은 빼고 쓴다."""
    if v.get("abroad"):
        s = f" · {v['hours'] // 24}일 전"
    else:
        s = f" · {v['hours']}시간 전" if "hours" in v else ""
    if "age" in v and not v.get("abroad"):
        s += f" · {v['age']} {v['age_n']}개 중 {v['age_rank']}위"
    return s + (f" · 구독자의 {v['per_sub']:g}배" if "per_sub" in v else "")


def _popular_text(videos: list[dict], start: int = 1) -> str:
    return "\n".join(f"{i}. {v['title']} · {v['channel']} · 조회수 {v['views']:,} · 시간당 {v['views_per_hour']:,}"
                     + _age(v)
                     + (f"\n   설명: {d}" if (d := " ".join(v["description"].split())) else "")
                     for i, v in enumerate(videos, start))


# ---------- 선정 ----------

class Scores(BaseModel):
    trend: int = Field(description="화제성 1~5: " + CRITERIA["trend"][1])
    curious: int = Field(description="호기심 1~5: " + CRITERIA["curious"][1])
    fit: int = Field(description="제작 적합도 1~5: " + CRITERIA["fit"][1])
    fresh: int = Field(description="차별화 1~5: " + CRITERIA["fresh"][1])
    safe: int = Field(description="안전성 1~5: " + CRITERIA["safe"][1])


class IdeaOut(BaseModel):
    topic: str = Field(description="작업 주제로 그대로 쓸 한 줄. 80자 이내")
    angle: str = Field(description="훅과 전개 방향. 대본 작가에게 넘길 참고. 200자 이내")
    content: str = Field(description="핵심 답 한 문장 + 확인할 주장 3~5개(끝에 출처 기관). 500자 이내")
    format: Format
    why_now: str = Field(description="왜 지금, 왜 사람들이 궁금해하는지 한두 문장")
    scores: Scores
    search_terms: list[str] = Field(description="화면에 보일 장면을 나타내는 영어 키워드 3~5개")
    refs: list[int] = Field(default=[], description="참고한 인기 쇼츠 번호. 목록이 없거나 참고하지 않았으면 빈 목록")


class IdeasOut(BaseModel):
    summary: str = Field(description="이번 목록의 방향 한두 문장")
    picks: list[IdeaOut] = Field(description=f"추천 주제 {IDEA_N}개")


def system_idea(ch: Channel) -> str:
    """prompts/trend_idea.md(롱폼은 long_trend_idea.md)에 채널 값과 주제 기준(ideas.md, 없는 채널은 빈 값)을 채운다."""
    rules = ch.text("ideas.md") if (ch.dir / "ideas.md").exists() else ""
    if _long(ch):
        lo, hi = ch.long.minutes
        return prompts.render("long_trend_idea", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                              channel_rules=ch.text("trends.md"), idea_rules=rules, n=IDEA_N,
                              minutes=f"{lo}~{hi}분", facts=ch.long.max_facts)
    return prompts.render("trend_idea", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                          channel_rules=ch.text("trends.md"), idea_rules=rules, n=IDEA_N,
                          duration=ch.script.duration, scenes=ch.script.scenes)


def finish_ideas(out: IdeasOut, weights: dict[str, int], ordered: bool = False) -> dict:
    """LLM 답에 총점(채널 weights, 합 100)을 붙여 total 내림차순(ordered면 받은 순서 그대로) 상위 IDEA_N개.
    refs는 참고한 인기 쇼츠 번호(1부터). excluded는 예전 기록과 화면 모양을 맞추려고 빈 값으로 둔다."""
    picks = []
    for p in out.picks:
        scores = {k: min(5, max(1, v)) for k, v in p.scores.model_dump().items()}
        total = round(sum(weights[k] * (scores[k] - 1) / 4 for k in weights))
        picks.append({"topic": p.topic.strip()[:80], "angle": p.angle.strip()[:200], "content": p.content.strip()[:500],
                      "format": p.format, "why_now": p.why_now, "scores": scores, "total": total, "refs": p.refs,
                      "search_terms": p.search_terms})
    if not ordered:
        picks.sort(key=lambda p: p["total"], reverse=True)
    return {"summary": out.summary, "picks": picks[:IDEA_N], "excluded": []}


# ponytail: 앞서 나온 주제를 전부 지시문에 넣는다(채널마다 수백 줄). 수천 개가 되면 오래된 것을 줄여 넣는다
def _made(cid: str) -> list[str]:
    """이 채널에서 이미 만든 작업 주제 전부(겹치지 않게 지시문에 넣는다)."""
    return [d["topic"] for d in (j.data for j in Job.all()) if d.get("channel") == cid]


def _shown(t: Trend) -> list[str]:
    """이 채널에서 한 번이라도 추천했던 주제 전부(새 것 먼저): 이어진 기록(avoid)뿐 아니라 지난 주제 찾기 전부.
    새로 시작한 주제 찾기도 지난 추천을 되풀이하지 않게."""
    cid = t.data["channel"]
    past = [p["topic"] for o in reversed(Trend.all()) if o.id != t.id and o.data.get("channel") == cid
            for p in (o.doc("picks.json") or {}).get("picks", [])]
    return list(dict.fromkeys((t.data.get("avoid") or []) + past))


def _key(topic: str) -> str:
    return re.sub(r"[\W_]+", "", topic)


def _repeat(topic: str, seen: list[str]) -> bool:
    """앞서 나온 주제를 말만 바꿔 다시 낸 것인지. LLM은 피하라고 해도 같은 물음을 자주 되풀이해 코드로 거른다.
    ponytail: 글자 닮음만 본다(뜻이 같아도 말이 많이 다르면 못 거른다). 더 필요하면 LLM에 겹침 판정을 따로 묻는다."""
    k = _key(topic)
    return any(SequenceMatcher(None, k, _key(s)).ratio() >= SAME for s in seen)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {m}" for m in items) or "(없음)"


def _web(ch: Channel) -> bool | list[str]:
    """추천 단계 검색도 조사와 같은 허용 사이트로 묶는다. 사이트가 없는 채널은 어디서나."""
    return research.sites(ch) or True


def _where(web: bool | list[str]) -> str:
    return f"허용 사이트 {len(web)}곳에서 검색하며" if isinstance(web, list) else "웹을 검색하며"


def _log_picks(t: Trend, picks: dict) -> None:
    """선정 결과를 남긴다: 방향 → 추천마다 점수 내역."""
    if picks["summary"]:
        t.log(f"방향: {picks['summary']}")
    for i, p in enumerate(picks["picks"], 1):
        detail = " · ".join(f"{CRITERIA[k][0]} {v}" for k, v in p["scores"].items())
        t.log(f"추천 {i}: {p['topic']} ({p['total']}점 · {detail})")


def _criteria(w: dict[str, int], keys) -> str:
    return "\n".join(f"- {k} {CRITERIA[k][0]} (가중치 {w[k]}): {CRITERIA[k][1]}" for k in keys)


class SeriesOut(BaseModel):
    name: str = Field(description="시리즈 이름. 사건 이름만 짧게(예: 한국전쟁)")
    summary: str = Field(description="편을 이렇게 나눈 까닭 한두 문장")
    picks: list[IdeaOut] = Field(description=f"편 목록 {SERIES[0]}~{SERIES[1]}개, 시간 순서")


def system_series(ch: Channel) -> str:
    lo, hi = ch.long.minutes
    return prompts.render("long_series", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                          minutes=f"{lo}~{hi}분", facts=ch.long.max_facts, lo=SERIES[0], hi=SERIES[1])


def step_series(t: Trend, sv: Services) -> str:
    """추천 하나 → 시리즈 편 목록(picks.json). 편마다 series {name, no, of, parts}를 달아 작업이 편 목록을 받는다.
    편은 시간 순서 그대로 둔다(총점으로 섞지 않는다). 만들기는 사람이 편마다 하나씩 누른다."""
    ch, src = sv.channel, t.data["series"]
    web = _web(ch)
    text = (f"오늘: {datetime.now():%Y-%m-%d}\n고른 추천: {src['topic']}\n{src['brief']}\n\n"
            f"추가 요청: {t.data['keyword'] or '없음'}\n\n점수 기준:\n{_criteria(ch.trends.weights, CRITERIA)}\n\n"
            f"이미 만든 작업 주제:\n{_bullets(_made(ch.id))}")
    t.log(f"{_where(web)} '{src['topic']}'을 시리즈 편으로 나누는 중")
    llm = sv.trends_llm or sv.llm
    out, usage = llm.ask(system_series(ch), text, SeriesOut, what="시리즈 편", web=web,
                         refusal=f"{llm.label}가 이 주제를 시리즈로 나누지 않았어요. 추가 요청을 바꿔 보세요.")
    t.update(usage=add_usage(t.data["usage"], usage))
    if len(out.picks) < SERIES[0]:
        raise RuntimeError(f"편을 {len(out.picks)}개만 받았어요. 시리즈로 나눌 국면이 모자란 주제예요.")
    picks = finish_ideas(IdeasOut(summary=out.summary, picks=out.picks[:SERIES[1]]), ch.trends.weights, ordered=True)
    parts = [p["topic"] for p in picks["picks"]]
    for k, p in enumerate(picks["picks"], 1):
        p["series"] = {"name": out.name.strip()[:40], "no": k, "of": len(parts), "parts": parts}
    t.put("picks.json", picks)
    t.update(series=src | {"name": out.name.strip()[:40]})
    _log_picks(t, picks)
    return usage["model"]


def step_pick(t: Trend, sv: Services) -> str:
    if t.data.get("series"):
        return step_series(t, sv)
    ch = sv.channel
    made, avoid, web = _made(ch.id), _shown(t), _web(ch)
    head = (f"오늘: {datetime.now():%Y-%m-%d}\n추가 요청: {t.data['keyword'] or '없음'}\n\n"
            f"점수 기준:\n{_criteria(ch.trends.weights, CRITERIA)}\n\n이미 만든 작업 주제:\n{_bullets(made)}")
    if t.data.get("popular"):
        kind = _kind(ch)
        if (videos := t.doc("videos.json")) is None:   # 다시 시도할 때 할당량을 또 쓰지 않는다
            t.log(f"YouTube에서 최근 {POPULAR_DAYS}일 인기 {kind} 찾는 중: {' | '.join(ch.trends.keywords)}")
            videos = popular_videos(ch)
            if ch.trends.abroad and len(videos) >= 3:   # 국내가 모자라 멈출 거면 할당량을 더 쓰지 않는다
                t.log(f"YouTube에서 지난 {ABROAD_DAYS}일 해외 인기 {kind} 찾는 중: {' | '.join(ch.trends.abroad)}")
                videos += abroad_videos(ch)
            t.put("videos.json", videos)
        home, far = [v for v in videos if not v.get("abroad")], [v for v in videos if v.get("abroad")]
        if len(home) < 3:
            raise RuntimeError(f"인기 {kind}{'을' if _long(ch) else '를'} {len(home)}개만 찾았어요. "
                               "channel.toml의 [trends] keywords를 넓혀 보세요.")
        t.log(f"인기 {kind} {len(home)}개(시간당 조회수 순): " + ", ".join(v["title"] for v in home[:5]) + " …")
        head += f"\n\n요즘 뜨는 {kind}(최근 {POPULAR_DAYS}일, 시간당 조회수 순):\n{_popular_text(home)}"
        if far:   # 번호는 videos.json 순서(국내 다음 해외)와 같아 refs가 그대로 맞는다
            t.log(f"해외 인기 {kind} {len(far)}개(누적 조회수 순): " + ", ".join(v["title"] for v in far[:5]) + " …")
            head += (f"\n\n해외에서 크게 뜬 {kind}(지난 {ABROAD_DAYS}일, 누적 조회수 순):\n"
                     + _popular_text(far, len(home) + 1))
    t.log(f"{_where(web)} 주제 {IDEA_N}개 고르는 중 (이미 만든 주제 {len(made)}개, 앞서 보여 준 {len(avoid)}개 제외)")
    kept, seen, llm = [], made + avoid, sv.trends_llm or sv.llm
    for _ in range(2):   # 겹친 걸 빼고 절반도 안 남으면 뺀 것까지 알려 한 번 더 묻는다
        text = head + ("\n\n앞서 추천한 주제:\n" + _bullets(avoid) if avoid else "")
        out, usage = llm.ask(system_idea(ch), text, IdeasOut, what="추천 주제", web=web,
                             refusal=f"{llm.label}가 이번에는 주제를 고르지 않았어요. 추가 요청을 바꿔 보세요.")
        t.update(usage=add_usage(t.data["usage"], usage))
        t.log(f"{usage['model']} 답: 주제 {len(out.picks)}개 → 점수 매기는 중")
        new = [p for p in out.picks if not _repeat(p.topic, seen)]
        if dup := [p.topic for p in out.picks if p not in new]:
            t.log(f"앞서 나온 주제와 겹쳐 {len(dup)}개를 뺐어요: {', '.join(dup)}")
        kept, seen, avoid = kept + new, seen + [p.topic for p in out.picks], dup + avoid
        if not dup or len(kept) >= IDEA_N // 2:
            break
    picks = finish_ideas(IdeasOut(summary=out.summary, picks=kept), ch.trends.weights)
    if not picks["picks"]:
        raise RuntimeError("추천 주제를 받지 못했어요. 다시 시도해 보세요.")
    t.put("picks.json", picks)
    _log_picks(t, picks)
    return usage["model"]


def brief(trend: Trend, p: dict) -> str:
    """추천 주제 하나 → 대본 작가에게 넘길 참고: 방향·내용·포맷·지금 만들 이유·화면 검색어."""
    lines = [f"방향: {p['angle']}", f"포맷: {p['format']}", f"지금 만들 이유: {p['why_now']}",
             f"화면 검색어 후보: {', '.join(p['search_terms'])}"]
    if p.get("content"):   # 예전 기록(인기 쇼츠 근거)에는 없다
        lines.insert(1, f"내용: {p['content']}")
    return "\n".join(lines)


def run(trend: Trend, sv: Services) -> None:
    run_steps(trend, STEPS, LABELS, {"pick": lambda t: step_pick(t, sv)}, "주제 찾기 완료")

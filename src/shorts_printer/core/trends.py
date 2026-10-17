"""주제 찾기: 채널 기본 추천 기준(prompts/trend_idea.md + 채널 ideas.md·trends.md)으로 LLM이 웹을 찾아
주제 IDEA_N개를 고른다. 사용자가 적은 추가 요청이 있으면 기본 기준에 더해 따른다.
단계는 선정 하나. 작업(Job)과 같은 규칙으로 실패하면 다시 시도할 수 있다."""
from datetime import datetime
from pathlib import Path
from typing import Literal

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
MAX_REQUEST = 1000   # 추가 요청 최대 글자
CRITERIA = {
    "fit": ("제작 적합도", "우리 제작 방식으로 만들 수 있나"),
    "fresh": ("차별화", "이미 만든 주제·흔한 영상과 겹치지 않고 새 각도가 있나"),
    "safe": ("안전성", "저작권·민감 주제 위험이 낮나"),
}

Format = Literal["잡학·상식", "썰·사연", "명언·동기부여", "순위·리스트", "뉴스·이슈", "꿀팁·하우투", "유머·밈",
                 "음식", "일상·브이로그", "게임", "음악·댄스", "동물", "기타"]


class Trend(Record):
    KIND = "trend"
    WHAT = "추천"

    @classmethod
    def root(cls) -> Path:
        return config.TRENDS_DIR

    @classmethod
    def create(cls, channel: str, keyword: str = "") -> "Trend":
        """keyword는 사용자 추가 요청(자유 글). 예전 기록·스케줄과 맞추려고 저장 키 이름은 keyword 그대로 둔다."""
        return cls._new(STEPS, channel=channel, keyword=keyword.strip()[:MAX_REQUEST])

    def again(self) -> "Trend":
        """같은 채널·추가 요청으로 다시 뽑는 새 기록. 앞서 나온 주제(이어진 기록 포함, 최근 50개)는 피하게 넘긴다."""
        shown = self.data.get("avoid", []) + [p["topic"] for p in (self.doc("picks.json") or {}).get("picks", [])]
        t = Trend.create(self.data["channel"], self.data["keyword"])
        t.update(avoid=shown[-50:])
        return t


# ---------- 선정 ----------

class Scores(BaseModel):
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


class IdeasOut(BaseModel):
    summary: str = Field(description="이번 목록의 방향 한두 문장")
    picks: list[IdeaOut] = Field(description=f"추천 주제 {IDEA_N}개")


def system_idea(ch: Channel) -> str:
    """prompts/trend_idea.md에 채널 값과 주제 기준(ideas.md, 없는 채널은 빈 값)을 채운다."""
    rules = ch.text("ideas.md") if (ch.dir / "ideas.md").exists() else ""
    return prompts.render("trend_idea", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                          channel_rules=ch.text("trends.md"), idea_rules=rules, n=IDEA_N,
                          duration=ch.script.duration, scenes=ch.script.scenes)


def finish_ideas(out: IdeasOut, weights: dict[str, int]) -> dict:
    """LLM 답에 총점(채널 weights, 합 100)을 붙여 total 내림차순 상위 IDEA_N개.
    refs·excluded는 예전 기록(인기 쇼츠 근거)과 화면 모양을 맞추려고 빈 값으로 둔다."""
    picks = []
    for p in out.picks:
        scores = {k: min(5, max(1, v)) for k, v in p.scores.model_dump().items()}
        total = round(sum(weights[k] * (scores[k] - 1) / 4 for k in weights))
        picks.append({"topic": p.topic.strip()[:80], "angle": p.angle.strip()[:200], "content": p.content.strip()[:500],
                      "format": p.format, "why_now": p.why_now, "scores": scores, "total": total, "refs": [],
                      "search_terms": p.search_terms})
    picks.sort(key=lambda p: p["total"], reverse=True)
    return {"summary": out.summary, "picks": picks[:IDEA_N], "excluded": []}


def _made(cid: str) -> list[str]:
    """이 채널에서 이미 만든 작업 주제 최근 30개(겹치지 않게 지시문에 넣는다)."""
    return [d["topic"] for d in (j.data for j in Job.all()) if d.get("channel") == cid][-30:]


def _shown(t: Trend) -> list[str]:
    """이 채널에서 앞서 추천했던 주제 최근 50개(새 것 먼저): 이어진 기록(avoid)뿐 아니라 지난 주제 찾기 전부.
    새로 시작한 주제 찾기도 지난 추천을 되풀이하지 않게."""
    cid = t.data["channel"]
    past = [p["topic"] for o in reversed(Trend.all()) if o.id != t.id and o.data.get("channel") == cid
            for p in (o.doc("picks.json") or {}).get("picks", [])]
    return list(dict.fromkeys((t.data.get("avoid") or []) + past))[:50]


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


def step_pick(t: Trend, sv: Services) -> str:
    ch = sv.channel
    made, avoid, web = _made(ch.id), _shown(t), _web(ch)
    text = (f"오늘: {datetime.now():%Y-%m-%d}\n추가 요청: {t.data['keyword'] or '없음'}\n\n"
            f"점수 기준:\n{_criteria(ch.trends.weights, CRITERIA)}\n\n이미 만든 작업 주제:\n{_bullets(made)}")
    if avoid:
        text += "\n\n앞서 추천했지만 고르지 않은 주제:\n" + _bullets(avoid)
    t.log(f"{_where(web)} 주제 {IDEA_N}개 고르는 중 (이미 만든 주제 {len(made)}개, 앞서 보여 준 {len(avoid)}개 제외)")
    out, usage = sv.llm.ask(system_idea(ch), text, IdeasOut, what="추천 주제", web=web,
                            refusal=f"{sv.llm.label}가 이번에는 주제를 고르지 않았어요. 추가 요청을 바꿔 보세요.")
    t.update(usage=add_usage(t.data["usage"], usage))
    t.log(f"{usage['model']} 답: 주제 {len(out.picks)}개 → 점수 매기는 중")
    picks = finish_ideas(out, ch.trends.weights)
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

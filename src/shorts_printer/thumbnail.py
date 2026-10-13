"""썸네일 단계: 썸네일 스킬(.claude/skills/shorts-thumbnail/SKILL.md) 본문을 Claude 지시문으로 써서
문구·사진 검색어를 정하고, Pixabay 사진 후보를 보여 줘 한 장을 고른다. 합성은 render.thumbnail, 영상 첫 화면 삽입은 render.render."""
import base64
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import config, footage
from .jobs import read_json
from .script import add_usage, ask

SKILL = config.ROOT / ".claude" / "skills" / "shorts-thumbnail" / "SKILL.md"
PHOTOS = "https://pixabay.com/api/"
PER_QUERY, MAX_CANDIDATES = 5, 12


class Plan(BaseModel):
    lines: list[str] = Field(description="썸네일 문구 1~2줄, 줄마다 9자 이내")
    accent: str = Field(description="lines 안에 그대로 들어 있는 강조 낱말 하나")
    queries: list[str] = Field(description="Pixabay 사진 검색용 영어 검색어 2~3개, 좋은 순서")


class Choice(BaseModel):
    pick: int = Field(description="고른 사진 번호. 규칙에 맞는 사진이 없으면 -1")
    position: Literal["top", "bottom"] = Field(description="문구 자리. 얼굴·피사체를 가리지 않는 쪽")
    reason: str = Field(description="고른 이유 한국어 한 문장")


def rules() -> str:
    """스킬 파일에서 앞머리(--- ... ---)를 뺀 본문. 부를 때마다 읽어 스킬을 고치면 바로 반영된다."""
    return SKILL.read_text(encoding="utf-8").split("---", 2)[2].strip()


def plan(script: dict, topic: str, before: list[str]) -> tuple[Plan, dict]:
    text = (f"주제: {topic}\n제목: {script['title']}\n문장:\n" + "\n".join(f"- {s}" for s in script["sentences"])
            + (f"\n\n이전에 쓴 문구(이번엔 다르게): {' / '.join(before)}" if before else ""))
    out, usage = ask(rules() + "\n\n## 지금 할 일\n이 쇼츠 대본으로 썸네일 문구(lines, accent)와 사진 검색어(queries)를 정한다.",
                     text, Plan, "Claude가 이 대본으로는 썸네일 문구를 만들지 않았어요.", "썸네일 문구")
    lines = [ln.strip() for ln in out.lines if ln.strip()][:2]
    if not lines:
        raise RuntimeError("썸네일 문구를 받지 못했어요(문구가 비었어요).")
    accent = out.accent.strip() if out.accent.strip() and out.accent.strip() in " ".join(lines) else ""
    return out.model_copy(update={"lines": lines, "accent": accent}), usage


def candidates(queries: list[str], skip: set[int]) -> list[dict]:
    """검색어마다 앞쪽 몇 장씩, 이미 쓴 사진은 빼고."""
    out, seen = [], set(skip)
    for q in queries[:3]:
        hits = [h for h in footage.pixabay_hits(PHOTOS, q, image_type="photo", orientation="vertical")
                if h["id"] not in seen][:PER_QUERY]
        seen |= {h["id"] for h in hits}
        out += [h | {"query": q} for h in hits]
    return out[:MAX_CANDIDATES]


def _download(url: str, path: Path) -> None:
    with footage._open(url) as r:
        data = r.read()
        if r.length:   # 중간에 끊겼다
            raise RuntimeError("Pixabay 사진을 끝까지 받지 못했어요")
    path.write_bytes(data)


def choose(cands: list[dict], lines: list[str], topic: str) -> tuple[Choice, dict]:
    content = []
    for i, c in enumerate(cands):
        with footage._open(c["webformatURL"]) as r:   # 640px 미리보기. Pixabay는 바로 링크(핫링크)를 막아 받아서 보낸다
            data = base64.standard_b64encode(r.read()).decode()
        mt = "image/png" if c["webformatURL"].lower().endswith(".png") else "image/jpeg"
        content += [{"type": "text", "text": f"{i}번 (검색어 {c['query']})"},
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}]
    content.append({"type": "text", "text": f"주제: {topic}\n썸네일 문구: {' / '.join(lines)}"})
    return ask(rules() + "\n\n## 지금 할 일\n번호 붙은 사진 후보 가운데 규칙에 가장 맞는 한 장을 고르고 문구 자리를 정한다. "
               "'하지 않는 것'에 걸리는 사진은 고르지 않는다.",
               content, Choice, "Claude가 이 사진들로는 썸네일을 고르지 않았어요.", "썸네일 사진")


def make(job_dir: Path, script: dict, topic: str, log, taken: set[int] = frozenset()) -> dict:
    """thumb.json에 남길 값. 사진은 thumb_photo.jpg로 받는다. 다시 만들면 이전 사진·문구를, taken(다른 작업이 쓴 사진)도 피한다."""
    prev = read_json(job_dir / "thumb.json") or {}
    used, texts = prev.get("used", []), prev.get("texts", [])
    p, usage = plan(script, topic, texts)
    log(f"썸네일 문구: {' / '.join(p.lines)} · 검색어 {', '.join(p.queries)}")
    photo, position, reason = None, "top", None
    (job_dir / "thumb_photo.jpg").unlink(missing_ok=True)
    if config.secret("PIXABAY_API_KEY") and (cands := candidates(p.queries, set(used) | taken)):
        c, u = choose(cands, p.lines, topic)
        usage = add_usage(usage, u)
        position, reason = c.position, c.reason
        if 0 <= c.pick < len(cands):
            h = cands[c.pick]
            _download(h["largeImageURL"], job_dir / "thumb_photo.jpg")
            photo = {"id": h["id"], "url": h["pageURL"], "user": h["user"], "query": h["query"],
                     "user_url": f"https://pixabay.com/users/{h['user']}-{h['user_id']}/"}
            used = used + [h["id"]]
            log(f"썸네일 사진: {h['pageURL']} ({reason})")
    return {"lines": p.lines, "accent": p.accent, "queries": p.queries, "position": position, "photo": photo,
            "reason": reason, "usage": usage, "used": used, "texts": texts + [" / ".join(p.lines)]}

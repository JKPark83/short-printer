"""썸네일 단계: 썸네일 스킬(.claude/skills/shorts-thumbnail/SKILL.md) 본문을 Claude 지시문으로 써서
문구를 정한다. 배경은 첫 장면 클립(render.thumbnail). 문구는 영상 위 띠 제목으로도 쓴다(render.render)."""
from pathlib import Path

from pydantic import BaseModel, Field

from . import config
from .jobs import read_json
from .script import ask

SKILL = config.ROOT / ".claude" / "skills" / "shorts-thumbnail" / "SKILL.md"


class Plan(BaseModel):
    lines: list[str] = Field(description="썸네일 문구 1~2줄, 줄마다 9자 이내")
    accent: str = Field(description="lines 안에 그대로 들어 있는 강조 낱말 하나")


def rules() -> str:
    """스킬 파일에서 앞머리(--- ... ---)를 뺀 본문. 부를 때마다 읽어 스킬을 고치면 바로 반영된다."""
    return SKILL.read_text(encoding="utf-8").split("---", 2)[2].strip()


def plan(script: dict, topic: str, before: list[str], note: str = "") -> tuple[Plan, dict]:
    text = f"주제: {topic}\n제목: {script['title']}\n문장:\n" + "\n".join(f"- {s}" for s in script["sentences"])
    if note:   # 사용자가 지금 문구를 보고 고쳐 달라고 한 것. 규칙보다 앞선다
        text += (f"\n\n지금 문구: {before[-1]}" if before else "") + f"\n사용자 수정 요청(규칙보다 우선): {note}"
    elif before:
        text += f"\n\n이전에 쓴 문구(이번엔 다르게): {' / '.join(before)}"
    out, usage = ask(rules() + "\n\n## 지금 할 일\n이 쇼츠 대본으로 썸네일 문구(lines, accent)를 정한다.",
                     text, Plan, "Claude가 이 대본으로는 썸네일 문구를 만들지 않았어요.", "썸네일 문구")
    lines = [ln.strip() for ln in out.lines if ln.strip()][:2]
    if not lines:
        raise RuntimeError("썸네일 문구를 받지 못했어요(문구가 비었어요).")
    accent = out.accent.strip() if out.accent.strip() and out.accent.strip() in " ".join(lines) else ""
    return out.model_copy(update={"lines": lines, "accent": accent}), usage


def make(job_dir: Path, script: dict, topic: str, log, note: str = "") -> dict:
    """thumb.json에 남길 값. 다시 만들면 이전 문구를 피하고, note가 있으면 그 요청대로 고친다."""
    texts = (read_json(job_dir / "thumb.json") or {}).get("texts", [])
    p, usage = plan(script, topic, texts, note)
    log(f"썸네일 문구: {' / '.join(p.lines)}" + (f" (요청: {note})" if note else ""))
    return {"lines": p.lines, "accent": p.accent, "position": "top", "usage": usage, "note": note,
            "texts": texts + [" / ".join(p.lines)]}

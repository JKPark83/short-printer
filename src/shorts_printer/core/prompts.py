"""공통 LLM 지시문: prompts/<이름>.md를 읽어 ${이름} 자리를 채운다. 부를 때마다 읽어 고치면 바로 반영된다.
채널마다 다른 규칙은 channels/<id>/*.md(Channel.text)."""
from pathlib import Path
from string import Template

from .. import config


def body(path: Path) -> str:
    """md 본문. 앞머리(--- … ---)는 사람이 읽는 설명이라 뺀다."""
    t = path.read_text(encoding="utf-8")
    return t.split("---", 2)[2].strip() if t.startswith("---") else t.strip()


def render(name: str, **values: object) -> str:
    """빠진 값이 있으면 KeyError: 파일에 오타 난 ${이름}을 바로 알린다."""
    return Template(body(config.PROMPTS_DIR / f"{name}.md")).substitute(values)

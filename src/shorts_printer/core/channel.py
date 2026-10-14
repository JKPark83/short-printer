"""채널: channels/<id>/channel.toml(값)과 글 파일(script.md·video_style.md·thumbnail.md·trends.md).
채널을 늘릴 때 코드는 고치지 않는다. 폴더 하나를 더하면 된다(.claude/skills/channel-create)."""
import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .. import config
from . import prompts

# 언어 이름(지시문에 쓴다)과 기본 글꼴. 여기 없는 언어도 쓸 수 있다(이름은 코드 그대로, 글꼴은 DEFAULT_FONT)
LANGS = {"ko": "한국어", "en": "영어", "ja": "일본어"}
FONTS = {"ko": "Apple SD Gothic Neo", "ja": "Hiragino Sans", "en": "Helvetica Neue"}
DEFAULT_FONT = "Arial"
TEXTS = ("script.md", "video_style.md", "thumbnail.md", "trends.md")
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
HEX = r"^#[0-9a-fA-F]{6}$"


class ScriptCfg(BaseModel):
    scenes: int = Field(7, ge=1, le=20)
    sentence: tuple[int, int] = (48, 55)   # 문장 하나 길이(unit 기준)
    unit: Literal["chars", "words"] = "chars"
    duration: str = "40~50초"


class TTSCfg(BaseModel):
    provider: str = "elevenlabs"
    voices: dict[str, str] = Field(min_length=1)   # {목소리 키: 화면 이름}. 앞이 기본
    default: str = ""
    sample: str   # 미리 듣기 문장(채널 언어)

    @model_validator(mode="after")
    def _default(self):
        if self.default and self.default not in self.voices:
            raise ValueError(f"tts.default({self.default})가 tts.voices에 없어요")
        self.default = self.default or next(iter(self.voices))
        return self


class VideoCfg(BaseModel):
    provider: str = "flow"
    style: str = ""   # 모든 장면 프롬프트 앞 머리말(영어)


class StyleCfg(BaseModel):
    font: str = ""   # 비우면 언어 기본 글꼴
    accent: str = Field("#FFE500", pattern=HEX)
    background: tuple[str, str] = ("#0f172a", "#14532d")
    subtitle_limit: int = Field(0, ge=0)   # 0이면 언어 기본(Splitter.limit)


class ThumbCfg(BaseModel):
    max_line: int = Field(9, ge=1)
    max_total: int = Field(16, ge=1)


class PublishCfg(BaseModel):
    provider: str = "youtube"
    category: str = "22"
    channel_id: str = ""   # UC… 스튜디오 화면으로 올릴 때 이 채널로 간다


class TrendsCfg(BaseModel):
    region: str = "KR"
    language: str = ""   # 비우면 채널 language
    keywords: list[str] = []   # 키워드 없이 찾을 때 OR로 묶어 검색
    production: str   # 우리 제작 방식 한 단락
    weights: dict[str, int] = {"trend": 35, "fit": 35, "fresh": 15, "safe": 15}

    @model_validator(mode="after")
    def _weights(self):
        if set(self.weights) != {"trend", "fit", "fresh", "safe"} or sum(self.weights.values()) != 100:
            raise ValueError("trends.weights는 trend·fit·fresh·safe 네 개, 합 100이어야 해요")
        return self


class Channel(BaseModel):
    id: str
    dir: Path
    name: str
    description: str
    concept: str   # 대본·추천이 이 분야 안에서 돈다
    language: str
    daily_goal: int = Field(3, ge=1)
    sensitive_gate: bool = True   # 민감 분야 대본은 사람이 확인해야 장면을 만든다
    llm: str = "claude"
    script: ScriptCfg = ScriptCfg()
    tts: TTSCfg
    video: VideoCfg = VideoCfg()
    style: StyleCfg = StyleCfg()
    thumbnail: ThumbCfg = ThumbCfg()
    publish: PublishCfg = PublishCfg()
    trends: TrendsCfg

    @property
    def lang_name(self) -> str:
        return LANGS.get(self.language, self.language)

    @property
    def font(self) -> str:
        return self.style.font or FONTS.get(self.language, DEFAULT_FONT)

    @property
    def trend_language(self) -> str:
        return self.trends.language or self.language

    def text(self, name: str) -> str:
        """글 파일 본문. 부를 때마다 읽어 고치면 바로 반영된다. 앞머리(--- … ---)가 있으면 뺀다."""
        return prompts.body(self.dir / name)


def root() -> Path:
    return config.CHANNELS_DIR   # 테스트가 바꾸므로 부를 때마다 읽는다


def load(cid: str) -> Channel:
    d = root() / cid
    if not ID.fullmatch(cid) or not (d / "channel.toml").exists():
        raise KeyError(f"채널이 없어요: {cid}")
    with open(d / "channel.toml", "rb") as f:
        data = tomllib.load(f)
    if miss := [n for n in TEXTS if not (d / n).exists()]:
        raise ValueError(f"채널 {cid}에 {', '.join(miss)} 파일이 없어요")
    return Channel(id=cid, dir=d, **data)


def load_all() -> list[Channel]:
    """폴더 이름 순. 설정이 틀린 채널은 바로 알 수 있게 오류를 낸다."""
    return [load(p.parent.name) for p in sorted(root().glob("*/channel.toml"))]


def ids() -> list[str]:
    return [p.parent.name for p in sorted(root().glob("*/channel.toml"))]

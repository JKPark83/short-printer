"""채널 하나를 만들 때 쓰는 것 묶음. registry가 만들어 core에 넘긴다(core는 구현을 모른다)."""
from dataclasses import dataclass, field

from ..ports.llm import LLM
from ..ports.publisher import Publisher
from ..ports.research import Researcher
from ..ports.splitter import Splitter
from ..ports.tts import TTS
from ..ports.video import VideoProvider
from .channel import Channel


@dataclass(frozen=True)
class Services:
    channel: Channel
    llm: LLM
    tts: TTS
    video: VideoProvider
    publisher: Publisher
    splitter: Splitter
    research: Researcher
    script_llm: LLM | None = None   # 대본 쓰기·고치기·검수·번역(script.llm). 없으면 llm
    trends_llm: LLM | None = None   # 주제 찾기(trends.llm). 없으면 llm
    also: dict[str, Publisher] = field(default_factory=dict)   # 더 올리는 곳(publish.also). 사람이 눌러 올린다

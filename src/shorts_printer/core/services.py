"""채널 하나를 만들 때 쓰는 것 묶음. registry가 만들어 core에 넘긴다(core는 구현을 모른다)."""
from dataclasses import dataclass

from ..ports.llm import LLM
from ..ports.publisher import Publisher
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

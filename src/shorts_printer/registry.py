"""조립 지점: 이름 → 구현. 채널 설정을 읽어 core에 넘길 Services를 만든다.
adapters를 아는 곳은 여기(와 web·cli의 로그인·Chrome 명령)뿐이다. 새 공급자는 adapters에 파일 하나 + 여기 한 줄."""
from functools import cache

from . import config
from .adapters.claude import Claude
from .adapters.elevenlabs import ElevenLabs
from .adapters.flow import Flow
from .adapters.flow_auto import FlowAuto
from .adapters.splitters.ja import Japanese
from .adapters.splitters.ko import Korean
from .adapters.splitters.whitespace import Whitespace
from .adapters.youtube import YouTube
from .core import channel
from .core.channel import Channel
from .core.services import Services
from .infra.worker import LocalQueue
from .ports.llm import LLM
from .ports.publisher import Publisher
from .ports.splitter import Splitter
from .ports.tts import TTS
from .ports.video import VideoProvider

LLMS: dict[str, LLM] = {"claude": Claude()}
TTSES: dict[str, TTS] = {"elevenlabs": ElevenLabs()}
VIDEOS: dict[str, VideoProvider] = {"flow": Flow(), "flow-auto": FlowAuto()}
FALLBACK_VIDEO = "flow"   # 고른 공급자를 쓸 수 없을 때(사람이 올린다)
SPLITTERS: dict[str, Splitter] = {"ko": Korean(), "ja": Japanese(), "en": Whitespace()}
DEFAULT_SPLITTER = Whitespace()   # 그 밖의 언어: 띄어쓰기에서 끊는다


def youtube(ch: Channel) -> YouTube:
    return YouTube(token=config.SECRETS_DIR / "channels" / ch.id / "youtube_token.json", channel=ch.id,
                   language=ch.language, category=ch.publish.category, studio_channel=ch.publish.channel_id)


PUBLISHERS = {"youtube": youtube}   # 채널 계정마다 하나라 채널을 받아 만든다


def _pick(table: dict, name: str, what: str):
    if name not in table:
        raise RuntimeError(f"모르는 {what}예요: {name} (가능: {', '.join(table)})")
    return table[name]


def video(ch: Channel) -> tuple[str, VideoProvider]:
    """채널이 고른 영상 공급자. 쓸 수 없으면 Flow(직접 올림)."""
    name = ch.video.provider
    p = _pick(VIDEOS, name, "영상 공급자")
    return (name, p) if p.ready() else (FALLBACK_VIDEO, VIDEOS[FALLBACK_VIDEO])


def splitter(language: str) -> Splitter:
    return SPLITTERS.get(language, DEFAULT_SPLITTER)


def services(channel_id: str) -> Services:
    ch = channel.load(channel_id)
    return Services(channel=ch, llm=_pick(LLMS, ch.llm, "LLM"), tts=_pick(TTSES, ch.tts.provider, "음성 공급자"),
                    video=video(ch)[1], publisher=publisher(ch), splitter=splitter(ch.language))


def publisher(ch: Channel) -> Publisher:
    return _pick(PUBLISHERS, ch.publish.provider, "업로드 공급자")(ch)


@cache
def queue() -> LocalQueue:
    return LocalQueue(services)

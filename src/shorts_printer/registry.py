"""조립 지점: 이름 → 구현. 채널 설정을 읽어 core에 넘길 Services를 만든다.
adapters를 아는 곳은 여기(와 web·cli의 로그인·Chrome 명령)뿐이다. 새 공급자는 adapters에 파일 하나 + 여기 한 줄."""
import logging
from functools import cache

from . import config
from .adapters.claude import Claude
from .adapters.claude_code import ClaudeCode
from .adapters.claude_research import ClaudeResearch
from .adapters.discord import Discord
from .adapters.elevenlabs import ElevenLabs
from .adapters.fish_audio import FishAudio
from .adapters.flow import Flow
from .adapters.flow_auto import FlowAuto
from .adapters.instagram import Instagram
from .adapters.splitters.ja import Japanese
from .adapters.splitters.ko import Korean
from .adapters.splitters.whitespace import Whitespace
from .adapters.telegram import Telegram
from .adapters.typecast import Typecast
from .adapters.youtube import YouTube
from .core import channel
from .core.channel import Channel
from .core.services import Services
from .infra import store
from .infra.sqlite import SQLiteStore
from .infra.store import redact
from .infra.worker import LocalQueue
from .ports.llm import LLM
from .ports.notifier import Notifier
from .ports.publisher import Publisher
from .ports.research import Researcher
from .ports.splitter import Splitter
from .ports.tts import TTS
from .ports.video import VideoProvider

LLMS: dict[str, LLM] = {"claude": Claude(), "claude-code": ClaudeCode()}
RESEARCHERS: dict[str, Researcher] = {"claude": ClaudeResearch()}
TTSES: dict[str, TTS] = {"elevenlabs": ElevenLabs(), "typecast": Typecast(), "fish": FishAudio()}
VIDEOS: dict[str, VideoProvider] = {"flow": Flow(), "flow-auto": FlowAuto(),
                                    "flow-16x9": Flow("16:9", "360p"), "flow-auto-16x9": FlowAuto("16:9", "360p")}
FALLBACK_VIDEO = "flow"   # 고른 공급자를 쓸 수 없을 때(사람이 올린다)
FALLBACK_VIDEO_LONG = "flow-16x9"   # 롱폼 채널은 16:9
SPLITTERS: dict[str, Splitter] = {"ko": Korean(), "ja": Japanese(), "en": Whitespace()}
DEFAULT_SPLITTER = Whitespace()   # 그 밖의 언어: 띄어쓰기에서 끊는다
NOTIFIERS: dict[str, Notifier] = {"discord": Discord(), "telegram": Telegram()}   # .env에 켜진 것 모두로 보낸다

STORE = SQLiteStore(config.DB)   # 다른 DB는 infra에 구현 하나 + 이 줄
store.use(STORE)

log = logging.getLogger(__name__)


def youtube(ch: Channel) -> YouTube:
    return YouTube(token=config.SECRETS_DIR / "channels" / ch.id / "youtube_token.json", channel=ch.id,
                   language=ch.language, category=ch.publish.category, studio_channel=ch.publish.channel_id)


def instagram(ch: Channel) -> Instagram:
    return Instagram(token=config.SECRETS_DIR / "channels" / ch.id / "instagram_token.json", channel=ch.id,
                     footer=ch.publish.footer)


PUBLISHERS = {"youtube": youtube, "instagram": instagram}   # 채널 계정마다 하나라 채널을 받아 만든다


def _pick(table: dict, name: str, what: str):
    if name not in table:
        raise RuntimeError(f"모르는 {what}예요: {name} (가능: {', '.join(table)})")
    return table[name]


def video(ch: Channel) -> tuple[str, VideoProvider]:
    """채널이 고른 영상 공급자(롱폼은 같은 이름의 16:9 판). 쓸 수 없으면 Flow(직접 올림, 롱폼은 16:9)."""
    name = ch.video.provider
    if ch.format == "long" and f"{name}-16x9" in VIDEOS:   # 9:16 클립을 16:9 영상에 깔면 위아래가 잘린다
        name += "-16x9"
    p = _pick(VIDEOS, name, "영상 공급자")
    if p.ready():
        return name, p
    name = FALLBACK_VIDEO_LONG if ch.format == "long" else FALLBACK_VIDEO
    return name, VIDEOS[name]


def splitter(language: str) -> Splitter:
    return SPLITTERS.get(language, DEFAULT_SPLITTER)


def services(channel_id: str) -> Services:
    ch = channel.load(channel_id)
    return Services(channel=ch, llm=_pick(LLMS, ch.llm, "LLM"), tts=_pick(TTSES, ch.tts.provider, "음성 공급자"),
                    video=video(ch)[1], publisher=publisher(ch), splitter=splitter(ch.language),
                    research=_pick(RESEARCHERS, ch.research.provider, "조사 공급자"),
                    script_llm=_pick(LLMS, ch.script.llm or ch.llm, "LLM"),
                    also={n: publisher(ch, n) for n in ch.publish.also})


def publisher(ch: Channel, name: str | None = None) -> Publisher:
    """채널 업로드 공급자. name을 주면 그 이름(publish.also의 더 올리는 곳)."""
    return _pick(PUBLISHERS, name or ch.publish.provider, "업로드 공급자")(ch)


def notify(text: str) -> list[tuple[str, str | None]]:
    """준비된 알림 공급자 모두에 보낸다. [(이름, 오류 또는 None)]. 알림 실패로 작업이 실패하지 않게 삼킨다."""
    out = []
    for n in NOTIFIERS.values():
        if not n.ready():
            continue
        try:
            n.send(text)
            out.append((n.label, None))
        except Exception as e:
            msg = redact(str(e)) or type(e).__name__
            log.warning("%s 알림 실패: %s", n.label, msg)
            out.append((n.label, msg))
    return out


@cache
def queue() -> LocalQueue:
    return LocalQueue(services, notify)

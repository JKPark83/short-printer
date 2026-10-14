"""경로·외부 도구·모델 상수와 .env 로더."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k and not k.startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_dotenv()

FFMPEG = os.environ.get("SP_FFMPEG") or "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"   # 빈 값이면 기본값
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-opus-5-5"
JOBS_DIR = ROOT / "jobs"
TRENDS_DIR = ROOT / "trends"   # 주제 찾기(인기 쇼츠 분석) 결과
# YouTube 업로드: 데스크톱 앱 OAuth 클라이언트 JSON 경로(.env)와 sp youtube-login이 남기는 토큰
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET") or None
YOUTUBE_TOKEN = ROOT / ".secrets" / "youtube_token.json"
# 웹 화면이 받는 호스트 이름. tailscale serve로 열 때는 .env의 SP_HOSTS에 machine.tailnet.ts.net을 쉼표로 더한다
HOSTS = ["127.0.0.1", "localhost", *filter(None, map(str.strip, os.environ.get("SP_HOSTS", "").split(",")))]

# 채널 분야. 대본과 추천 주제가 이 분야 안에서 돈다
CHANNEL = os.environ.get("SP_CHANNEL") or "사람들에게 실제로 도움이 되는 상식"
VIDEO = os.environ.get("SP_VIDEO") or "flow"   # 영상 공급자(video.VIDEO 키). flow | stock


def secret(name: str) -> str | None:
    return os.environ.get(name) or None


# ElevenLabs(유료): 키와 목소리 ID가 둘 다 있어야 켜진다(voice.ElevenLabs.ready)
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID") or None
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL") or "eleven_multilingual_v2"

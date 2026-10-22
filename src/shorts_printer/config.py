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
CLAUDE_MODEL = "claude-opus-5-5"   # 대본·검수·조사 모두 이 모델로 고정한다(출력 상한 128000)
JOBS_DIR = ROOT / "jobs"
TRENDS_DIR = ROOT / "trends"   # 주제 찾기(추천) 기록 폴더
SCHEDULES_DIR = ROOT / "schedules"   # 정해진 시각에 만들어 올리는 스케줄
DB = ROOT / "shorts.db"   # 상태·로그·JSON 결과물(SQLite). 미디어는 위 폴더에 남는다
CHANNELS_DIR = ROOT / "channels"   # 채널 설정. 폴더 하나 = 채널 하나
PROMPTS_DIR = ROOT / "prompts"   # 모든 채널 공통 LLM 지시문
SECRETS_DIR = ROOT / ".secrets"   # 로그인 토큰·전용 Chrome 프로필. 내용을 출력하지 않는다
# YouTube 업로드: 데스크톱 앱 OAuth 클라이언트 JSON 경로(.env).
# 토큰은 채널마다 .secrets/channels/<id>/youtube_token.json
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET") or None
# 웹 화면이 받는 호스트 이름. tailscale serve로 열 때는 .env의 SP_HOSTS에 machine.tailnet.ts.net을 쉼표로 더한다
# 알림에 넣는 이 화면 주소. tailscale serve로 열면 .env SP_URL에 https://machine.tailnet.ts.net
URL = (os.environ.get("SP_URL") or "http://127.0.0.1:8765").rstrip("/")
HOSTS = ["127.0.0.1", "localhost", *filter(None, map(str.strip, os.environ.get("SP_HOSTS", "").split(",")))]


def secret(name: str) -> str | None:
    return os.environ.get(name) or None


# Claude 남은 크레딧(선택): ANTHROPIC_ADMIN_API_KEY로 비용 보고서를 읽어 SINCE(YYYY-MM-DD) 날의 잔액 USD에서 뺀다
CLAUDE_CREDIT_USD = os.environ.get("CLAUDE_CREDIT_USD") or None
CLAUDE_CREDIT_SINCE = os.environ.get("CLAUDE_CREDIT_SINCE") or None

# ElevenLabs(유료): 키가 있어야 읽는다. VOICE_ID는 channel.toml 목소리 키 "elevenlabs"가 가리키는 목소리
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID") or None
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL") or "eleven_multilingual_v2"
# Typecast(유료): 목소리는 channel.toml [tts.voices]의 tc_… ID
TYPECAST_MODEL = os.environ.get("TYPECAST_MODEL") or "ssfm-v30"

"""Fish Audio 음성(TTS 포트). Drama 3 모델. 낱말 시각은 주지 않는다."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .. import config

FISH = "https://api.fish.audio/v1/tts"
MODEL = "drama-3"   # model 머리말이 틀리면 조용히 s2.1-pro로 바뀐다


class FishAudio:
    label = "Fish Audio"
    hint = "유료 · 자막은 글자 수 비례 · .env에 FISH_AUDIO_API_KEY"

    def ready(self) -> bool:
        return bool(config.secret("FISH_AUDIO_API_KEY"))

    def speak(self, voice, text, out):
        body = json.dumps({"text": text, "reference_id": voice, "format": "mp3"}).encode()
        req = Request(FISH, data=body, headers={
            "Authorization": f"Bearer {config.secret('FISH_AUDIO_API_KEY')}",
            "Content-Type": "application/json", "model": MODEL})
        try:
            with urlopen(req, timeout=120) as r:
                audio = r.read()
        except HTTPError as e:   # 크레딧 부족·없는 목소리 같은 이유가 본문에 있다
            raise RuntimeError(f"Fish Audio {e.code}: {e.read()[:200].decode(errors='replace')}") from None
        path = out.with_suffix(".mp3")
        path.write_bytes(audio)
        # ponytail: 시각 없이 글자 수 비례로 자막을 나눈다. with-timestamps 경로가 문서화되면 낱말 시각을 받는다
        return path, None

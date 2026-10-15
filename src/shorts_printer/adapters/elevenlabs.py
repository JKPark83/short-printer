"""ElevenLabs 음성(TTS 포트). 낱말 시각도 준다."""
import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .. import config

ELEVENLABS = "https://api.elevenlabs.io/v1/text-to-speech/{}/with-timestamps?output_format=mp3_44100_128"


def words(chars: list[str], starts: list[float]) -> list[dict]:
    """글자별 시작 시각을 띄어쓰기 단위 낱말로 묶는다."""
    if not any(c.isspace() for c in chars):   # 일본어는 띄어쓰기가 없어 묶으면 문장 하나가 된다: 글자마다 그대로 쓴다
        return [{"text": c, "start": t} for c, t in zip(chars, starts, strict=False)]
    out, new = [], True
    for c, t in zip(chars, starts, strict=False):
        if c.isspace():
            new = True
        elif new:
            out.append({"text": c, "start": t})
            new = False
        else:
            out[-1]["text"] += c
    return out


class ElevenLabs:
    label = "ElevenLabs"
    hint = "유료 · 자막이 낱말 시각에 맞아요 · .env에 ELEVENLABS_API_KEY"

    def ready(self) -> bool:
        return bool(config.secret("ELEVENLABS_API_KEY"))

    def speak(self, voice, text, out):
        if voice == "elevenlabs":   # 예전 작업의 목소리 키: .env ELEVENLABS_VOICE_ID
            voice = config.ELEVENLABS_VOICE_ID
        # 숫자·단위 읽기(1173년→천백칠십삼 년, 45cm→사십오 센티미터). 기본값 auto는 한국어를 안 바꾼다.
        # alignment는 원문 글자 기준이라 자막은 그대로 맞는다.
        body = json.dumps({"text": text, "model_id": config.ELEVENLABS_MODEL,
                           "apply_text_normalization": "on"}).encode()
        req = Request(ELEVENLABS.format(voice), data=body, headers={
            "xi-api-key": config.secret("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=60) as r:
                d = json.load(r)
        except HTTPError as e:   # 한도 초과·잘못된 목소리 ID 같은 이유가 본문에 있다
            raise RuntimeError(f"ElevenLabs {e.code}: {e.read()[:200].decode(errors='replace')}") from None
        path = out.with_suffix(".mp3")
        path.write_bytes(base64.b64decode(d["audio_base64"]))
        a = d["alignment"]
        return path, words(a["characters"], a["character_start_times_seconds"])

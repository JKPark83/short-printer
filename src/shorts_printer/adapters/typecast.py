"""Typecast 음성(TTS 포트). 글자 시각을 띄어쓰기 낱말로 묶어 준다."""
import base64
import json
from itertools import accumulate
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .. import config

# granularity=char: 일본어처럼 띄어쓰기가 없는 언어는 word로 받으면 문장 전체가 한 낱말이 된다
TYPECAST = "https://api.typecast.ai/v1/text-to-speech/with-timestamps?granularity=char"


def words(text: str, chars: list[dict]) -> list[dict] | None:
    """글자별 시각을 원문의 띄어쓰기 낱말로 묶는다. 글자 수가 안 맞으면 None(글자 수 비례로 나눈다)."""
    starts = [c["start"] for c in chars if not c["text"].isspace()]
    toks = text.split()
    if sum(map(len, toks)) != len(starts):
        return None
    first = accumulate(map(len, toks), initial=0)   # 낱말마다 첫 글자 위치(끝에 하나 남는다)
    return [{"text": t, "start": starts[i]} for t, i in zip(toks, first, strict=False)]


class Typecast:
    label = "Typecast"
    hint = "유료 · 자막이 낱말 시각에 맞아요 · .env에 TYPECAST_API_KEY"

    def ready(self) -> bool:
        return bool(config.secret("TYPECAST_API_KEY"))

    def speak(self, voice, text, out):
        body = json.dumps({"text": text, "model": config.TYPECAST_MODEL, "voice_id": voice,
                           "output": {"audio_format": "mp3"}}).encode()
        req = Request(TYPECAST, data=body, headers={
            "X-API-KEY": config.secret("TYPECAST_API_KEY"), "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=60) as r:
                d = json.load(r)
        except HTTPError as e:   # 크레딧 부족(402)·없는 목소리(404) 같은 이유가 본문에 있다
            raise RuntimeError(f"Typecast {e.code}: {e.read()[:200].decode(errors='replace')}") from None
        path = out.with_suffix(".mp3")
        path.write_bytes(base64.b64decode(d["audio"]))
        return path, words(text, d.get("characters") or [])

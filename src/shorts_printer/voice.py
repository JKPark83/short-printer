"""3단계 음성: ElevenLabs로 문장마다 읽어 잇는다. 문장 시각이 곧 자막 시각이다."""
import base64
import json
import wave
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import config, ffmpeg
from .jobs import atomic_write_json

RATE = 24000
GAP = 0.2   # 문장 사이 쉼(초)
ELEVENLABS = "https://api.elevenlabs.io/v1/text-to-speech/{}/with-timestamps?output_format=mp3_44100_128"
# {ElevenLabs 목소리 ID: 화면 이름}. 맨 앞이 기본값. "elevenlabs"는 .env ELEVENLABS_VOICE_ID(예전 작업도 이 키)
VOICES = {"LKOcTG4J4tYTPR9DnLeM": "미스터킴", "QPFsEL6IBxlT15xfiD6C": "이하나",
          "iWLjl1zCuqXRkW6494ve": "지수", "elevenlabs": "미스터최"}


def words(chars: list[str], starts: list[float]) -> list[dict]:
    """글자별 시작 시각을 띄어쓰기 단위 낱말로 묶는다."""
    out, new = [], True
    for c, t in zip(chars, starts):
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
        if voice == "elevenlabs":
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


TTS = ElevenLabs()


def _read_all(sentences: list[str], job_dir: Path, log, speak) -> float:
    out = job_dir / "voice"
    out.mkdir(exist_ok=True)
    timing, t = [], 0.0
    silence = b"\0\0" * int(RATE * GAP)
    with wave.open(str(job_dir / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        for i, text in enumerate(sentences):
            (src, ws), wav = speak(text, out / f"s{i:02d}"), out / f"s{i:02d}.pcm.wav"   # 공급자가 .wav를 줘도 안 겹치게
            ffmpeg.run(["-i", src, "-ar", RATE, "-ac", 1, "-c:a", "pcm_s16le", wav])
            with wave.open(str(wav), "rb") as r:
                frames = r.readframes(r.getnframes())
            wav.unlink()
            dur = len(frames) / 2 / RATE
            w.writeframes(frames + silence)
            timing.append({"text": text, "start": round(t, 3), "end": round(t + dur, 3)}
                          | ({"words": [{"text": x["text"], "start": round(t + x["start"], 3)} for x in ws]} if ws else {}))
            t += dur + GAP
            log(f"음성 {i + 1}/{len(sentences)}: {dur:.1f}s")
    atomic_write_json(job_dir / "timing.json", timing)
    return t


SAMPLE = "안녕하세요. 오늘 알려 드릴 생활 꿀팁, 끝까지 보면 분명 도움이 될 거예요."


def sample(v: str) -> Path:
    """목소리 미리 듣기 mp3. 목소리마다 처음 한 번만 ElevenLabs로 읽고 .cache에 둔다."""
    path = config.ROOT / ".cache" / "voices" / f"{v}.mp3"
    if not path.exists():
        if not TTS.ready():
            raise RuntimeError("ElevenLabs 키가 없어요. .env에 ELEVENLABS_API_KEY를 넣고 서버를 다시 켜세요")
        path.parent.mkdir(parents=True, exist_ok=True)
        TTS.speak(v, SAMPLE, path)
    return path


def synth(sentences: list[str], v: str, job_dir: Path, log) -> str:
    """읽은 엔진 이름."""
    if v not in VOICES:   # 예전 작업의 edge-tts·macOS say 목소리
        raise RuntimeError(f"더는 쓰지 않는 목소리({v})예요. 작업 화면에서 다른 목소리를 골라 주세요")
    if not TTS.ready():
        raise RuntimeError("ElevenLabs 키가 없어요. .env에 ELEVENLABS_API_KEY를 넣고 서버를 다시 켜세요")
    _read_all(sentences, job_dir, log, lambda text, out: TTS.speak(v, text, out))
    return TTS.label

"""3단계 음성: 채널의 TTS로 문장마다 읽어 잇는다. 문장 시각이 곧 자막 시각이다."""
import hashlib
import os
import wave
from pathlib import Path

from .. import config
from ..infra import ffmpeg
from ..ports.tts import TTS
from .channel import Channel
from .render import TAIL

RATE = 24000
GAP = 0.2   # 문장 사이 쉼(초)
SPEED = 1.1   # 쇼츠 목소리는 늘 이만큼 빠르게(대본 길이는 그대로 두고 영상을 줄인다)
MAX_SEC = 89   # 쇼츠 최대 길이(1분 29초). SPEED로도 넘치면 더 빠르게 맞춘다


def _read_all(sentences: list[str], job_dir: Path, log, speak) -> list[dict]:
    """voice.wav와 문장 시각(timing)."""
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
    return timing


def _fit(timing: list[dict], job_dir: Path, log) -> list[dict]:
    """voice.wav를 atempo로 SPEED배(목소리 끝 + 렌더 여유 TAIL이 MAX_SEC를 넘으면 그보다 더) 빠르게 하고
    시각을 같은 비로 줄인다."""
    end = timing[-1]["end"]
    k = max(SPEED, end / (MAX_SEC - TAIL - 0.1))
    wav, tmp = job_dir / "voice.wav", job_dir / "voice.tmp.wav"
    ffmpeg.run(["-i", wav, "-af", f"atempo={k:.4f}", "-ar", RATE, "-ac", 1, "-c:a", "pcm_s16le", tmp])
    os.replace(tmp, wav)
    log(f"음성 {end:.1f}s → {end / k:.1f}s({k:.2f}배 빠르게)")

    def at(x: float) -> float:
        return round(x / k, 3)
    return [t | {"start": at(t["start"]), "end": at(t["end"])}
            | ({"words": [w | {"start": at(w["start"])} for w in t["words"]]} if "words" in t else {}) for t in timing]


def _check(tts: TTS) -> None:
    if not tts.ready():
        raise RuntimeError(f"{tts.label}을(를) 쓸 수 없어요({tts.hint}). 설정을 고치고 서버를 다시 켜세요")


def sample(tts: TTS, ch: Channel, voice: str) -> Path:
    """목소리 미리 듣기 mp3. 채널·목소리·문장마다 처음 한 번만 읽고 .cache에 둔다(문장을 고치면 새로 읽는다)."""
    tag = hashlib.sha1(ch.tts.sample.encode()).hexdigest()[:8]
    path = config.ROOT / ".cache" / "voices" / ch.id / f"{voice}-{tag}.mp3"
    if not path.exists():
        _check(tts)
        path.parent.mkdir(parents=True, exist_ok=True)
        tts.speak(voice, ch.tts.sample, path)
    return path


def synth(tts: TTS, ch: Channel, sentences: list[str], voice: str, job_dir: Path, log) -> tuple[str, list[dict]]:
    """(읽은 엔진 이름, 문장 시각). voice.wav는 job_dir에, 시각은 부른 쪽이 저장한다."""
    if voice not in ch.tts.voices:   # 예전 작업의 edge-tts·macOS say 목소리, 다른 채널 목소리
        raise RuntimeError(f"더는 쓰지 않는 목소리({voice})예요. 작업 화면에서 다른 목소리를 골라 주세요")
    _check(tts)
    timing = _read_all(sentences, job_dir, log, lambda text, out: tts.speak(voice, text, out))
    return tts.label, _fit(timing, job_dir, log)


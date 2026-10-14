"""3단계 음성: 문장마다 읽어 잇는다. 문장 시각이 곧 자막 시각이다.
공급자(TTS)마다 클래스 하나. 고른 목소리가 안 되면 FALLBACK 순서로 전체를 다시 읽는다."""
import base64
import json
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import edge_tts
import edge_tts.communicate

from . import config, ffmpeg
from .jobs import atomic_write_json

RATE = 24000
GAP = 0.2   # 문장 사이 쉼(초)
ELEVENLABS = "https://api.elevenlabs.io/v1/text-to-speech/{}/with-timestamps?output_format=mp3_44100_128"

# ponytail: 2026-10부터 옛 주소(speech.platform.bing.com)가 403을 준다. edge-tts가 고친 판(PR #491)을 내면 저절로 건너뛴다.
if "speech.platform.bing.com" in edge_tts.communicate.WSS_URL:
    edge_tts.communicate.WSS_URL = ("wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
                                    f"?Ocp-Apim-Subscription-Key={edge_tts.constants.TRUSTED_CLIENT_TOKEN}")


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


class TtsProvider(Protocol):
    label: str   # 엔진 이름(단계 엔진 칸·알림)
    hint: str    # 환경 점검 한 줄
    voices: dict[str, str]   # {목소리 ID: 화면 이름}. 상수이거나 캐시(화면이 그릴 때마다 읽는다)

    def ready(self) -> bool: ...

    def speak(self, voice: str, text: str, out: Path) -> tuple[Path, list[dict] | None]:
        """out은 확장자 없는 경로(voice/s00). (오디오 파일, 문장 기준 낱말 시각 [{text, start}] 또는 None)."""


class ElevenLabs:
    label = "ElevenLabs"
    hint = "유료 · 자막이 낱말 시각에 맞아요 · .env에 ELEVENLABS_API_KEY"
    # 키는 ElevenLabs 목소리 ID. "elevenlabs"는 .env ELEVENLABS_VOICE_ID(예전 작업도 이 키)
    voices = {"elevenlabs": "ElevenLabs 기본 (.env)",
              "LKOcTG4J4tYTPR9DnLeM": "미스터킴 (ElevenLabs)",
              "QPFsEL6IBxlT15xfiD6C": "이하나 (ElevenLabs)",
              "iWLjl1zCuqXRkW6494ve": "지수 (ElevenLabs)"}

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


class Edge:
    label = "edge-tts"
    hint = "무료 · 키 없음(비공식 Edge 엔드포인트)"
    voices = {"ko-KR-SunHiNeural": "선희 (여)", "ko-KR-InJoonNeural": "인준 (남)",
              "ko-KR-HyunsuMultilingualNeural": "현수 (남, 다국어)"}

    def ready(self) -> bool:
        return True

    def speak(self, voice, text, out):
        path = out.with_suffix(".mp3")
        for wait in (2, 5, 0):   # 429 같은 일시 오류는 두 번 더 해 본다
            try:
                edge_tts.Communicate(text, voice).save_sync(str(path))
                return path, None
            except Exception:
                if not wait:
                    raise
                time.sleep(wait)


class Say:
    label = "macOS say"
    hint = "오프라인 · macOS 내장"
    voices = {"Yuna": "유나 (macOS, 오프라인)"}

    def ready(self) -> bool:
        return bool(shutil.which("say"))

    def speak(self, voice, text, out):
        path = out.with_suffix(".aiff")
        subprocess.run(["say", "-v", voice, "-o", str(path), "--", text], check=True, capture_output=True)
        return path, None


TTS: dict[str, TtsProvider] = {"elevenlabs": ElevenLabs(), "edge": Edge(), "say": Say()}   # 앞이 화면 기본값
FALLBACK = ("ko-KR-SunHiNeural", "Yuna")   # 고른 목소리가 안 되면 차례로(같은 공급자는 건너뜀)


def owner(v: str) -> TtsProvider:
    # ponytail: ID가 공급자끼리 겹치면 앞 공급자가 이긴다. 모르는 ID(목록에 없는 edge 목소리)는 edge로
    return next((p for p in TTS.values() if v in p.voices), TTS["edge"])


def choices() -> dict[str, str]:
    """화면·CLI 목소리 목록. 쓸 수 없는 공급자는 빠진다."""
    return {vid: name for p in TTS.values() if p.ready() for vid, name in p.voices.items()}


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


def synth(sentences: list[str], v: str, job_dir: Path, log) -> str:
    """읽은 공급자 이름. 한 영상 안에서 목소리가 섞이지 않게 대체 공급자는 처음부터 다시 읽는다."""
    first = owner(v)
    chain = [(owner(x), x) for x in (v, *(f for f in FALLBACK if owner(f) is not first)) if owner(x).ready()]
    if not chain:
        raise RuntimeError("읽을 수 있는 TTS가 없어요")
    for (p, vid), nxt in zip(chain, chain[1:] + [None]):
        try:
            _read_all(sentences, job_dir, log, lambda text, out: p.speak(vid, text, out))
            return p.label
        except Exception as e:
            if not nxt:
                raise
            log(f"{p.label} 실패({type(e).__name__}: {str(e)[:200]}) → {nxt[0].label}로 다시 읽어요")

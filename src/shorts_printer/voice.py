"""3단계 음성: 문장마다 읽어 잇는다. 문장 시각이 곧 자막 시각이다.
ElevenLabs(유료, 낱말 시각까지 받음) → edge-tts(무료, 키 없음, 비공식 Edge 엔드포인트) → macOS 내장 say(Yuna, 오프라인) 순서로,
앞 엔진이 안 되면 다음 엔진으로 전체를 다시 읽는다."""
import base64
import json
import shutil
import subprocess
import time
import wave
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import edge_tts
import edge_tts.communicate

from . import config, ffmpeg
from .jobs import atomic_write_json

RATE = 24000
GAP = 0.2   # 문장 사이 쉼(초)
ELEVENLABS = "https://api.elevenlabs.io/v1/text-to-speech/{}/with-timestamps?output_format=mp3_44100_128"
EDGE_DEFAULT = "ko-KR-SunHiNeural"   # ElevenLabs가 안 될 때 대신 읽을 목소리

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


def _eleven(voice_id: str):
    def speak(text: str, out: Path) -> tuple[Path, list[dict]]:
        body = json.dumps({"text": text, "model_id": config.ELEVENLABS_MODEL}).encode()
        req = Request(ELEVENLABS.format(voice_id), data=body, headers={
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
    return speak


def _edge(voice: str):
    def speak(text: str, out: Path) -> tuple[Path, None]:
        path = out.with_suffix(".mp3")
        for wait in (2, 5, 0):   # 429 같은 일시 오류는 두 번 더 해 본다
            try:
                edge_tts.Communicate(text, voice).save_sync(str(path))
                return path, None
            except Exception:
                if not wait:
                    raise
                time.sleep(wait)
    return speak


def _say(text: str, out: Path) -> tuple[Path, None]:
    path = out.with_suffix(".aiff")
    subprocess.run(["say", "-v", "Yuna", "-o", str(path), "--", text], check=True, capture_output=True)
    return path, None


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
            (src, ws), wav = speak(text, out / f"s{i:02d}"), out / f"s{i:02d}.wav"
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


def synth(sentences: list[str], voice: str, job_dir: Path, log) -> str:
    """엔진 이름을 돌려준다. 한 영상 안에서 목소리가 섞이지 않게 대체 엔진은 처음부터 다시 읽는다."""
    engines = [("edge-tts", _edge(voice))]
    if voice == "elevenlabs":
        engines = [("ElevenLabs", _eleven(config.ELEVENLABS_VOICE_ID)), ("edge-tts", _edge(EDGE_DEFAULT))]
    if shutil.which("say"):
        engines.append(("macOS say", _say))
    for (name, speak), nxt in zip(engines, engines[1:] + [None]):
        try:
            _read_all(sentences, job_dir, log, speak)
            return name
        except Exception as e:
            if not nxt:
                raise
            log(f"{name} 실패({type(e).__name__}: {str(e)[:200]}) → {nxt[0]}로 다시 읽어요")

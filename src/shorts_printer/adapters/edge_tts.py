"""Microsoft Edge 소리 내어 읽기 음성(TTS 포트). 무료·키 없음이라 확정 전 초안 음성에 쓴다.
비공식 서비스라 막힐 수 있어, 실패하면 fallback(macOS say)으로 읽는다."""
from pathlib import Path

import edge_tts

from ..ports.tts import TTS

VOICES = {"ko": "ko-KR-SunHiNeural", "ja": "ja-JP-NanamiNeural", "en": "en-US-JennyNeural"}   # 언어 기본 목소리


class EdgeTTS:
    label = "Edge TTS(초안)"
    hint = "무료 · 확정 전 미리 듣기용 · 막히면 macOS say로 읽는다"

    def __init__(self, language: str, fallback: TTS | None = None):
        self.voice = VOICES.get(language)
        self.fallback = fallback

    def ready(self) -> bool:
        return bool(self.voice) or bool(self.fallback and self.fallback.ready())

    def speak(self, voice: str, text: str, out: Path) -> tuple[Path, list[dict] | None]:
        """voice(채널 목소리 키)는 무시하고 언어 기본 목소리로 읽는다."""
        try:
            return self._edge(text, out)
        except Exception as e:
            # ponytail: 문장마다 따로 넘어가 한 초안에 목소리가 섞일 수 있다. 초안이라 그냥 둔다
            if not (self.fallback and self.fallback.ready()):
                raise RuntimeError(f"Edge TTS 실패: {str(e)[:200]}") from e
            return self.fallback.speak(voice, text, out)

    def _edge(self, text: str, out: Path) -> tuple[Path, list[dict]]:
        if not self.voice:
            raise RuntimeError("이 언어의 Edge 목소리가 없어요")
        path, tmp, words = out.with_suffix(".mp3"), out.with_suffix(".mp3.tmp"), []
        with tmp.open("wb") as f:
            for c in edge_tts.Communicate(text, self.voice, boundary="WordBoundary").stream_sync():
                if c["type"] == "audio":
                    f.write(c["data"])
                elif c["type"] == "WordBoundary":
                    words.append({"text": c["text"], "start": c["offset"] / 1e7})   # offset은 100ns 단위
        if not tmp.stat().st_size:
            tmp.unlink()
            raise RuntimeError("Edge TTS가 소리를 주지 않았어요")
        tmp.replace(path)
        return path, words

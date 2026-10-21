"""macOS 내장 say 음성(TTS 포트). 무료라 확정 전 초안 음성에만 쓴다(상업용 사용은 허락되지 않는다)."""
import shutil
import subprocess

VOICES = {"ko": "Yuna", "ja": "Kyoko", "en": "Samantha"}   # 언어마다 기본으로 깔린 목소리


class MacSay:
    label = "macOS say(초안)"
    hint = "무료 · 확정 전 미리 듣기용 · macOS에서만"

    def __init__(self, language: str):
        self.voice = VOICES.get(language)

    def ready(self) -> bool:
        return bool(shutil.which("say"))

    def speak(self, voice, text, out):
        """voice(채널 목소리 키)는 무시하고 언어 기본 목소리로 읽는다."""
        path = out.with_suffix(".aiff")
        r = subprocess.run(["say", *(["-v", self.voice] if self.voice else []), "-o", str(path), text],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"macOS say 실패: {r.stderr.strip()[:200]}")
        return path, None

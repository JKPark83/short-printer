"""Google Flow 자동 공급자: 전용 Chrome(sp chrome으로 한 번 로그인)에 CDP로 붙어 사람이 하던 클릭을 대신한다.
Flow는 API가 없어 화면을 누른다. 화면이 바뀌면 장면을 건너뛰어 "클립 대기"로 남고, 직접 올리면 된다."""
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

from . import config

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = config.ROOT / ".secrets" / "flow-chrome"   # Chrome 136+는 기본 프로필에 디버그 포트를 안 연다
PORT = 9333
FLOW = "https://flow.google.com/"
# 설정 팝오버 radio 이름. 순서가 중요하다(동영상을 골라야 나머지가 나온다). 장면 하나에 6크레딧
SETTINGS = ("동영상", "소재", "9:16", "360p", "8초", "x1")
MODEL = "Omni 1.1 Flash"
GEN_TIMEOUT = 360   # 초. 보통 2분 안팎
TILE = '.container:has(button[aria-label="프롬프트 재사용"])'


def _up() -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2):
            return True
    except OSError:
        return False


def open_chrome() -> None:
    """전용 Chrome을 디버그 포트로 띄운다. 이미 떠 있으면 그대로 둔다. 서버와 따로 산다."""
    if _up():
        return
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}", "--lang=ko",
                      "--no-first-run", "--no-default-browser-check", FLOW],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(30):
        if _up():
            return
        time.sleep(0.5)
    raise RuntimeError("Flow용 Chrome을 띄우지 못했어요")


def _settings(page) -> None:
    page.locator('button[aria-label="설정 트리거"]').click()
    for name in SETTINGS:
        r = page.locator('button[role="radio"]', has_text=name).first
        if r.get_attribute("aria-checked") != "true":
            r.click()
    m = page.locator('button[aria-label="모델 제품군 선택"]')
    if MODEL not in m.inner_text():
        m.click()
        page.get_by_text(MODEL, exact=True).last.click()
    page.keyboard.press("Escape")
    got = page.locator('button[aria-label="설정 트리거"]').inner_text()
    if not all(w in got for w in ("동영상", "360p", "8초", "crop_9_16", "x1")):
        raise RuntimeError(f"Flow 설정을 맞추지 못했어요: {got}")


def _generate(page, prompt: str, path: Path) -> None:
    """프롬프트 하나 → 새 타일이 끝나면 원본 크기로 받아 path에. 실패하면 던진다(장면만 건너뜀)."""
    page.evaluate(f"document.querySelectorAll('{TILE}').forEach(t => t.dataset.sp = '1')")
    box = page.locator('[contenteditable="true"]').first
    box.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(prompt)
    page.locator('button[aria-label="생성 시작"]').click()
    tile = page.locator(f"{TILE}:not([data-sp])").first
    tile.wait_for(timeout=30_000)
    # 끝난 타일에만 옵션 메뉴가 붙는다
    tile.locator('button[aria-label="옵션 더보기"]').wait_for(state="attached", timeout=GEN_TIMEOUT * 1000)
    tile.hover()
    with page.expect_download(timeout=60_000) as d:
        tile.locator('button[aria-label="옵션 더보기"]').click()
        page.locator('[role="menuitem"]', has_text="다운로드").first.hover()
        page.locator('[role="menuitem"]', has_text="원본 크기").first.click()
    tmp = path.with_suffix(".tmp.mp4")
    d.value.save_as(tmp)
    os.replace(tmp, path)


class FlowAuto:
    label = "Google Flow(자동)"
    hint = "Flow 크레딧 · 장면마다 6크레딧 · 처음 한 번 uv run sp chrome으로 띄운 창에서 Google 로그인"

    def ready(self) -> bool:
        return Path(CHROME).exists()

    def make(self, scenes, out, log):
        from playwright.sync_api import sync_playwright   # 이 공급자를 쓸 때만 불러온다

        scenes = [s for s in scenes if s["prompt"]]
        if not scenes:
            return
        open_chrome()
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
            page = browser.contexts[0].new_page()
            try:
                page.goto(FLOW)
                new = page.locator('button:has-text("새 프로젝트")').first
                try:
                    new.wait_for(timeout=30_000)
                except Exception:  # noqa: BLE001 — 로그인 화면이면 버튼이 없다
                    raise RuntimeError("Flow에 로그인이 필요해요. uv run sp chrome으로 띄운 창에서 로그인한 뒤 다시 시도하세요") from None
                new.click()   # 작업마다 프로젝트 하나
                page.wait_for_url("**/project/**")
                _settings(page)
                log(f"Flow 프로젝트: {page.url}")
                # ponytail: 장면을 하나씩 만든다(7장면 약 15분). 느리면 한꺼번에 넣고 타일을 프롬프트로 짝지을 것
                for s in scenes:
                    t0 = time.monotonic()
                    try:
                        _generate(page, s["prompt"], out / s["file"])
                    except Exception as e:  # noqa: BLE001 — 그 장면만 직접 올리게 남긴다
                        log(f"Flow: 장면 {s['i'] + 1} 못 만듦({type(e).__name__}: {str(e)[:120]}) → 직접 올려 주세요")
                        continue
                    log(f"Flow: 장면 {s['i'] + 1} 완료 ({time.monotonic() - t0:.0f}s)")
                    yield {"file": s["file"], "source": self.label, "url": page.url}
            finally:
                page.close()

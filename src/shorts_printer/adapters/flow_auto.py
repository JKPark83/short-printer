"""Google Flow 자동 공급자: 전용 Chrome(sp chrome으로 한 번 로그인)에 CDP로 붙어 사람이 하던 클릭을 대신한다.
Flow는 API가 없어 화면을 누른다. 화면이 바뀌면 장면을 건너뛰어 "클립 대기"로 남고, 직접 올리면 된다."""
import hashlib
import os
import time
from pathlib import Path

from .chrome import CHROME, FLOW, PORT, open_chrome

# 설정 팝오버 radio 이름. 순서가 중요하다(동영상을 골라야 나머지가 나온다). 장면 하나에 6크레딧
SETTINGS = ("동영상", "소재", "9:16", "360p", "8초", "x1")
MODEL = "Omni 1.1 Flash"
GEN_TIMEOUT = 360   # 초. 보통 2분 안팎
RETRY_AFTER = 300   # 초. 실패한 장면은 이만큼 뒤 한 번만 다시
TILE = '.container:has(button[aria-label="프롬프트 재사용"])'


class Refused(RuntimeError):
    """Flow가 정책으로 거절했다. 같은 프롬프트로 다시 해도 또 거절되므로 다시 시도하지 않는다."""


def _settings(page) -> None:
    # 에이전트 모드(새 로그인 첫 기본값)면 설정 버튼이 숨는다. 끄면 Flow가 기억한다
    chip = page.locator("button.agent-mode-chip").first
    chip.wait_for(timeout=30_000)
    if chip.get_attribute("aria-pressed") == "true":
        chip.click()
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


class Lost(RuntimeError):
    """생성은 넣었는데 받지 못했다. 다시 넣으면 크레딧이 또 들므로 다시 넣지 않는다."""


# Flow는 타일 컨테이너를 겹쳐 두고(한 영상이 두 번 잡힌다) 다시 그릴 때 DOM 표시·썸네일 주소를 바꾼다.
# 그래서 가장 안쪽 타일만 세고, 새 타일은 맨 앞에 붙는 것으로 알아본다
SNAPSHOT = f"""() => [...document.querySelectorAll('{TILE}')].filter(t => !t.querySelector('{TILE}')).map(t => ({{
  done: !!t.querySelector('button[aria-label="옵션 더보기"]'),
  error: t.querySelector('.error-message-text')?.innerText || null}}))"""


def _state(tiles: list[dict]) -> tuple[str, str] | None:
    """맨 앞(새) 타일이 끝났으면 ("done", ""), 거절됐으면 ("error", 문구), 아직이면 None."""
    t = tiles[0]
    return ("error", t["error"]) if t["error"] else ("done", "") if t["done"] else None


def _wait(page, until, timeout: int):
    """until(타일 목록)이 참이 될 때까지 2초마다 본다."""
    end = time.monotonic() + timeout
    while not (got := until(page.evaluate(SNAPSHOT))):
        if time.monotonic() > end:
            raise TimeoutError(f"Flow 타일을 {timeout}초 기다렸어요")
        page.wait_for_timeout(2000)
    return got


def _generate(page, prompt: str, path: Path) -> None:
    """프롬프트 하나 → 새 타일이 끝나면 원본 크기로 받아 path에. 실패하면 던진다(장면만 건너뜀)."""
    before = len(page.evaluate(SNAPSHOT))
    box = page.locator('[contenteditable="true"]').first
    box.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(prompt)
    page.locator('button[aria-label="생성 시작"]').click()
    _wait(page, lambda now: len(now) > before, 30)   # 넣었는지만 빨리 본다. 안 늘면 안 들어간 것이라 다시 넣어도 된다
    try:
        _download(page, path)
    except Refused:
        raise
    except Exception as e:  # noqa: BLE001
        raise Lost(f"{type(e).__name__}: {e}") from e


def _download(page, path: Path) -> None:
    # 끝난 타일에만 옵션 메뉴가 붙는다. 거절은 몇 초 만에 오류 타일로 뜨니 기다리지 않고 바로 던진다
    kind, text = _wait(page, lambda now: _state(now), GEN_TIMEOUT)
    if kind == "error":
        raise Refused(" ".join(text.split()) or "Flow가 이 프롬프트를 거절했어요")
    tile = page.locator(TILE).filter(has_not=page.locator(TILE)).first
    tile.hover()
    with page.expect_download(timeout=60_000) as d:
        tile.locator('button[aria-label="옵션 더보기"]').click()
        page.locator('[role="menuitem"]', has_text="다운로드").first.hover()
        page.locator('[role="menuitem"]', has_text="원본 크기").first.click()
    tmp = path.with_suffix(".tmp.mp4")
    d.value.save_as(tmp)
    if not tmp.stat().st_size:   # 다운로드가 끊기면 0바이트가 남는다. 완료로 치지 않고 다시 받게 던진다
        tmp.unlink()
        raise RuntimeError(f"Flow 다운로드가 비었어요({d.value.failure() or '0바이트'})")
    os.replace(tmp, path)


class FlowAuto:
    label = "Google Flow(자동)"
    hint = "Flow 크레딧 · 장면마다 6크레딧 · 처음 한 번 uv run sp chrome으로 띄운 창에서 Google 로그인"

    def ready(self) -> bool:
        return Path(CHROME).exists()

    def make(self, scenes, out, log):
        from playwright.sync_api import sync_playwright  # 이 공급자를 쓸 때만 불러온다

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
                failed, left = [], []
                seen: dict[str, int] = {}

                def fresh(s) -> bool:
                    """앞 장면과 같은 영상을 받았으면(타일을 잘못 짚음) 버리고 못 만든 장면으로 남긴다."""
                    f = out / s["file"]
                    digest = hashlib.md5(f.read_bytes()).hexdigest()
                    if digest in seen:
                        f.unlink()
                        log(f"Flow: 장면 {s['i'] + 1}에 장면 {seen[digest] + 1}과 같은 영상이 받아져 버렸어요")
                        left.append(s["i"] + 1)
                        return False
                    seen[digest] = s["i"]
                    return True

                for s in scenes:
                    t0 = time.monotonic()
                    try:
                        _generate(page, s["prompt"], out / s["file"])
                    except Refused as e:
                        log(f"Flow: 장면 {s['i'] + 1} 거절됨({str(e)[:120]})")
                        left.append(s["i"] + 1)
                        continue
                    except Lost as e:
                        log(f"Flow: 장면 {s['i'] + 1} 넣었지만 받지 못함({str(e)[:120]}) → 크레딧이 또 들지 않게 다시 넣지 않아요")
                        left.append(s["i"] + 1)
                        continue
                    except Exception as e:  # noqa: BLE001 — 나머지 장면을 먼저 만들고 나중에 한 번 더
                        log(f"Flow: 장면 {s['i'] + 1} 못 만듦({type(e).__name__}: {str(e)[:120]}) → {RETRY_AFTER // 60}분 뒤 한 번 더")
                        failed.append((s, time.monotonic()))
                        continue
                    if not fresh(s):
                        continue
                    log(f"Flow: 장면 {s['i'] + 1} 완료 ({time.monotonic() - t0:.0f}s)")
                    yield {"file": s["file"], "source": self.label, "url": page.url}
                for s, at in failed:   # 실패한 때부터 5분 뒤 딱 한 번(크레딧이 또 든다)
                    time.sleep(max(0, at + RETRY_AFTER - time.monotonic()))
                    t0 = time.monotonic()
                    try:
                        _generate(page, s["prompt"], out / s["file"])
                    except Exception as e:  # noqa: BLE001 — 그 장면만 남기고 끝에 실패로 알린다
                        log(f"Flow: 장면 {s['i'] + 1} 다시 해도 못 만듦({type(e).__name__}: {str(e)[:120]})")
                        left.append(s["i"] + 1)
                        continue
                    if not fresh(s):
                        continue
                    log(f"Flow: 장면 {s['i'] + 1} 다시 시도해 완료 ({time.monotonic() - t0:.0f}s)")
                    yield {"file": s["file"], "source": self.label, "url": page.url}
                if left:   # 만든 장면은 위에서 기록됐다. 못 만든 장면은 대기로 두지 않고 실패로 알린다
                    raise RuntimeError(f"Flow가 장면 {', '.join(map(str, sorted(left)))}을 못 만들었어요. "
                                       "로그의 사유를 보고 프롬프트를 고쳐 다시 시도하거나 클립을 직접 올려 주세요")
            finally:
                page.close()

"""Google Flow 자동 공급자: 전용 Chrome(sp chrome으로 한 번 로그인)에 CDP로 붙어 사람이 하던 클릭을 대신한다.
Flow는 API가 없어 화면을 누른다. 화면이 바뀌면 장면을 건너뛰어 "클립 대기"로 남고, 직접 올리면 된다."""
import base64
import hashlib
import json
import os
import time
from pathlib import Path

from ..infra.store import atomic_write_text
from ..ports import video
from .chrome import CHROME, FLOW, PORT, open_chrome, up

SCENE_CREDITS = 12   # 장면 하나에 드는 크레딧
MODEL = "Omni 1.1 Flash"
GEN_TIMEOUT = 360   # 초. 보통 2분 안팎
RETRY_AFTER = 300   # 초. 실패한 장면은 이만큼 뒤 한 번만 다시
TILE = '.container:has(button[aria-label="프롬프트 재사용"])'
# 받은 영상(blob:)을 페이지 안에서 읽는다. Chrome 다운로드 폴더는 CDP로 붙은 마지막 연결 것이라,
# 크레딧 조회·스튜디오 업로드가 붙었다 떨어지면 그 폴더가 지워져 이후 다운로드가 0바이트가 된다
READ_BLOB = """async u => { const b = await (await fetch(u)).blob();
  return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result.split(',')[1]); f.readAsDataURL(b); }); }"""


class Refused(RuntimeError):
    """Flow가 정책으로 거절했다. 같은 프롬프트로 다시 해도 또 거절되므로 다시 시도하지 않는다."""


def _settings(page, aspect: str) -> None:
    # 에이전트 모드(새 로그인 첫 기본값)면 설정 버튼이 숨는다. 끄면 Flow가 기억한다
    chip = page.locator("button.agent-mode-chip").first
    chip.wait_for(timeout=30_000)
    if chip.get_attribute("aria-pressed") == "true":
        chip.click()
    page.locator('button[aria-label="설정 트리거"]').click()
    # 설정 팝오버 radio 이름. 순서가 중요하다(동영상을 골라야 나머지가 나온다). aspect는 "9:16"·"16:9"
    for name in ("동영상", "소재", aspect, "720p", "8초", "x1"):
        r = page.locator('button[role="radio"]', has_text=name).first
        if r.get_attribute("aria-checked") != "true":
            r.click()
    m = page.locator('button[aria-label="모델 제품군 선택"]')
    if MODEL not in m.inner_text():
        m.click()
        page.get_by_text(MODEL, exact=True).last.click()
    page.keyboard.press("Escape")
    got = page.locator('button[aria-label="설정 트리거"]').inner_text()
    if not all(w in got for w in ("동영상", "720p", "8초", "crop_" + aspect.replace(":", "_"), "x1")):
        raise RuntimeError(f"Flow 설정을 맞추지 못했어요: {got}")


class Lost(RuntimeError):
    """생성은 넣었는데 받지 못했다. 다시 넣으면 크레딧이 또 들므로 다시 넣지 않고, 끝에 새로 불러와 다시 받는다."""

    def __init__(self, msg: str, pos: int):
        super().__init__(msg)
        self.pos = pos   # 거절 아닌 타일 가운데 오래된 쪽부터 센 자리. 새 타일은 맨 앞에 붙어 이 자리는 안 바뀐다


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
    tiles = page.evaluate(SNAPSHOT)
    before, pos = len(tiles), sum(not t["error"] for t in tiles)
    box = page.locator('[contenteditable="true"]').first
    box.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(prompt)
    page.locator('button[aria-label="생성 시작"]').click()
    _wait(page, lambda now: len(now) > before, 30)   # 넣었는지만 빨리 본다. 안 늘면 안 들어간 것이라 다시 넣어도 된다
    # 넣은 자리를 남긴다: 받기 전에 서버가 꺼지거나 끝내 못 받아도 다시 시도 때 다시 넣지 않고 이 프로젝트에서 받는다
    atomic_write_text(path.with_suffix(".task"), json.dumps({"url": page.url, "pos": pos}))
    try:
        _download(page, path)
    except Refused:
        path.with_suffix(".task").unlink()
        raise
    except Exception as e:  # noqa: BLE001
        raise Lost(f"{type(e).__name__}: {e}", pos) from e


def _download(page, path: Path) -> None:
    # 끝난 타일에만 옵션 메뉴가 붙는다. 거절은 몇 초 만에 오류 타일로 뜨니 기다리지 않고 바로 던진다
    kind, text = _wait(page, lambda now: _state(now), GEN_TIMEOUT)
    if kind == "error":
        raise Refused(" ".join(text.split()) or "Flow가 이 프롬프트를 거절했어요")
    _save(page, page.locator(TILE).filter(has_not=page.locator(TILE)).first, path)


def _ok_index(tiles: list[dict], pos: int) -> int | None:
    """오래된 쪽부터 pos번째인 거절 아닌 타일의 화면 순서. 아직 안 보이면 None."""
    ok = [i for i, t in enumerate(tiles) if not t["error"]]
    return ok[-1 - pos] if pos < len(ok) else None


def _refetch(page, pos: int, path: Path) -> None:
    """받지 못한 타일을 (새로 불러온) 프로젝트에서 자리로 찾아 다시 받는다. 받기는 크레딧이 들지 않는다.
    프롬프트가 화면에 없어 자리로 짚는다. 잘못 짚으면 make()의 fresh()가 같은 영상을 걸러 낸다."""
    tiles = _wait(page, lambda now: now if _ok_index(now, pos) is not None else None, 60)
    i = _ok_index(tiles, pos)
    if not tiles[i]["done"]:
        raise RuntimeError("Flow 타일이 아직 끝나지 않았어요")
    _save(page, page.locator(TILE).filter(has_not=page.locator(TILE)).nth(i), path)


def _save(page, tile, path: Path) -> None:
    tmp = path.with_suffix(".tmp.mp4")
    # 다운로드는 페이지가 받아 둔 영상(blob:)을 저장한다. 타일이 막 끝나면 아직 비어 0바이트가 오니
    # 조금 기다렸다 다시 받는다(받기는 크레딧이 들지 않는다)
    for wait in (0, 5, 15, 30):
        page.wait_for_timeout(wait * 1000)
        tile.hover()
        with page.expect_download(timeout=60_000) as d:
            tile.locator('button[aria-label="옵션 더보기"]').click()
            page.locator('[role="menuitem"]', has_text="다운로드").first.hover()
            page.locator('[role="menuitem"]', has_text="원본 크기").first.click()
        if data := base64.b64decode(page.evaluate(READ_BLOB, d.value.url)):
            tmp.write_bytes(data)
            os.replace(tmp, path)
            path.with_suffix(".task").unlink(missing_ok=True)
            return
    raise RuntimeError("Flow 다운로드가 비었어요(0바이트)")


def _count(text: str) -> int:
    """"Google Flow 크레딧 5,883개" → 5883."""
    digits = "".join(c for c in text if c.isdigit())
    if not digits:
        raise RuntimeError(f"Flow 크레딧 문구를 못 읽었어요: {text}")
    return int(digits)


class FlowAuto:
    label = "Google Flow(자동)"
    hint = f"Flow 크레딧 · 장면마다 {SCENE_CREDITS}크레딧 · 처음 한 번 uv run sp chrome으로 띄운 창에서 Google 로그인"

    def __init__(self, aspect: str = "9:16"):
        self.aspect = aspect   # Flow 설정의 화면비 이름. 쇼츠 9:16, 롱폼 16:9

    def ready(self) -> bool:
        return Path(CHROME).exists()

    def cost(self, n: int) -> int:
        """장면 n개를 만드는 크레딧."""
        return n * SCENE_CREDITS

    def credits(self) -> int:
        """계정 패널의 "Google Flow 크레딧 5,883개"를 읽는다. 전용 Chrome이 꺼져 있으면 띄우지 않고 던진다."""
        from playwright.sync_api import sync_playwright  # 이 공급자를 쓸 때만 불러온다

        if not up():
            raise RuntimeError("전용 Chrome이 꺼져 있어요. uv run sp chrome으로 띄우면 보여요")
        with sync_playwright() as p:
            page = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}").contexts[0].new_page()
            try:
                page.goto(FLOW)
                try:
                    page.locator('[aria-label="계정 세부정보"]').first.click(timeout=20_000)
                    text = page.locator(".credits-count").first.inner_text(timeout=10_000)
                except Exception:  # noqa: BLE001 — 로그인 화면이거나 화면이 바뀌었다
                    raise RuntimeError("Flow 크레딧을 읽지 못했어요. 전용 Chrome에서 로그인했는지 봐 주세요") from None
            finally:
                page.close()
        return _count(text)

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
                failed, left, lost, refused = [], [], [], {}
                # 이미 있는 장면 영상도 넣어 둔다: 지난 프로젝트에서 자리로 받다 잘못 짚으면 걸러 낸다
                seen = {hashlib.md5(f.read_bytes()).hexdigest(): int(f.stem[4:])
                        for f in out.glob("clip*.mp4") if f.stem[4:].isdigit()}

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

                # 지난 시도에서 넣고 못 받은 장면은 다시 넣으면 크레딧이 또 드니, 그 프로젝트에서 먼저 찾아 받는다
                todo = []
                for s in scenes:
                    task = (out / s["file"]).with_suffix(".task")
                    if not task.exists():
                        todo.append(s)
                        continue
                    t = json.loads(task.read_text())
                    try:
                        if page.url != t["url"]:
                            page.goto(t["url"])
                        _refetch(page, t["pos"], out / s["file"])
                    except Exception as e:  # noqa: BLE001 — 프로젝트가 지워졌거나 타일이 없으면 새로 만든다
                        log(f"Flow: 장면 {s['i'] + 1} 지난 프로젝트에서 못 받음({type(e).__name__}: {str(e)[:120]}) → 새로 만들어요")
                        task.unlink()
                        todo.append(s)
                        continue
                    if fresh(s):
                        log(f"Flow: 장면 {s['i'] + 1} 지난 프로젝트에서 받음")
                        yield {"file": s["file"], "source": self.label, "url": t["url"]}
                if todo:
                    page.goto(FLOW)
                    new = page.locator('button:has-text("새 프로젝트")').first
                    try:
                        new.wait_for(timeout=30_000)
                    except Exception:  # noqa: BLE001 — 로그인 화면이면 버튼이 없다
                        raise RuntimeError("Flow에 로그인이 필요해요. uv run sp chrome으로 띄운 창에서 로그인한 뒤 다시 시도하세요") from None
                    new.click()   # 작업마다 프로젝트 하나
                    page.wait_for_url("**/project/**")
                    _settings(page, self.aspect)
                    log(f"Flow 프로젝트: {page.url}")
                # ponytail: 장면을 하나씩 만든다(7장면 약 15분). 느리면 한꺼번에 넣고 타일을 프롬프트로 짝지을 것
                for s in todo:
                    t0 = time.monotonic()
                    try:
                        _generate(page, s["prompt"], out / s["file"])
                    except Refused as e:
                        log(f"Flow: 장면 {s['i'] + 1} 거절됨({str(e)[:120]})")
                        left.append(s["i"] + 1)
                        refused[s["i"]] = str(e)
                        continue
                    except Lost as e:
                        log(f"Flow: 장면 {s['i'] + 1} 넣었지만 받지 못함({str(e)[:120]}) → 다시 넣지 않고 끝에 새로 불러와 받아요")
                        lost.append((s, e.pos))
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
                    except Lost as e:
                        log(f"Flow: 장면 {s['i'] + 1} 다시 넣었지만 받지 못함({str(e)[:120]}) → 끝에 새로 불러와 받아요")
                        lost.append((s, e.pos))
                        continue
                    except Exception as e:  # noqa: BLE001 — 그 장면만 남기고 끝에 실패로 알린다
                        log(f"Flow: 장면 {s['i'] + 1} 다시 해도 못 만듦({type(e).__name__}: {str(e)[:120]})")
                        left.append(s["i"] + 1)
                        continue
                    if not fresh(s):
                        continue
                    log(f"Flow: 장면 {s['i'] + 1} 다시 시도해 완료 ({time.monotonic() - t0:.0f}s)")
                    yield {"file": s["file"], "source": self.label, "url": page.url}
                if lost:   # 오래 쓴 탭은 새 영상을 빈 채로 줄 때가 있다. 새로 불러오면 받힌다
                    page.reload()
                for s, pos in lost:
                    try:
                        _refetch(page, pos, out / s["file"])
                    except Exception as e:  # noqa: BLE001 — 그 장면만 남기고 끝에 실패로 알린다
                        log(f"Flow: 장면 {s['i'] + 1} 새로 불러와도 받지 못함({type(e).__name__}: {str(e)[:120]}) "
                            "→ Flow 프로젝트에서 직접 받아 올려 주세요")
                        left.append(s["i"] + 1)
                        continue
                    if not fresh(s):
                        continue
                    log(f"Flow: 장면 {s['i'] + 1} 새로 불러와 받음")
                    yield {"file": s["file"], "source": self.label, "url": page.url}
                if left:   # 만든 장면은 위에서 기록됐다. 못 만든 장면은 대기로 두지 않고 실패로 알린다
                    msg = f"Flow가 장면 {', '.join(map(str, sorted(left)))}을 못 만들었어요. "
                    if refused:
                        raise video.Refused(msg + "[다시 시도]하면 거절된 장면은 정책을 피하게 프롬프트를 고쳐 다시 만들어요",
                                            refused)
                    raise RuntimeError(msg + "로그의 사유를 보고 다시 시도하거나 클립을 직접 올려 주세요")
            finally:
                page.close()

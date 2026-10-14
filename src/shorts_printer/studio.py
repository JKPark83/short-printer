"""YouTube 스튜디오 화면으로 올리기: API 업로드 한도(uploadLimitExceeded)에 걸렸을 때만 쓴다.
Flow 자동과 같은 전용 Chrome(같은 Google 계정)을 눌러 비공개로 올린다. 화면이 바뀌면 실패로 남고 직접 올리면 된다."""
from pathlib import Path

from .flow_auto import PORT, open_chrome

STUDIO = "https://studio.youtube.com/"
UPLOAD_TIMEOUT = 300   # 초. 몇 MB라 보통 몇 초


def _details(page, snippet: dict) -> str:
    """파일이 올라간 업로드 대화상자에서 세부정보를 채우고 비공개로 저장한다. 영상 id를 돌려준다."""
    page.locator("#title-textarea #textbox").fill(snippet["title"])
    page.locator("#description-textarea #textbox").fill(snippet["description"])
    page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()
    page.locator("#toggle-button").click()   # 자세히 보기: 태그
    if snippet["tags"]:
        page.locator('input#text-input[aria-label="태그"]').fill(",".join(snippet["tags"]) + ",")
    link = page.locator('ytcp-uploads-dialog a[href*="youtube.com/shorts/"]').first
    video_id = link.get_attribute("href").rstrip("/").rsplit("/", 1)[-1]
    for _ in range(3):   # 동영상 요소 → 검토 → 공개 상태
        page.locator("#next-button").click()
    page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
    # 올리는 중에 창을 닫으면 끊긴다. 다 올라간 뒤 저장
    page.locator("ytcp-video-upload-progress", has_text="업로드 완료").wait_for(timeout=UPLOAD_TIMEOUT * 1000)
    page.locator("#done-button").click()
    page.locator("ytcp-uploads-dialog").wait_for(state="hidden", timeout=60_000)
    return video_id


def upload(path: Path, meta: dict) -> str:
    """youtube.metadata() 본문으로 비공개 업로드하고 영상 id를 돌려준다."""
    from playwright.sync_api import sync_playwright   # 이 경로를 쓸 때만 불러온다

    open_chrome()
    with sync_playwright() as p:
        page = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}").contexts[0].new_page()
        try:
            page.goto(STUDIO)
            up = page.locator("#upload-icon")
            try:
                up.wait_for(timeout=30_000)
            except Exception:  # noqa: BLE001 — 로그인 화면이면 버튼이 없다
                raise RuntimeError("YouTube 스튜디오에 로그인이 필요해요. uv run sp chrome으로 띄운 창에서 로그인한 뒤 다시 올리세요") from None
            up.click()
            page.locator('input[type="file"]').set_input_files(path)
            page.locator("#title-textarea #textbox").wait_for(timeout=60_000)
            return _details(page, meta["snippet"])
        finally:
            page.close()

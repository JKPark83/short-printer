"""YouTube 스튜디오 화면으로 올리기: API 업로드 한도(uploadLimitExceeded)에 걸렸을 때만 쓴다.
Flow 자동과 같은 전용 Chrome(같은 Google 계정)을 눌러 비공개로 올린다. 화면이 바뀌면 실패로 남고 직접 올리면 된다."""
import re
from pathlib import Path

from .chrome import PORT, open_chrome

STUDIO = "https://studio.youtube.com/"
UPLOAD_TIMEOUT = 300   # 초. 쇼츠는 몇 MB라 보통 몇 초
SEC_PER_MB = 2   # 롱폼(1 GB 남짓)은 크기에 비례해 기다린다. 0.5 MB/s 회선 기준
# 쇼츠는 youtube.com/shorts/ID, 16:9 영상은 youtu.be/ID나 watch?v=ID 링크가 뜬다
LINK = ('ytcp-uploads-dialog a[href*="youtube.com/shorts/"], ytcp-uploads-dialog a[href*="youtu.be/"], '
        'ytcp-uploads-dialog a[href*="/watch?v="]')


def video_id(href: str) -> str:
    """업로드 대화상자 링크에서 영상 id(11자)를 꺼낸다."""
    m = re.search(r"(?:/shorts/|youtu\.be/|[?&]v=)([\w-]{11})", href)
    if not m:
        raise RuntimeError(f"스튜디오 링크에서 영상 id를 못 찾았어요: {href}")
    return m.group(1)


def wait_seconds(path: Path) -> int:
    """파일이 다 올라가길 기다릴 시간(초). 작은 파일은 UPLOAD_TIMEOUT."""
    return max(UPLOAD_TIMEOUT, path.stat().st_size // 2**20 * SEC_PER_MB)


def _details(page, snippet: dict, wait: int) -> str:
    """파일이 올라간 업로드 대화상자에서 세부정보를 채우고 비공개로 저장한다. 영상 id를 돌려준다."""
    page.locator("#title-textarea #textbox").fill(snippet["title"])
    page.locator("#description-textarea #textbox").fill(snippet["description"])
    page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()
    page.locator("#toggle-button").click()   # 자세히 보기: 태그
    if snippet["tags"]:
        page.locator('input#text-input[aria-label="태그"]').fill(",".join(snippet["tags"]) + ",")
    vid = video_id(page.locator(LINK).first.get_attribute("href"))
    for _ in range(3):   # 동영상 요소 → 검토 → 공개 상태
        page.locator("#next-button").click()
    page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
    # 올리는 중에 창을 닫으면 끊긴다. 다 올라간 뒤 저장
    page.locator("ytcp-video-upload-progress", has_text="업로드 완료").wait_for(timeout=wait * 1000)
    page.locator("#done-button").click()
    page.locator("ytcp-uploads-dialog").wait_for(state="hidden", timeout=60_000)
    return vid


def upload(path: Path, meta: dict, channel_id: str = "") -> str:
    """youtube.metadata() 본문으로 비공개 업로드하고 영상 id를 돌려준다.
    channel_id(UC…)가 있으면 그 채널 스튜디오로 간다(브랜드 채널). 없으면 Chrome에서 마지막으로 고른 채널."""
    from playwright.sync_api import sync_playwright  # 이 경로를 쓸 때만 불러온다

    open_chrome()
    with sync_playwright() as p:
        page = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}").contexts[0].new_page()
        try:
            page.goto(f"https://studio.youtube.com/channel/{channel_id}" if channel_id else STUDIO)
            up = page.locator("#upload-icon")
            try:
                up.wait_for(timeout=30_000)
            except Exception:  # noqa: BLE001 — 로그인 화면이면 버튼이 없다
                raise RuntimeError("YouTube 스튜디오에 로그인이 필요해요. uv run sp chrome으로 띄운 창에서 로그인한 뒤 다시 올리세요") from None
            up.click()
            page.locator('input[type="file"]').set_input_files(path)
            page.locator("#title-textarea #textbox").wait_for(timeout=60_000)
            return _details(page, meta["snippet"], wait_seconds(path))
        finally:
            page.close()

"""YouTube 성과 읽기(ChannelAnalytics 포트). 업로드와 같은 채널 토큰을 쓰고 yt-analytics.readonly 범위가 있어야 한다.
GET만 하고, 같은 요청은 5분 동안 메모리에서 돌려준다(화면을 오가도 할당량을 다시 쓰지 않게)."""
import copy
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import youtube

DATA = "https://www.googleapis.com/youtube/v3/"
REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
RESOURCES = ("channels", "videos", "playlistItems")
CACHE = 300   # 초
RELOGIN = ("채널 성과를 읽을 권한이 없어요. 터미널에서 uv run sp youtube-login --channel {channel}을 한 번 더 하세요"
           "(분석 권한이 더해졌어요).")
DISABLED = "Google Cloud 프로젝트에서 YouTube Analytics API를 켜야 해요(API 및 서비스 → 라이브러리)."


class YouTubeAnalytics:
    label = "YouTube 성과"

    def __init__(self, token: Path, channel: str):
        self.token, self.channel = token, channel
        self._cache: dict[str, tuple[float, dict]] = {}
        self._access, self._until = "", 0.0
        self._lock = threading.Lock()   # 화면 요청(스레드 풀)과 core의 동시 요청이 같은 인스턴스를 쓴다

    @property
    def hint(self) -> str:
        if self.ready():
            return "채널 성과를 읽어요"
        return f"선택 · .env에 YOUTUBE_CLIENT_SECRET, 터미널에서 uv run sp youtube-login --channel {self.channel}"

    def ready(self) -> bool:
        return youtube.ready(self.token)

    def data(self, resource: str, **params) -> dict:
        if resource not in RESOURCES:
            raise RuntimeError(f"읽지 않는 YouTube 자원이에요: {resource}")
        return self._get(DATA + resource, params)

    def report(self, **params) -> dict:
        return self._get(REPORTS, params)

    def _auth(self) -> str:
        with self._lock:
            return self._fresh()

    def _fresh(self) -> str:
        if self._access and time.time() < self._until:
            return self._access
        try:
            got = youtube.refresh(self.token)
        except youtube.Expired:
            raise RuntimeError(youtube.EXPIRED.format(channel=self.channel)) from None
        if youtube.ANALYTICS_SCOPE not in got.get("scope", "").split():
            raise RuntimeError(RELOGIN.format(channel=self.channel))
        self._access, self._until = got["access_token"], time.time() + int(got.get("expires_in", 3600)) - 60
        return self._access

    def _get(self, base: str, params: dict) -> dict:
        url = base + "?" + urlencode(params)
        with self._lock:
            hit = self._cache.get(url)
        if hit and time.time() - hit[0] < CACHE:
            return copy.deepcopy(hit[1])
        err = None
        for attempt in range(3):
            try:   # 토큰 갱신(_auth)도 네트워크라 같은 try 안에서 받는다
                req = Request(url, headers={"Authorization": f"Bearer {self._auth()}", "Accept": "application/json"})
                with urlopen(req, timeout=20) as r:
                    body = json.loads(r.read() or b"{}")
                break
            except HTTPError as e:
                if e.code == 401 and attempt == 0:   # 접근 토큰이 먼저 끝났다: 한 번 새로 받는다
                    with self._lock:
                        self._access = ""
                    continue
                if (e.code == 429 or e.code >= 500) and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                err = youtube._error(e)
            # OSError: URLError·TimeoutError·RemoteDisconnected(urlopen이 감싸지 않는다)의 공통 부모
            except (OSError, ValueError):
                err = RuntimeError("YouTube 응답을 받지 못했어요. 잠시 뒤 다시 열어 보세요.")
            break
        if err:   # except 밖에서 던져 요청 정보(토큰 헤더)를 달고 가지 않게
            text = str(err)
            if "accessNotConfigured" in text or "SERVICE_DISABLED" in text:
                raise RuntimeError(DISABLED)
            if "insufficient" in text.lower():
                raise RuntimeError(RELOGIN.format(channel=self.channel))
            raise err
        body["fetched_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            if len(self._cache) >= 200:
                self._cache.pop(next(iter(self._cache)))
            self._cache[url] = (time.time(), body)
        return copy.deepcopy(body)

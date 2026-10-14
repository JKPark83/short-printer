"""YouTube 업로드: 데스크톱 앱 OAuth(PKCE)로 채널마다 한 번 로그인하고, 완성 영상을 비공개로 올린다.
표준 라이브러리만 쓴다. API 업로드 한도에 걸리면 스튜디오 화면(전용 Chrome)으로 올린다."""
import base64
import hashlib
import json
import os
import secrets
import webbrowser
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen

from .. import config
from . import youtube_studio

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
THUMBNAIL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?uploadType=media&videoId="
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
EXPIRED = "YouTube 로그인이 만료됐어요. 터미널에서 uv run sp youtube-login --channel {channel}을 다시 하세요."


def _client() -> dict:
    path = config.YOUTUBE_CLIENT_SECRET
    if not path or not Path(path).expanduser().exists():
        raise RuntimeError("YouTube 클라이언트 파일이 없어요. .env의 YOUTUBE_CLIENT_SECRET에 JSON 경로를 넣으세요.")
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if "installed" not in data:
        raise RuntimeError("OAuth 클라이언트 종류가 맞지 않아요. Google Cloud에서 '데스크톱 앱' 클라이언트를 새로 만들어 그 JSON을 쓰세요.")
    return data["installed"]


def ready(token: Path) -> bool:
    path = config.YOUTUBE_CLIENT_SECRET
    return bool(path) and Path(path).expanduser().exists() and token.exists()


class Expired(RuntimeError):
    """refresh_token이 만료·취소됐다. 채널 id는 YouTube가 채워 다시 던진다."""


def _call(req: Request, timeout: int = 30) -> tuple[dict, dict]:
    """(JSON 본문, 헤더). HTTP 오류는 Google이 준 이유만 담은 한국어 오류로 바꾼다(요청 헤더·토큰은 넣지 않는다)."""
    try:
        with urlopen(req, timeout=timeout) as r:
            body = r.read()
            return (json.loads(body) if body else {}), r.headers
    except HTTPError as e:
        code = e.code
        try:
            err = json.loads(e.read() or b"{}").get("error") or {}
        except ValueError:
            err = {}
    if err == "invalid_grant":   # 토큰 엔드포인트: 로그인 만료·취소(테스트 모드는 7일)
        raise Expired(EXPIRED.format(channel="<채널 id>"))
    if isinstance(err, dict):   # YouTube API: {"error": {"message", "errors": [{"reason"}]}}
        reason = next((x.get("reason") for x in err.get("errors", [])), None)
        detail = " · ".join(filter(None, [reason, err.get("message")]))
    else:
        detail = str(err)
    raise RuntimeError(f"YouTube 요청 실패({code}{': ' + detail if detail else ''})")


def _token(client: dict, **form) -> dict:
    body = urlencode({"client_id": client["client_id"], "client_secret": client["client_secret"], **form}).encode()
    return _call(Request(TOKEN, data=body))[0]


def _save(token: Path, refresh_token: str) -> None:
    token.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(token.parent, 0o700)
    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 처음부터 나만 읽을 수 있게 만든다
    os.fchmod(fd, 0o600)   # 예전 파일 권한이 넓었어도 쓰기 전에 좁힌다
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"refresh_token": refresh_token}, f)


def login(token: Path) -> None:
    """브라우저로 Google 로그인 → 127.0.0.1로 돌아온 code를 refresh_token으로 바꿔 저장한다."""
    client = _client()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state, got = secrets.token_urlsafe(16), {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(parse_qsl(urlsplit(self.path).query))
            if "code" in q or "error" in q:   # /favicon.ico 같은 다른 요청은 무시
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p>shorts-printer: 터미널로 돌아가세요. 이 창을 닫아도 돼요.</p>".encode())

        def log_message(self, *_):   # 주소에 든 code가 터미널에 찍히지 않게
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as srv:
        redirect = f"http://127.0.0.1:{srv.server_port}"
        url = AUTH + "?" + urlencode({
            "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
            "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
            "access_type": "offline", "prompt": "consent"})
        print(f"브라우저에서 Google 로그인을 마치세요. 창이 안 열리면 이 주소를 여세요:\n{url}")
        webbrowser.open(url)
        while not got:
            srv.handle_request()
    if got.get("state") != state:
        raise RuntimeError("로그인 응답이 이 요청과 맞지 않아요. 다시 하세요.")
    if "error" in got:
        raise RuntimeError(f"Google 로그인이 끝나지 않았어요({got['error']}).")
    tok = _token(client, code=got["code"], code_verifier=verifier, grant_type="authorization_code", redirect_uri=redirect)
    if not tok.get("refresh_token"):
        raise RuntimeError("refresh_token을 받지 못했어요. 다시 하세요.")
    _save(token, tok["refresh_token"])


def _access_token(token: Path) -> str:
    refresh = json.loads(token.read_text(encoding="utf-8"))["refresh_token"]
    return _token(_client(), grant_type="refresh_token", refresh_token=refresh)["access_token"]


def _clean(s: str) -> str:
    return s.replace("<", "").replace(">", "").strip()


def metadata(script: dict, language: str = "ko", category: str = "22") -> dict:
    """script.json → videos.insert 본문. YouTube 한도(제목 100자, 설명 5000바이트, 태그 합계 500자)에 맞춘다."""
    tags, size = [], 0
    for t in map(_clean, script.get("tags", [])):
        n = len(t) + 2 * (" " in t) + bool(tags)   # 띄어쓰기 든 태그는 따옴표 2자, 태그 사이 쉼표 1자
        if not t:
            continue
        if size + n > 500:
            break
        tags.append(t)
        size += n
    return {
        "snippet": {"title": _clean(script["title"])[:100],
                    "description": _clean(script.get("description", "")).encode()[:5000].decode("utf-8", "ignore"),
                    "tags": tags, "categoryId": category, "defaultLanguage": language,
                    "defaultAudioLanguage": language},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def upload(token: Path, path: Path, body: dict) -> str:
    """metadata() 본문으로 비공개로 올리고 영상 id를 돌려준다."""
    auth = {"Authorization": f"Bearer {_access_token(token)}"}
    _, headers = _call(Request(UPLOAD, data=json.dumps(body).encode(), method="POST", headers=auth | {
        "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(path.stat().st_size),
        "X-Upload-Content-Type": "video/mp4"}))
    # ponytail: 40초 남짓 mp4는 몇 MB라 PUT 한 번에 보낸다. 파일이 커지면 청크로 나눠 끊긴 곳부터 이어 올린다
    try:
        video, _ = _call(Request(headers["Location"], data=path.read_bytes(), method="PUT",
                                 headers=auth | {"Content-Type": "video/mp4"}), timeout=300)
    except (OSError, HTTPException):   # 끊김·시간 초과: 이미 올라갔을 수 있어 다시 누르면 중복된다
        raise RuntimeError("업로드 응답을 못 받았어요. 올라갔는지 YouTube 스튜디오에서 먼저 확인하세요.") from None
    return video["id"]


def set_thumbnail(token: Path, video_id: str, path: Path) -> None:
    """thumbnails.set. 채널 전화 인증이 안 됐거나 Shorts 맞춤 썸네일 권한(현재 YPP)이 없으면 403이 난다."""
    _call(Request(THUMBNAIL + video_id, data=path.read_bytes(), method="POST", headers={
        "Authorization": f"Bearer {_access_token(token)}", "Content-Type": "image/jpeg"}))


class YouTube:
    """Publisher 구현. 채널 하나(브랜드 계정)에 토큰 하나."""
    label = "YouTube"

    def __init__(self, token: Path, channel: str, language: str, category: str, studio_channel: str = ""):
        self.token, self.channel, self.language, self.category = token, channel, language, category
        self.studio_channel = studio_channel   # UC… 스튜디오 화면으로 올릴 때 갈 채널. 비우면 Chrome에서 고른 채널

    @property
    def hint(self) -> str:
        if self.ready():
            return "비공개로 올려요"
        return f"선택 · .env에 YOUTUBE_CLIENT_SECRET, 터미널에서 uv run sp youtube-login --channel {self.channel}"

    def ready(self) -> bool:
        return ready(self.token)

    def _run(self, f, *a):
        try:
            return f(self.token, *a)
        except Expired:
            raise RuntimeError(EXPIRED.format(channel=self.channel)) from None

    def login(self) -> None:
        self._run(login)

    def upload(self, path: Path, meta: dict, log) -> str:
        body = metadata(meta, self.language, self.category)
        try:
            return self._run(upload, path, body)
        except RuntimeError as e:
            # API 업로드 한도는 채널 하루 몫이라 기다려도 안 풀린다. 스튜디오 화면 업로드는 따로 센다
            if "uploadLimitExceeded" not in str(e):
                raise
        log("API 업로드 한도가 차서 YouTube 스튜디오 화면(전용 Chrome)으로 올려요")
        return youtube_studio.upload(path, body, self.studio_channel)

    def set_thumbnail(self, video_id: str, path: Path) -> None:
        self._run(set_thumbnail, video_id, path)

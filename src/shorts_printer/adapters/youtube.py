"""YouTube 업로드: 데스크톱 앱 OAuth(PKCE)로 채널마다 한 번 로그인하고, 완성 영상을 비공개로 올린다.
표준 라이브러리만 쓴다. API 업로드 한도에 걸리면 스튜디오 화면(전용 Chrome)으로 올린다."""
import base64
import hashlib
import json
import os
import secrets
import time
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
CAPTIONS = "https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&part=snippet"
CAPTION_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"   # captions.insert는 upload 범위로 안 된다
SCOPE = "https://www.googleapis.com/auth/youtube.upload " + CAPTION_SCOPE
EXPIRED = "YouTube 로그인이 만료됐어요. 터미널에서 uv run sp youtube-login --channel {channel}을 다시 하세요."
CHUNK = 8 * 1024 * 1024   # 이어 올리기 조각. 256 KiB의 배수여야 한다
RETRIES = 5   # 끊긴 뒤 받은 곳을 물어 다시 보내는 횟수(조각이 들어가면 새로 센다)
RELOGIN = "자막을 올릴 권한이 없어요. 터미널에서 uv run sp youtube-login --channel {channel}을 한 번 더 하세요."


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


def _error(e: HTTPError) -> RuntimeError:
    """HTTP 오류 → Google이 준 이유만 담은 한국어 오류(요청 헤더·토큰은 넣지 않는다)."""
    try:
        err = json.loads(e.read() or b"{}").get("error") or {}
    except ValueError:
        err = {}
    if err == "invalid_grant":   # 토큰 엔드포인트: 로그인 만료·취소(테스트 모드는 7일)
        return Expired(EXPIRED.format(channel="<채널 id>"))
    if isinstance(err, dict):   # YouTube API: {"error": {"message", "errors": [{"reason"}]}}
        reason = next((x.get("reason") for x in err.get("errors", [])), None)
        detail = " · ".join(filter(None, [reason, err.get("message")]))
    else:
        detail = str(err)
    return RuntimeError(f"YouTube 요청 실패({e.code}{': ' + detail if detail else ''})")


def _call(req: Request, timeout: int = 30) -> tuple[dict, dict]:
    """(JSON 본문, 헤더). HTTP 오류는 _error로 바꾼다."""
    try:
        with urlopen(req, timeout=timeout) as r:
            body = r.read()
            return (json.loads(body) if body else {}), r.headers
    except HTTPError as e:
        err = _error(e)
    raise err   # except 밖에서 던져 원래 HTTPError(요청 정보)를 달고 가지 않게


def _token(client: dict, **form) -> dict:
    body = urlencode({"client_id": client["client_id"], "client_secret": client["client_secret"], **form}).encode()
    return _call(Request(TOKEN, data=body))[0]


def _save(token: Path, data: dict) -> None:
    """토큰 파일을 나만 읽게(0600, 폴더 0700) 원자적으로 쓴다. Instagram도 같이 쓴다."""
    token.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(token.parent, 0o700)
    tmp = token.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 처음부터 나만 읽을 수 있게 만든다
    os.fchmod(fd, 0o600)   # 예전 파일 권한이 넓었어도 쓰기 전에 좁힌다
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, token)


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
    _save(token, {"refresh_token": tok["refresh_token"]})


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
    # ponytail: access token은 1시간이라 그보다 오래 걸리는 업로드는 401로 멈춘다. 그때는 401에서 토큰을 새로 받는다
    return _send(headers["Location"], auth, path)["id"]


def _put(url: str, auth: dict, data: bytes, rng: str) -> tuple[dict | None, int]:
    """세션 주소로 조각 하나(빈 본문이면 상태 묻기)를 PUT한다. 다 올라갔으면 (영상 본문, -1),
    덜 올라갔으면(308 Resume Incomplete) (None, 다음에 보낼 바이트). 5xx는 HTTPError 그대로(이어 올린다)."""
    req = Request(url, data=data, method="PUT", headers=auth | {"Content-Type": "video/mp4", "Content-Range": rng})
    try:
        with urlopen(req, timeout=300) as r:
            return json.loads(r.read() or b"{}"), -1
    except HTTPError as e:
        if e.code == 308:   # Range "bytes=0-N"까지 받았다. 없으면 아무것도 못 받았다
            got = e.headers.get("Range")
            return None, (int(got.rsplit("-", 1)[1]) + 1 if got else 0)
        if e.code >= 500:
            raise
        err = _error(e)
    raise err


def _send(url: str, auth: dict, path: Path) -> dict:
    """CHUNK씩 읽어 이어 올린다(1 GB 롱폼도 한꺼번에 읽지 않는다). 끊김·5xx면 "bytes */N"으로
    받은 곳을 물어 거기서부터 다시 보낸다. 조각이 들어가지 않은 채 RETRIES번 넘게 실패하면 멈춘다."""
    size, pos, fails, ask = path.stat().st_size, 0, 0, False
    with path.open("rb") as f:
        while True:
            if ask or pos >= size:   # 끊긴 뒤, 또는 다 보냈는데 완료 응답이 없으면 받은 곳부터 묻는다
                data, rng = b"", f"bytes */{size}"
            else:
                f.seek(pos)
                data = f.read(CHUNK)
                rng = f"bytes {pos}-{pos + len(data) - 1}/{size}"
            try:
                video, nxt = _put(url, auth, data, rng)
            except (OSError, HTTPException):   # HTTPError(5xx)도 OSError
                fails += 1
                if fails > RETRIES:   # 마지막 조각이 들어갔을 수 있어 다시 누르면 중복된다
                    raise RuntimeError("업로드 응답을 못 받았어요. 올라갔는지 YouTube 스튜디오에서 먼저 확인하세요.") from None
                time.sleep(min(2 ** fails, 30))
                ask = True
                continue
            if video is not None:
                return video
            if not ask:
                fails = 0   # 조각이 들어갔으니 실패 횟수를 새로 센다
            pos, ask = nxt, False


def set_thumbnail(token: Path, video_id: str, path: Path) -> None:
    """thumbnails.set. 채널 전화 인증이 안 됐거나 Shorts 맞춤 썸네일 권한(현재 YPP)이 없으면 403이 난다."""
    _call(Request(THUMBNAIL + video_id, data=path.read_bytes(), method="POST", headers={
        "Authorization": f"Bearer {_access_token(token)}", "Content-Type": "image/jpeg"}))


def set_captions(token: Path, video_id: str, srt: Path, language: str, name: str = "") -> None:
    """captions.insert(multipart): SRT를 초안 아닌 자막으로 붙인다. 범위 youtube.force-ssl이 있어야 한다."""
    boundary = secrets.token_hex(16)
    meta = json.dumps({"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    body += srt.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    _call(Request(CAPTIONS, data=body, method="POST", headers={
        "Authorization": f"Bearer {_access_token(token)}", "Content-Type": f"multipart/related; boundary={boundary}"}),
        timeout=60)


class YouTube:
    """Publisher 구현. 채널 하나(브랜드 계정)에 토큰 하나."""
    label = "YouTube"
    private = True

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

    def set_captions(self, video_id: str, srt: Path, language: str) -> None:
        try:
            self._run(set_captions, video_id, srt, language)
        except RuntimeError as e:
            # 자막 범위 전에 로그인한 토큰: 403 insufficientPermissions(ACCESS_TOKEN_SCOPE_INSUFFICIENT)
            if not any(w in str(e) for w in ("insufficientPermissions", "insufficient authentication scopes")):
                raise
            raise RuntimeError(RELOGIN.format(channel=self.channel)) from None

    def link(self, video_id: str) -> str:
        return f"https://youtu.be/{video_id}"

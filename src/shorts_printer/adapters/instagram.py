"""Instagram 릴스 업로드: Facebook 로그인(페이지 토큰)으로 채널마다 한 번 연결하고, 완성 영상을 올린다.
Instagram에는 비공개 업로드가 없어 바로 공개된다. 그래서 스케줄은 올리지 않고 사람이 버튼을 눌러야 올린다.
로컬 파일을 올리려면 Facebook 로그인 경로(rupload)가 필요하다. 표준 라이브러리만 쓴다."""
import getpass
import json
import time
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import config
from .youtube import _save

GRAPH = "https://graph.facebook.com/v26.0"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v26.0/"
PERMS = "instagram_basic, instagram_content_publish, pages_read_engagement, pages_show_list, business_management"
MAX_CAPTION, MAX_TAGS = 2200, 30   # Instagram 한도: 캡션 글자 수, 해시태그 수
POLL, WAIT = 10, 300   # 초. 영상 처리 상태를 10초마다 5분까지 본다
STEPS = f"""Instagram 연결(Facebook 로그인):
1. https://developers.facebook.com/tools/explorer 를 연다
2. Meta 앱에서 이 앱(.env의 META_APP_ID)을 고르고, 사용자 또는 페이지에서 '사용자 토큰'을 고른다
3. 권한 추가: {PERMS}
4. [Generate Access Token] → 채널의 인스타 계정이 연결된 페이스북 페이지를 허용 → 나온 토큰을 복사한다"""


def _call(req: Request, timeout: int = 30, hide: tuple[str, ...] = ()) -> dict:
    """JSON 본문. Graph 오류는 Meta가 준 코드·문구만 담은 한국어 오류로 바꾼다.
    주소·헤더는 넣지 않고, 문구에 토큰이 섞여 와도 가린다(Authorization 헤더 토큰과 hide)."""
    try:
        with urlopen(req, timeout=timeout) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except HTTPError as e:
        code = e.code
        try:
            err = json.loads(e.read() or b"{}").get("error") or {}
        except ValueError:
            err = {}
    if not isinstance(err, dict):
        err = {"message": str(err)}
    msg = str(err.get("message") or "")
    for s in (*hide, (req.get_header("Authorization") or "").removeprefix("OAuth ")):
        if s:
            msg = msg.replace(s, "***")
    raise RuntimeError(f"Instagram 요청 실패({err.get('code', code)}{': ' + msg if msg else ''})")


def _auth(token: str) -> dict:
    return {"Authorization": f"OAuth {token}"}


def caption(meta: dict, footer: str = "") -> str:
    """제목 / 설명(출처·footer 포함) / 해시태그. 2200자를 넘으면 해시태그를 뒤에서부터 빼고, 그래도 넘으면
    설명 본문 뒤를 자른다. footer(AI 표시)는 자르지 않게 떼어 냈다가 다시 붙인다."""
    body = meta.get("description", "").strip()
    if footer:
        body = body.removesuffix(footer).rstrip()
    tags = list(dict.fromkeys(t for x in meta.get("tags", []) if (t := x.replace(" ", "").lstrip("#"))))
    tags = ["#" + t for t in tags[:MAX_TAGS]]

    def join() -> str:
        return "\n\n".join(x for x in (meta["title"].strip(), body, footer, " ".join(tags)) if x)

    out = join()
    while len(out) > MAX_CAPTION and tags:
        tags.pop()
        out = join()
    if len(out) > MAX_CAPTION:
        body = body[:len(body) - (len(out) - MAX_CAPTION)].rstrip()
        out = join()
    return out


class Instagram:
    """Publisher 구현. 채널 하나에 인스타 프로페셔널 계정 하나(페이스북 페이지 토큰)."""
    label = "Instagram"
    private = False   # 비공개 업로드가 없다

    def __init__(self, token: Path, channel: str, footer: str = ""):
        self.token, self.channel, self.footer = token, channel, footer

    @property
    def hint(self) -> str:
        if self.ready():
            return "바로 공개로 올려요"
        return ("선택 · .env에 META_APP_ID·META_APP_SECRET, 터미널에서 "
                f"uv run sp instagram-login --channel {self.channel}")

    def ready(self) -> bool:
        return self.token.exists()

    def _account(self) -> dict:
        if not self.ready():
            raise RuntimeError(f"Instagram 연결이 안 돼 있어요. 터미널에서 uv run sp instagram-login --channel "
                               f"{self.channel}을 하세요.")
        return json.loads(self.token.read_text(encoding="utf-8"))

    def login(self) -> str:
        """Graph API 탐색기에서 받은 짧은 토큰 → 오래가는 사용자 토큰 → 페이지 토큰(만료 없음)을 저장한다.
        연결한 인스타 사용자 이름을 돌려준다."""
        app_id, app_secret = config.secret("META_APP_ID"), config.secret("META_APP_SECRET")
        if not (app_id and app_secret):
            raise RuntimeError(".env에 META_APP_ID·META_APP_SECRET을 넣으세요.")
        print(STEPS)
        short = getpass.getpass("토큰 붙여넣기(화면에 안 보여요): ").strip()
        if not short:
            raise RuntimeError("토큰을 넣지 않았어요.")
        q = urlencode({"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
                       "fb_exchange_token": short})
        user = _call(Request(f"{GRAPH}/oauth/access_token?{q}"), hide=(app_secret, short))["access_token"]
        q = urlencode({"fields": "id,name,access_token,instagram_business_account{id,username}"})
        pages = [p for p in _call(Request(f"{GRAPH}/me/accounts?{q}", headers=_auth(user)), hide=(user,))
                 .get("data", []) if p.get("instagram_business_account")]
        if not pages:
            raise RuntimeError("인스타 프로페셔널 계정이 연결된 페이스북 페이지가 없어요. 페이지에 계정을 연결했는지, "
                               "토큰을 만들 때 그 페이지를 허용했는지 보세요.")
        p = pages[0]
        if len(pages) > 1:
            for i, x in enumerate(pages, 1):
                print(f"{i}. {x['name']} · @{x['instagram_business_account']['username']}")
            n = input("이 채널에 연결할 번호: ").strip()
            if not (n.isdigit() and 1 <= int(n) <= len(pages)):
                raise RuntimeError("번호를 잘못 골랐어요. 다시 하세요.")
            p = pages[int(n) - 1]
        ig = p["instagram_business_account"]
        _save(self.token, {"page_id": p["id"], "ig_user_id": ig["id"], "username": ig["username"],
                           "page_token": p["access_token"]})
        return ig["username"]

    def upload(self, path: Path, meta: dict, log) -> str:
        """컨테이너 만들기 → 파일 보내기 → 처리 끝날 때까지 보기 → 게시. 게시물(미디어) id를 돌려준다."""
        acc = self._account()
        auth = _auth(acc["page_token"])
        form = {"media_type": "REELS", "upload_type": "resumable", "caption": caption(meta, self.footer),
                "share_to_feed": "true", "thumb_offset": "0"}   # cover_url은 공개 주소가 필요해 첫 프레임을 쓴다
        box = _call(Request(f"{GRAPH}/{acc['ig_user_id']}/media", data=urlencode(form).encode(), headers=auth))
        _call(Request(box.get("uri") or RUPLOAD + box["id"], data=path.read_bytes(), method="POST",
                      headers=auth | {"offset": "0", "file_size": str(path.stat().st_size)}), timeout=300)
        for _ in range(WAIT // POLL):
            st = _call(Request(f"{GRAPH}/{box['id']}?fields=status_code,status", headers=auth))
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram이 영상을 처리하지 못했어요({st['status_code']}: {st.get('status')})")
            time.sleep(POLL)
        else:
            raise RuntimeError("Instagram 영상 처리가 5분 안에 끝나지 않았어요. 잠시 뒤 다시 올리세요.")
        try:
            done = _call(Request(f"{GRAPH}/{acc['ig_user_id']}/media_publish",
                                 data=urlencode({"creation_id": box["id"]}).encode(), headers=auth))
        except (OSError, HTTPException):   # 끊김·시간 초과: 이미 게시됐을 수 있어 다시 누르면 중복된다
            raise RuntimeError("게시 응답을 못 받았어요. 올라갔는지 Instagram에서 먼저 확인하세요.") from None
        log(f"Instagram @{acc['username']}에 게시")
        return done["id"]

    def set_thumbnail(self, video_id: str, path: Path) -> None:
        raise RuntimeError("Instagram API로는 커버를 따로 올릴 수 없어 첫 프레임이 커버예요")

    def link(self, video_id: str) -> str:
        acc = self._account()
        return _call(Request(f"{GRAPH}/{video_id}?fields=permalink", headers=_auth(acc["page_token"])))["permalink"]

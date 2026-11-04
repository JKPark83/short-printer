"""VidoGrid 영상 공급자(API). 장면을 한꺼번에 넣고 history를 돌며 끝난 것부터 받는다.
문서 https://docs.vidogrid.ai/: POST /video-gen/veo → uuid,
GET /history/{uuid}의 status 0 대기·1 진행·2 완료·3 실패·-2 정책 거절"""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import config
from ..infra.store import atomic_write_text
from ..ports import video

API = "https://api.vidogrid.ai/uapi/v1"
POLL = 10   # 초. history를 보는 간격
GEN_TIMEOUT = 1800   # 초. 넘으면 .task를 남기고 멈춘다(다시 시도하면 새로 넣지 않고 이어 받는다)
BUSY = {"HIGH_TRAFFIC_ERROR", "SYSTEM_ERROR"}   # 잠깐 뒤 다시 넣으면 되는 오류


def _api(path: str, form: dict | None = None) -> dict:
    """form이 있으면 POST(글만 보낼 땐 폼 본문을 받는다), 없으면 GET. 오류는 error_code를 단 ApiError로 던진다."""
    req = Request(API + path, data=urlencode(form).encode() if form else None,
                  headers={"x-api-key": config.secret("VIDOGRID_API_KEY") or "", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=60) as r:
            return json.load(r)
    except HTTPError as e:   # {"detail": {"error_code", "error_message"}}
        body = e.read()[:300].decode(errors="replace")
        try:
            code = json.loads(body)["detail"]["error_code"]
        except (ValueError, KeyError, TypeError):
            code = ""
        raise ApiError(code, f"VidoGrid {e.code} {code}: {body}") from None


class ApiError(RuntimeError):
    def __init__(self, code: str, msg: str):
        super().__init__(msg)
        self.code = code


def _download(url: str, path) -> None:
    tmp = path.with_suffix(".tmp.mp4")
    with urlopen(url, timeout=300) as r:
        tmp.write_bytes(r.read())
    if not tmp.stat().st_size:
        raise RuntimeError("VidoGrid 영상이 비었어요(0바이트)")
    os.replace(tmp, path)


class VidoGrid:
    label = "VidoGrid"

    def __init__(self, aspect: str = "9:16", model: str = "omni-1.1-flash"):
        self.aspect = aspect   # 쇼츠 9:16, 롱폼 16:9
        self.model = model   # Flow와 같은 Omni 1.1 Flash. veo-3.1-fast·veo-3.1도 같은 자리에 넣으면 된다
        self.hint = f"유료 · VidoGrid 크레딧 · {model} {aspect} · 720p · 8초 · .env에 VIDOGRID_API_KEY"

    def ready(self) -> bool:
        return bool(config.secret("VIDOGRID_API_KEY"))

    def _submit(self, prompt: str) -> dict:
        form = {"prompt": prompt, "model": self.model, "resolution": "720p", "duration": 8,
                "aspect_ratio": self.aspect}
        # 붐빌 때만 조금 뒤 다시. 키·크레딧·플랜 오류는 그대로 던진다.
        # 연결 오류는 다시 넣지 않는다: 서버가 받았을 수 있어 크레딧이 두 번 든다
        for wait in (30, 60):
            try:
                return _api("/video-gen/veo", form)
            except ApiError as e:
                if e.code not in BUSY:
                    raise
            time.sleep(wait)
        return _api("/video-gen/veo", form)

    def make(self, scenes, out, log):
        scenes = [s for s in scenes if s["prompt"]]
        pending = {}   # 장면 번호 → (장면, uuid)
        # 넣은 uuid를 .task에 남긴다: 서버가 꺼졌다 다시 시도해도 새로 넣지 않아 크레딧이 두 번 들지 않는다
        for s in scenes:
            task = (out / s["file"]).with_suffix(".task")
            if task.exists():
                uuid = json.loads(task.read_text())["uuid"]
                log(f"VidoGrid: 장면 {s['i'] + 1} 지난번에 넣은 것을 이어 받아요")
            else:
                r = self._submit(s["prompt"])
                uuid = r["uuid"]
                atomic_write_text(task, json.dumps({"uuid": uuid}))
                log(f"VidoGrid: 장면 {s['i'] + 1} 넣음({r.get('estimated_credit')}크레딧)")
            pending[s["i"]] = (s, uuid)
        left, refused = [], {}
        end = time.monotonic() + GEN_TIMEOUT
        while pending and time.monotonic() < end:
            time.sleep(POLL)
            for i, (s, uuid) in list(pending.items()):
                try:
                    h = _api(f"/history/{uuid}")
                except (ApiError, URLError) as e:   # 잠깐 끊겨도 다음 바퀴에 다시 본다
                    log(f"VidoGrid: 장면 {i + 1} 상태를 못 읽음({str(e)[:120]})")
                    continue
                task = (out / s["file"]).with_suffix(".task")
                if h["status"] == 2:
                    url = h["generated_video"][0]["video_url"]
                    _download(url, out / s["file"])
                    task.unlink(missing_ok=True)
                    del pending[i]
                    log(f"VidoGrid: 장면 {i + 1} 완료({h.get('used_credit')}크레딧)")
                    yield {"file": s["file"], "source": self.label, "url": url}
                elif h["status"] in (3, -2):   # 실패는 과금되지 않아 .task를 지우고 다시 시도 때 새로 넣는다
                    reason = h.get("error_message") or h.get("error_code") or "사유 없음"
                    task.unlink(missing_ok=True)
                    del pending[i]
                    log(f"VidoGrid: 장면 {i + 1} {'거절됨' if h['status'] == -2 else '실패'}({reason[:120]})")
                    if h["status"] == -2:
                        refused[i] = reason
                    left.append(i + 1)
        if pending:
            raise RuntimeError(f"VidoGrid 장면 {', '.join(str(i + 1) for i in sorted(pending))}이 "
                               f"{GEN_TIMEOUT // 60}분 안에 끝나지 않았어요. "
                               "[다시 시도]하면 새로 넣지 않고 이어 받아요")
        if left:
            msg = f"VidoGrid가 장면 {', '.join(map(str, sorted(left)))}을 못 만들었어요. "
            if refused:
                raise video.Refused(msg + "[다시 시도]하면 거절된 장면은 정책을 피하게 프롬프트를 고쳐 다시 만들어요",
                                    refused)
            raise RuntimeError(msg + "[다시 시도]하거나 클립을 직접 올려 주세요")

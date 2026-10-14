"""브라우저 화면: 주제 넣기(또는 인기 쇼츠 분석에서 고르기) → 여섯 단계 진행 보기(장면 클립 올리기) → 완성 영상."""
import asyncio
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .. import config, ffmpeg, pipeline, script, trends, video, voice, worker, youtube
from ..jobs import LABELS, STEPS, Job, read_json, upload_state
from ..trends import Trend

HERE = Path(__file__).parent
DAILY_GOAL = 3   # 하루 목표 편수
ACTIVE = ("queued", "running")
MAX_CLIP = 200 * 1024 * 1024   # 클립 한 개 상한(app.js에도 같은 값)
MAX_NOTE = 300   # 썸네일·대본 수정 요청 글자 수 상한(job.html maxlength와 같은 값)
QUOTA_PER_RUN, QUOTA_DAY = 101, 10_000   # 주제 찾기 한 번: search.list 100 + videos.list 1 / YouTube 무료 할당량(하루)
# ponytail: 어림값(영상 8개 × 프레임 8장 + 선정 1번). 실제 값은 분석 화면의 사용량에 남는다
EST_TOKENS = (55_000, 11_000)
STATUS = {"draft": "준비", "queued": "대기 중", "running": "제작 중", "done": "완성",
          "failed": "실패", "interrupted": "중단", "waiting": "클립 대기"}
TSTATUS = STATUS | {"running": "분석 중", "done": "완료"}
STATE = {"pending": "대기", "running": "진행 중", "done": "완료", "failed": "실패"}
# Lucide 아이콘 경로(ISC 라이선스). 이모지 대신 쓴다.
ICONS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "loader": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "rotate": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "play": '<path d="M6 3 20 12 6 21Z"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/>',
    "trending": '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
    "film": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18M17 3v18M3 7.5h4M3 12h18M3 16.5h4M17 7.5h4M17 16.5h4"/>',
}
NODE_ICON = {"pending": "circle", "running": "loader", "done": "check", "failed": "x"}
CHECK_ICON = {"ok": "check", "warn": "alert", "bad": "x"}


def icon(name: str, size: int = 16, cls: str = "") -> Markup:
    return Markup(f'<svg class="i {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
                  'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
                  f'aria-hidden="true">{ICONS[name]}</svg>')


def sig(data: dict) -> str:
    """화면 조각을 다시 그려야 하는지 가르는 값. 템플릿과 상태 API가 같은 함수를 쓴다."""
    return (f'{data["status"]}:{"".join(data["steps"][s]["status"][0] for s in STEPS)}:{len(data["notices"])}'
            f':{(data.get("upload") or {}).get("status", "-")}')


def say(data: dict) -> str:
    """화면 읽기 프로그램에 알릴 한 줄."""
    running = [LABELS[s] for s in STEPS if data["steps"][s]["status"] == "running"]
    if running:
        return f"{running[0]} 진행 중"
    upload = (data.get("upload") or {}).get("status")
    if upload in ACTIVE:
        return "YouTube에 올리는 중"
    if upload == "failed" and data["status"] == "done":
        return "YouTube 업로드 실패"
    if data["status"] == "failed":
        return f'실패: {LABELS[data["error"]["step"]]}'
    return STATUS[data["status"]]


def tsig(data: dict) -> str:
    """분석 화면용 sig. 분석 단계는 영상 하나 끝날 때마다 바뀐다."""
    return (f'{data["status"]}:{"".join(data["steps"][s]["status"][0] for s in trends.STEPS)}'
            f':{(data.get("progress") or {}).get("done", "-")}:{len(data["notices"])}')


def tsay(data: dict) -> str:
    running = [s for s in trends.STEPS if data["steps"][s]["status"] == "running"]
    if running:
        p = data.get("progress") if running[0] == "analyze" else None
        return f'{trends.LABELS[running[0]]} 진행 중' + (f' {p["done"]}/{p["total"]}' if p else "")
    if data["status"] == "failed":
        return f'실패: {trends.LABELS[data["error"]["step"]]}'
    return TSTATUS[data["status"]]


def hm(iso: str | None) -> str:
    # YouTube 게시 시각은 UTC라 내 시간대로 바꿔 보여 준다
    return datetime.fromisoformat(iso).astimezone().strftime("%m/%d %H:%M") if iso else ""


def kn(n: float | None) -> str:
    """한국식 큰 수: 950, 3.4천, 1.2만, 12만, 1.1억."""
    if n is None:
        return "-"
    for unit, size in (("억", 1e8), ("만", 1e4), ("천", 1e3)):
        v = round(n / size, 1)
        if v >= 1:
            return (f"{v:.1f}".removesuffix(".0") if v < 10 else f"{v:.0f}") + unit
    return f"{n:.0f}"


def ago(hours: float | None) -> str:
    if hours is None:
        return ""
    return f"{round(hours)}시간 전" if hours < 24 else f"{round(hours / 24)}일 전"


def mmss(sec: float | None) -> str:
    if sec is None:
        return ""
    s = round(sec)
    return f"{s // 60}:{s % 60:02d}"


def cue_ts(sec: float) -> str:
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def job_cost(j: dict) -> float | None:
    """대본 + 썸네일 Claude 비용. 둘 다 모르면 None."""
    costs = [u["cost_usd"] for u in (j["usage"], j.get("thumb_usage")) if u and u["cost_usd"] is not None]
    return round(sum(costs), 4) if costs else None


def recover() -> None:
    """앱이 켜질 때: 끊긴 작업·분석을 interrupted로, 반쯤 쓰인 *.tmp 파일을 지운다."""
    # ponytail: 다른 터미널에서 `sp run`·`sp trends`가 돌고 있어도 중단으로 표시한다. 둘을 같이 쓰려면 상태 json에 pid를 남겨 살아 있는지 볼 것
    for root in (config.JOBS_DIR, config.TRENDS_DIR):
        root.mkdir(parents=True, exist_ok=True)
    for t in Trend.all():
        t.interrupt()
    for job in Job.all():
        job.interrupt()
        # PUT이 끝났을 수도 있어 다시 올리기 전에 확인하게 한다(같은 영상 두 번 올리기 방지)
        if (job.data.get("upload") or {}).get("status") in ACTIVE:
            job.update(upload=upload_state(
                "failed", error="서버가 꺼져 멈췄어요. 올라갔는지 YouTube 스튜디오에서 먼저 확인하세요."))
    for root in (config.JOBS_DIR, config.TRENDS_DIR):
        for pattern in ("*.tmp", "*.tmp.mp4"):
            for p in root.rglob(pattern):
                p.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(_app):
    recover()
    worker.start()
    yield


app = FastAPI(lifespan=lifespan)
# DNS 리바인딩 막기: 이 이름으로 온 요청만 받는다
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.HOSTS)


@app.middleware("http")
async def same_origin_post(request: Request, call_next):
    """다른 사이트(다른 포트 포함)가 사용자 브라우저로 작업을 만들어 Claude 비용을 쓰지 못하게 한다."""
    origin = request.headers.get("origin")
    # 스킴은 보지 않는다: tailscale serve가 https를 받아 http로 넘긴다
    if request.method == "POST" and origin and urlsplit(origin).netloc != request.headers.get("host"):
        return PlainTextResponse("다른 사이트에서 보낸 요청은 받지 않아요", status_code=403)
    return await call_next(request)

app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.mount("/files", StaticFiles(directory=config.JOBS_DIR, check_dir=False), name="files")
app.mount("/trend-files", StaticFiles(directory=config.TRENDS_DIR, check_dir=False), name="trend-files")
templates = Jinja2Templates(directory=HERE / "templates")
VOICES = voice.choices()   # 켤 때 한 번. 쓸 수 있는 공급자의 목소리만
templates.env.globals |= {
    "v": int(datetime.now().timestamp()),   # 서버를 켠 시각으로 정적 파일 캐시를 깬다
    "icon": icon, "sig": sig, "job_cost": job_cost, "STEPS": STEPS, "LABELS": LABELS, "STATUS": STATUS, "STATE": STATE,
    "ACTIVE": ACTIVE, "youtube": youtube, "trends": trends, "tsig": tsig, "TSTATUS": TSTATUS,
    "QUOTA_PER_RUN": QUOTA_PER_RUN, "QUOTA_DAY": QUOTA_DAY, "NODE_ICON": NODE_ICON, "CHECK_ICON": CHECK_ICON, "VOICES": VOICES,
}
templates.env.filters |= {"hm": hm, "mmss": mmss, "cue_ts": cue_ts, "kn": kn, "ago": ago}


def _load(cls, rec_id: str):
    """Job·Trend 하나. id 모양을 먼저 봐서 폴더 밖 경로를 막는다."""
    if not re.fullmatch(r"[\w-]+", rec_id):
        raise HTTPException(404, f"{cls.WHAT}이 없어요")
    try:
        return cls.load(rec_id)
    except FileNotFoundError:
        raise HTTPException(404, f"{cls.WHAT}이 없어요") from None


def _picks(trend: Trend) -> list[dict]:
    return (read_json(trend.dir / "picks.json") or {}).get("picks", [])


def _tail(job: Job | Trend, n: int = 200) -> list[str]:
    p = job.dir / "log.txt"
    return p.read_text(encoding="utf-8").splitlines()[-n:] if p.exists() else []


def _stats(jobs: list[dict]) -> dict:
    today = datetime.now().astimezone().date().isoformat()
    return {
        "today": sum(j["status"] == "done" and (j["finished_at"] or "")[:10] == today for j in jobs),
        "goal": DAILY_GOAL,
        "total": len(jobs),
        "failed": sum(j["status"] == "failed" for j in jobs),
        "cost": sum(job_cost(j) or 0 for j in jobs),
    }


def _checks() -> list[tuple[str, str, str]]:
    """(ok|warn|bad, 이름, 한 줄 설명). 값은 보여 주지 않고 있는지만 본다."""
    claude = config.secret("ANTHROPIC_API_KEY") or config.secret("ANTHROPIC_AUTH_TOKEN")
    ff = Path(config.FFMPEG).exists()
    checks = [
        ("ok" if claude else "bad", "Claude API 키",
         config.CLAUDE_MODEL if claude else ".env에 ANTHROPIC_API_KEY를 넣어 주세요"),
        ("ok" if ff else "bad", "ffmpeg-full",
         config.FFMPEG if ff else "brew install ffmpeg-full 또는 .env에 SP_FFMPEG"),
    ]
    v = video.default()
    checks += [("ok" if p.ready() else "warn", f"영상 · {p.label}" + (" (기본)" if k == v else ""), p.hint)
               for k, p in video.VIDEO.items()]
    checks += [("ok" if p.ready() else "warn", f"음성 · {p.label}", p.hint) for p in voice.TTS.values()]
    return checks + [
        ("ok", "YouTube 업로드", "비공개로 올려요") if youtube.ready()
        else ("warn", "YouTube 업로드", "선택 · .env에 YOUTUBE_CLIENT_SECRET, 터미널에서 uv run sp youtube-login"),
        ("ok", "YouTube Data API 키", "주제 찾기에서 인기 쇼츠를 모아요") if trends.ready()
        else ("warn", "YouTube Data API 키", "선택 · 주제 찾기용 · .env에 YOUTUBE_API_KEY"),
    ]


def _latest_picks() -> dict | None:
    """대시보드에 띄울 최신 완료 분석의 추천 상위 3개."""
    for t in reversed(Trend.all()):
        if t.data["status"] == "done" and (picks := _picks(t)):
            return {"trend": t.data, "picks": list(enumerate(picks))[:3]}
    return None


def _can_upload(data: dict) -> bool:
    """클립을 올리거나 바꿀 수 있나: 돌고 있지 않고, 아직 유튜브에 올리지 않았을 때."""
    return data["status"] not in ACTIVE and (data.get("upload") or {}).get("status") not in ("queued", "running", "done")


def _scenes(job: Job) -> list[dict]:
    """장면 카드용. 끝난 예전 작업(클립 수 ≠ 문장 수)은 []를 돌려 예전 화면으로 보인다."""
    s = read_json(job.dir / "script.json")
    if not s:
        return []
    clips = {c["file"]: c for c in read_json(job.dir / "clips.json", [])}
    if job.data["steps"]["footage"]["status"] == "done" and len(clips) != len(s["sentences"]):
        return []
    out = video.scenes(s, read_json(job.dir / "timing.json"))
    for x in out:
        p = job.dir / "clips" / x["file"]
        x["v"] = p.stat().st_mtime_ns if p.exists() else None   # 미리보기 캐시 깨기(같은 초에 바꿔도)
        x["clip"] = clips.get(x["file"])   # 출처(스톡 촬영자 등)
    return out


@app.get("/")
def index(request: Request):
    jobs = [j.data for j in reversed(Job.all())]
    checks = _checks()
    return templates.TemplateResponse(request, "index.html", {
        "jobs": jobs, "stats": _stats(jobs), "checks": checks, "claude_ok": checks[0][0] == "ok",
        "active": any(j["status"] in ACTIVE for j in jobs), "rec": _latest_picks()})


@app.post("/jobs")
def create_job(topic: str = Form(""), voice: str = Form(...), trend: str | None = Form(None), pick: int | None = Form(None)):
    if voice not in VOICES:
        raise HTTPException(400, "모르는 목소리예요")
    if trend is not None:
        # 추천에서 만들 때는 주제·방향을 서버가 picks.json에서 꺼낸다(클라이언트가 보낸 값은 믿지 않는다)
        t = _load(Trend, trend)
        picks = _picks(t)
        if pick is None or not 0 <= pick < len(picks):
            raise HTTPException(400, "그 추천을 찾지 못했어요")
        p = picks[pick]
        job = Job.create(p["topic"], voice, brief=trends.brief(t.dir, p), source={"trend": trend, "pick": pick})
        worker.enqueue(job.id)
        return RedirectResponse(f"/jobs/{job.id}", status_code=303)
    topic = topic.strip()
    if not 1 <= len(topic) <= 200:
        raise HTTPException(400, "주제는 1~200자로 넣어 주세요")
    job = Job.create(topic, voice)
    worker.enqueue(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}")
def job_page(request: Request, job_id: str):
    job = _load(Job, job_id)
    return templates.TemplateResponse(request, "job.html", {
        "job": job.data, "script": read_json(job.dir / "script.json"), "clips": read_json(job.dir / "clips.json"),
        "cues": read_json(job.dir / "cues.json"), "has_thumb": (job.dir / "thumbnail.jpg").exists(),
        "thumb": read_json(job.dir / "thumb.json"), "log": _tail(job),
        "scenes": _scenes(job), "can_upload": _can_upload(job.data)})


@app.get("/api/jobs/{job_id}")
def job_api(job_id: str):
    job = _load(Job, job_id)
    data = job.data
    return data | {"sig": sig(data), "say": say(data), "log": _tail(job)}


@app.post("/api/jobs/{job_id}/retry")
def retry(job_id: str):
    job = _load(Job, job_id)
    if not worker.enqueue(job_id):
        raise HTTPException(409, "이미 완성된 작업이에요" if job.data["status"] == "done" else "이미 제작 중이에요")
    return {"ok": True}


def _note(note: str) -> str:
    if len(note) > MAX_NOTE:
        raise HTTPException(400, f"수정 요청은 {MAX_NOTE}자까지 적을 수 있어요")
    return note.strip()


def _redo(job_id: str, steps: tuple, uploaded: str, **kw) -> None:
    """완성 뒤 고치기. 안 되면 409(uploaded: 이미 올렸을 때 안내)."""
    job = _load(Job, job_id)
    if not worker.redo(job_id, steps, **kw):
        raise HTTPException(409, "완성된 작업만 고칠 수 있어요" if job.data["status"] != "done" else uploaded)


@app.post("/api/jobs/{job_id}/thumbnail")
def rethumb(job_id: str, note: str = Form("")):
    _redo(job_id, ("thumbnail", "render"), "이미 올린 영상은 스튜디오에서 썸네일을 바꾸세요", thumb_note=_note(note))
    return {"ok": True, "msg": "썸네일을 다시 만들고 영상도 다시 렌더해요"}


@app.post("/api/jobs/{job_id}/script")
def save_script(job_id: str, title: str = Form(""), description: str = Form(""), tags: str = Form(""),
                sentences: list[str] = Form([])):
    """손으로 고친 대본. 문장이 바뀌면 음성부터 다시(장면 클립·썸네일은 그대로), 아니면 저장만."""
    old = read_json(_load(Job, job_id).dir / "script.json")
    lines, title = [s.strip() for s in sentences], title.strip()
    if not old or len(lines) != len(old["sentences"]) or not all(lines) or any(len(s) > 100 for s in lines):
        raise HTTPException(400, "문장은 장면 수만큼, 비우지 않고 100자 안으로 적어 주세요")
    if not title or len(title) > 100 or len(description) > 5000:
        raise HTTPException(400, "제목은 1~100자, 설명은 5000자까지 적을 수 있어요")
    tags = [t for t in (x.strip().lstrip("#").strip() for x in tags.split(",")) if t]
    rerun = lines != old["sentences"]
    _redo(job_id, ("voice", "subtitles", "render") if rerun else (), "이미 올린 영상은 대본을 고칠 수 없어요",
          script=old | {"title": title, "description": description.strip(), "tags": tags, "sentences": lines})
    return {"ok": True, "msg": "저장했어요. 음성·자막·렌더를 다시 해요" if rerun else "저장했어요"}


@app.post("/api/jobs/{job_id}/script/revise")
def revise_script(job_id: str, note: str = Form("")):
    if not (note := _note(note)):
        raise HTTPException(400, "고칠 내용을 적어 주세요")
    _redo(job_id, ("script", "voice", "subtitles", "render"), "이미 올린 영상은 대본을 고칠 수 없어요", script_note=note)
    return {"ok": True, "msg": "Claude가 대본을 고친 뒤 음성·자막·렌더를 다시 해요"}


@app.post("/api/jobs/{job_id}/upload")
def upload(job_id: str):
    job = _load(Job, job_id)
    if not youtube.ready():
        raise HTTPException(400, "YouTube 연결이 안 돼 있어요. .env에 YOUTUBE_CLIENT_SECRET을 넣고 uv run sp youtube-login을 하세요.")
    if not worker.enqueue_upload(job_id):
        data = job.data
        raise HTTPException(409, "완성된 영상만 올릴 수 있어요" if data["status"] != "done"
                            else "이미 올렸어요" if data["upload"]["status"] == "done" else "이미 올리는 중이에요")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/clips/{i}")
async def put_clip(request: Request, job_id: str, i: int):
    """장면 i(0부터) 클립 원본을 raw body로 받는다. 다 모이면 이어서, 완성 뒤 교체면 뒤 단계만 다시."""
    job = _load(Job, job_id)
    s = read_json(job.dir / "script.json")
    if not s or not _can_upload(job.data):   # 큰 파일을 받기 전에 거절
        raise HTTPException(409, "지금은 클립을 올릴 수 없어요")
    if not 0 <= i < len(s["sentences"]):
        raise HTTPException(404, "그 장면이 없어요")
    if int(request.headers.get("content-length") or 0) > MAX_CLIP:
        raise HTTPException(413, "클립이 너무 커요(200MB 이하)")
    d = job.dir / "clips"
    d.mkdir(exist_ok=True)
    # 동시에 같은 장면을 올려도 겹치지 않는 이름. 서버가 꺼져 남은 것은 recover()가 지운다
    tmp, size = d / f"clip{i}.{secrets.token_hex(4)}.tmp.mp4", 0
    try:
        # ponytail: 쓰기는 동기라 받는 동안 이벤트 루프를 잠깐씩 잡는다. 혼자 쓰는 로컬 앱이라 충분하다
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_CLIP:   # Content-Length 없이 와도 상한을 지킨다
                    raise HTTPException(413, "클립이 너무 커요(200MB 이하)")
                f.write(chunk)
        with open(tmp, "rb") as f:
            if f.read(8)[4:8] != b"ftyp":   # mp4·mov 머리
                raise HTTPException(400, "mp4나 mov 영상만 올릴 수 있어요")
        try:   # 한 프레임 디코드해 영상인지 본다(아이폰 .mov·HEVC도 통과)
            await asyncio.to_thread(ffmpeg.run, ["-f", "mov", "-i", tmp.name, "-map", "0:v:0", "-frames:v", 1,
                                                 "-f", "null", "-"], d)
        except RuntimeError:
            raise HTTPException(400, "영상 파일이 아니에요") from None
        dst = d / f"clip{i}.mp4"
        with worker._lock:   # 확인·교체·다시 넣기를 한 번에(RLock이라 안에서 enqueue 가능)
            job = Job.load(job_id)
            if not _can_upload(job.data):   # 받는 사이 다시 시도·업로드가 시작됐다
                raise HTTPException(409, "지금은 클립을 올릴 수 없어요")
            os.replace(tmp, dst)
            video.set_clip(job.dir, {"file": dst.name, "source": "직접 올림"})
            job.log(f"장면 {i + 1} 클립 올림 ({size // 1024}KB)")
            if job.data["steps"]["footage"]["status"] == "done":   # 완성(또는 뒤 단계 실패) 뒤 교체: 다음 단계만
                worker.redo(job_id, ("thumbnail", "render") if i == 0 else ("render",))
            elif not pipeline.missing_clips(job.dir):
                worker.enqueue(job_id)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return {"ok": True}


@app.get("/trends")
def trends_page(request: Request):
    items = [t.data for t in reversed(Trend.all())]
    return templates.TemplateResponse(request, "trends.html", {
        "items": items, "ready": trends.ready(), "claude_ok": _checks()[0][0] == "ok",
        "est": script.cost(config.CLAUDE_MODEL, *EST_TOKENS),
        "active": any(t["status"] in ACTIVE for t in items)})


@app.post("/trends")
def create_trend(keyword: str = Form(""), period: str = Form(trends.DEFAULT_PERIOD)):
    keyword = keyword.strip()
    if len(keyword) > 50:
        raise HTTPException(400, "키워드는 50자 이내로 넣어 주세요")
    if period not in trends.PERIODS:
        raise HTTPException(400, "모르는 기간이에요")
    if not trends.ready():
        raise HTTPException(400, "YouTube Data API 키가 없어요. .env에 YOUTUBE_API_KEY를 넣고 서버를 다시 켜세요.")
    trend = Trend.create(keyword, period)
    worker.enqueue_trend(trend.id)
    return RedirectResponse(f"/trends/{trend.id}", status_code=303)


@app.get("/trends/{trend_id}")
def trend_page(request: Request, trend_id: str):
    trend = _load(Trend, trend_id)
    videos = read_json(trend.dir / "videos.json", [])
    return templates.TemplateResponse(request, "trend.html", {
        "t": trend.data, "videos": videos, "vids": {v["id"]: v for v in videos},
        "analyses": read_json(trend.dir / "analyses.json", {}), "picks": read_json(trend.dir / "picks.json"),
        "log": _tail(trend)})


@app.get("/api/trends/{trend_id}")
def trend_api(trend_id: str):
    trend = _load(Trend, trend_id)
    data = trend.data
    return data | {"sig": tsig(data), "say": tsay(data), "log": _tail(trend)}


@app.post("/api/trends/{trend_id}/retry")
def trend_retry(trend_id: str):
    trend = _load(Trend, trend_id)
    if not worker.enqueue_trend(trend_id):
        raise HTTPException(409, "이미 끝난 분석이에요" if trend.data["status"] == "done" else "이미 분석 중이에요")
    return {"ok": True}

"""브라우저 화면: 주제 넣기(또는 인기 쇼츠 분석에서 고르기) → 대본·음성·자막 확정
→ 영상·썸네일 진행 보기(장면 클립 올리기) → 완성 영상."""
import asyncio
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .. import config, registry
from ..core import channel, pipeline, scenes, schedule, script, trends, voice
from ..core.channel import Channel
from ..core.pipeline import LABELS, STEPS, Job, in_review
from ..core.schedule import Schedule
from ..core.trends import Trend
from ..infra import ffmpeg
from ..infra.store import migrate, upload_state
from ..ports.llm import add_usage

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
ALL = "all"   # 채널 고르기의 "전체 채널"
COOKIE = "sp_channel"   # 고른 채널을 기억한다
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
# 상세 화면 단계 묶음: 대본·음성·자막을 확정해야 영상으로 넘어간다
PHASES = (("대본", ("research", "script", "voice", "subtitles")), ("영상", ("footage",)), ("썸네일", ("thumbnail",)),
          ("완성", ("render",)))
# 스케줄 회차 배지(글, 색)
RUN = {"skipped": ("건너뜀", ""), "missed": ("놓침", "b-interrupted"), "failed": ("실패", "b-failed")}
# Lucide 아이콘 경로(ISC 라이선스). 이모지 대신 쓴다.
ICONS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "loader": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'),
    "rotate": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "play": '<path d="M6 3 20 12 6 21Z"/>',
    "alert": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
        '<path d="M12 9v4"/>'
        '<path d="M12 17h.01"/>'),
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "external": (
        '<path d="M15 3h6v6"/>'
        '<path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'),
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "sparkles": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5'
        'l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964'
        'L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>'
        '<path d="M20 3v4"/>'
        '<path d="M22 5h-4"/>'),
    "trending": '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
    "trash": (
        '<path d="M3 6h18"/>'
        '<path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>'
        '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>'),
    "film": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M7 3v18M17 3v18M3 7.5h4M3 12h18M3 16.5h4M17 7.5h4M17 16.5h4"/>'),
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "list": ('<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/>'
             '<path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>'),
    "pencil": (
        '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622'
        'l4.353-1.32a2 2 0 0 0 .83-.497z"/>'
        '<path d="m15 5 4 4"/>'),
    "bell": (
        '<path d="M10.268 21a2 2 0 0 0 3.464 0"/>'
        '<path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8'
        'c0 4.499-1.411 5.956-2.738 7.326"/>'),
    "send": (
        '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937'
        'l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>'
        '<path d="m21.854 2.147-10.94 10.939"/>'),
}
q = registry.queue()   # 작업 큐 하나(registry가 cache)
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


def status_label(data: dict) -> str:
    return "대본 확인" if in_review(data) else STATUS[data["status"]]


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
    return status_label(data)


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


def at(v: datetime | str | None) -> str:
    """스케줄 시각: 10/16(목) 09:00."""
    if not v:
        return ""
    dt = (datetime.fromisoformat(v) if isinstance(v, str) else v).astimezone()
    return f"{dt:%m/%d}({schedule.DAYS[dt.weekday()]}) {dt:%H:%M}"


def until(dt: datetime) -> str:
    """다음 실행까지: 곧, 12분 뒤, 3시간 20분 뒤, 2일 뒤."""
    m = max(0, round((dt - datetime.now().astimezone()).total_seconds() / 60))
    if m >= 1440:
        return f"{round(m / 1440)}일 뒤"
    if m >= 60:
        return f"{m // 60}시간{f' {m % 60}분' if m % 60 else ''} 뒤"
    return f"{m}분 뒤" if m else "곧"


def mmss(sec: float | None) -> str:
    if sec is None:
        return ""
    s = round(sec)
    return f"{s // 60}:{s % 60:02d}"


def cue_ts(sec: float) -> str:
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def job_cost(j: dict) -> float | None:
    """자료 조사 + 대본 + 썸네일 + 한국어 뜻 Claude 비용. 모두 모르면 None."""
    costs = [u["cost_usd"] for u in (j.get("research_usage"), j["usage"], j.get("thumb_usage"), j.get("ko_usage"))
             if u and u["cost_usd"] is not None]
    return round(sum(costs), 4) if costs else None


def recover() -> None:
    """앱이 켜질 때: 끊긴 작업·분석을 interrupted로, 반쯤 쓰인 *.tmp 파일을 지운다."""
    # ponytail: 다른 터미널에서 `sp run`·`sp trends`가 돌고 있어도 중단으로 표시한다.
    # 둘을 같이 쓰려면 상태 json에 pid를 남겨 살아 있는지 볼 것
    for root in (config.JOBS_DIR, config.TRENDS_DIR):
        root.mkdir(parents=True, exist_ok=True)
    # 스케줄 것이면 실패 알림을 보낸다(after_*는 손으로 만든 것엔 아무것도 하지 않는다)
    for t in Trend.all():
        if t.data["status"] in ACTIVE:
            t.interrupt()
            schedule.after_trend(t, q, q.notify)
    for job in Job.all():
        if job.data["status"] in ACTIVE:
            job.interrupt()
            schedule.after_job(job, "run", q, q.notify)
        # PUT이 끝났을 수도 있어 다시 올리기 전에 확인하게 한다(같은 영상 두 번 올리기 방지)
        if (job.data.get("upload") or {}).get("status") in ACTIVE:
            job.update(upload=upload_state(
                "failed", error="서버가 꺼져 멈췄어요. 올라갔는지 YouTube 스튜디오에서 먼저 확인하세요."))
            schedule.after_job(job, "upload", q, q.notify)
    for root in (config.JOBS_DIR, config.TRENDS_DIR):
        for pattern in ("*.tmp", "*.tmp.mp4"):
            for p in root.rglob(pattern):
                p.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(_app):
    # 예전 폴더(json·log.txt)를 DB로. 이미 옮긴 id는 건너뛴다
    if moved := {k: n for k, n in migrate().items() if n}:
        log.warning("DB로 옮김: %s", moved)
    recover()
    q.start()
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


@app.middleware("http")
async def remember_channel(request: Request, call_next):
    """?channel=<id|all>로 고른 채널을 쿠키에 남긴다. 모르는 채널이면 404."""
    cid = request.query_params.get("channel")
    if cid is not None and cid != ALL and cid not in channel.ids():
        return PlainTextResponse("채널이 없어요", status_code=404)
    response = await call_next(request)
    if cid is not None:
        response.set_cookie(COOKIE, cid, max_age=365 * 86400, samesite="lax")
    return response

app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.mount("/files", StaticFiles(directory=config.JOBS_DIR, check_dir=False), name="files")
app.mount("/trend-files", StaticFiles(directory=config.TRENDS_DIR, check_dir=False), name="trend-files")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals |= {
    "v": int(datetime.now().timestamp()),   # 서버를 켠 시각으로 정적 파일 캐시를 깬다
    "icon": icon, "sig": sig, "job_cost": job_cost, "STEPS": STEPS, "LABELS": LABELS, "STATUS": STATUS, "STATE": STATE,
    "ACTIVE": ACTIVE, "trends": trends, "tsig": tsig, "TSTATUS": TSTATUS, "ALL": ALL, "LANGS": channel.LANGS,
    "QUOTA_PER_RUN": QUOTA_PER_RUN, "QUOTA_DAY": QUOTA_DAY, "NODE_ICON": NODE_ICON, "CHECK_ICON": CHECK_ICON,
    "schedule": schedule, "PHASES": PHASES, "status_label": status_label, "in_review": in_review,
}
templates.env.filters |= {"hm": hm, "mmss": mmss, "cue_ts": cue_ts, "kn": kn, "ago": ago, "at": at, "until": until}


def _load(cls, rec_id: str):
    """Job·Trend 하나. id 모양을 먼저 봐서 폴더 밖 경로를 막는다."""
    if not re.fullmatch(r"[\w-]+", rec_id):
        raise HTTPException(404, f"{cls.WHAT}이 없어요")
    try:
        return cls.load(rec_id)
    except FileNotFoundError:
        raise HTTPException(404, f"{cls.WHAT}이 없어요") from None


def _sel(request: Request) -> str:
    """고른 채널 id 또는 ALL. ?channel → 쿠키 → 첫 채널."""
    ids = channel.ids()
    cid = request.query_params.get("channel") or request.cookies.get(COOKIE)
    return cid if cid == ALL or cid in ids else ids[0]


def _channels() -> dict[str, Channel]:
    """설정이 틀린 채널은 빼고 로그에 남긴다. 한 채널 때문에 모든 화면이 500이 되지 않게."""
    out = {}
    for cid in channel.ids():
        try:
            out[cid] = channel.load(cid)
        except (KeyError, ValueError) as e:   # pydantic·toml 오류도 ValueError
            log.warning("채널 %s 설정 오류: %s", cid, e)
    return out


def _channel(cid: str | None, code: int = 404) -> Channel:
    """채널 하나. 없거나 ALL이면 code로 거절한다."""
    try:
        return channel.load(cid or "")
    except KeyError:
        raise HTTPException(code, "채널을 먼저 골라 주세요" if cid in (None, "", ALL) else "채널이 없어요") from None
    except ValueError as e:   # channel.toml 값이 틀렸다(pydantic·toml)
        raise HTTPException(code, f"채널 설정이 틀려요: {e}") from None


def _page(request: Request, name: str, ctx: dict):
    """상단바(채널 고르기·환경 점검)에 필요한 값을 더해 그린다."""
    sel = _sel(request)
    top = {"channels": _channels(), "sel": sel, "checks": _checks(sel)}
    return templates.TemplateResponse(request, name, top | ctx)


def _picks(trend: Trend) -> list[dict]:
    return (trend.doc("picks.json") or {}).get("picks", [])


def _tail(job: Job | Trend, n: int = 200) -> list[str]:
    return job.tail(n)


def _stats(jobs: list[dict], goal: int) -> dict:
    today = datetime.now().astimezone().date().isoformat()
    return {
        "today": sum(j["status"] == "done" and (j["finished_at"] or "")[:10] == today for j in jobs),
        "goal": goal,
        "total": len(jobs),
        "failed": sum(j["status"] == "failed" for j in jobs),
        "cost": sum(job_cost(j) or 0 for j in jobs),
    }


def _checks(cid: str) -> list[tuple[str, str, str]]:
    """고른 채널(전체면 첫 채널)의 (ok|warn|bad, 이름, 한 줄 설명). 값은 보여 주지 않고 있는지만 본다."""
    try:
        sv = registry.services(channel.ids()[0] if cid == ALL else cid)
    except (KeyError, ValueError, RuntimeError) as e:
        return [("bad", "채널 설정", str(e))]
    ff = Path(config.FFMPEG).exists()
    checks = [
        ("ok" if sv.llm.ready() else "bad", f"{sv.llm.label} API 키", sv.llm.hint),
        ("ok" if ff else "bad", "ffmpeg-full",
         config.FFMPEG if ff else "brew install ffmpeg-full 또는 .env에 SP_FFMPEG"),
    ]
    mine = sv.channel.video.provider
    checks += [("ok" if p.ready() else "warn", f"영상 · {p.label}" + (" (이 채널)" if k == mine else ""), p.hint)
               for k, p in registry.VIDEOS.items()]
    pub = sv.publisher
    on = [n.label for n in registry.NOTIFIERS.values() if n.ready()]
    return checks + [
        ("ok" if sv.tts.ready() else "bad", f"음성 · {sv.tts.label}", sv.tts.hint),
        ("ok" if sv.research.ready() else "bad", f"조사 · {sv.research.label}", sv.research.hint)
        if sv.channel.research.domains or sv.channel.research.news
        else ("bad", f"조사 · {sv.research.label}", "channel.toml [research] domains에 허용 사이트를 넣어 주세요"),
        ("ok" if pub.ready() else "warn", f"{pub.label} 업로드", pub.hint),
        ("ok", "YouTube Data API 키", "주제 찾기에서 인기 쇼츠를 모아요") if trends.ready()
        else ("warn", "YouTube Data API 키", "선택 · 주제 찾기용 · .env에 YOUTUBE_API_KEY"),
        ("ok", f"알림 · {'·'.join(on)}", "스케줄 작업의 업로드 완료·실패·확인 필요를 보내요") if on
        else ("warn", "알림",
              "선택 · 스케줄 결과 받기 · " + " 또는 ".join(n.hint for n in registry.NOTIFIERS.values())),
    ]


def _latest_picks(cid: str, chs: dict[str, Channel]) -> dict | None:
    """대시보드에 띄울, 고른 채널의 최신 완료 분석 추천 상위 3개. 지웠거나 설정이 틀린 채널 것은 뺀다."""
    for t in reversed(Trend.all()):
        tc = t.data.get("channel")
        if cid in (ALL, tc) and tc in chs and t.data["status"] == "done" and (picks := _picks(t)):
            return {"trend": t.data, "picks": list(enumerate(picks))[:3]}
    return None


def _can_upload(data: dict) -> bool:
    """클립을 올리거나 바꿀 수 있나: 대본을 확정했고, 만들거나 YouTube에 올리는 중이 아닐 때
    (올린 뒤에 바꾸면 새로 올린다)."""
    return (data["status"] not in ACTIVE and not in_review(data)
            and (data.get("upload") or {}).get("status") not in ACTIVE)


def _scenes(job: Job) -> list[dict]:
    """장면 카드용. 끝난 예전 작업(클립 수 ≠ 문장 수)은 []를 돌려 예전 화면으로 보인다."""
    s = job.doc("script.json")
    if not s:
        return []
    clips = {c["file"]: c for c in job.doc("clips.json", [])}
    if job.data["steps"]["footage"]["status"] == "done" and len(clips) != len(s["sentences"]):
        return []
    out = scenes.scenes(s, job.doc("timing.json"))
    for x in out:
        p = job.dir / "clips" / x["file"]
        x["v"] = p.stat().st_mtime_ns if p.exists() else None   # 미리보기 캐시 깨기(같은 초에 바꿔도)
        x["clip"] = clips.get(x["file"])   # 출처(스톡 촬영자 등)
    return out


@app.get("/")
def index(request: Request):
    sel, chs = _sel(request), _channels()
    jobs = [j.data for j in reversed(Job.all()) if sel in (ALL, j.data.get("channel"))]
    ch = chs.get(sel)
    goal = ch.daily_goal if ch else sum(c.daily_goal for c in chs.values())
    return _page(request, "index.html", {
        "jobs": jobs, "stats": _stats(jobs, goal), "ch": ch, "llm_ok": _checks(sel)[0][0] == "ok",
        "active": any(j["status"] in ACTIVE for j in jobs), "rec": _latest_picks(sel, chs)})


@app.post("/jobs")
def create_job(topic: str = Form(""), voice: str = Form(...), cid: str = Form("", alias="channel"),
               trend: str | None = Form(None), pick: int | None = Form(None)):
    if trend is not None:
        # 추천에서 만들 때는 채널·주제·방향을 서버가 분석 기록에서 꺼낸다(클라이언트가 보낸 값은 믿지 않는다)
        t = _load(Trend, trend)
        ch = _channel(t.data.get("channel"), 400)
        if voice not in ch.tts.voices:
            raise HTTPException(400, "모르는 목소리예요")
        picks = _picks(t)
        if pick is None or not 0 <= pick < len(picks):
            raise HTTPException(400, "그 추천을 찾지 못했어요")
        p = picks[pick]
        job = Job.create(ch.id, p["topic"], voice, brief=trends.brief(t, p), source={"trend": trend, "pick": pick},
                         review=True)
        q.enqueue(job.id)
        return RedirectResponse(f"/jobs/{job.id}", status_code=303)
    ch = _channel(cid, 400)
    if voice not in ch.tts.voices:
        raise HTTPException(400, "모르는 목소리예요")
    topic = topic.strip()
    if not 1 <= len(topic) <= 200:
        raise HTTPException(400, "주제는 1~200자로 넣어 주세요")
    job = Job.create(ch.id, topic, voice, review=True)
    q.enqueue(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}")
def job_page(request: Request, job_id: str):
    job = _load(Job, job_id)
    ch = _channel(job.data.get("channel"))
    s, thumb, ko, cues = job.doc("script.json"), job.doc("thumb.json"), job.doc("ko.json"), job.doc("cues.json")
    facts = (job.doc("facts.json") or {}).get("facts", [])
    return _page(request, "job.html", {
        # 조사 없이 만든 예전 작업은 근거 검사를 하지 않는다(모든 숫자 문장이 걸린다)
        "facts": facts, "unverified": script.unverified(s, facts) if s and facts else [],
        "desc": pipeline.description(job, ch) if s else "",
        "job": job.data, "ch": ch, "publisher": registry.publisher(ch),
        "script": s, "clips": job.doc("clips.json"),
        "cues": cues, "has_thumb": (job.dir / "thumbnail.jpg").exists(),
        "thumb": thumb, "log": _tail(job),
        "ko": ko, "ko_stale": bool(ko and s and ko["src"] != script.ko_source(s, thumb)),
        # 옮긴 뒤 자막을 고쳤거나 옮길 때 자막이 없었으면 자막 뜻은 안 보인다
        "ko_cues": ko["ko"]["cues"] if ko and cues and ko.get("cues") == [c["text"] for c in cues] else None,
        "scenes": _scenes(job), "can_upload": _can_upload(job.data)})


@app.get("/api/jobs/{job_id}")
def job_api(job_id: str):
    job = _load(Job, job_id)
    data = job.data
    return data | {"sig": sig(data), "say": say(data), "log": _tail(job)}


@app.post("/api/jobs/{job_id}/retry")
def retry(job_id: str):
    job = _load(Job, job_id)
    if not q.enqueue(job_id):
        raise HTTPException(409, "이미 완성된 작업이에요" if job.data["status"] == "done" else "이미 제작 중이에요")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/delete")
def delete_job(job_id: str):
    """작업 기록과 폴더를 지운다. 이미 올린 YouTube 영상은 그대로 둔다."""
    job = _load(Job, job_id)
    with q.lock:   # 검사와 지우기 사이에 작업이 시작되지 않게
        data = job.data
        if data["status"] in ACTIVE or (data.get("upload") or {}).get("status") in ACTIVE:
            raise HTTPException(409, "제작·업로드 중인 작업은 지울 수 없어요")
        job.delete()
    return {"ok": True}


@app.post("/api/jobs/{job_id}/confirm")
def confirm(job_id: str):
    """대본(민감 분야 포함)을 사람이 확인했다. 멈춘 단계부터 이어서."""
    job = _load(Job, job_id)
    with q.lock:   # 고쳐 쓰는 중(queued·running)에 확정하면 고치기 전 대본을 확정한 셈이 된다
        if job.data["status"] != "waiting":
            raise HTTPException(409, "지금은 확정할 수 없어요")
        job.update(confirmed=True)
    return retry(job_id)


def _note(note: str) -> str:
    if len(note) > MAX_NOTE:
        raise HTTPException(400, f"수정 요청은 {MAX_NOTE}자까지 적을 수 있어요")
    return note.strip()


def _redo(job_id: str, steps: tuple, **kw) -> None:
    """확정 전·완성 뒤 고치기. 만들거나 올리는 중이면 409."""
    job = _load(Job, job_id)
    if not q.redo(job_id, steps, **kw):
        done = job.data["status"] in ("done", "failed", "interrupted", "waiting")
        raise HTTPException(409, "올리는 중에는 고칠 수 없어요" if done else "만드는 중에는 고칠 수 없어요")


@app.post("/api/jobs/{job_id}/thumbnail")
def rethumb(job_id: str, note: str = Form("")):
    _redo(job_id, ("thumbnail", "render"), thumb_note=_note(note), thumb_hand=None)
    return {"ok": True, "msg": "썸네일을 다시 만들고 영상도 다시 렌더해요"}


@app.get("/api/channels/{cid}/voices/{key}/sample")
def voice_sample(cid: str, key: str):
    ch = _channel(cid)
    if key not in ch.tts.voices:
        raise HTTPException(404, "모르는 목소리예요")
    try:
        return FileResponse(voice.sample(registry.services(ch.id).tts, ch, key), media_type="audio/mpeg")
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None


def _clean(s: str) -> str:
    return " ".join(s.split())   # 칸 안의 줄바꿈은 띄어쓰기로


@app.post("/api/jobs/{job_id}/edit")
def save_edit(job_id: str, title: str = Form(""), description: str = Form(""), tags: str = Form(""),
              sentences: list[str] = Form([]), voice: str = Form(""), cues: list[str] = Form([]),  # noqa: B008
              thumb: list[str] = Form([]), accent: str = Form(""), prompts: list[str] = Form([])):  # noqa: B008
    """상세 화면에서 손으로 고친 값. 바뀐 칸을 보고 다시 할 단계만 고른다.
    문장·목소리 → 음성부터(자막은 새로 나뉘어 고친 자막 줄은 버린다), 자막 줄 → 렌더, 썸네일 문구 → 썸네일·렌더.
    제목·설명·태그만이면 저장만. 장면 클립은 그대로. 장면 프롬프트는 확정 전(클립을 아직 안 만들었을 때)만 받는다."""
    job = _load(Job, job_id)
    old, was = job.doc("script.json"), job.data["voice"]
    lines, title, voice = [_clean(s) for s in sentences], title.strip(), voice or was
    ch = _channel(job.data.get("channel"))
    if voice != was and voice not in ch.tts.voices:
        raise HTTPException(400, "모르는 목소리예요")
    # 채널 문장 길이의 두 배까지. 바꾼 문장만 본다(예전 대본이 한도를 넘어도 저장은 되게)
    cap, unit = ch.script.sentence[1] * 2, ch.script.unit
    size = (lambda s: len(s.split())) if unit == "words" else len
    if (not old or len(lines) != len(old["sentences"]) or not all(lines)
            or any(size(s) > cap for s, o in zip(lines, old["sentences"], strict=True) if s != o)):
        raise HTTPException(400, f"문장은 장면 수만큼, 비우지 않고 {cap}{script.UNITS[unit]} 안으로 적어 주세요")
    if not title or len(title) > 100 or len(description) > 5000:
        raise HTTPException(400, "제목은 1~100자, 설명은 5000자까지 적을 수 있어요")
    tags = [t for t in (x.strip().lstrip("#").strip() for x in tags.split(",")) if t]
    files = {"script.json": old | {"title": title, "description": description.strip(), "tags": tags,
                                   "sentences": lines}}
    if prompts:
        if not in_review(job.data):
            raise HTTPException(409, "장면 프롬프트는 대본을 확정하기 전에만 고칠 수 있어요")
        shots = [_clean(x) for x in prompts]
        if len(shots) != len(lines) or not all(shots) or any(len(x) > 1000 for x in shots):
            raise HTTPException(400, "장면 프롬프트는 장면 수만큼, 비우지 않고 1000자 안으로 적어 주세요")
        files["script.json"] |= {"prompts": shots, "prompts_ko": script.keep_ko(old, shots)}
    fields, steps = {"voice": voice}, set()
    if lines != old["sentences"] or voice != was:
        steps |= {"voice", "subtitles", "render"}
    elif cues and (before := job.doc("cues.json")):
        texts = [_clean(c) for c in cues]
        if len(texts) != len(before) or not all(texts) or any(len(t) > 40 for t in texts):
            raise HTTPException(400, "자막은 줄 수 그대로, 비우지 않고 40자 안으로 적어 주세요")
        if texts != [c["text"] for c in before]:
            files["cues.json"] = [c | {"text": t} for c, t in zip(before, texts, strict=True)]
            steps.add("render")
    if thumb and (t := job.doc("thumb.json")):
        hand = [_clean(x) for x in thumb if x.strip()]
        # 문구에 없는 강조는 뺀다
        accent = accent.strip() if accent.strip() and accent.strip() in " ".join(hand) else ""
        if (hand, accent) != (t["lines"], t.get("accent", "")):
            cap = ch.thumbnail.max_line + 3   # 손으로 고칠 땐 채널 한도보다 조금 넉넉히
            if not 1 <= len(hand) <= 2 or any(len(x) > cap for x in hand):
                raise HTTPException(400, f"썸네일 문구는 1~2줄, 줄마다 {cap}자 안으로 적어 주세요")
            fields["thumb_hand"] = {"lines": hand, "accent": accent}
            steps |= {"thumbnail", "render"}
    if in_review(job.data):   # 확정 전엔 썸네일·렌더를 아직 안 했다(확정하면 그때 만든다)
        steps -= {"thumbnail", "render"}
    steps = tuple(s for s in STEPS if s in steps)
    _redo(job_id, steps, files=files, **fields)
    redo = "·".join(LABELS[s] for s in steps)
    return {"ok": True, "msg": f"저장했어요. {redo}를 다시 해요" if steps else "저장했어요"}


@app.post("/api/jobs/{job_id}/script/revise")
def revise_script(job_id: str, note: str = Form("")):
    if not (note := _note(note)):
        raise HTTPException(400, "고칠 내용을 적어 주세요")
    review = in_review(_load(Job, job_id).data)
    _redo(job_id, ("script", "voice", "subtitles", "render"), script_note=note)
    return {"ok": True, "msg": "Claude가 대본을 고치고 음성·자막을 다시 만들어요. 끝나면 다시 확인해 주세요" if review
            else "Claude가 대본을 고친 뒤 음성·자막·렌더를 다시 해요"}


@app.post("/api/jobs/{job_id}/translate")
def translate(job_id: str):
    """한국어가 아닌 채널: 운영자가 확인하도록 대본·썸네일 문구를 한국어로 옮긴다. 작업 단계는 다시 하지 않는다."""
    job = _load(Job, job_id)
    if not (s := job.doc("script.json")):
        raise HTTPException(409, "대본이 아직 없어요")
    sv = registry.services(job.data["channel"])
    try:
        ko, usage = script.translate(sv.llm, sv.channel, s, job.doc("thumb.json"),
                                     [c["text"] for c in job.doc("cues.json") or []])
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from None
    job.put("ko.json", ko)
    job.update(ko_usage=add_usage(job.data.get("ko_usage"), usage))
    return {"ok": True, "msg": "한국어로 옮겼어요"}


@app.post("/api/jobs/{job_id}/upload")
def upload(job_id: str):
    job = _load(Job, job_id)
    pub = registry.publisher(_channel(job.data.get("channel")))
    if not pub.ready():
        raise HTTPException(400, f"{pub.label} 연결이 안 돼 있어요. {pub.hint}")
    if not q.enqueue_upload(job_id):
        data = job.data
        raise HTTPException(409, "완성된 영상만 올릴 수 있어요" if data["status"] != "done"
                            else "이미 올렸어요" if data["upload"]["status"] == "done" else "이미 올리는 중이에요")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/clips/{i}")
async def put_clip(request: Request, job_id: str, i: int):
    """장면 i(0부터) 클립 원본을 raw body로 받는다. 다 모이면 이어서, 완성 뒤 교체면 뒤 단계만 다시."""
    job = _load(Job, job_id)
    s = job.doc("script.json")
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
        with q.lock:   # 확인·교체·다시 넣기를 한 번에(RLock이라 안에서 enqueue 가능)
            job = Job.load(job_id)
            if not _can_upload(job.data):   # 받는 사이 다시 시도·업로드가 시작됐다
                raise HTTPException(409, "지금은 클립을 올릴 수 없어요")
            os.replace(tmp, dst)
            scenes.set_clip(job, {"file": dst.name, "source": "직접 올림"})
            job.log(f"장면 {i + 1} 클립 올림 ({size // 1024}KB)")
            if job.data["steps"]["footage"]["status"] == "done":   # 완성(또는 뒤 단계 실패) 뒤 교체: 다음 단계만
                q.redo(job_id, ("thumbnail", "render") if i == 0 else ("render",))
            elif not pipeline.missing_clips(job):
                q.enqueue(job_id)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return {"ok": True}


@app.get("/trends")
def trends_page(request: Request):
    sel = _sel(request)
    items = [t.data for t in reversed(Trend.all()) if sel in (ALL, t.data.get("channel"))]
    try:
        sv = None if sel == ALL else registry.services(sel)
    except (KeyError, ValueError, RuntimeError):   # 상단바 환경 점검에 이유가 뜬다
        sv = None
    return _page(request, "trends.html", {
        "items": items, "ready": trends.ready(), "ch": sv and sv.channel, "llm_ok": _checks(sel)[0][0] == "ok",
        "est": sv and sv.llm.cost(*EST_TOKENS), "active": any(t["status"] in ACTIVE for t in items)})


@app.post("/trends")
def create_trend(keyword: str = Form(""), period: str = Form(trends.DEFAULT_PERIOD), mode: str = Form("trend"),
                 cid: str = Form("", alias="channel")):
    ch = _channel(cid, 400)
    keyword = keyword.strip()
    if len(keyword) > 50:
        raise HTTPException(400, "키워드는 50자 이내로 넣어 주세요")
    if period not in trends.PERIODS:
        raise HTTPException(400, "모르는 기간이에요")
    if mode not in trends.MODES:
        raise HTTPException(400, "모르는 방식이에요")
    if mode == "trend" and not trends.ready():   # 아이디어 모드는 YouTube를 부르지 않는다
        raise HTTPException(400, "YouTube Data API 키가 없어요. .env에 YOUTUBE_API_KEY를 넣고 서버를 다시 켜세요.")
    trend = Trend.create(ch.id, keyword, period, mode)
    q.enqueue_trend(trend.id)
    return RedirectResponse(f"/trends/{trend.id}", status_code=303)


@app.post("/trends/{trend_id}/again")
def trend_again(trend_id: str):
    trend = _load(Trend, trend_id)
    if not trend.idea or trend.data["status"] != "done":
        raise HTTPException(409, "끝난 아이디어 추천만 다시 뽑을 수 있어요")
    new = trend.again()
    q.enqueue_trend(new.id)
    return RedirectResponse(f"/trends/{new.id}", status_code=303)


@app.get("/trends/{trend_id}")
def trend_page(request: Request, trend_id: str):
    trend = _load(Trend, trend_id)
    videos = trend.doc("videos.json", [])
    return _page(request, "trend.html", {
        "t": trend.data, "ch": _channel(trend.data.get("channel")),
        "videos": videos, "vids": {v["id"]: v for v in videos},
        "analyses": trend.doc("analyses.json", {}), "picks": trend.doc("picks.json"),
        "log": _tail(trend)})


@app.get("/api/trends/{trend_id}")
def trend_api(trend_id: str):
    trend = _load(Trend, trend_id)
    data = trend.data
    return data | {"sig": tsig(data), "say": tsay(data), "log": _tail(trend)}


@app.post("/api/trends/{trend_id}/retry")
def trend_retry(trend_id: str):
    trend = _load(Trend, trend_id)
    if not q.enqueue_trend(trend_id):
        raise HTTPException(409, "이미 끝난 분석이에요" if trend.data["status"] == "done" else "이미 분석 중이에요")
    return {"ok": True}


# ---------- 스케줄 ----------

def _notifiers() -> list[tuple[str, bool, str]]:
    return [(n.label, n.ready(), n.hint) for n in registry.NOTIFIERS.values()]


def _run_view(run: dict) -> dict:
    """회차 한 줄의 배지(label·cls)·링크·주제. 시작한 회차는 작업·주제 찾기의 지금 상태를 보여 준다."""
    label, cls = RUN.get(run["result"], ("", ""))
    view = {"label": label, "cls": cls, "href": None, "topic": run["topic"]}
    try:
        if run["job"]:
            job = Job.load(run["job"])
            d, up = job.data, (job.data.get("upload") or {}).get("status")
            view |= {"href": f"/jobs/{job.id}", "topic": run["topic"] or d["topic"]}
            if run["result"] != "started":
                return view
            st = d["status"]
            if up == "done":
                return view | {"label": "업로드됨", "cls": "b-up"}
            if up in ACTIVE:
                return view | {"label": "올리는 중", "cls": "b-running"}
            if up == "failed":
                return view | {"label": "업로드 실패", "cls": "b-failed"}
            if in_review(d):
                return view | {"label": "대본 확인", "cls": "b-waiting"}
            sc = job.doc("script.json") if st == "waiting" else None
            if sc and sc.get("sensitive") and not d.get("confirmed"):
                return view | {"label": "확인 필요", "cls": "b-waiting"}
            return view | {"label": STATUS[st], "cls": {"draft": "b-queued"}.get(st, f"b-{st}")}
        if run["trend"]:
            st = Trend.load(run["trend"]).data["status"]
            view["href"] = f"/trends/{run['trend']}"
            if run["result"] == "started":   # 작업 없이 멈춘 주제 찾기(중단 등)는 그 상태를 보인다
                view |= {"label": "주제 찾는 중", "cls": "b-running"} if st in ("draft", *ACTIVE) \
                    else {"label": TSTATUS[st], "cls": f"b-{st}"}
    except FileNotFoundError:
        view |= {"label": view["label"] if run["result"] != "started" else "지워진 작업", "href": None}
    return view


def _manual(ch: Channel | None) -> str:
    """지금 이 채널이 클립을 사람이 올려야 하면 그 공급자 이름(스케줄 작업이 멈춘다)."""
    if not ch:
        return ""
    name, p = registry.video(ch)
    return p.label if name == registry.FALLBACK_VIDEO else ""


def _card(s: Schedule, now: datetime) -> dict:
    d = s.data
    w = schedule.When(**d["when"])
    nxt = schedule.next_runs(w, now, 1) if d["enabled"] else []
    return d | {"summary": schedule.summary(w), "next": nxt[0] if nxt else None, "busy": schedule.busy(d),
                "last": d["runs"][-1] | _run_view(d["runs"][-1]) if d["runs"] else None}


def _preview(w: schedule.When) -> dict:
    nxt = schedule.next_runs(w, datetime.now().astimezone())
    return {"summary": schedule.summary(w), "next": [{"iso": t.isoformat(), "label": at(t), "rel": until(t)}
                                                     for t in nxt]}


async def _fields(request: Request) -> dict:
    """스케줄 폼 → Schedule.create·change 인자(+channel). 시각이 틀리면 400. 나머지 검사는 core가 한다."""
    f = await request.form()
    when = {"kind": f.get("kind", ""), "times": [t for t in f.getlist("times") if t], "days": f.getlist("days")}
    when |= {k: f[k] for k in ("every", "start", "end") if f.get(k)}   # 비우면 기본값
    try:
        when = schedule.parse_when(when)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"channel": f.get("channel", ""), "name": f.get("name", ""), "source": f.get("source", ""),
            "voice": f.get("voice", ""), "keyword": f.get("keyword", ""),
            "period": f.get("period", trends.DEFAULT_PERIOD), "topics": f.get("topics", "").splitlines(), "when": when}


@app.get("/schedules")
def schedules_page(request: Request):
    sel, chs, now = _sel(request), _channels(), datetime.now().astimezone()
    items = [_card(s, now) for s in Schedule.all() if sel in (ALL, s.data["channel"])]
    items.sort(key=lambda c: (c["next"] is None, c["next"] or now))   # 다음에 도는 것부터, 꺼진 것은 뒤로
    pub = {c: registry.publisher(chs[c]) for c in {i["channel"] for i in items} if c in chs}
    return _page(request, "schedules.html", {
        "items": items, "ch": chs.get(sel), "notifiers": _notifiers(), "trend_ok": trends.ready(),
        "pub_bad": [p for p in pub.values() if not p.ready()][:1], "active": any(i["busy"] for i in items)})


@app.get("/schedules/new")
def new_schedule_page(request: Request):
    sel = _sel(request)
    ch = None if sel == ALL else _channels().get(sel)
    w = schedule.When(kind="times", times=["09:00"])
    s = {"name": "", "source": "trend", "keyword": "", "period": trends.DEFAULT_PERIOD, "topics": [],
         "voice": ch.tts.default if ch else "", "when": w.model_dump(), "enabled": True}
    return _page(request, "schedule.html", {"s": s, "ch": ch, "preview": _preview(w), "notifiers": _notifiers(),
                                            "trend_ok": trends.ready(), "runs": [], "manual": _manual(ch)})


@app.get("/schedules/{sid}")
def schedule_page(request: Request, sid: str):
    s = _load(Schedule, sid)
    d = s.data
    runs = [r | _run_view(r) for r in reversed(d["runs"])]
    ch = _channel(d["channel"])
    return _page(request, "schedule.html", {
        "s": d, "ch": ch, "preview": _preview(schedule.When(**d["when"])), "manual": _manual(ch),
        "notifiers": _notifiers(), "trend_ok": trends.ready(), "runs": runs, "active": schedule.busy(d)})


@app.post("/schedules")
async def create_schedule(request: Request):
    f = await _fields(request)
    ch = _channel(f.pop("channel"), 400)
    try:
        Schedule.create(ch.id, **f)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return RedirectResponse("/schedules", status_code=303)


@app.post("/api/schedules/preview")
async def preview_schedule(request: Request):
    """폼의 시각 값으로 요약과 다음 실행 5번. 저장하지 않는다."""
    return _preview((await _fields(request))["when"])


@app.post("/api/schedules/{sid}")
async def save_schedule(request: Request, sid: str):
    s = _load(Schedule, sid)
    f = await _fields(request)
    del f["channel"]   # 채널은 바꾸지 않는다
    base = (await request.form()).get("topics_base", "").splitlines()   # 화면을 열 때의 주제 목록
    with q.lock:
        used = set(base) - set(s.data["topics"])   # 그 뒤 회차가 쓴 주제는 다시 넣지 않는다(같은 영상 두 번)
        f["topics"] = [t for t in f["topics"] if t.strip() not in used]
        try:
            s.change(**f)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    return RedirectResponse("/schedules", status_code=303)


@app.post("/api/schedules/{sid}/toggle")
def toggle_schedule(sid: str):
    s = _load(Schedule, sid)
    with q.lock:
        on = not s.data["enabled"]
        try:
            s.change(enabled=on)
        except ValueError as e:   # 주제 목록이 빈 채로 켜기
            raise HTTPException(400, str(e)) from None
    return {"ok": True, "enabled": on, "msg": "켰어요. 다음 시각부터 돌아요" if on else "껐어요"}


@app.post("/api/schedules/{sid}/run")
def run_schedule(sid: str):
    """[지금 실행]: 정해진 시각을 기다리지 않고 한 회차를 시작한다(꺼진 스케줄도). 다음 예정 시각은 그대로."""
    s = _load(Schedule, sid)
    if s.data["source"] == "trend" and not trends.ready():
        raise HTTPException(400, "YouTube Data API 키가 없어 추천 주제를 찾을 수 없어요. "
                                 ".env에 YOUTUBE_API_KEY를 넣어 주세요.")
    run = schedule.fire(s, q, q.notify, datetime.now().astimezone())
    msg = {"started": f"시작했어요: {run['topic']}" if run["topic"] else "추천 주제를 찾기 시작했어요"}
    return {"ok": run["result"] == "started", "result": run["result"], "msg": msg.get(run["result"], run["note"])}


@app.post("/api/schedules/{sid}/delete")
def delete_schedule(sid: str):
    """스케줄만 지운다. 이미 만든 작업·올린 영상은 남는다(진행 중인 작업은 자동 업로드·알림 없이 끝난다)."""
    s = _load(Schedule, sid)
    with q.lock:   # 회차 기록과 겹치지 않게
        s.delete()
    return {"ok": True}


@app.post("/api/notify/test")
def notify_test():
    sent = registry.notify("[테스트] shorts-printer 알림이에요. 스케줄 결과가 이렇게 와요.")
    if not sent:
        hints = " 또는 ".join(n.hint for n in registry.NOTIFIERS.values())
        raise HTTPException(400, f"알림 설정이 없어요. {hints}. 넣은 뒤 서버를 다시 켜세요.")
    ok = [label for label, err in sent if not err]
    bad = " · ".join(f"{label}: {err}" for label, err in sent if err)
    if not ok:
        raise HTTPException(502, bad)
    return {"ok": True, "msg": f"{'·'.join(ok)}로 보냈어요" + (f" ({bad})" if bad else "")}

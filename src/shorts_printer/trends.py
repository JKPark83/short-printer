"""주제 찾기: 지금 인기 있는 한국 쇼츠를 모아(YouTube Data API) 영상을 뜯어보고(yt-dlp·ffmpeg·Claude 비전) 만들 만한 주제를 고른다.
단계는 수집 → 분석 → 선정. 작업(Job)과 같은 규칙으로 끝난 단계는 건너뛰어 다시 시도할 수 있다."""
import base64
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import ClassVar, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from . import config, ffmpeg
from .jobs import Job, Record, atomic_write_json, read_json
from .pipeline import run_steps
from .script import add_usage, ask

STEPS = ("collect", "analyze", "pick")
LABELS = {"collect": "수집", "analyze": "분석", "pick": "선정"}
PERIODS = {"1d": "24시간", "3d": "3일", "7d": "7일"}
DEFAULT_PERIOD = "3d"
TOP_N = 8          # 분석할 쇼츠 수
MIN_OK = 3         # 선정에 필요한 최소 쇼츠 수(수집·분석 모두)
MAX_SEC = 180      # 쇼츠 최대 길이
MAX_FRAMES = 8
# 장면 전환 기준. 0.3이면 뉴스·자막 틀이 화면 절반 넘게 고정된 쇼츠에서 컷을 못 잡는다(실측 0.16~0.30)
SCENE = 0.15
CRITERIA = {
    "trend": ("화제성", "지금 조회수가 빨리 오르는 흐름인가(참고 쇼츠의 시간당 조회수 순위로 계산)"),
    "fit": ("제작 적합도", "스톡 영상·TTS·자막만으로 만들 수 있나"),
    "fresh": ("차별화", "이미 만든 주제·흔한 영상과 겹치지 않고 새 각도가 있나"),
    "safe": ("안전성", "저작권·민감 주제 위험이 낮나"),
}
WEIGHTS = {"trend": 35, "fit": 35, "fresh": 15, "safe": 15}   # 합 100
OK = ("ok", "meta_only")

API = "https://www.googleapis.com/youtube/v3/"
NO_KEY = "YouTube API 키가 없어요. .env에 YOUTUBE_API_KEY를 넣고 서버를 다시 켜세요."
QUOTA = "YouTube API 오늘 할당량을 다 썼어요. 태평양 시간 자정(한국 오후 4~5시)에 다시 채워져요."
HANGUL = re.compile("[가-힣]")

Format = Literal["잡학·상식", "썰·사연", "명언·동기부여", "순위·리스트", "뉴스·이슈", "꿀팁·하우투", "유머·밈",
                 "음식", "일상·브이로그", "게임", "음악·댄스", "동물", "기타"]
Footage = Literal["스톡 영상", "직접 촬영", "AI 생성", "게임 화면", "방송·영화 클립", "애니메이션·일러스트", "텍스트·슬라이드", "혼합"]
Narration = Literal["TTS", "사람 목소리", "음악만", "현장음", "없음"]


def ready() -> bool:
    return bool(config.secret("YOUTUBE_API_KEY"))


class Trend(Record):
    FILE = "trend.json"
    WHAT = "분석"
    EXTRA: ClassVar[dict] = {"progress": None, "quota": None}

    @classmethod
    def root(cls) -> Path:
        return config.TRENDS_DIR

    @classmethod
    def create(cls, keyword: str = "", period: str = DEFAULT_PERIOD) -> "Trend":
        if period not in PERIODS:
            raise ValueError(f"기간은 {', '.join(PERIODS)} 가운데 하나예요")
        return cls._new(STEPS, keyword=keyword.strip()[:50], period=period)


# ---------- 1 수집 ----------

def iso_seconds(s: str) -> float:
    """ISO 8601 길이(PT1M5S, P0D 등)를 초로."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", s or "")
    if not m:
        return 0.0
    d, h, mi, sec = (float(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def _api(path: str, **params) -> dict:
    url = f"{API}{path}?{urlencode(params | {'key': config.secret('YOUTUBE_API_KEY')})}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "shorts-printer/0.1"}), timeout=30) as r:
            return json.load(r)
    except HTTPError as e:
        try:
            reason = json.loads(e.read())["error"]["errors"][0]["reason"]
        except Exception:  # noqa: BLE001 — 본문이 json이 아니면 상태 코드만 쓴다
            reason = str(e.code)
        if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            raise RuntimeError(QUOTA) from None
        if e.code in (400, 403):
            raise RuntimeError(f"YouTube API 키가 맞지 않거나 YouTube Data API v3가 사용 설정되지 않았어요({reason}). "
                               "Google Cloud 콘솔에서 확인하세요.") from None
        raise RuntimeError(f"YouTube API 오류({e.code}, {reason})") from None
    except URLError:
        raise RuntimeError("YouTube API에 연결하지 못했어요. 네트워크를 확인하세요.") from None


def _thumb(thumbs: dict) -> str:
    return next((thumbs[k]["url"] for k in ("maxres", "standard", "high", "medium", "default") if k in thumbs), "")


def rank(items: list[dict], now: datetime) -> list[dict]:
    """videos.list 결과를 거른다(180초 이하, 한글 제목·설명) → 시간당 조회수 내림차순."""
    out = []
    for it in items:
        sn, st = it["snippet"], it.get("statistics", {})
        dur = iso_seconds(it.get("contentDetails", {}).get("duration"))
        if not 0 < dur <= MAX_SEC or not HANGUL.search(sn["title"] + sn.get("description", "")):
            continue
        views, likes, comments = (int(st.get(k, 0)) for k in ("viewCount", "likeCount", "commentCount"))   # 숨긴 값은 0
        age = max((now - datetime.fromisoformat(sn["publishedAt"])).total_seconds() / 3600, 1)
        out.append({"id": it["id"], "title": sn["title"], "channel": sn["channelTitle"], "published_at": sn["publishedAt"],
                    "duration": dur, "views": views, "likes": likes, "comments": comments,
                    "thumb": _thumb(sn.get("thumbnails", {})), "url": f"https://www.youtube.com/shorts/{it['id']}",
                    "age_hours": round(age, 1), "views_per_hour": round(views / age, 1),
                    "engagement": round((likes + comments) / views, 4) if views else 0.0,
                    "description": sn.get("description", "")[:500]})
    return sorted(out, key=lambda v: v["views_per_hour"], reverse=True)


def is_short(video_id: str) -> bool:
    """/shorts/<id>를 열었을 때 /watch로 넘어가면 일반 영상. 확인이 안 되면 통과시킨다."""
    try:
        req = Request(f"https://www.youtube.com/shorts/{video_id}", method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as r:
            return "/watch" not in r.geturl()
    except Exception:  # noqa: BLE001
        return True


def step_collect(t: Trend) -> str:
    if not ready():
        raise RuntimeError(NO_KEY)
    d, now = t.data, datetime.now(timezone.utc)
    q = {"part": "snippet", "type": "video", "videoDuration": "short", "regionCode": "KR", "relevanceLanguage": "ko",
         "order": "viewCount", "maxResults": 50,
         "publishedAfter": (now - timedelta(days=int(d["period"][:-1]))).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if d["keyword"]:
        q["q"] = d["keyword"]
    ids = [it["id"]["videoId"] for it in _api("search", **q).get("items", [])]
    t.update(quota=(d.get("quota") or 0) + 100)
    items = []
    if ids:
        items = _api("videos", part="snippet,contentDetails,statistics", id=",".join(ids)).get("items", [])
        t.update(quota=t.data["quota"] + 1)
    cands = rank(items, now)
    t.log(f"검색 {len(ids)}개 → 3분 이하 한국어 {len(cands)}개")
    top = []
    for v in cands:
        if is_short(v["id"]):
            top.append(v | {"rank": len(top) + 1})
        else:
            t.log(f"일반 영상이라 뺌: {v['title'][:30]}")
        if len(top) == TOP_N:
            break
    if len(top) < MIN_OK:   # 적으면 분석 단계가 매번 실패하고, 수집은 다시 시도해도 건너뛴다
        raise RuntimeError(f"조건에 맞는 한국어 쇼츠가 {len(top)}개뿐이에요({MIN_OK}개 이상 필요). 기간을 늘리거나 키워드를 바꿔 보세요.")
    atomic_write_json(t.dir / "videos.json", top)
    for v in top:
        t.log(f"#{v['rank']} {v['title'][:40]} · 조회수 {v['views']:,} · 시간당 {v['views_per_hour']:,.0f}")
    return f"YouTube {len(top)}개"


# ---------- 2 분석 ----------

class VideoAnalysis(BaseModel):
    topic: str = Field(description="이 쇼츠가 다루는 주제 한 줄")
    format: Format
    hook: str = Field(description="첫 1~3초에 시선을 잡는 방법(화면·말·자막). 한 문장")
    footage_type: Footage
    footage_desc: str = Field(description="화면에 무엇이 어떻게 나오는지 한두 문장")
    narration: Narration
    text_overlay: str = Field(description="화면 자막·텍스트를 쓰는 방식. 없으면 '없음'")
    why_popular: str = Field(description="지금 조회수가 잘 나오는 이유 추정 한두 문장")
    replicable: int = Field(description="무료 스톡 영상+한국어 TTS+번인 자막만으로 비슷하게 만들 수 있는 정도. 1(불가)~5(쉬움)")
    replicable_reason: str = Field(description="replicable 점수 이유 한 문장")


SYSTEM_VIDEO = """너는 유튜브 쇼츠 기획자다. 지금 한국에서 조회수가 빠르게 오르는 쇼츠 하나를 받아, 따라 만들 수 있을지 판단하려고 뜯어본다.
받는 것: 컷마다 뽑은 프레임(또는 썸네일 한 장), 제목·설명, 자막 일부, 조회 통계, 컷 정보.
- 보이는 것과 자막에 근거해서 쓴다. 근거가 없으면 짐작이라고 밝힌다.
- 우리 제작 방식은 영어 검색어로 찾은 무료 스톡 영상(Pexels·Pixabay) + 한국어 TTS + 번인 자막, 30~45초다. replicable은 이 방식 기준이다.
- 모든 답은 짧은 한국어로."""


def vtt_text(vtt: str) -> str:
    """자동 자막(vtt)에서 글자만. 자동 자막은 같은 줄이 겹쳐 나와서 바로 앞 줄과 같으면 뺀다."""
    lines: list[str] = []
    for ln in vtt.splitlines():
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if not ln or "-->" in ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or ln.isdigit():
            continue
        if not lines or lines[-1] != ln:
            lines.append(ln)
    return " ".join(lines)


class _Quiet:
    """yt-dlp가 터미널에 찍는 경고·오류를 막는다(오류는 예외로 받는다)."""
    def debug(self, msg): pass
    info = warning = error = debug


def download(video_id: str, out: Path) -> tuple[Path, str]:
    """720p 이하 영상(소리 없어도 됨)과 한국어 자막 글자. 막히면(봇 확인 등) yt-dlp 예외가 난다."""
    import yt_dlp   # 무거워서 쓸 때만 불러온다

    url = f"https://www.youtube.com/shorts/{video_id}"
    opts = {"format": "bv*/b", "format_sort": ["res:720", "vcodec:h264", "ext:mp4"], "outtmpl": str(out / "%(id)s.%(ext)s"),
            "quiet": True, "no_warnings": True, "noprogress": True, "logger": _Quiet(), "noplaylist": True,
            "socket_timeout": 30, "retries": 2}
    subs = {"writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["ko"], "subtitlesformat": "vtt"}
    try:
        with yt_dlp.YoutubeDL(opts | subs) as y:
            info = y.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        if "subtitles" not in str(e):
            raise
        with yt_dlp.YoutubeDL(opts) as y:   # 자막만 막혔으면 영상만 받는다
            info = y.extract_info(url, download=True)
    sub = next(out.glob("*.vtt"), None)
    return Path(info["requested_downloads"][0]["filepath"]), vtt_text(sub.read_text(encoding="utf-8")) if sub else ""


def scene_cuts(video: Path) -> list[float]:
    """ffmpeg 장면 전환(scene>SCENE) 시각."""
    r = subprocess.run([config.FFMPEG, "-hide_banner", "-nostats", "-i", str(video), "-an",
                        "-vf", f"select='gt(scene,{SCENE})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 장면 분석 실패({r.returncode}): {r.stderr[-300:]}")
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def to_shots(cuts: list[float], dur: float) -> list[dict]:
    bounds = [0.0, *sorted(c for c in cuts if 0.2 < c < dur - 0.2), dur]
    return [{"start": round(a, 2), "end": round(b, 2)} for a, b in zip(bounds, bounds[1:])]


def frame_times(shots: list[dict], dur: float) -> list[float]:
    """컷마다 가운데 시점. 많으면 고르게 MAX_FRAMES장, 컷이 4개 미만이면 고르게 4장."""
    mids = [(s["start"] + s["end"]) / 2 for s in shots]
    if len(mids) > MAX_FRAMES:
        mids = [mids[round(i * (len(mids) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    elif len(mids) < 4:
        mids = [(i + 0.5) * dur / 4 for i in range(4)]
    return [round(t, 2) for t in mids]


def media(trend_dir: Path, v: dict) -> dict:
    """받기 → 장면 전환 → 프레임 저장 → 영상 지우기. 결과는 analyses.json 필드."""
    with tempfile.TemporaryDirectory() as tmp:
        video, transcript = download(v["id"], Path(tmp))
        shots = to_shots(scene_cuts(video), v["duration"])
        frames = []
        for i, t in enumerate(frame_times(shots, v["duration"])):
            rel = f"frames/{v['id']}_{i}.jpg"
            ffmpeg.run(["-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", trend_dir / rel])
            frames.append({"file": rel, "t": t})
    return {"shots": shots, "shot_count": len(shots), "avg_shot_sec": round(v["duration"] / len(shots), 2),
            "frames": frames, "has_transcript": bool(transcript), "transcript": transcript[:1500]}


def _image(trend_dir: Path, rel: str) -> dict:
    data = base64.standard_b64encode((trend_dir / rel).read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def analyze_video(trend_dir: Path, v: dict) -> tuple[dict, dict | None]:
    """영상 하나. (분석 결과, Claude 사용량). 다운로드가 막히면 썸네일·정보로만(meta_only)."""
    a = {"status": "ok", "error": None, "shots": [], "shot_count": None, "avg_shot_sec": None,
         "frames": [], "has_transcript": False, "claude": None}
    try:
        a |= media(trend_dir, v)
    except Exception as e:  # noqa: BLE001 — 봇 확인·지역 제한·ffmpeg 오류 모두 썸네일로 넘어간다
        a |= {"status": "meta_only", "error": f"영상을 못 받아 썸네일로만 봤어요: {str(e).removeprefix('ERROR: ')[:200]}"}
    if a["frames"]:
        images = [_image(trend_dir, f["file"]) for f in a["frames"]]
        cut = f"컷 {a['shot_count']}개, 평균 {a['avg_shot_sec']}초. 프레임 시각(초): {', '.join(str(f['t']) for f in a['frames'])}"
    else:
        images = [{"type": "image", "source": {"type": "url", "url": v["thumb"]}}] if v["thumb"] else []
        cut = "영상을 못 받아 썸네일 한 장뿐이다. 컷 정보 없음."
    text = (f"제목: {v['title']}\n채널: {v['channel']}\n설명: {v.get('description', '')}\n"
            f"길이 {v['duration']:.0f}초 · 조회수 {v['views']:,} · 게시 {v['age_hours']:.0f}시간 전 · "
            f"시간당 조회수 {v['views_per_hour']:,.0f} · 좋아요+댓글 비율 {v['engagement']:.2%}\n{cut}\n"
            f"자막: {a.pop('transcript', '') or '(없음)'}")
    try:
        out, usage = ask(SYSTEM_VIDEO, [*images, {"type": "text", "text": text}], VideoAnalysis,
                         "Claude가 이 영상은 분석하지 않았어요.", "영상 분석")
    except Exception as e:  # noqa: BLE001 — 영상 하나 실패는 다른 영상 분석을 막지 않는다
        return a | {"status": "failed", "error": str(e)[:300]}, None
    a["claude"] = out.model_dump() | {"replicable": min(5, max(1, out.replicable))}
    return a, usage


def step_analyze(t: Trend) -> str:
    videos, path = read_json(t.dir / "videos.json"), t.dir / "analyses.json"
    found = read_json(path, {})
    todo = [v for v in videos if found.get(v["id"], {}).get("status") not in OK]   # 끝난 영상은 다시 하지 않는다
    (t.dir / "frames").mkdir(exist_ok=True)
    n = len(videos) - len(todo)
    t.update(progress={"done": n, "total": len(videos)})
    # ponytail: 동시에 3개. Claude 요청 한도에 걸리면 줄인다. trend.json은 이 스레드에서만 쓴다
    pool = ThreadPoolExecutor(3)
    try:
        futures = {pool.submit(analyze_video, t.dir, v): v for v in todo}
        for f in as_completed(futures):
            v, (a, usage) = futures[f], f.result()
            found[v["id"]] = a
            atomic_write_json(path, found)
            n += 1
            t.update(progress={"done": n, "total": len(videos)}, usage=add_usage(t.data["usage"], usage))
            what = {"ok": f"컷 {a['shot_count']}개", "meta_only": "썸네일만", "failed": "실패"}[a["status"]]
            t.log(f"#{v['rank']} {v['title'][:30]} → {what}" + (f" ({a['error']})" if a["error"] else ""))
    finally:
        # Ctrl+C·오류 때 아직 시작 안 한 영상은 취소한다(with 블록은 다 돌 때까지 기다리고 결과는 버린다)
        pool.shutdown(wait=False, cancel_futures=True)
    good = [found[v["id"]]["status"] for v in videos if found.get(v["id"], {}).get("status") in OK]
    meta = good.count("meta_only")
    if meta:
        note = f"영상 {meta}개는 다운로드가 막혀 썸네일과 정보로만 분석했어요"
        t.update(notices=[x for x in t.data["notices"] if "썸네일과 정보로만" not in x] + [note])
    if len(good) < MIN_OK:
        raise RuntimeError(f"분석에 성공한 영상이 {len(good)}개뿐이에요({MIN_OK}개 이상 필요). 다시 시도하면 실패한 영상만 다시 봐요.")
    return f"영상 {len(good) - meta}개 · 썸네일만 {meta}개"


# ---------- 3 선정 ----------

class ClaudeScores(BaseModel):
    fit: int = Field(description="제작 적합도 1~5: " + CRITERIA["fit"][1])
    fresh: int = Field(description="차별화 1~5: " + CRITERIA["fresh"][1])
    safe: int = Field(description="안전성 1~5: " + CRITERIA["safe"][1])


class PickOut(BaseModel):
    topic: str = Field(description="작업 주제로 그대로 쓸 한 줄. 80자 이내")
    angle: str = Field(description="훅과 전개 방향. 대본 작가에게 넘길 참고. 200자 이내")
    format: Format
    why_now: str = Field(description="지금 이 주제를 만들 이유. 참고 쇼츠 근거로 한두 문장")
    scores: ClaudeScores
    refs: list[str] = Field(description="근거가 된 쇼츠 video_id 1~3개")
    search_terms: list[str] = Field(description="Pexels·Pixabay에서 찾을 영어 검색어 3~5개")


class Excluded(BaseModel):
    video_id: str
    reason: str = Field(description="따라 하지 않는 이유 한 문장")


class PicksOut(BaseModel):
    summary: str = Field(description="지금 인기 쇼츠 흐름 2~3문장")
    picks: list[PickOut] = Field(description="추천 주제 3~5개")
    excluded: list[Excluded] = Field(description="참고하지 않을 쇼츠와 이유(우리 방식으로 못 만들거나 위험한 것)")


SYSTEM_PICK = """너는 한국어 유튜브 쇼츠 채널의 기획자다. 지금 조회수가 빨리 오르는 쇼츠 분석 결과를 보고, 우리가 바로 만들 주제 3~5개를 고른다.

우리 제작 방식(이것만 된다):
- Claude가 쓴 한국어 대본을 TTS가 읽고, 번인 자막이 뜬다. 30~45초.
- 배경은 영어 검색어로 찾은 무료 스톡 영상(Pexels·Pixabay). 직접 촬영, 실존 인물·방송·게임 화면, 특정 브랜드는 못 쓴다.

규칙:
- 주제를 베끼지 말고, 인기 이유(포맷·훅·소재)를 우리 방식에 맞게 옮긴다.
- 이미 만든 작업 주제와 겹치지 않게 한다.
- 사실 확인이 어렵거나, 저작권·초상권·정치·혐오·의료 위험이 있는 주제는 피하고 excluded에 이유를 남긴다.
- 점수(fit, fresh, safe)는 아래 기준으로 1~5. 화제성은 코드가 조회수로 따로 계산하니 매기지 않는다.
- 모든 글은 짧은 한국어. search_terms만 영어."""


def percentile(videos: list[dict], vid: str) -> float:
    """수집 영상 안에서 시간당 조회수 백분위(0~1). 가장 높으면 1."""
    mine = next(v["views_per_hour"] for v in videos if v["id"] == vid)
    return sum(v["views_per_hour"] < mine for v in videos) / (len(videos) - 1) if len(videos) > 1 else 1.0


def finish_picks(out: PicksOut, videos: list[dict]) -> dict:
    """Claude 답에 화제성 점수와 총점(WEIGHTS)을 붙여 total 내림차순으로."""
    ids = {v["id"] for v in videos}
    picks = []
    for p in out.picks:
        refs = list(dict.fromkeys(r for r in p.refs if r in ids))   # 모르는 id는 버리고 순서 유지
        scores = {"trend": 1 + round(4 * max((percentile(videos, r) for r in refs), default=0)),
                  **{k: min(5, max(1, v)) for k, v in p.scores.model_dump().items()}}
        total = round(sum(WEIGHTS[k] * (scores[k] - 1) / 4 for k in WEIGHTS))
        picks.append({"topic": p.topic.strip()[:80], "angle": p.angle.strip()[:200], "format": p.format,
                      "why_now": p.why_now, "scores": scores, "total": total, "refs": refs, "search_terms": p.search_terms})
    picks.sort(key=lambda p: p["total"], reverse=True)
    return {"summary": out.summary, "picks": picks[:5],
            "excluded": [e.model_dump() for e in out.excluded if e.video_id in ids]}


def step_pick(t: Trend) -> str:
    videos, found = read_json(t.dir / "videos.json"), read_json(t.dir / "analyses.json", {})
    rows = [{k: v[k] for k in ("id", "rank", "title", "duration", "views", "views_per_hour", "engagement", "age_hours")}
            | {"shots": found[v["id"]]["shot_count"], "analysis": found[v["id"]]["claude"]}
            for v in videos if found.get(v["id"], {}).get("status") in OK]
    made = [j.data["topic"] for j in Job.all()][-30:]
    criteria = "\n".join(f"- {k} {name} (가중치 {WEIGHTS[k]}): {desc}" for k, (name, desc) in CRITERIA.items())
    text = (f"키워드: {t.data['keyword'] or '(없음, 한국 전체)'} · 기간: 최근 {PERIODS[t.data['period']]}\n\n"
            f"선정 기준:\n{criteria}\n\n이미 만든 작업 주제:\n" + ("\n".join(f"- {m}" for m in made) or "(없음)") +
            "\n\n인기 쇼츠 분석(시간당 조회수 순):\n" + json.dumps(rows, ensure_ascii=False, indent=1))
    out, usage = ask(SYSTEM_PICK, text, PicksOut, "Claude가 이번 쇼츠 목록으로는 주제를 고르지 않았어요. 키워드를 바꿔 보세요.", "추천 주제")
    t.update(usage=add_usage(t.data["usage"], usage))
    picks = finish_picks(out, videos)
    if not picks["picks"]:
        raise RuntimeError("추천 주제를 받지 못했어요. 다시 시도해 보세요.")
    atomic_write_json(t.dir / "picks.json", picks)
    for i, p in enumerate(picks["picks"], 1):
        t.log(f"추천 {i}: {p['topic']} ({p['total']}점)")
    return usage["model"]


def brief(trend_dir: Path, p: dict) -> str:
    """추천 주제 하나 → 대본 작가에게 넘길 참고. 방향에 근거 쇼츠의 분석(훅·화면·자막·인기 이유·컷 속도)을 붙인다."""
    videos = {v["id"]: v for v in read_json(trend_dir / "videos.json", [])}
    found = read_json(trend_dir / "analyses.json", {})
    lines = [f"방향: {p['angle']}", f"포맷: {p['format']}", f"지금 만들 이유: {p['why_now']}",
             f"화면 검색어 후보: {', '.join(p['search_terms'])}"]
    for r in p["refs"]:
        c = found.get(r, {}).get("claude")
        if r not in videos or not c:
            continue
        pace = f", 컷 평균 {found[r]['avg_shot_sec']}초" if found[r].get("avg_shot_sec") else ""
        lines.append(f"- 참고 쇼츠 「{videos[r]['title']}」({videos[r]['duration']:.0f}초{pace}): 훅 {c['hook']} / "
                     f"화면 {c['footage_desc']} / 자막 {c['text_overlay']} / 인기 이유 {c['why_popular']}")
    return "\n".join(lines)


RUN = {"collect": step_collect, "analyze": step_analyze, "pick": step_pick}


def run(trend: Trend) -> None:
    run_steps(trend, STEPS, LABELS, RUN, "주제 찾기 완료")


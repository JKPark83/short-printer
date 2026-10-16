"""주제 찾기: 채널 지역·언어에서 지금 인기 있는 쇼츠를 모아(YouTube Data API) 영상을 뜯어보고(yt-dlp·ffmpeg·LLM 비전)
만들 만한 주제를 고른다.
아이디어 모드(mode="idea")는 수집·분석을 건너뛰고 채널 기준(ideas.md)으로 LLM에게 바로 주제를 받는다.
단계는 수집 → 분석 → 선정. 작업(Job)과 같은 규칙으로 끝난 단계는 건너뛰어 다시 시도할 수 있다."""
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import ClassVar, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from .. import config
from ..infra import ffmpeg
from ..infra.store import Record
from ..ports.llm import add_usage
from . import prompts
from .channel import LANGS, Channel
from .pipeline import Job, run_steps
from .services import Services

STEPS = ("collect", "analyze", "pick")
LABELS = {"collect": "수집", "analyze": "분석", "pick": "선정"}
PERIODS = {"1d": "24시간", "3d": "3일", "7d": "7일"}
DEFAULT_PERIOD = "3d"
MODES = {"trend": "인기 쇼츠 분석", "idea": "아이디어"}
IDEA_N = 10        # 아이디어 모드 추천 수
TOP_N = 8          # 분석할 쇼츠 수
MIN_OK = 3         # 선정에 필요한 최소 쇼츠 수(수집·분석 모두)
MAX_SEC = 180      # 쇼츠 최대 길이
MAX_FRAMES = 8
# 장면 전환 기준. 0.3이면 뉴스·자막 틀이 화면 절반 넘게 고정된 쇼츠에서 컷을 못 잡는다(실측 0.16~0.30)
SCENE = 0.15
CRITERIA = {
    "trend": ("화제성", "지금 조회수가 빨리 오르는 흐름인가(참고 쇼츠의 시간당 조회수 순위로 계산)"),
    "fit": ("제작 적합도", "우리 제작 방식으로 만들 수 있나"),
    "fresh": ("차별화", "이미 만든 주제·흔한 영상과 겹치지 않고 새 각도가 있나"),
    "safe": ("안전성", "저작권·민감 주제 위험이 낮나"),
}
OK = ("ok", "meta_only")

API = "https://www.googleapis.com/youtube/v3/"
NO_KEY = "YouTube API 키가 없어요. .env에 YOUTUBE_API_KEY를 넣고 서버를 다시 켜세요."
QUOTA = "YouTube API 오늘 할당량을 다 썼어요. 태평양 시간 자정(한국 오후 4~5시)에 다시 채워져요."
# 언어마다 제목·설명에 있어야 할 글자. 여기 없는 언어는 글자로 거르지 않는다(relevanceLanguage만)
SCRIPTS = {"ko": re.compile("[가-힣]"), "ja": re.compile("[\u3040-\u30ff\u4e00-\u9fff]")}

Format = Literal["잡학·상식", "썰·사연", "명언·동기부여", "순위·리스트", "뉴스·이슈", "꿀팁·하우투", "유머·밈",
                 "음식", "일상·브이로그", "게임", "음악·댄스", "동물", "기타"]
Footage = Literal["스톡 영상", "직접 촬영", "AI 생성", "게임 화면", "방송·영화 클립", "애니메이션·일러스트", "텍스트·슬라이드", "혼합"]
Narration = Literal["TTS", "사람 목소리", "음악만", "현장음", "없음"]


def ready() -> bool:
    return bool(config.secret("YOUTUBE_API_KEY"))


class Trend(Record):
    KIND = "trend"
    WHAT = "분석"
    EXTRA: ClassVar[dict] = {"progress": None, "quota": None}

    @classmethod
    def root(cls) -> Path:
        return config.TRENDS_DIR

    @classmethod
    def create(cls, channel: str, keyword: str = "", period: str = DEFAULT_PERIOD, mode: str = "trend") -> "Trend":
        if period not in PERIODS:
            raise ValueError(f"기간은 {', '.join(PERIODS)} 가운데 하나예요")
        if mode not in MODES:
            raise ValueError(f"방식은 {', '.join(MODES)} 가운데 하나예요")
        return cls._new(STEPS, channel=channel, keyword=keyword.strip()[:50], period=period, mode=mode)

    @property
    def idea(self) -> bool:
        return self.data.get("mode", "trend") == "idea"   # 예전 기록에는 mode가 없다

    def again(self) -> "Trend":
        """같은 채널·키워드로 아이디어를 다시 뽑는 새 기록. 앞서 나온 주제(이어진 기록 포함, 최근 50개)는 피하게 넘긴다."""
        shown = self.data.get("avoid", []) + [p["topic"] for p in (self.doc("picks.json") or {}).get("picks", [])]
        t = Trend.create(self.data["channel"], self.data["keyword"], mode="idea")
        t.update(avoid=shown[-50:])
        return t


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


def rank(items: list[dict], now: datetime, language: str) -> list[dict]:
    """videos.list 결과를 거른다(180초 이하, 제목·설명에 그 언어 글자) → 시간당 조회수 내림차순."""
    out, script = [], SCRIPTS.get(language)
    for it in items:
        sn, st = it["snippet"], it.get("statistics", {})
        dur = iso_seconds(it.get("contentDetails", {}).get("duration"))
        if not 0 < dur <= MAX_SEC or script and not script.search(sn["title"] + sn.get("description", "")):
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


class KeywordsOut(BaseModel):
    keywords: list[str] = Field(description="YouTube 검색어 3~6개. 채널 언어로, 각각 1~3낱말")


def search_words(t: Trend, sv: Services) -> str:
    """검색어. 넣은 키워드 → 채널 keywords → LLM이 웹에서 지금 이 분야 화제를 찾아 정한 낱말.
    검색어 없이 찾으면 지역 전체 인기 쇼츠(드라마·아이돌·축구)가 모여 채널과 상관없는 주제가 나온다."""
    if kw := t.data["keyword"] or " | ".join(sv.channel.trends.keywords):   # | 는 YouTube 검색의 OR
        return kw
    ch = sv.channel
    system = prompts.render("trend_keywords", lang=ch.lang_name, concept=ch.concept, channel_rules=ch.text("trends.md"))
    out, usage = sv.llm.ask(system, f"오늘: {datetime.now():%Y-%m-%d}\n지역: {ch.trends.region}", KeywordsOut,
                            what="검색어", web=True, refusal=f"{sv.llm.label}가 검색어를 정하지 않았어요. 키워드를 넣어 보세요.")
    t.update(usage=add_usage(t.data["usage"], usage))
    words = [w.strip() for w in out.keywords if w.strip()][:6]
    if not words:
        raise RuntimeError("검색어를 받지 못했어요. 키워드를 넣어 보세요.")
    t.log(f"채널 분야 검색어: {', '.join(words)}")
    return " | ".join(words)


def step_collect(t: Trend, sv: Services) -> str:
    if t.idea:
        return "건너뜀"
    if not ready():
        raise RuntimeError(NO_KEY)
    d, now, ch = t.data, datetime.now(UTC), sv.channel
    lang = LANGS.get(ch.trend_language, ch.trend_language)
    q = {"part": "snippet", "type": "video", "videoDuration": "short", "regionCode": ch.trends.region,
         "relevanceLanguage": ch.trend_language,
         "order": "viewCount", "maxResults": 50,
         "publishedAfter": (now - timedelta(days=int(d["period"][:-1]))).strftime("%Y-%m-%dT%H:%M:%SZ")}
    q["q"] = search_words(t, sv)
    t.update(search=q["q"])
    ids = [it["id"]["videoId"] for it in _api("search", **q).get("items", [])]
    t.update(quota=(d.get("quota") or 0) + 100)
    items = []
    if ids:
        items = _api("videos", part="snippet,contentDetails,statistics", id=",".join(ids)).get("items", [])
        t.update(quota=t.data["quota"] + 1)
    cands = rank(items, now, ch.trend_language)
    t.log(f"검색 {len(ids)}개 → 3분 이하 {lang} {len(cands)}개")
    top = []
    for v in cands:
        if is_short(v["id"]):
            top.append(v | {"rank": len(top) + 1})
        else:
            t.log(f"일반 영상이라 뺌: {v['title'][:30]}")
        if len(top) == TOP_N:
            break
    if len(top) < MIN_OK:   # 적으면 분석 단계가 매번 실패하고, 수집은 다시 시도해도 건너뛴다
        raise RuntimeError(f"조건에 맞는 {lang} 쇼츠가 {len(top)}개뿐이에요({MIN_OK}개 이상 필요). "
                           "기간을 늘리거나 키워드를 바꿔 보세요.")
    t.put("videos.json", top)
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
    replicable: int = Field(description="우리 제작 방식(지시문)으로 비슷하게 만들 수 있는 정도. 1(불가)~5(쉬움)")
    replicable_reason: str = Field(description="replicable 점수 이유 한 문장")


def system_video(ch: Channel) -> str:
    return prompts.render("trend_video", region=ch.trends.region,
                          lang=LANGS.get(ch.trend_language, ch.trend_language), production=ch.trends.production)


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


def download(video_id: str, out: Path, lang: str) -> tuple[Path, str]:
    """720p 이하 영상(소리 없어도 됨)과 lang 자막 글자. 막히면(봇 확인 등) yt-dlp 예외가 난다."""
    import yt_dlp  # 무거워서 쓸 때만 불러온다

    url = f"https://www.youtube.com/shorts/{video_id}"
    opts = {"format": "bv*/b", "format_sort": ["res:720", "vcodec:h264", "ext:mp4"], "outtmpl": str(out / "%(id)s.%(ext)s"),
            "quiet": True, "no_warnings": True, "noprogress": True, "logger": _Quiet(), "noplaylist": True,
            "socket_timeout": 30, "retries": 2}
    subs = {"writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": [lang], "subtitlesformat": "vtt"}
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
    return [{"start": round(a, 2), "end": round(b, 2)} for a, b in pairwise(bounds)]


def frame_times(shots: list[dict], dur: float) -> list[float]:
    """컷마다 가운데 시점. 많으면 고르게 MAX_FRAMES장, 컷이 4개 미만이면 고르게 4장."""
    mids = [(s["start"] + s["end"]) / 2 for s in shots]
    if len(mids) > MAX_FRAMES:
        mids = [mids[round(i * (len(mids) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    elif len(mids) < 4:
        mids = [(i + 0.5) * dur / 4 for i in range(4)]
    return [round(t, 2) for t in mids]


def media(trend_dir: Path, v: dict, lang: str) -> dict:
    """받기 → 장면 전환 → 프레임 저장 → 영상 지우기. 결과는 analyses.json 필드."""
    with tempfile.TemporaryDirectory() as tmp:
        video, transcript = download(v["id"], Path(tmp), lang)
        shots = to_shots(scene_cuts(video), v["duration"])
        frames = []
        for i, t in enumerate(frame_times(shots, v["duration"])):
            rel = f"frames/{v['id']}_{i}.jpg"
            ffmpeg.run(["-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", trend_dir / rel])
            frames.append({"file": rel, "t": t})
    return {"shots": shots, "shot_count": len(shots), "avg_shot_sec": round(v["duration"] / len(shots), 2),
            "frames": frames, "has_transcript": bool(transcript), "transcript": transcript[:1500]}


def analyze_video(trend_dir: Path, v: dict, sv: Services) -> tuple[dict, dict | None]:
    """영상 하나. (분석 결과, LLM 사용량). 다운로드가 막히면 썸네일·정보로만(meta_only).
    분석 결과는 예전 기록과 맞추려고 "claude" 키에 둔다."""
    a = {"status": "ok", "error": None, "shots": [], "shot_count": None, "avg_shot_sec": None,
         "frames": [], "has_transcript": False, "claude": None}
    try:
        a |= media(trend_dir, v, sv.channel.trend_language)
    except Exception as e:  # noqa: BLE001 — 봇 확인·지역 제한·ffmpeg 오류 모두 썸네일로 넘어간다
        a |= {"status": "meta_only", "error": f"영상을 못 받아 썸네일로만 봤어요: {str(e).removeprefix('ERROR: ')[:200]}"}
    if a["frames"]:
        images: list[bytes | str] = [(trend_dir / f["file"]).read_bytes() for f in a["frames"]]
        cut = f"컷 {a['shot_count']}개, 평균 {a['avg_shot_sec']}초. 프레임 시각(초): {', '.join(str(f['t']) for f in a['frames'])}"
    else:
        images = [v["thumb"]] if v["thumb"] else []
        cut = "영상을 못 받아 썸네일 한 장뿐이다. 컷 정보 없음."
    text = (f"제목: {v['title']}\n채널: {v['channel']}\n설명: {v.get('description', '')}\n"
            f"길이 {v['duration']:.0f}초 · 조회수 {v['views']:,} · 게시 {v['age_hours']:.0f}시간 전 · "
            f"시간당 조회수 {v['views_per_hour']:,.0f} · 좋아요+댓글 비율 {v['engagement']:.2%}\n{cut}\n"
            f"자막: {a.pop('transcript', '') or '(없음)'}")
    try:
        out, usage = sv.llm.ask(system_video(sv.channel), text, VideoAnalysis, images=images,
                                refusal=f"{sv.llm.label}가 이 영상은 분석하지 않았어요.", what="영상 분석")
    except Exception as e:  # noqa: BLE001 — 영상 하나 실패는 다른 영상 분석을 막지 않는다
        return a | {"status": "failed", "error": str(e)[:300]}, None
    a["claude"] = out.model_dump() | {"replicable": min(5, max(1, out.replicable))}
    return a, usage


def step_analyze(t: Trend, sv: Services) -> str:
    if t.idea:
        return "건너뜀"
    videos, found = t.doc("videos.json"), t.doc("analyses.json", {})
    todo = [v for v in videos if found.get(v["id"], {}).get("status") not in OK]   # 끝난 영상은 다시 하지 않는다
    (t.dir / "frames").mkdir(exist_ok=True)
    n = len(videos) - len(todo)
    t.update(progress={"done": n, "total": len(videos)})
    # ponytail: 동시에 3개. LLM 요청 한도에 걸리면 줄인다. 상태·analyses.json은 이 스레드에서만 쓴다
    pool = ThreadPoolExecutor(3)
    try:
        futures = {pool.submit(analyze_video, t.dir, v, sv): v for v in todo}
        for f in as_completed(futures):
            v, (a, usage) = futures[f], f.result()
            found[v["id"]] = a
            t.put("analyses.json", found)
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

class Scores(BaseModel):
    fit: int = Field(description="제작 적합도 1~5: " + CRITERIA["fit"][1])
    fresh: int = Field(description="차별화 1~5: " + CRITERIA["fresh"][1])
    safe: int = Field(description="안전성 1~5: " + CRITERIA["safe"][1])


class PickOut(BaseModel):
    topic: str = Field(description="작업 주제로 그대로 쓸 한 줄. 80자 이내")
    angle: str = Field(description="훅과 전개 방향. 대본 작가에게 넘길 참고. 200자 이내")
    format: Format
    why_now: str = Field(description="지금 이 주제를 만들 이유. 참고 쇼츠 근거로 한두 문장")
    scores: Scores
    refs: list[str] = Field(description="근거가 된 쇼츠 video_id 1~3개")
    search_terms: list[str] = Field(description="화면에 보일 장면을 나타내는 영어 키워드 3~5개")


class Excluded(BaseModel):
    video_id: str
    reason: str = Field(description="따라 하지 않는 이유 한 문장")


class PicksOut(BaseModel):
    summary: str = Field(description="지금 인기 쇼츠 흐름 2~3문장")
    picks: list[PickOut] = Field(description="추천 주제 3~5개")
    excluded: list[Excluded] = Field(description="참고하지 않을 쇼츠와 이유(우리 방식으로 못 만들거나 위험한 것)")


def system_pick(ch: Channel) -> str:
    """prompts/trend_pick.md에 채널 분야·제작 방식·언어·채널 규칙(trends.md)을 채운다."""
    return prompts.render("trend_pick", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                          channel_rules=ch.text("trends.md"), duration=ch.script.duration, scenes=ch.script.scenes)


def percentile(videos: list[dict], vid: str) -> float:
    """수집 영상 안에서 시간당 조회수 백분위(0~1). 가장 높으면 1."""
    mine = next(v["views_per_hour"] for v in videos if v["id"] == vid)
    return sum(v["views_per_hour"] < mine for v in videos) / (len(videos) - 1) if len(videos) > 1 else 1.0


def finish_picks(out: PicksOut, videos: list[dict], weights: dict[str, int]) -> dict:
    """LLM 답에 화제성 점수와 총점(채널 weights)을 붙여 total 내림차순으로."""
    ids = {v["id"] for v in videos}
    picks = []
    for p in out.picks:
        refs = list(dict.fromkeys(r for r in p.refs if r in ids))   # 모르는 id는 버리고 순서 유지
        scores = {"trend": 1 + round(4 * max((percentile(videos, r) for r in refs), default=0)),
                  **{k: min(5, max(1, v)) for k, v in p.scores.model_dump().items()}}
        total = round(sum(weights[k] * (scores[k] - 1) / 4 for k in weights))
        picks.append({"topic": p.topic.strip()[:80], "angle": p.angle.strip()[:200], "format": p.format,
                      "why_now": p.why_now, "scores": scores, "total": total, "refs": refs, "search_terms": p.search_terms})
    picks.sort(key=lambda p: p["total"], reverse=True)
    return {"summary": out.summary, "picks": picks[:5],
            "excluded": [e.model_dump() for e in out.excluded if e.video_id in ids]}


class IdeaOut(BaseModel):
    topic: str = Field(description="작업 주제로 그대로 쓸 한 줄. 80자 이내")
    angle: str = Field(description="훅과 전개 방향. 대본 작가에게 넘길 참고. 200자 이내")
    content: str = Field(description="핵심 답 한 문장 + 확인할 주장 3~5개(끝에 출처 기관). 500자 이내")
    format: Format
    why_now: str = Field(description="왜 지금, 왜 사람들이 궁금해하는지 한두 문장")
    scores: Scores
    search_terms: list[str] = Field(description="화면에 보일 장면을 나타내는 영어 키워드 3~5개")


class IdeasOut(BaseModel):
    summary: str = Field(description="이번 목록의 방향 한두 문장")
    picks: list[IdeaOut] = Field(description=f"추천 주제 {IDEA_N}개")


def system_idea(ch: Channel) -> str:
    """prompts/trend_idea.md에 채널 값과 주제 기준(ideas.md, 없는 채널은 빈 값)을 채운다."""
    rules = ch.text("ideas.md") if (ch.dir / "ideas.md").exists() else ""
    return prompts.render("trend_idea", lang=ch.lang_name, concept=ch.concept, production=ch.trends.production,
                          channel_rules=ch.text("trends.md"), idea_rules=rules, n=IDEA_N,
                          duration=ch.script.duration, scenes=ch.script.scenes)


def idea_weights(weights: dict[str, int]) -> dict[str, int]:
    """아이디어 모드 가중치: 화제성을 뺀 셋. 가중치를 화제성에만 몰아 둔 채널은 셋을 똑같이 본다."""
    w = {k: weights[k] for k in ("fit", "fresh", "safe")}
    return w if sum(w.values()) else dict.fromkeys(w, 1)


def finish_ideas(out: IdeasOut, weights: dict[str, int]) -> dict:
    """아이디어 모드: 조회수 근거가 없어 화제성을 빼고 나머지 가중치로 100점 만점을 다시 나눈다. 상위 IDEA_N개."""
    w = idea_weights(weights)
    picks = []
    for p in out.picks:
        scores = {k: min(5, max(1, v)) for k, v in p.scores.model_dump().items()}
        total = round(100 * sum(w[k] * (scores[k] - 1) / 4 for k in w) / sum(w.values()))
        picks.append({"topic": p.topic.strip()[:80], "angle": p.angle.strip()[:200], "content": p.content.strip()[:500],
                      "format": p.format, "why_now": p.why_now, "scores": scores, "total": total, "refs": [],
                      "search_terms": p.search_terms})
    picks.sort(key=lambda p: p["total"], reverse=True)
    return {"summary": out.summary, "picks": picks[:IDEA_N], "excluded": []}


def _made(cid: str) -> str:
    """이 채널에서 이미 만든 작업 주제 최근 30개(겹치지 않게 지시문에 넣는다)."""
    made = [d["topic"] for d in (j.data for j in Job.all()) if d.get("channel") == cid][-30:]
    return "\n".join(f"- {m}" for m in made) or "(없음)"


def _criteria(w: dict[str, int], keys) -> str:
    return "\n".join(f"- {k} {CRITERIA[k][0]} (가중치 {w[k]}): {CRITERIA[k][1]}" for k in keys)


def pick_ideas(t: Trend, sv: Services) -> str:
    ch = sv.channel
    keys = ("fit", "fresh", "safe")
    text = (f"오늘: {datetime.now():%Y-%m-%d}\n좁힐 주제: {t.data['keyword'] or '없음'}\n\n"
            f"점수 기준:\n{_criteria(ch.trends.weights, keys)}\n\n이미 만든 작업 주제:\n{_made(ch.id)}")
    if avoid := t.data.get("avoid"):
        text += "\n\n앞서 추천했지만 고르지 않은 주제:\n" + "\n".join(f"- {a}" for a in avoid)
    out, usage = sv.llm.ask(system_idea(ch), text, IdeasOut, what="추천 주제", web=True,
                            refusal=f"{sv.llm.label}가 이번에는 주제를 고르지 않았어요. 좁힐 주제를 바꿔 보세요.")
    t.update(usage=add_usage(t.data["usage"], usage))
    picks = finish_ideas(out, ch.trends.weights)
    if not picks["picks"]:
        raise RuntimeError("추천 주제를 받지 못했어요. 다시 시도해 보세요.")
    t.put("picks.json", picks)
    for i, p in enumerate(picks["picks"], 1):
        t.log(f"추천 {i}: {p['topic']} ({p['total']}점)")
    return usage["model"]


def step_pick(t: Trend, sv: Services) -> str:
    if t.idea:
        return pick_ideas(t, sv)
    ch, w = sv.channel, sv.channel.trends.weights
    videos, found = t.doc("videos.json"), t.doc("analyses.json", {})
    rows = [{k: v[k] for k in ("id", "rank", "title", "duration", "views", "views_per_hour", "engagement", "age_hours")}
            | {"shots": found[v["id"]]["shot_count"], "analysis": found[v["id"]]["claude"]}
            for v in videos if found.get(v["id"], {}).get("status") in OK]
    keyword = t.data.get("search") or t.data["keyword"] or f"(없음, {ch.trends.region} 전체)"   # 예전 기록은 search가 없다
    text = (f"오늘: {datetime.now():%Y-%m-%d}\n검색어: {keyword} · 기간: 최근 {PERIODS[t.data['period']]}\n\n"
            f"선정 기준:\n{_criteria(w, CRITERIA)}\n\n이미 만든 작업 주제:\n{_made(ch.id)}"
            "\n\n인기 쇼츠 분석(시간당 조회수 순):\n" + json.dumps(rows, ensure_ascii=False, indent=1))
    out, usage = sv.llm.ask(system_pick(ch), text, PicksOut, what="추천 주제", web=True,
                            refusal=f"{sv.llm.label}가 이번 쇼츠 목록으로는 주제를 고르지 않았어요. "
                                    "키워드를 바꿔 보세요.")
    t.update(usage=add_usage(t.data["usage"], usage))
    picks = finish_picks(out, videos, w)
    if not picks["picks"]:
        raise RuntimeError("추천 주제를 받지 못했어요. 다시 시도해 보세요.")
    t.put("picks.json", picks)
    for i, p in enumerate(picks["picks"], 1):
        t.log(f"추천 {i}: {p['topic']} ({p['total']}점)")
    return usage["model"]


def brief(trend: Trend, p: dict) -> str:
    """추천 주제 하나 → 대본 작가에게 넘길 참고. 방향에 근거 쇼츠의 분석(훅·화면·자막·인기 이유·컷 속도)을 붙인다."""
    videos = {v["id"]: v for v in trend.doc("videos.json", [])}
    found = trend.doc("analyses.json", {})
    lines = [f"방향: {p['angle']}", f"포맷: {p['format']}", f"지금 만들 이유: {p['why_now']}",
             f"화면 검색어 후보: {', '.join(p['search_terms'])}"]
    if p.get("content"):   # 아이디어 모드: 핵심 답·사실
        lines.insert(1, f"내용: {p['content']}")
    for r in p["refs"]:
        c = found.get(r, {}).get("claude")
        if r not in videos or not c:
            continue
        pace = f", 컷 평균 {found[r]['avg_shot_sec']}초" if found[r].get("avg_shot_sec") else ""
        lines.append(f"- 참고 쇼츠 「{videos[r]['title']}」({videos[r]['duration']:.0f}초{pace}): 훅 {c['hook']} / "
                     f"화면 {c['footage_desc']} / 자막 {c['text_overlay']} / 인기 이유 {c['why_popular']}")
    return "\n".join(lines)


RUN = {"collect": step_collect, "analyze": step_analyze, "pick": step_pick}


def run(trend: Trend, sv: Services) -> None:
    run_steps(trend, STEPS, LABELS, {k: lambda t, f=f: f(t, sv) for k, f in RUN.items()}, "주제 찾기 완료")


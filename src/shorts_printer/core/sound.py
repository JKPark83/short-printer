"""롱폼 지도 영상의 효과음·음악 자리 잡기(history-map-video 스킬 references/sound.md).

자리 계산만 한다: 효과음 길이·onset·peak는 표(assets/sfx/sfx.json)에서, 곡 길이·앞뒤 무음은 track()으로 잰다.
돌려주는 소리 줄은 film dict의 sounds 모양 [id, assets 안 파일, 시작, 길이, 음량, 파일 안 시작, 페이드 인, 페이드 아웃].
"""
import json
import math
from pathlib import Path

from .. import config
from ..infra import ffmpeg

ASSETS = config.ROOT / "assets"   # sfx.json의 file과 music.json이 이 아래. 작업 폴더 assets/로 같은 경로에 복사한다

# 역할: (sfx 이름, 맞출 곳 onset|peak, 미리 당기는 초, 음량, 맞출 곳 뒤 남길 초 | None=끝까지, 페이드 인, 페이드 아웃)
CUES = {
    "move": ("whoosh-cinematic", "peak", 0, 0.35, 1.0, 0, 1.0),   # 카메라가 닿을 때 휙 소리가 가장 크다
    "turn": ("riser", "peak", 0, 0.3, 0.3, 0.5, 0.2),             # 라이저가 전환 첫 프레임에 터진다
    "hit": ("distant-boom", "onset", 0, 0.45, None, 0, 0),
    "final": ("impact-bass-2", "onset", 0, 0.35, None, 0, 0),
    "photo": ("shutter", "onset", 0.03, 0.6, 0.6, 0, 0),
}
WHOOSH_GAP = 2.0   # 휙 소리끼리 이보다 가까우면 뒤엣것을 뺀다
MUSIC_LUFS = -28.0   # 곡마다 이 크기로 맞춘다(내레이션 10 LU 아래). 곡 음량이 10 dB 넘게 달라 고정 배율은 안 된다
JOIN_FADE = 2.0    # 곡을 이어 붙인 자리의 페이드


def tables() -> tuple[dict, dict]:
    """(효과음 표 sfx.json, 분위기별 곡 표 music.json)."""
    return tuple(json.loads((ASSETS / p).read_text(encoding="utf-8")) for p in ("sfx/sfx.json", "music.json"))


def _big(a: list, b: list) -> bool:
    """크게 움직였는지: 배율이 2배 넘게 바뀌거나, 중심 거리(도, 경도는 cos(위도)를 곱한다) × 배율이 1을 넘는다."""
    # ponytail: 배율은 지도 타일 px 기준이라 타일 확대 단계가 다른 영상에선 1.0이 달라진다. 그때는 화면 px 거리로 잰다
    (_, _, x0, y0, s0), (_, _, x1, y1, s1) = a, b
    dist = math.hypot((x1 - x0) * math.cos(math.radians((y0 + y1) / 2)), y1 - y0)
    return max(s0, s1) / min(s0, s1) >= 2 or dist * max(s0, s1) >= 1.0


def _cue(sid: str, role: str, t: float, lib: dict) -> list:
    name, align, lead, vol, tail, fi, fo = CUES[role]
    e = lib[name]
    start, length, offset = t - lead - e[align], e["duration"], 0.0
    if tail is not None:
        length = min(length, e[align] + tail)
    if start < 0:   # 영상 맨 앞이면 파일 앞을 잘라 맞출 곳을 지킨다
        offset, length, start = -start, length + start, 0.0
    return [sid, e["file"], round(start, 2), round(length, 2), vol, round(offset, 2), fi, fo]


def pick(tracks: list[dict], used: list[str | None]) -> dict:
    """안 쓴 곡 먼저, 다 썼으면 가장 오래전에 쓴 곡. used는 채널 작업들이 쓴 곡 제목(오래된 것부터)."""
    last = {t: i for i, t in enumerate(used)}
    return min(tracks, key=lambda t: last.get(t["title"], -1))


def track(path: Path, credit: str) -> dict:
    """place()에 넘길 곡 정보 {file, duration, credit, head, tail, vol}. head·tail은 곡 앞뒤 무음 초(이어 붙일 때
    건너뛴다), vol은 곡을 MUSIC_LUFS로 맞추는 배율.
    file은 path 이름이다: 부르는 쪽이 곡을 작업 폴더 assets/<이름>으로 복사한다."""
    dur = ffmpeg.duration(path)
    quiet = ffmpeg.silences(path)
    head = next((b for a, b in quiet if a <= 0.1), 0.0)
    tail = next((dur - a for a, b in quiet if b >= dur - 0.5 and a > head), 0.0)
    vol = min(1.0, 10 ** ((MUSIC_LUFS - ffmpeg.loudness(path)["lufs"]) / 20))
    return {"file": path.name, "duration": dur, "credit": credit, "head": round(head, 2), "tail": round(tail, 2),
            "vol": round(vol, 3)}


def _music(music: dict, spans: list[tuple[float, float]], total: float) -> list[list]:
    """곡 하나로 구간들을 채운다. 곡보다 긴 구간은 같은 길이로 나눠 이어 붙인다(같은 11번 줄이라 겹치지 않게).
    영상 끝에 닿는 조각은 곡의 진짜 끝이 영상 끝에 오게, 영상 맨 앞 조각은 곡 처음부터,
    그 사이 조각은 곡 앞 무음(head) 뒤에서 시작해 이은 자리에 빈 틈이 생기지 않게 한다."""
    # ponytail: 11번 줄 하나라 이은 자리는 크로스페이드가 아닌 페이드 아웃→인. film.py가 음악 줄을 둘 쓰면 겹쳐 잇는다
    dur, head = music["duration"], music.get("head", 0)
    usable = dur - head - music.get("tail", 0)
    out = []
    for a, b in spans:
        n = math.ceil((b - a) / usable - 1e-9)
        cuts = [round(a + (b - a) * k / n, 2) for k in range(n + 1)]
        for k in range(n):
            d = round(cuts[k + 1] - cuts[k], 2)
            last, to_end = k == n - 1, b >= total
            if last and to_end:
                offset = round(dur - d, 2)
            else:
                offset = 0 if cuts[k] == 0 else head
            fi = (1.5 if a == 0 else 2.5) if k == 0 else JOIN_FADE
            fo = (3 if to_end else 6) if last else JOIN_FADE
            out.append([f"music-{len(out) + 1}", music["file"], cuts[k], d, music["vol"], offset, fi, fo])
    return out


def place(*, total: float, end_start: float, cam: list, turns: list[float], hits: list[float], final: float | None,
          photos: list[float], music: dict, lib: dict, silence: tuple[float, float] | None = None) -> list[list]:
    """음악과 효과음을 film dict의 sounds 줄로 놓는다. 끝 화면(end_start 뒤)에는 효과음을 두지 않는다.

    cam: [[시작, 옮기는 초, lng, lat, scale]], music: track()이 돌려준 것, lib: sfx.json,
    silence: 음악을 끄는 정적 (시작, 끝) — 앞 구간은 페이드 아웃으로 끝나고 뒤 구간이 영상 끝까지 간다.
    """
    spans = [(0, silence[0]), (silence[1], total)] if silence else [(0, total)]
    fx, last = [], -math.inf
    for prev, key in zip(cam, cam[1:], strict=False):
        arrive = key[0] + key[1]
        if key[1] > 0 and _big(prev, key) and arrive - last >= WHOOSH_GAP:
            fx.append(_cue(f"fx-move-{len(fx) + 1}", "move", arrive, lib))
            last = arrive
    for role, times in [("turn", turns), ("hit", hits), ("final", [final] if final is not None else []),
                        ("photo", photos)]:
        fx += [_cue(f"fx-{role}-{i}", role, t, lib) for i, t in enumerate(times, 1)]
    fx = sorted((c for c in fx if c[2] < end_start), key=lambda c: c[2])
    return _music(music, spans, total) + fx


SOURCE_LICENSE = {"Freesound": "(CC0)"}


def credits(lib: dict, used_ids: set[str], music: dict) -> list[str]:
    """끝 화면 크레딧 줄: 음악 한 줄(CC BY 표기는 라이선스 의무) + 쓴 효과음 출처 한 줄.

    used_ids는 sfx.json 이름이다. sounds에서는 {Path(f).stem for _, f, *_ in sounds}로 얻는다
    (음악 파일 이름은 표에 없어 빠진다).
    """
    by: dict[str, set[str]] = {}
    for name in used_ids & lib.keys():
        src, _, who = lib[name]["credit"].partition(" ")
        by.setdefault(src, set()).update([who] if who else [])
    parts = [" ".join(filter(None, [src, ", ".join(sorted(who)), SOURCE_LICENSE.get(src)]))
             for src, who in sorted(by.items())]
    return [f"음악 {music['credit']}"] + ([f"효과음 {' · '.join(parts)}"] if parts else [])

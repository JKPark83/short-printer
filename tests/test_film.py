"""core.film: 스킬 gen.py가 한국전쟁 film.py로 만든 HTML(fixtures/film_korean_war_out)과 같은지 본다.

fixture JSON은 스킬 film.py를 한 번 옮긴 것(ffprobe 값은 그때 풀어 넣었다). 클립이 없으면 다른 곳이 없어야 한다.
"""
import json
from pathlib import Path

import pytest

from shorts_printer.core import film

FIX = Path(__file__).parent / "fixtures"
PAGES = ["index.html", "compositions/map.html", "compositions/story.html", "compositions/end.html"]


def _film() -> dict:
    return json.loads((FIX / "film_korean_war.json").read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return " ".join(s.split())


def test_matches_gen_py(tmp_path):
    film.build(_film(), tmp_path)
    for page in PAGES:
        want = (FIX / "film_korean_war_out" / page).read_text(encoding="utf-8")
        assert _norm((tmp_path / page).read_text(encoding="utf-8")) == _norm(want), page
    assert not (tmp_path / "compositions/clips.html").exists()


def test_clips_layer(tmp_path):
    f = _film()
    f["clips"] = [{"id": "s07", "src": "assets/clips/s07.mp4", "start": 66.1, "duration": 8.0}]
    (tmp_path / "compositions").mkdir()
    film.build(f, tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    # 쌓는 순서: 지도 0 → 클립 1 → 이야기 2 → 끝 3
    hosts = [ln for ln in index.splitlines() if "data-composition-src" in ln]
    for ln, (name, ti) in zip(hosts, [("map", 0), ("clips", 1), ("story", 2), ("end", 3)], strict=True):
        assert f'<div id="{name}" ' in ln and f'data-track-index="{ti}" ' in ln and f'z-index:{ti + 1}"' in ln
    clips = (tmp_path / "compositions/clips.html").read_text(encoding="utf-8")
    assert 'data-composition-id="clips"' in clips
    # 시각은 무음 video에만, 페이드는 시각 없는 감싼 div에
    assert ('<div id="cl-s07" class="cl"><video id="v-s07" class="clip" src="assets/clips/s07.mp4" '
            'data-start="66.1" data-duration="8.0" data-track-index="1" muted playsinline></video></div>') in clips
    assert 'tl.fromTo("#cl-s07", {opacity: 0}, {opacity: 1, duration: 0.35}, 66.1);' in clips
    assert 'tl.to("#cl-s07", {opacity: 0, duration: 0.35}, 73.73);' in clips
    assert 'window.__timelines["clips"] = tl;' in clips

    f["clips"] = []   # 클립을 다 빼고 다시 만들면 남은 clips.html도 지운다
    film.build(f, tmp_path)
    assert not (tmp_path / "compositions/clips.html").exists()


def test_sound_needs_length(tmp_path):
    f = _film()
    f["sounds"][0][3] = None   # 길이를 재지 않은 소리는 아무것도 쓰기 전에 멈춘다
    with pytest.raises(RuntimeError, match="길이"):
        film.build(f, tmp_path)
    assert not (tmp_path / "index.html").exists()

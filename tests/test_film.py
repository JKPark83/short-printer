"""core.film: 스킬 gen.py가 한국전쟁 film.py로 만든 HTML(fixtures/film_korean_war_out)과 같은지 본다.

fixture JSON은 스킬 film.py를 한 번 옮긴 것(ffprobe 값은 그때 풀어 넣었다). 클립이 없으면 다른 곳이 없어야 한다.
gen.py와 일부러 다른 곳(map.html): 점령지를 양끝에서 옆으로 닫는다,
닫는 길이 땅을 지나면 끝점을 민 점을 더한다(_escape), 지도 위 출처 글이 없다(출처는 설명란에만, 끝 화면은 제목만),
불꽃 고리·카메라 흔들림·전선 빛·지명 튀어나옴, 날짜 막대·사진 떨어짐·켄 번스·숫자 막대(story.html)를 더했다.
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


def test_close_layer_sits_over_detail_with_soft_edges(tmp_path):
    f = _film()
    f["geo"] = f["geo"] | {"close": [4011.5, 4400.25, 4300.0, 4560.0]}
    film.build(f, tmp_path)
    html = (tmp_path / "compositions/map.html").read_text(encoding="utf-8")
    assert html.index('id="map-detail"') < html.index('<img id="map-close" src="assets/map/close.jpg"')
    assert "#map-close { left: 4011.5px; top: 4400.25px; width: 288.5px; height: 159.75px;" in html
    assert "mask-composite: intersect;" in html


def test_unit_badges(tmp_path):
    f = _film()
    for i, kind in [(0, "tank"), (4, "nope"), (7, "soldier"), (13, "ship")]:   # 모르는 그림은 그리지 않는다
        f["arrows"][i] = [*f["arrows"][i], kind]
    film.build(f, tmp_path)
    m = (tmp_path / "compositions/map.html").read_text(encoding="utf-8")

    def badges(aid):
        return sum(f'id="un-{aid}-{k}"' in m for k in range(3))
    # 화면에서 긴 화살표는 셋이 줄지어 가고, 짧으면 뒤 배지를 뺀다(겹치지 않게)
    assert [badges(a) for a in ("s6a", "s1a", "s11a", "s3a", "s1b")] == [3, 2, 1, 0, 0]
    assert m.index('id="un-s6a-2"') < m.index('id="un-s6a-0"')   # 맨 앞 배지가 위에 그려진다


def test_sound_needs_length(tmp_path):
    f = _film()
    f["sounds"][0][3] = None   # 길이를 재지 않은 소리는 아무것도 쓰기 전에 멈춘다
    with pytest.raises(RuntimeError, match="길이"):
        film.build(f, tmp_path)
    assert not (tmp_path / "index.html").exists()


def test_escape_pushes_closing_point_past_land():
    # 땅 상자 x 0~100, y 0~100. 남쪽 점령지(side=north: 북쪽이 점령)는 양끝에서 옆으로 닫는다
    land = "M0,0L100,0L100,100L0,100Z"
    line = [[120, 50], [150, 50]]
    # 왼쪽 끝(120,50)에서 왼쪽으로 가면 땅을 지난다 → 땅 아래(y 103)까지 민다. 오른쪽은 비어 그대로
    assert film._escape(line, "north", land) == [[120, 103.0], *line, [150, 50]]
    assert film._escape(line, "south", land) == [[120, -3.0], *line, [150, 50]]
    assert film._escape(line, "north", "") == [[120, 50], *line, [150, 50]]


def test_captions_layer(tmp_path):
    f = _film()
    f["captions"] = [[1.4, 3.2, "서울 새벽"], [3.2, 4.0, "A&amp;B"]]
    film.build(f, tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    hosts = [ln for ln in index.splitlines() if "data-composition-src" in ln]
    # 자막은 이야기 위·끝 화면 아래, captions 줄 하나
    for ln, (name, ti) in zip(hosts, [("map", 0), ("story", 1), ("captions", 2), ("end", 3)], strict=True):
        assert f'<div id="{name}" ' in ln and f'data-track-index="{ti}" ' in ln
    assert 'data-track-kind="captions"' in hosts[2] and 'data-track-kind="graphics"' in hosts[1]
    caps = (tmp_path / "compositions/captions.html").read_text(encoding="utf-8")
    assert ('<div id="cap-0" class="clip cap" data-start="1.4" data-duration="1.8" data-track-index="1">'
            '<span>서울 새벽</span></div>') in caps
    assert 'data-start="3.2" data-duration="0.8"' in caps and "<span>A&amp;B</span>" in caps
    assert 'window.__timelines["captions"] = tl;' in caps

    f["captions"] = []
    film.build(f, tmp_path)
    assert not (tmp_path / "compositions/captions.html").exists()

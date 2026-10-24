"""롱폼 지도 영상 엔진: film dict → index.html + compositions/{map,story,end,clips}.html (HyperFrames).

history-map-video 스킬 gen.py를 옮긴 것. 같은 값이면 같은 HTML이 나온다(tests/test_film.py).
파일을 읽지도 ffprobe를 부르지도 않는다: 크기·길이는 부르는 쪽이 재서 넣는다.
시각은 모두 절대 초, 좌표는 [lng, lat]. 튜플 대신 리스트,
칸 순서는 스킬 references/map.md "film.py field reference"와 같다.
글은 HTML로 그대로 들어간다(이스케이프하지 않는다).

film 키:
- title, subtitle, lang("ko"), locale("ko-KR"), size([1920, 1080], 빼면 이 값), ink·accent·bg(hex)
- total: 영상 끝, end_start: 끝 화면 시작
- tiles: tiles.json {z, x0, y0, width, height} — 지도 이미지의 타일 원점·px 크기
- geo: geo.json {crop: [x0, y0, x1, y1] detail.jpg 자리, land: 점령지 자를 땅 path, border: 이웃 국경 path}
- 지도 그림은 assets/map/wide.jpg(전체)·detail.jpg(crop 자리)로 둔다
- states: {이름: [[lng, lat], ...]} 상태마다 점 개수·순서 같게, side: 점령지 쪽 north|south|west|east
- front: [[시작, 옮기는 초, 상태]], cam: [[시작, 옮기는 초, lng, lat, scale]] — 키끼리 겹치지 않는다
- labels: [[id, 글, lng, lat, 시작, 끝, 왼쪽에 쓰기, 점 찍기]]
- arrows: [[id, [[lng, lat] 시작, 굽이, 끝], 시작, 그리는 초, 끝, 색, 볼 때 카메라 scale]]
- flashes: [[시각, lng, lat]], night: [어둡기, 시작, 초] | None
- reflines: [[id, [[lng, lat], ...], 시작, 그리는 초, 화면 px 굵기, 점선 "16 11" | None]]
- ghosts: [[상태, ...], 시작, 간격, 숨기는 시각] | None, map_tweens: [GSAP 줄], map_credit: 글
- date_pos: [x, y], dates: [[시작, 해, 큰 글, 작은 줄 | ""]], date_end
- photos: [[id, assets/photos 안 파일, 설명, 시작, 끝, left, top, 너비, 기울기, 높이/너비 | None,
  원본 w, 원본 h]] — 원본 px 크기는 높이/너비가 None일 때 높이를 정하는 데만 쓴다
- panels: [[id, 머리글, 큰 글, [항목], 시작, 큰 글 시각, 끝, left, top]]
- notes: [[id, [[줄, 시각], ...], 시작, 끝, left, top, 글자 px]]
- counters: [[id, 이름, 값, 단위, 시작, 끝, left, top]], credits: [줄]
- sounds: [[id, assets 안 파일, 시작, 길이, 음량, 파일 안 시작, 페이드 인, 페이드 아웃]]
  길이(초)는 꼭 적는다. id가 music으로 시작하면 11번 줄, 나머지는 12번부터 빈 줄을 차례로 받는다
- voices: [{id, src, start, duration}] 10번 줄
- clips: [{id, src, start, duration}] Flow 16:9 무음 mp4. 지도 위·이야기 아래에 화면 가득, 0.35초 페이드
- voices·clips의 src는 프로젝트 기준 경로(assets/...)
"""
import json
import math
from pathlib import Path

from ..infra.store import atomic_write_text

FONT_FACE = "\n".join(
    f"    @font-face {{ font-family: 'Pretendard'; font-weight: {w}; "
    f"src: url('assets/fonts/Pretendard-{n}.woff2') format('woff2'); }}"
    for w, n in [(500, "Medium"), (700, "Bold"), (800, "ExtraBold"), (900, "Black")])
CLIP_FADE = 0.35


def build(film: dict, project: Path) -> None:
    """film 값으로 project/index.html과 compositions/*.html을 쓴다. 클립이 없으면 clips.html을 지운다."""
    # 다 만든 뒤에 쓴다: 중간에 틀린 값이 있으면 지난 결과가 그대로 남는다
    pages = {"map": _map(film), "story": _story(film), "end": _end(film)}
    if film["clips"]:
        pages["clips"] = _clips(film)
    index = _index(film)
    comp = project / "compositions"
    comp.mkdir(parents=True, exist_ok=True)
    if not film["clips"]:
        (comp / "clips.html").unlink(missing_ok=True)
    for name, html in pages.items():
        atomic_write_text(comp / f"{name}.html", html)
    atomic_write_text(project / "index.html", index)


def _size(film: dict) -> tuple[int, int]:
    return tuple(film.get("size", (1920, 1080)))


def _proj(tiles: dict):
    """lng, lat → 지도 이미지 px. 타일과 같은 웹 메르카토르."""
    n = 2 ** tiles["z"]

    def px(lng, lat):
        y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        return round(((lng + 180) / 360 * n - tiles["x0"]) * 256, 1), round((y - tiles["y0"]) * 256, 1)
    return px


def _r(v):
    return round(v, 2)


def _pts_d(pts):
    return "M" + " L".join(f"{x},{y}" for x, y in pts)


def _arrow_svg(a, px):
    aid, ll, start, draw, end, color, scale = a
    (x1, y1), (cx, cy), (x2, y2) = [px(*p) for p in ll]
    ang = math.atan2(y2 - cy, x2 - cx)
    h = 30 / scale  # 머리는 이 화살표를 볼 때 카메라 scale에서 화면 30px
    tip = (x2 + math.cos(ang) * h * 0.6, y2 + math.sin(ang) * h * 0.6)
    left = (tip[0] - math.cos(ang - 0.45) * h, tip[1] - math.sin(ang - 0.45) * h)
    right = (tip[0] - math.cos(ang + 0.45) * h, tip[1] - math.sin(ang + 0.45) * h)
    head = f"M{tip[0]:.1f},{tip[1]:.1f} L{left[0]:.1f},{left[1]:.1f} L{right[0]:.1f},{right[1]:.1f} Z"
    d = f"M{x1},{y1} Q{cx},{cy} {x2},{y2}"
    # 어두운 테두리가 강조색 점령지 위에서도 화살표를 읽히게 한다.
    # 머리 채움은 style=에: CSS `path {fill:none}`이 fill 속성을 이긴다
    return (f'<path id="arh-{aid}" class="arrow halo" d="{d}" pathLength="1" data-sw="13" />\n'
            f'      <path id="ar-{aid}" class="arrow" d="{d}" pathLength="1" stroke="{color}" data-sw="7" />\n'
            f'      <path id="ah-{aid}" class="arrowhead" d="{head}" style="fill:{color}" />')


def _appear(sel, at, dy=12, dur=0.35):
    return (f'tl.fromTo("{sel}", {{opacity: 0, y: {dy}}}, '
            f'{{opacity: 1, y: 0, duration: {dur}, ease: "power3.out"}}, {_r(at)});')


def _fade(sel, end):
    # 이 요소의 첫 tween은 위 fromTo라 두 번째는 .to가 맞다
    return f'tl.to("{sel}", {{opacity: 0, duration: 0.3}}, {_r(end - 0.32)});'


def _map(F: dict) -> str:
    px = _proj(F["tiles"])
    W, H = _size(F)
    WORLD = (F["tiles"]["width"], F["tiles"]["height"])
    GEO = F["geo"]
    labels = []
    for lid, name, lng, lat, a, b, left, pin in F["labels"]:
        x, y = px(lng, lat)
        labels.append(f'    <div id="lab-{lid}" class="clip lab{" l" if left else ""}" style="left:{x}px;top:{y}px" '
                      f'data-start="{_r(a)}" data-duration="{_r(b - a)}" data-track-index="3">'
                      f'<div class="lab-in">{"<i></i>" if pin else ""}<span>{name}</span></div></div>')
    flashes = "\n".join(f'      <circle id="fl-{i}" class="flash" cx="{x}" cy="{y}" r="0" />'
                        for i, (x, y) in enumerate(px(lng, lat) for _, lng, lat in F["flashes"]))
    ghost_keys = F["ghosts"][0] if F["ghosts"] else []
    ghosts = "\n".join(f'        <path id="gh-{k}" class="ghost" d="{_pts_d([px(*p) for p in F["states"][k]])}" '
                       f'data-sw="2.5" />' for k in ghost_keys)
    reflines, clips = [], []
    for lid, ll, _, _, sw, dash in F["reflines"]:
        pts = [px(*p) for p in ll]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        clips.append(f'<clipPath id="map-{lid}-clip"><rect id="map-{lid}-rect" x="{_r(min(xs) - 20)}" '
                     f'y="{_r(min(ys) - 400)}" width="0" height="{_r(max(ys) - min(ys) + 800)}" /></clipPath>')
        dash_attr = f' data-dash="{dash}"' if dash else ""
        reflines.append(f'      <path id="map-{lid}" class="refline" d="{_pts_d(pts)}" '
                        f'clip-path="url(#map-{lid}-clip)" data-sw="{sw}"{dash_attr} />')
    crop = GEO["crop"]
    cx, cy, cw, ch = crop[0], crop[1], crop[2] - crop[0], crop[3] - crop[1]

    tweens = []
    for lid, _, _, _, a, b, _, _ in F["labels"]:
        tweens += [_appear(f"#lab-{lid} .lab-in", a), _fade(f"#lab-{lid} .lab-in", b)]
    for aid, _, start, draw, end, _, _ in F["arrows"]:
        tweens.append(f'tl.fromTo(["#arh-{aid}", "#ar-{aid}"], {{strokeDashoffset: 1, opacity: 1}}, '
                      f'{{strokeDashoffset: 0, duration: {draw}, ease: "power2.out"}}, {_r(start)});')
        tweens.append(f'tl.fromTo("#ah-{aid}", {{opacity: 0}}, {{opacity: 1, duration: 0.12}}, '
                      f'{_r(start + draw - 0.1)});')
        tweens.append(f'tl.to(["#arh-{aid}", "#ar-{aid}", "#ah-{aid}"], {{opacity: 0, duration: 0.4}}, '
                      f'{_r(end - 0.4)});')
    if F["night"]:
        dark, at, dur = F["night"]
        tweens.append(f'tl.fromTo("#map-night", {{opacity: {dark}}}, {{opacity: 0, duration: {dur}, '
                      f'ease: "power1.inOut"}}, {_r(at)});')
    for lid, ll, a, dur, _, _ in F["reflines"]:
        xs = [px(*p)[0] for p in ll]
        tweens.append(f'tl.fromTo("#map-{lid}-rect", {{attr: {{width: 0}}}}, '
                      f'{{attr: {{width: {_r(max(xs) - min(xs) + 40)}}}, duration: {dur}, ease: "power2.inOut"}}, '
                      f'{_r(a)});')
    if F["ghosts"]:
        keys, at, stagger, hide = F["ghosts"]
        for i, k in enumerate(keys):
            tweens.append(f'tl.fromTo("#gh-{k}", {{opacity: 0}}, {{opacity: 0.85, duration: 0.25}}, '
                          f'{_r(at + i * stagger)});')
        tweens.append(f'tl.to("#map-ghosts", {{opacity: 0, duration: 0.8}}, {_r(hide)});')
    tweens += F["map_tweens"]

    cam = [[_r(t), d, *px(lng, lat), s] for t, d, lng, lat, s in F["cam"]]
    front = [[_r(t), d, k] for t, d, k in F["front"]]
    lines = {k: [list(px(*p)) for p in v] for k, v in F["states"].items()}
    # 점령지 = 전선을 강조색 쪽으로 닫은 다각형, 그 뒤 땅 모양으로 자른다
    close = {"north": "${last[0]},-50 L${first[0]},-50",
             "south": f"${{last[0]}},{WORLD[1] + 50} L${{first[0]}},{WORLD[1] + 50}",
             "west": "-50,${last[1]} L-50,${first[1]}",
             "east": f"{WORLD[0] + 50},${{last[1]}} L{WORLD[0] + 50},${{first[1]}}"}
    return f"""<template>
  <style>
{FONT_FACE}
    #root {{ position: absolute; inset: 0; overflow: hidden; background: {F["bg"]}; font-family: 'Pretendard', sans-serif; }}
    #map-cam {{ position: absolute; left: 0; top: 0; width: {WORLD[0]}px; height: {WORLD[1]}px; transform-origin: 0 0;
      will-change: transform; --inv: 1; }}
    #map-cam img, #map-svg, #map-night {{ position: absolute; }}
    #map-wide {{ left: 0; top: 0; width: {WORLD[0]}px; height: {WORLD[1]}px; }}
    #map-detail {{ left: {cx}px; top: {cy}px; width: {cw}px; height: {ch}px; }}
    #map-night {{ left: 0; top: 0; width: {WORLD[0]}px; height: {WORLD[1]}px; background: #07090c; opacity: 0; }}
    #map-svg {{ left: 0; top: 0; overflow: visible; }}
    #map-svg path {{ fill: none; stroke-linejoin: round; stroke-linecap: round; }}
    #map-border {{ stroke: rgba(243, 239, 231, 0.5); }}
    #map-occ {{ fill: {F["accent"]} !important; stroke: none; opacity: 0.4; }}
    #map-front {{ stroke: {F["accent"]}; }}
    .refline {{ stroke: {F["ink"]}; }}
    .ghost {{ stroke: {F["accent"]}; opacity: 0; }}
    .arrow {{ stroke-dasharray: 1 1; stroke-dashoffset: 1; }}
    .halo {{ stroke: rgba(15, 12, 10, 0.55); }}
    .arrowhead {{ stroke: rgba(15, 12, 10, 0.55); stroke-width: calc(4px * var(--inv)); opacity: 0; }}
    .flash {{ fill: #F6D27A; opacity: 0; }}
    .lab {{ position: absolute; width: 0; height: 0; transform: scale(var(--inv)); transform-origin: 0 0; }}
    .lab-in {{ position: absolute; left: -7px; top: -21px; display: flex; align-items: center; gap: 10px;
      white-space: nowrap; color: {F["ink"]}; font-weight: 700; font-size: 30px; letter-spacing: -0.01em;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.75), 0 0 2px rgba(0, 0, 0, 0.8); }}
    .lab.l .lab-in {{ left: auto; right: -7px; flex-direction: row-reverse; }}
    .lab i {{ width: 14px; height: 14px; border-radius: 50%; background: {F["ink"]}; box-shadow: 0 0 0 3px rgba(20, 20, 20, 0.7);
      flex: none; }}
    #map-credit {{ position: absolute; left: 96px; bottom: 40px; padding: 6px 12px; border-radius: 4px;
      background: rgba(10, 10, 10, 0.55); color: rgba(243, 239, 231, 0.85); font-size: 18px; font-weight: 500; }}
  </style>
  <div id="root" data-composition-id="map" data-width="{W}" data-height="{H}">
  <div id="map-cam" data-layout-allow-overflow data-layout-ignore>
    <img id="map-wide" src="assets/map/wide.jpg" alt="" />
    <img id="map-detail" src="assets/map/detail.jpg" alt="" />
    <div id="map-night"></div>
    <svg id="map-svg" width="{WORLD[0]}" height="{WORLD[1]}" viewBox="0 0 {WORLD[0]} {WORLD[1]}">
      <defs>
        <clipPath id="map-land"><path d="{GEO['land']}" /></clipPath>
        {chr(10).join('        ' + c for c in clips).lstrip()}
      </defs>
      <path id="map-border" d="{GEO['border']}" data-sw="1.5" />
      <g clip-path="url(#map-land)">
        <path id="map-occ" d="" />
        <g id="map-ghosts">
{ghosts}
        </g>
        <path id="map-front" d="" data-sw="5" />
      </g>
{chr(10).join(reflines)}
{flashes}
      {chr(10).join('      ' + _arrow_svg(a, px) for a in F["arrows"]).lstrip()}
    </svg>
{chr(10).join(labels)}
  </div>
  <div id="map-credit" data-layout-ignore>{F["map_credit"]}</div>
  </div>
  <script>
    (() => {{
      const CAM = {json.dumps(cam)};
      const FLASH = {json.dumps([ft for ft, _, _ in F["flashes"]])};
      const FRONT = {json.dumps(front)};
      const LINES = {json.dumps(lines)};
      const W = {WORLD[0]}, H = {WORLD[1]}, CX = {W / 2}, CY = {H / 2};
      const camE = gsap.parseEase("power2.inOut"), frE = gsap.parseEase("power1.inOut"), flE = gsap.parseEase("power2.out");
      const cam = document.getElementById("map-cam");
      const occ = document.getElementById("map-occ"), front = document.getElementById("map-front");
      const strokes = [...cam.querySelectorAll("[data-sw]")];

      // [previous key, current key, eased progress] at time t; keys must not overlap in time
      const at = (keys, t, e) => {{
        let a = keys[0], b = keys[0], p = 1;
        for (let i = 1; i < keys.length && t >= keys[i][0]; i++) {{
          a = keys[i - 1]; b = keys[i]; p = Math.min(1, (t - b[0]) / b[1]);
        }}
        return [a, b, e(p)];
      }};
      const lerp = (a, b, p) => a + (b - a) * p;

      // everything on the map is a pure function of t, so any seek lands on the same frame
      function render(t) {{
        const [ca, cb, cp] = at(CAM, t, camE);
        const s = Math.exp(lerp(Math.log(ca[4]), Math.log(cb[4]), cp));
        const hw = CX / s, hh = CY / s;
        const x = Math.min(Math.max(lerp(ca[2], cb[2], cp), hw), W - hw);
        const y = Math.min(Math.max(lerp(ca[3], cb[3], cp), hh), H - hh);
        cam.style.transform = `translate(${{CX - x * s}}px, ${{CY - y * s}}px) scale(${{s}})`;
        const inv = 1 / s;
        cam.style.setProperty("--inv", inv);
        for (const el of strokes) {{
          el.style.strokeWidth = el.dataset.sw * inv;
          if (el.dataset.dash) el.style.strokeDasharray = el.dataset.dash.split(" ").map((v) => v * inv).join(" ");
        }}
        FLASH.forEach((ft, i) => {{
          const p = (t - ft) / 0.55, el = document.getElementById("fl-" + i);
          const e = flE(Math.min(1, Math.max(0, p)));
          el.setAttribute("r", 24 + 150 * e);
          el.style.opacity = p >= 0 && p < 1 ? 1 - e : 0;
        }});
        if (!FRONT.length) return;
        const [fa, fb, fp] = at(FRONT, t, frE);
        const pts = LINES[fa[2]].map((p, i) => [lerp(p[0], LINES[fb[2]][i][0], fp), lerp(p[1], LINES[fb[2]][i][1], fp)]);
        const line = "M" + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" L");
        const first = pts[0], last = pts[pts.length - 1];
        front.setAttribute("d", line);
        occ.setAttribute("d", `${{line}} L{close[F["side"]]} Z`);
      }}

      const tl = gsap.timeline({{ paused: true }});
      const clock = {{ t: 0 }};
      tl.fromTo(clock, {{ t: 0 }}, {{ t: {F["total"]}, duration: {F["total"]}, ease: "none", onUpdate: () => render(clock.t) }}, 0);
      {chr(10).join('      ' + tw for tw in tweens).lstrip()}
      render(0);
      window.__timelines["map"] = tl;
    }})();
  </script>
</template>
"""  # noqa: E501


def _story(F: dict) -> str:
    W, H = _size(F)
    els, tweens, counters = [], [], []
    dx, dy = F["date_pos"]
    dates = F["dates"]
    for i, (a, y, md, tm) in enumerate(dates):
        b = dates[i + 1][0] if i + 1 < len(dates) else F["date_end"]
        tm_html = f'<div class="tm">{tm}</div>' if tm else ""
        els.append(f'    <div id="dt-{i}" class="clip date" data-start="{_r(a)}" data-duration="{_r(b - a)}" '
                   f'data-track-index="1"><div class="y">{y}</div><div class="md">{md}</div>{tm_html}</div>')
        tweens.append(_appear(f"#dt-{i} .md", a, 22, 0.3))
        if tm:
            tweens.append(f'tl.fromTo("#dt-{i} .tm", {{opacity: 0}}, {{opacity: 1, duration: 0.3}}, {_r(a + 0.15)});')
    if dates:
        tweens.append(f'tl.to("#dt-{len(dates) - 1}", {{opacity: 0, duration: 0.4}}, {_r(F["date_end"] - 0.42)});')

    for pid, f, cap, a, b, x, y, w, rot, ratio, iw, ih in F["photos"]:
        h = round(w * (ratio or ih / iw))
        els.append(f'    <figure id="ph-{pid}" class="clip photo" '
                   f'style="left:{x}px;top:{y}px;transform:rotate({rot}deg)" '
                   f'data-start="{_r(a)}" data-duration="{_r(b - a)}" data-track-index="2">'
                   f'<div class="ph-in"><img src="assets/photos/{f}" alt="" style="width:{w}px;height:{h}px" />'
                   f'<figcaption>{cap}</figcaption></div></figure>')
        tweens.append(f'tl.fromTo("#ph-{pid} .ph-in", {{opacity: 0, scale: 1.04}}, '
                      f'{{opacity: 1, scale: 1, duration: 0.3, ease: "power2.out"}}, {_r(a)});')
        tweens.append(_fade(f"#ph-{pid} .ph-in", b))

    for pid, head, big, items, a, big_at, b, x, y in F["panels"]:
        lis = "".join(f"<li>{n}</li>" for n in items)
        els.append(f'    <div id="pn-{pid}" class="clip panel" style="left:{x}px;top:{y}px" data-start="{_r(a)}" '
                   f'data-duration="{_r(b - a)}" data-track-index="3"><div class="pn-in">'
                   f'<div class="pn-head">{head}</div><div class="pn-big">{big}</div><ol>{lis}</ol></div></div>')
        tweens.append(_appear(f"#pn-{pid} .pn-head", a, 14))
        tweens.append(_appear(f"#pn-{pid} .pn-big", big_at, 14))
        tweens.append(f'tl.fromTo("#pn-{pid} li", {{opacity: 0, x: -10}}, '
                      f'{{opacity: 1, x: 0, duration: 0.25, stagger: 0.05, ease: "power2.out"}}, {_r(big_at + 0.2)});')
        tweens.append(_fade(f"#pn-{pid} .pn-in", b))

    for nid, lines, a, b, x, y, size in F["notes"]:
        spans = "".join(f'<div class="ln">{text}</div>' for text, _ in lines)
        els.append(f'    <div id="nt-{nid}" class="clip note" style="left:{x}px;top:{y}px;font-size:{size}px" '
                   f'data-start="{_r(a)}" data-duration="{_r(b - a)}" data-track-index="3">{spans}</div>')
        for k, (_, at) in enumerate(lines):
            tweens.append(_appear(f"#nt-{nid} .ln:nth-child({k + 1})", at, 16, 0.4))
        tweens.append(_fade(f"#nt-{nid} .ln", b))

    for cid, label, value, suffix, a, b, x, y in F["counters"]:
        els.append(f'    <div id="ct-{cid}" class="clip counter" style="left:{x}px;top:{y}px" data-start="{_r(a)}" '
                   f'data-duration="{_r(b - a)}" data-track-index="3"><div class="ct-in">'
                   f'<div class="ct-l">{label}</div><div id="ct-{cid}-n" class="ct-n">0{suffix}</div></div></div>')
        tweens.append(_appear(f"#ct-{cid} .ct-in", a, 16))
        tweens.append(_fade(f"#ct-{cid} .ct-in", b))
        # 숫자를 tween 값에서 계산해 어느 프레임으로 건너뛰어도 같은 수가 보인다
        counters.append(f'{{ const o = {{ n: 0 }}, el = document.getElementById("ct-{cid}-n"); '
                        f'tl.fromTo(o, {{ n: 0 }}, {{ n: {value}, duration: 1.5, ease: "power2.out", onUpdate: () => '
                        f'(el.textContent = Math.round(o.n).toLocaleString("{F["locale"]}") + "{suffix}") }}, '
                        f'{_r(a + 0.2)}); }}')

    return f"""<template>
  <style>
{FONT_FACE}
    #root {{ position: absolute; inset: 0; font-family: 'Pretendard', sans-serif; color: {F["ink"]}; }}
    .date, .panel, .note, .counter, figcaption {{ text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7); }}
    .date {{ position: absolute; left: {dx}px; top: {dy}px; }}
    .date .y {{ font-size: 40px; font-weight: 700; letter-spacing: -0.01em; }}
    .date .md {{ font-size: 96px; font-weight: 900; letter-spacing: -0.02em; line-height: 1.02; }}
    .date .tm {{ font-size: 36px; font-weight: 700; margin-top: 6px; }}
    .photo {{ position: absolute; margin: 0; transform-origin: 50% 50%; }}
    .ph-in {{ background: #ECE6D8; padding: 14px 14px 12px; box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45); }}
    .ph-in img {{ display: block; object-fit: cover; object-position: 50% 0; }}
    figcaption {{ color: #2b2925; text-shadow: none; font-size: 28px; font-weight: 700; margin-top: 10px; }}
    .panel {{ position: absolute; width: 560px; }}
    .pn-head {{ font-size: 40px; font-weight: 800; letter-spacing: -0.01em; }}
    .pn-big {{ font-size: 120px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.05; }}
    .panel ol {{ list-style: none; padding: 0; margin: 14px 0 0; columns: 2; column-gap: 32px; }}
    .panel li {{ font-size: 30px; font-weight: 700; line-height: 1.5; }}
    .note {{ position: absolute; font-weight: 800; letter-spacing: -0.02em; line-height: 1.18; }}
    .counter {{ position: absolute; }}
    .ct-l {{ font-size: 44px; font-weight: 800; }}
    .ct-n {{ font-size: 140px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.05; font-variant-numeric: tabular-nums; }}
  </style>
  <div id="root" data-composition-id="story" data-width="{W}" data-height="{H}">
{chr(10).join(els)}
  </div>
  <script>
    (() => {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + c for c in counters).lstrip()}
      {chr(10).join('      ' + tw for tw in tweens).lstrip()}
      tl.to({{}}, {{ duration: 0.01 }}, {_r(F["total"] - 0.01)});
      window.__timelines["story"] = tl;
    }})();
  </script>
</template>
"""  # noqa: E501


def _end(F: dict) -> str:
    W, H = _size(F)
    d = _r(F["total"] - F["end_start"])
    lines = "".join(f"<li>{c}</li>" for c in F["credits"])
    return f"""<template>
  <style>
{FONT_FACE}
    #root {{ position: absolute; inset: 0; font-family: 'Pretendard', sans-serif; color: {F["ink"]}; }}
    #end-shade {{ position: absolute; inset: 0; background: #121110; opacity: 0; }}
    #end-body {{ position: absolute; left: 112px; top: 300px; }}
    #end-title {{ font-size: 96px; font-weight: 900; letter-spacing: -0.03em; }}
    #end-sub {{ font-size: 40px; font-weight: 700; margin-top: 4px; color: {F["accent"]}; }}
    #end-credits {{ list-style: none; padding: 0; margin: 64px 0 0; }}
    #end-credits li {{ font-size: 28px; font-weight: 500; line-height: 1.6; color: rgba(243, 239, 231, 0.88); }}
  </style>
  <div id="root" data-composition-id="end" data-width="{W}" data-height="{H}">
    <div id="end-shade"></div>
    <div id="end-body">
      <div id="end-title">{F["title"]}</div>
      <div id="end-sub">{F["subtitle"]}</div>
      <ul id="end-credits">{lines}</ul>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#end-shade", {{ opacity: 0 }}, {{ opacity: 0.78, duration: 0.8, ease: "power1.inOut" }}, 0);
    tl.fromTo("#end-title", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, 0.5);
    tl.fromTo("#end-sub", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 0.7);
    tl.fromTo("#end-credits li", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4, stagger: 0.08 }}, 1.1);
    tl.to({{}}, {{ duration: 0.01 }}, {d - 0.01});
    window.__timelines["end"] = tl;
  </script>
</template>
"""  # noqa: E501


def _clips(F: dict) -> str:
    """Flow 클립을 화면 가득 보인다.

    시각은 video에만 둔다(감싼 것과 둘 다 두면 안 되고, lint는 video 쪽을 바란다).
    페이드는 시각 없는 감싼 div에 준다(.clip은 tween하지 않는다).
    """
    W, H = _size(F)
    els, tweens = [], []
    for c in F["clips"]:
        cid, a, d = c["id"], c["start"], c["duration"]
        els.append(f'    <div id="cl-{cid}" class="cl"><video id="v-{cid}" class="clip" src="{c["src"]}" '
                   f'data-start="{_r(a)}" data-duration="{_r(d)}" data-track-index="1" muted playsinline>'
                   '</video></div>')
        tweens.append(f'tl.fromTo("#cl-{cid}", {{opacity: 0}}, {{opacity: 1, duration: {CLIP_FADE}}}, {_r(a)});')
        tweens.append(f'tl.to("#cl-{cid}", {{opacity: 0, duration: {CLIP_FADE}}}, {_r(a + d - CLIP_FADE - 0.02)});')
    return f"""<template>
  <style>
    #root {{ position: absolute; inset: 0; }}
    .cl {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0; }}
    .cl video {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
  </style>
  <div id="root" data-composition-id="clips" data-width="{W}" data-height="{H}">
{chr(10).join(els)}
  </div>
  <script>
    (() => {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + tw for tw in tweens).lstrip()}
      tl.to({{}}, {{ duration: 0.01 }}, {_r(F["total"] - 0.01)});
      window.__timelines["clips"] = tl;
    }})();
  </script>
</template>
"""  # noqa: E501


def _index(F: dict) -> str:
    W, H = _size(F)
    total, end_start = F["total"], F["end_start"]
    voices = "\n".join(
        f'      <audio id="{v["id"]}" class="clip" src="{v["src"]}" data-start="{v["start"]}" '
        f'data-duration="{v["duration"]}" data-track-index="10" data-volume="1"></audio>' for v in F["voices"])
    # <audio>마다 길이를 적고, 겹치는 소리는 다른 줄에 둔다(duplicate_audio_track)
    sounds, ends = [], {}
    for sid, f, a, d, vol, ms, fi, fo in F["sounds"]:
        if not d:  # gen.py는 여기서 ffprobe로 쟀다. core는 재지 않는다
            raise RuntimeError(f"소리 {sid}의 길이가 없어요")
        attrs = f'data-start="{_r(a)}" data-duration="{d}" data-volume="{vol}"'
        attrs += (f' data-media-start="{ms}"' if ms else "") + (f' data-fade-in="{fi}"' if fi else "")
        attrs += f' data-fade-out="{fo}"' if fo else ""
        track = 11 if sid.startswith("music") else next(k for k in range(12, 40) if ends.get(k, 0) <= a)
        ends[track] = a + d
        sounds.append(f'      <audio id="{sid}" class="clip" src="assets/{f}" {attrs} '
                      f'data-track-index="{track}"></audio>')
    # 쌓는 순서(z): 지도 → 클립 → 이야기 → 끝 화면. 클립이 없으면 gen.py와 같은 번호
    names = ["map", "clips", "story"] if F["clips"] else ["map", "story"]
    hosts = [(h, 0, total, i) for i, h in enumerate(names)]
    hosts.append(("end", end_start, _r(total - end_start), len(names)))
    host_html = "\n".join(
        f'      <div id="{h}" data-composition-id="{h}" data-composition-src="compositions/{h}.html" data-start="{a}" '
        f'data-duration="{d}" data-track-index="{ti}" data-track-kind="graphics" data-width="{W}" data-height="{H}" '
        f'style="z-index:{ti + 1}"></div>' for h, a, d, ti in hosts)
    return f"""<!doctype html>
<html lang="{F["lang"]}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{F["title"]} {F["subtitle"]}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: {F["bg"]}; }}
      #root {{ width: 100%; height: 100%; position: relative; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
{host_html}
{voices}
{chr(10).join(sounds)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""  # noqa: E501

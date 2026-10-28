// 롱폼 지도 영상(Satellite Briefing). 1920×1080, 데이터는 data/(film.json = 작업의 지도 계획, plates·realms·land·cine).
// 지도 계획(카메라·이름표·화살표·번쩍임·전선·날짜·숫자·사진·클립·자막)을 3D 위성 위에 그린다.
// 소리는 렌더 뒤 따로 섞어 덮는다(시각은 film.json 그대로). render(t)는 t만의 순수 함수, ?from=&to=는 한 토막만 뽑는다.
import { clamp, lerp, seg, ss, eio, eo } from '/core/lib.js';
import { Engine, makeCamera, project, ecef, R } from './engine.js';
import { C, text, measure, hair, pathLL, brackets, beginTexts, endTexts } from './overlay.js';

const W = 1920, H = 1080;
const gl = new Engine(document.getElementById('gl'));
const cv = document.getElementById('ov'), ctx = cv.getContext('2d');
const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error('image ' + src)); i.src = src; });
const json = p => fetch(p).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
const Q = new URLSearchParams(location.search);
const FROM = +(Q.get('from') || 0);

const RED = '#E5483F', BLUE = '#5AA0FF';
const colOf = c => (c === '#C9302C' ? RED : c === '#3A7BD5' ? BLUE : C.ink);   // 채널 색을 회색 위성 위에서 읽히게
const p1io = p => (p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2);
const p3o = p => 1 - (1 - clamp(p)) ** 4;
const sio = p => -(Math.cos(Math.PI * clamp(p)) - 1) / 2;
const halo = 'rgba(3,6,8,.62)';

let F, BB, CINES, RE, LAND, KM, CAM, ARR, PHOTO = {}, PIN = {}, N, X0, Y0, TW, TH, INTRO;
// 지도 계획의 세계 px(Web Mercator z9) <-> 경위도
const toPx = (lon, lat) => [((lon + 180) / 360 * N - X0) * 256, ((1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * N - Y0) * 256];
const toLL = (x, y) => [(x / 256 + X0) / N * 360 - 180, Math.atan(Math.sinh(Math.PI * (1 - 2 * (y / 256 + Y0) / N))) * 180 / Math.PI];

// film.py의 at(): 키끼리 겹치지 않는다. [앞 키, 지금 키, 진행]
function at(keys, t, e) {
  let a = keys[0], b = keys[0], p = 1;
  for (let i = 1; i < keys.length && t >= keys[i][0]; i++) { a = keys[i - 1]; b = keys[i]; p = b[1] > 0 ? Math.min(1, (t - b[0]) / b[1]) : 1; }
  return [a, b, e(p)];
}

// ------------------------------------------------------------------ 카메라: film.py와 같은 틀(scale s), 거리 d = 화면 높이가 같은 km
// 화면 높이 1080/s 세계 px × 0.30574·2^(9-z)·cos(위도) km, 세로 시야 30°면 높이 = 0.5359·d
const dOf = (lat, s) => KM * Math.cos(lat * Math.PI / 180) / s;
function planAt(t) {
  const [a, b, p] = at(CAM, t, eio);
  const s = Math.exp(lerp(Math.log(a[4]), Math.log(b[4]), p));
  const x = Math.min(Math.max(lerp(a[2], b[2], p), 960 / s), TW - 960 / s);
  const y = Math.min(Math.max(lerp(a[3], b[3], p), 540 / s), TH - 540 / s);
  const [lon, lat] = toLL(x, y);
  let d = dOf(lat, s);
  // 3D: 멀리선 22°(지구가 둥근 게 보이게), 가까이 갈수록 48°까지 눕혀서 땅을 비스듬히 보고, 50초 주기로 천천히 돈다
  const near = ss(seg(Math.log(d), Math.log(900), Math.log(160)));
  let tilt = lerp(22, 48, near), heading = lerp(5, 14, near) * Math.sin(2 * Math.PI * t / 50);
  if (t < INTRO) { const u = eio(t / INTRO); d *= Math.exp(lerp(Math.log(8), 0, u)); tilt = lerp(34, tilt, u); heading *= u; }   // 궤도에서 내려온다
  return { lat, lon, d, tilt, heading, sy: 150 * pinned(t) };   // 땅에 꽂는 사진이 있으면 꽂힐 자리를 화면 아래로 내린다
}
const pinned = t => F.photos.reduce((m, p) => PIN[p[0]] ? Math.max(m, sio(seg(t, p[3] - 1, p[3])) * (1 - sio(seg(t, p[4], p[4] + 1)))) : m, 0);
// 손으로 짠 3D 구간(data/cine.json, 선택): [시작, 옮기는 초, lat, lon, d km, tilt, heading, sy(px, 목표를 화면 아래로)]
// 앞뒤에 그 시각의 평면 카메라를 붙여서(끝은 3초 동안 돌아간다) 앞뒤와 이어진다. plate = 가까운 곳 선명한 판
const cineOf = t => CINES.find(w => t >= w.at[0] && t < w.at[1]);
function cineAt(t, w) {
  if (!w.k) {
    const c = (k, dur) => { const q = planAt(k); return [k, dur, q.lat, q.lon, q.d, q.tilt, q.heading, q.sy]; };
    w.k = [c(w.at[0], 0), ...w.keys, c(w.at[1], 3)];
    w.k[w.k.length - 1][0] = w.at[1] - 3;
  }
  const [a, b, p] = at(w.k, t, eio);
  return { lat: lerp(a[2], b[2], p), lon: lerp(a[3], b[3], p), d: Math.exp(lerp(Math.log(a[4]), Math.log(b[4]), p)),
    tilt: lerp(a[5], b[5], p), heading: lerp(a[6], b[6], p), sy: lerp(a[7] || 0, b[7] || 0, p) };
}
function camAt(t) {
  const w = cineOf(t), q = w ? cineAt(t, w) : planAt(t);
  let sx = 0, sy = q.sy || 0;
  for (const [ft] of F.flashes) {   // 번쩍일 때 0.5초 흔들림
    const u = t - ft;
    if (u >= 0 && u < 0.5) { const m = 10 * (1 - u / 0.5); sx += Math.sin(u * 70) * m; sy += Math.cos(u * 55) * m; }
  }
  return { cam: makeCamera({ ...q, sx, sy, fov: 30 }, W, H), s: KM * Math.cos(q.lat * Math.PI / 180) / q.d, q };
}

// ------------------------------------------------------------------ 클립 프레임(24fps JPG)
const FRAMES = new Map();
function frame(c, i) {
  const k = c.id + '/' + i;
  if (!FRAMES.has(k)) {
    FRAMES.set(k, load(`assets/clips/${c.id}/${String(i).padStart(4, '0')}.jpg`));
    if (FRAMES.size > 96) FRAMES.delete(FRAMES.keys().next().value);
  }
  return FRAMES.get(k);
}
const clipAt = t => F.clips.find(c => t >= c.start && t < c.start + c.duration);
const clipIdx = (c, t) => clamp(Math.floor((t - c.start) * 24) + 1, 1, Math.round(c.duration * 24));

// ------------------------------------------------------------------ 불러오기
async function init() {
  const opt = p => fetch(p).then(r => (r.ok ? r.json() : null));
  [F, BB, CINES, RE, LAND] = await Promise.all([json('data/film.json'), json('data/plates.json'),
    opt('data/cine.json'), opt('data/realms.json'), opt('data/land.json')]);
  CINES ||= [];
  // 나라 영역: 변을 0.25°마다 쪼개 둥근 땅 위에서도 경계가 꺾이지 않게 한다
  if (RE) for (const r of RE.realms) r.poly = r.poly.flatMap((a, i) => {
    const b = r.poly[(i + 1) % r.poly.length], k = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25);
    return Array.from({ length: k }, (_, j) => [lerp(a[0], b[0], j / k), lerp(a[1], b[1], j / k)]);
  });
  ({ z: N, x0: X0, y0: Y0, width: TW, height: TH } = F.tiles); KM = 616.2 * 2 ** (9 - N); N = 2 ** N;
  CAM = F.cam.map(([t, d, lon, lat, s]) => [t, d, ...toPx(lon, lat), s]);
  INTRO = F.clips.length ? F.clips[0].start : 0;
  // 화살표: film.py처럼 세계 px에서 2차 베지어를 찍고 경위도로 돌린다
  ARR = F.arrows.map(row => {
    const P = row[1].map(p => toPx(...p)), pts = [];
    for (let i = 0; i <= 64; i++) {
      const u = i / 64, v = 1 - u;
      pts.push(toLL(v * v * P[0][0] + 2 * v * u * P[1][0] + u * u * P[2][0], v * v * P[0][1] + 2 * v * u * P[1][1] + u * u * P[2][1]));
    }
    return { row, pts };
  });
  const names = ['world', ...Object.keys(BB), ...CINES.map(w => w.plate)];   // close는 좁은 곳이 있을 때만
  const imgs = await Promise.all(names.map(n => load(`assets/plates/${n}.jpg`)));
  names.forEach((n, i) => gl.upload(n, imgs[i]));
  await Promise.all(F.photos.map(async p => { PHOTO[p[0]] = await load('assets/photos/' + p[1]); }));
  for (const p of F.photos) {   // 사진이 떠 있는 동안 보이는 이름표 중 설명에 든 것(핀 먼저)
    const ls = F.labels.filter(l => l[4] < p[4] && l[5] > p[3] && p[2].includes(l[1].replace(/\(.*\)/, '')));
    PIN[p[0]] = ls.find(l => l[7]) || ls[0];
  }
  await Promise.all(['500 30px SC', '700 30px SC', '800 30px SC', '900 30px SC', '300 100px BC', '500 30px BC', '400 22px PM', '500 22px PM']
    .map(f => document.fonts.load(f, '가나다 귀주 거란 0123456789')));
  window.DUR = Math.min(+(Q.get('to') || F.total), F.total) - FROM;
  window.READY = true;
}

// ------------------------------------------------------------------ 한 장
async function render(t) {
  t = clamp(t + FROM, 0, F.total - 1e-4);
  const c = clipAt(t), img = c ? await frame(c, clipIdx(c, t)) : null;
  if (c) for (let k = 1; k <= 4; k++) frame(c, Math.min(clipIdx(c, t) + k, Math.round(c.duration * 24)));   // 미리 읽기
  beginTexts();
  const { cam, s, q } = camAt(t);
  const ph = F.photos.reduce((m, p) => Math.max(m, (PIN[p[0]] ? 0.4 : 1) * ss(seg(t, p[3], p[3] + 0.6)) * (1 - ss(seg(t, p[4] - 0.3, p[4])))), 0);
  gl.draw({
    cam,
    slots: {
      ca: { tex: 'wide', bbox: BB.wide, a: 1 - ss(seg(cam.alt, 1500, 2600)) },   // 높을 땐 판 가장자리가 보여서 세계판으로
      regA: { tex: 'detail', bbox: BB.detail, a: 1 },
      detA: cineOf(t) ? { tex: cineOf(t).plate, bbox: BB[cineOf(t).plate], a: 1 } : { tex: BB.close ? 'close' : 'detail', bbox: BB.close || BB.detail, a: +!!BB.close },
    },
    grey: 0.72, shade: clamp(1 - ss(seg(Math.log(cam.alt), Math.log(2500), Math.log(600)))),
    contrast: 1.04, clarity: 0.4, detail: 0.8,
    dim: Math.max(0.22 * ph, 0.7 * ss(seg(t, F.end_start, F.end_start + 0.8))),
  });
  ctx.clearRect(0, 0, W, H);
  drawRealms(t, cam);
  drawFront(t, cam);
  drawHaze(q);
  drawArrows(t, cam, s);
  drawLabels(t, cam);
  drawFlashes(t, cam, s);
  drawHud(t, cam, q);
  if (img) drawClip(t, c, img);
  drawDate(t);
  drawCounters(t);
  drawPhotos(t, cam);
  drawCaption(t);
  drawEnd(t);
  return endTexts();
}

// ------------------------------------------------------------------ 그때 나라 영역(data/realms.json): 땅만 옅게 칠하고 이름을 얹는다
// 멀리서(고도 400km 위) 보이고 150km 아래로 다가가면 사라진다: 가까이선 화면이 한 나라 색으로 덮인다
function drawRealms(t, cam) {
  const a = !RE || !LAND ? 0 : ss(seg(t, INTRO, INTRO + 1)) * (1 - ss(seg(t, F.end_start, F.end_start + 0.8))) * ss(seg(cam.alt, 150, 400));
  if (a <= 0) return;
  const path = ring => clipRing(cam, ring).forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  const yr = +(F.dates.filter(d => d[0] <= t).pop() || F.dates[0])[1];   // 회상 장면은 그해 이름(old: [바뀐 해, 옛 이름])
  const realms = RE.realms.filter(r => !r.years || (yr >= r.years[0] && yr <= r.years[1]));   // years: 그 해 안에만 있던 영역
  ctx.save(); ctx.beginPath(); LAND.forEach(r => { path(r); ctx.closePath(); }); ctx.clip();
  for (const r of realms) {
    ctx.beginPath(); path(r.poly); ctx.closePath();
    ctx.globalAlpha = a * 0.18; ctx.fillStyle = r.color; ctx.fill();
    ctx.globalAlpha = a * 0.8; ctx.strokeStyle = r.color; ctx.lineWidth = 2; ctx.setLineDash([12, 7]); ctx.stroke();
  }
  ctx.restore();
  const shown = new Set(F.labels.filter(l => t >= l[4] && t <= l[5]).map(l => l[1]));   // 같은 이름표가 떠 있으면 비킨다
  for (const r of realms) {
    const [x, y, v] = project(cam, r.label[1], r.label[0]), name = r.old && yr < r.old[0] ? r.old[1] : r.name;
    if (v && !shown.has(name)) text(ctx, name, x, y, { font: '800 44px SC', col: r.color, align: 'center', track: 10, alpha: a * 0.95, halo: 12 });
  }
}

// 다각형을 3차원에서 지평선(보이는 땅 P·C > R²)과 카메라 앞 1km 면으로 잘라 화면 점으로 돌린다.
// 안 보이는 점을 그대로 투영하면 뒤집힌 점 때문에 확대·기울인 장면에서 색 구역이 찢어진다.
// 지평선 밖으로 나갔다 들어오는 토막은 직선(현)이 아니라 지평선 원호로 잇는다: 현은 보이는 땅을 가로질러
// 넓은 땅 고리(land.json)의 가림을 뒤집는다. 원호 방향은 밖 토막이 지평선 축을 돈 각도로 정한다
function clipRing(cam, ring) {
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], c = Math.hypot(...cam.C);
  const n = cam.C.map(x => x / c), d = R * R / c, rho = Math.sqrt(R * R - d * d);
  const t = Math.abs(n[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0], tn = dot(t, n), e1n = Math.hypot(...t.map((x, k) => x - n[k] * tn));
  const e1 = t.map((x, k) => (x - n[k] * tn) / e1n), e2 = [n[1] * e1[2] - n[2] * e1[1], n[2] * e1[0] - n[0] * e1[2], n[0] * e1[1] - n[1] * e1[0]];
  const ang = P => Math.atan2(dot(P, e2), dot(P, e1)), wrap = a => a - 2 * Math.PI * Math.round(a / (2 * Math.PI));
  const arc = a => n.map((x, k) => x * d + rho * (Math.cos(a) * e1[k] + Math.sin(a) * e2[k]));
  const cut = (a, b, da, db) => a.map((x, k) => x + (b[k] - x) * da / (da - db));
  // 긴 변은 1°씩 쪼갠다: 3차원 직선은 땅속으로 파고들고(80° 변이면 1,500km) 밖 토막의 각도도 놓친다
  let pts = ring.flatMap(([lon, lat], i) => {
    const [lo, la] = ring[(i + 1) % ring.length], m = Math.max(1, Math.ceil(Math.max(Math.abs(lo - lon), Math.abs(la - lat))));
    return Array.from({ length: m }, (_, k) => ecef(lat + (la - lat) * k / m, lon + (lo - lon) * k / m));
  });
  const s = pts.findIndex(P => dot(P, n) >= d);   // 보이는 점에서 시작해야 밖 토막마다 나간 점이 먼저 온다
  if (s < 0) return [];
  pts = pts.slice(s).concat(pts.slice(0, s));
  let out = [], a0 = 0, sweep = 0, last = 0;
  pts.forEach((a, i) => {
    const b = pts[(i + 1) % pts.length], da = dot(a, n) - d, db = dot(b, n) - d;
    if (da >= 0) out.push(a);
    else { sweep += wrap(ang(a) - last); last = ang(a); }
    if ((da >= 0) === (db >= 0)) return;
    const X = cut(a, b, da, db);
    if (da >= 0) { out.push(X); a0 = last = ang(X); sweep = 0; return; }
    sweep += wrap(ang(X) - last);
    for (let k = 1, m = Math.ceil(Math.abs(sweep) / 0.03); k < m; k++) out.push(arc(a0 + sweep * k / m));
    out.push(X);
  });
  const fd = dot(cam.C, cam.f) + 1;
  pts = out, out = [];
  pts.forEach((a, i) => {
    const b = pts[(i + 1) % pts.length], da = dot(a, cam.f) - fd, db = dot(b, cam.f) - fd;
    if (da >= 0) out.push(a);
    if ((da >= 0) !== (db >= 0)) out.push(cut(a, b, da, db));
  });
  return out.map(P => { const r = Math.hypot(...P); return project(cam, Math.asin(P[2] / r) * 180 / Math.PI, Math.atan2(P[1], P[0]) * 180 / Math.PI, r - R); });
}

// ------------------------------------------------------------------ 전선·점령지(64.52초부터)
function drawFront(t, cam) {
  const tw = F.map_tweens.find(x => x.includes('#map-front')), fa0 = tw ? +tw.match(/([\d.]+)\);$/)[1] : 0;
  const a = ss(seg(t, fa0, fa0 + 0.6)) * (1 - ss(seg(t, F.end_start, F.end_start + 0.8)));
  if (a <= 0 || !F.front.length) return;
  const [ka, kb, p] = at(F.front, t, p1io);
  const mix = (A, B) => A.map((q, i) => [lerp(q[0], B[i][0], p), lerp(q[1], B[i][1], p)]);
  const line = mix(F.states[ka[2]], F.states[kb[2]]);   // 점령지는 칠하지 않는다: 위성 땅이 붉게 덮인다
  if (ka !== kb && p > 0 && p < 1) hair(ctx, () => pathLL(ctx, cam, line), { w: 18, col: RED, alpha: a * 0.4 * Math.sin(Math.PI * p), halo: 0, cap: 'round' });
  hair(ctx, () => pathLL(ctx, cam, line), { w: 3, col: RED, alpha: a, dash: [16, 9], off: -t * 12, halo: 4 });
  // 무슨 선인지 이름을 단다: 화면 가운데에서 가장 가까운 선 위 점(카메라가 움직여도 미끄러지듯 따라간다)
  const P = line.map(([lo, la]) => project(cam, la, lo)), cx = cam.W / 2, cy = cam.H / 2;
  let best = null;
  P.forEach((A, i) => {
    const B = P[i + 1];
    if (!B || !A[2] || !B[2]) return;
    const dx = B[0] - A[0], dy = B[1] - A[1], k = clamp(((cx - A[0]) * dx + (cy - A[1]) * dy) / (dx * dx + dy * dy || 1), 0, 1);
    const q = [A[0] + dx * k, A[1] + dy * k], d = Math.hypot(q[0] - cx, q[1] - cy);
    if (!best || d < best[2]) best = [...q, d];
  });
  if (best) text(ctx, '전선', best[0], best[1] - 16, { font: '800 30px SC', col: RED, align: 'center', track: 6, alpha: a, halo: 10 });
}

// 기울이면 먼 쪽이 대기에 흐려진다(먼 곳이 낮은 해상도 판으로 넘어가는 경계도 가린다)
function drawHaze(q) {
  const k = ss(seg(q.tilt, 15, 55));
  if (k <= 0) return;
  const g = ctx.createLinearGradient(0, 0, 0, H * 0.55);
  g.addColorStop(0, `rgba(150,166,178,${0.5 * k})`); g.addColorStop(0.45, `rgba(120,136,148,${0.18 * k})`); g.addColorStop(1, 'rgba(120,136,148,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.55);
}

// ------------------------------------------------------------------ 화살표: 그려지는 선 + 머리 + 따라 흐르는 빛, 병력은 점 셋
function partial(pts, e) {
  const f = clamp(e) * (pts.length - 1), k = Math.floor(f), out = pts.slice(0, k + 1);
  if (k < pts.length - 1) { const a = pts[k], b = pts[k + 1], u = f - k; out.push([lerp(a[0], b[0], u), lerp(a[1], b[1], u)]); }
  return out;
}
function screenPath(cam, pts) { return pts.map(([lo, la]) => project(cam, la, lo)); }
function along(sp, u) {   // 화면 경로에서 길이 몫 u의 점과 방향
  const L = [0];
  for (let i = 1; i < sp.length; i++) L.push(L[i - 1] + Math.hypot(sp[i][0] - sp[i - 1][0], sp[i][1] - sp[i - 1][1]));
  const want = clamp(u) * L[L.length - 1];
  let i = 1; while (i < sp.length - 1 && L[i] < want) i++;
  const a = sp[i - 1], b = sp[i], g = (want - L[i - 1]) / ((L[i] - L[i - 1]) || 1);
  return { x: lerp(a[0], b[0], g), y: lerp(a[1], b[1], g), dx: b[0] - a[0], dy: b[1] - a[1], len: L[L.length - 1] };
}
function drawArrows(t, cam) {
  for (const { row, pts } of ARR) {
    const [, , t0, dd, t1, col, , kind] = row;
    if (t < t0 || t > t1) continue;
    const c = colOf(col), a = 1 - ss(seg(t, t1 - 0.4, t1));
    const e = eo(dd > 0 ? (t - t0) / dd : 1);
    hair(ctx, () => pathLL(ctx, cam, partial(pts, e)), { w: 5, col: c, alpha: a, halo: 7, haloCol: halo, cap: 'round' });
    const sp = screenPath(cam, pts);
    const ha = a * ss(seg(t, t0 + dd - 0.1, t0 + dd + 0.02));
    if (ha > 0) {
      const end = sp[sp.length - 1], prev = sp[sp.length - 5], L = Math.hypot(end[0] - prev[0], end[1] - prev[1]) || 1;
      const ux = (end[0] - prev[0]) / L, uy = (end[1] - prev[1]) / L, tx = end[0] + ux * 16, ty = end[1] + uy * 16;
      const side = s => [tx - (ux * Math.cos(s) - uy * Math.sin(s)) * 32, ty - (uy * Math.cos(s) + ux * Math.sin(s)) * 32];
      const [lx, ly] = side(0.42), [rx, ry] = side(-0.42);
      ctx.save(); ctx.globalAlpha = ha;
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(lx, ly); ctx.lineTo(rx, ry); ctx.closePath();
      ctx.lineJoin = 'round'; ctx.strokeStyle = halo; ctx.lineWidth = 5; ctx.stroke(); ctx.fillStyle = c; ctx.fill();
      ctx.restore();
      for (let k = 0; k < 2; k++) {   // 다 그린 뒤 빛이 길을 따라 흐른다
        const u = ((t - t0 - dd) / 1.6 + k / 2) % 1, q = along(sp, u);
        ctx.save(); ctx.globalAlpha = ha * 0.85 * Math.sin(Math.PI * u);
        const g = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, 16); g.addColorStop(0, 'rgba(255,255,255,.95)'); g.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = g; ctx.fillRect(q.x - 16, q.y - 16, 32, 32); ctx.restore();
      }
    }
    if (kind) drawSquad(t, row, sp, c);
  }
}
// film.py 병력 배지와 같은 시각: start+0.1에 떠나 sine.inOut으로 길의 0.88까지, 뒤 둘은 54px씩 늦다
function drawSquad(t, row, sp, c) {
  const [, , t0, , t1, , , kind] = row, st = t0 + 0.1, mv = clamp(t1 - t0 - 1, 1.2, 3.2);
  if (t < st || t >= t1) return;
  const q = sio((t - st) / mv), len = along(sp, 1).len;
  [1, 0.72, 0.72].forEach((size, k) => {
    const lag = k * 54 / Math.max(len, 1);
    if (lag > 0.5) return;
    const u = q * 0.88 - lag;
    if (u < 0) return;
    const p = along(sp, u), al = Math.min(1, u / 0.04, (t - st) / 0.25, (t1 - t) / 0.4);
    const r = 11 * size, ang = Math.atan2(p.dy, p.dx);
    ctx.save(); ctx.globalAlpha = al; ctx.translate(p.x, p.y); ctx.rotate(ang);
    ctx.shadowColor = halo; ctx.shadowBlur = 8; ctx.fillStyle = c; ctx.strokeStyle = 'rgba(3,6,8,.8)'; ctx.lineWidth = 2;
    ctx.beginPath();
    if (kind === 'cavalry') { ctx.moveTo(r * 1.5, 0); ctx.lineTo(-r, -r); ctx.lineTo(-r * 0.4, 0); ctx.lineTo(-r, r); ctx.closePath(); }   // 기병: 쐐기
    else ctx.arc(0, 0, r * 0.85, 0, 6.2832);                                                                                           // 보병: 점
    ctx.fill(); ctx.shadowBlur = 0; ctx.stroke(); ctx.restore();
  });
}

// ------------------------------------------------------------------ 이름표
function drawLabels(t, cam) {
  for (const [, name, lon, lat, t0, t1, left, pin] of F.labels) {
    if (t < t0 || t > t1) continue;
    const a = eo(seg(t, t0, t0 + 0.35)) * (1 - ss(seg(t, t1 - 0.32, t1 - 0.02)));
    const [x, y, v] = project(cam, lat, lon);
    if (!v || a <= 0) continue;
    if (pin) {
      const pop = 1 + 0.8 * Math.exp(-(t - t0) * 9);
      hair(ctx, () => ctx.arc(x, y, 9 * pop, 0, 6.2832), { w: 2, alpha: a, halo: 3 });
      ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(x, y, 3.2, 0, 6.2832); ctx.fill(); ctx.restore();
    }
    const dx = pin ? 20 : 0, dy = 11;
    text(ctx, name, left ? x - dx : x + dx, y + dy, { font: '700 32px SC', align: pin ? (left ? 'right' : 'left') : 'center', alpha: a, halo: 10, track: pin ? 0 : 3 });
  }
}

// ------------------------------------------------------------------ 번쩍임: 흰 섬광 + 호박색 고리
function drawFlashes(t, cam, s) {
  const k = Math.min(s, 1.4);
  for (const [ft, lon, lat] of F.flashes) {
    const q = t - ft;
    if (q < 0 || q > 0.9) continue;
    const [x, y, v] = project(cam, lat, lon);
    if (!v) continue;
    if (q < 0.55) {
      const e = eo(q / 0.55), r = (24 + 150 * e) * k;
      ctx.save(); ctx.globalAlpha = 1 - e;
      const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.35, 'rgba(255,236,200,.75)'); g.addColorStop(1, 'rgba(255,190,85,0)');
      ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r); ctx.restore();
    }
    const e2 = eo(q / 0.9);
    hair(ctx, () => ctx.arc(x, y, (30 + 340 * e2) * k, 0, 6.2832), { w: 2.5, col: C.amber, alpha: 0.9 * (1 - e2), halo: 3 });
  }
}

// ------------------------------------------------------------------ 계기: 좌표·고도·축척(오른쪽 위), 출처(왼쪽 아래)
function drawHud(t, cam, q) {
  const a = ss(seg(t, 0.1, 0.5)) * (1 - ss(seg(t, F.end_start, F.end_start + 0.6)));
  if (a <= 0) return;
  const X = W - 64, { lat, lon } = cam.tgt;
  text(ctx, `N ${lat.toFixed(2)}°  E ${lon.toFixed(2)}°`, X, 66, { font: '400 22px PM', align: 'right', alpha: a * 0.9, halo: 5 });
  const alt = cam.alt, altTxt = alt >= 100 ? Math.round(alt / 10) * 10 : alt.toFixed(alt >= 10 ? 0 : 1);
  const tilt = q.tilt > 1 ? `   TILT ${Math.round(q.tilt)}°  HDG ${String(Math.round((q.heading + 360) % 360)).padStart(3, '0')}°` : '';
  text(ctx, `ALT ${Number(altTxt).toLocaleString('en-US')} km${tilt}`, X, 98, { font: '400 22px PM', align: 'right', alpha: a * 0.9, halo: 5 });
  const kmpx = cam.alt / cam.F;
  let m = 1; for (const n of [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]) if (n / kmpx <= 200) m = n;
  const L = m / kmpx, y = 134;
  hair(ctx, () => { ctx.moveTo(X - L, y - 8); ctx.lineTo(X - L, y); ctx.lineTo(X, y); ctx.lineTo(X, y - 8); }, { w: 1.4, alpha: a * 0.85, halo: 2 });
  text(ctx, m + ' km', X - L - 12, y + 2, { font: '400 20px PM', align: 'right', alpha: a * 0.85, halo: 5 });
  text(ctx, F.map_credit + (RE ? ' · ' + RE.credit : ''), 64, H - 30, { font: '500 17px SC', alpha: a * 0.7, halo: 4 });
}

// ------------------------------------------------------------------ Flow 클립: 화면 가득, 0.35초 페이드, 1.08 → 1 물러나기
function drawClip(t, c, img) {
  const a = ss(seg(t, c.start, c.start + 0.35)) * (1 - ss(seg(t, c.start + c.duration - 0.37, c.start + c.duration - 0.02)));
  const k = lerp(1.08, 1, (t - c.start) / c.duration), w = W * k, h = H * k;
  ctx.save(); ctx.globalAlpha = a; ctx.drawImage(img, (W - w) / 2, (H - h) / 2, w, h); ctx.restore();
}

// ------------------------------------------------------------------ 날짜(왼쪽 위): 해는 계기 글꼴, 달은 크게, 호박색 줄
function drawDate(t) {
  const D = F.dates;
  let i = -1; for (let k = 0; k < D.length; k++) if (t >= D[k][0]) i = k;
  if (i < 0 || t >= F.date_end) return;
  const [t0, year, big, small] = D[i], a = 1 - (i === D.length - 1 ? ss(seg(t, F.date_end - 0.42, F.date_end - 0.02)) : 0);
  const [x, y] = F.date_pos, e = eo(seg(t, t0, t0 + 0.6)), pop = 1 + 0.25 * (1 - e);
  text(ctx, year, x + 2, y + 34, { font: '500 30px PM', track: 3, alpha: a * 0.9, halo: 6 });
  ctx.save(); ctx.translate(x, y + 128 + 30 * (1 - e)); ctx.scale(pop, pop);
  text(ctx, big, 0, 0, { font: '900 92px SC', alpha: a * e, halo: 14 });
  ctx.restore();
  const b = p3o(seg(t, t0 + 0.1, t0 + 0.6));
  hair(ctx, () => { ctx.moveTo(x + 2, y + 152); ctx.lineTo(x + 2 + 220 * b, y + 152); }, { w: 3, col: C.amber, alpha: a, halo: 2 });
  if (small) text(ctx, small, x + 2, y + 198, { font: '700 32px SC', alpha: a * e, halo: 8 });
}

// ------------------------------------------------------------------ 숫자: 이름, 굴러가는 값, 단위, 호박색 줄
function drawCounters(t) {
  for (const [, name, value, unit, t0, t1, x, y] of F.counters) {
    if (t < t0 || t > t1) continue;
    const a = eo(seg(t, t0, t0 + 0.35)) * (1 - ss(seg(t, t1 - 0.32, t1)));
    const g = p3o(seg(t, t0 + 0.2, t0 + 1.8)), n = Math.round(value * g).toLocaleString('en-US');
    text(ctx, name, x + 2, y + 34, { font: '700 32px SC', alpha: a * 0.95, halo: 8 });
    const vw = text(ctx, n, x, y + 140, { font: '300 112px BC', col: C.amber, track: -1, alpha: a, halo: 12 });
    text(ctx, unit, x + vw + 12, y + 140, { font: '700 44px SC', col: C.amber, alpha: a, halo: 8 });
    hair(ctx, () => { ctx.moveTo(x + 2, y + 164); ctx.lineTo(x + 2 + Math.max(260, vw + 80) * p3o(seg(t, t0 + 0.2, t0 + 1.8)), y + 164); }, { w: 1.4, alpha: a * 0.6, halo: 0 });
  }
}

// ------------------------------------------------------------------ 기록 사진
// 설명에 그때 보이는 땅 이름이 있으면(핀 이름표 먼저) 그 땅에 꽂고, 없으면(그림·인물 등) 오른쪽 위 카드로 띄운다
function card(img, cap, x, y, w, h, a, k, fy) {   // 괄호 틀, 천천히 다가가기(k), 아래 설명
  const ir = img.width / img.height, fr = w / h;   // cover로 자른다
  const sw = ir > fr ? img.height * fr : img.width, sh = ir > fr ? img.height : img.width / fr;
  const f = w / 620;   // 설명·틀은 카드 크기에 맞춘다
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(5,8,11,.6)'; ctx.fillRect(x - 10, y - 10, w + 20, h + 74 * f);
  ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  ctx.filter = 'saturate(.55) contrast(1.05)';
  // 세로로 긴 그림은 위에서 자른다(초상화 얼굴이 위에 있다, 파이프라인 object-position 50% 0과 같게).
  // 인물이 아닌 그림은 photos의 fy(0 위 ~ 1 아래)로 볼 곳을 고른다
  const sy = ir > fr ? (img.height - sh / k) / 2 : fy == null ? (sh - sh / k) * 0.3 : (img.height - sh / k) * fy;
  ctx.drawImage(img, (img.width - sw / k) / 2, sy, sw / k, sh / k, x, y, w, h);
  ctx.restore();
  brackets(ctx, x - 18, y - 18, x + w + 18, y + h + 82 * f, { len: 26, w: 1.8, alpha: a });
  ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = C.amber; ctx.fillRect(x, y + h + 26 * f, 10, 10); ctx.restore();
  text(ctx, cap, x + 22, y + h + 41 * f, { font: `700 ${Math.round(27 * Math.max(f, 0.85))}px SC`, alpha: a, halo: 4 });
}
function drawPhotos(t, cam) {
  for (const [id, , cap, t0, t1, x, y, w, , ratio, , , fy] of F.photos) {
    if (t < t0 || t > t1) continue;
    const img = PHOTO[id], k = lerp(1, 1.1, (t - t0) / (t1 - t0)), out = 1 - ss(seg(t, t1 - 0.32, t1));
    const pin = PIN[id];
    if (!pin) {
      const h = Math.round(w * (ratio || img.height / img.width)), e = eo(seg(t, t0, t0 + 0.6));
      ctx.save(); ctx.translate(0, -40 * (1 - e)); card(img, cap, x, y, w, h, e * out, k, fy); ctx.restore();
      continue;
    }
    // 땅에 꽂기: 땅 점에서 기둥이 솟고(0~0.35초) 카드가 그 위에 펼쳐진다(0.25~0.8초)
    const [px, py, v] = project(cam, pin[3], pin[2]);
    if (!v) continue;
    const pw = 440, ph = Math.round(pw * (ratio || img.height / img.width)), tall = ph + 70;
    const cx = clamp(px - pw / 2, 64, W - 64 - pw), cy = clamp(py - 110 - tall, 200, H - 300 - tall);
    const top = [clamp(px, cx + 14, cx + pw - 14), cy + tall], g = eo(seg(t, t0, t0 + 0.35));
    hair(ctx, () => { ctx.moveTo(px, py); ctx.lineTo(lerp(px, top[0], g), lerp(py, top[1], g)); }, { w: 2, col: C.amber, alpha: out, halo: 3 });
    const r = (t - t0) % 1.6 / 1.6;   // 땅 점에서 고리가 퍼진다
    hair(ctx, () => ctx.ellipse(px, py, 8 + 34 * r, (8 + 34 * r) * 0.55, 0, 0, 6.2832), { w: 2, col: C.amber, alpha: out * (1 - r), halo: 2 });
    ctx.save(); ctx.globalAlpha = out; ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(px, py, 5, 0, 6.2832); ctx.fill(); ctx.restore();
    const u = eo(seg(t, t0 + 0.25, t0 + 0.8));
    if (u <= 0) continue;
    ctx.save(); ctx.translate(top[0], top[1]); ctx.scale(lerp(0.6, 1, u), u); ctx.translate(-top[0], -top[1]);   // 기둥 끝에서 펼친다
    card(img, cap, cx, cy, pw, ph, u * out, k, fy);
    ctx.restore();
  }
}

// ------------------------------------------------------------------ 자막: 아래 가운데, 어두운 판(film.py: 아래 112px, 50px, 폭 80%)
function lines(s, font, max) {
  if (measure(ctx, s, font) <= max) return [s];
  let best = null;
  for (let i = 1; i < s.length; i++) {
    if (s[i] !== ' ') continue;
    const d = Math.abs(measure(ctx, s.slice(0, i), font) - measure(ctx, s.slice(i + 1), font));
    if (!best || d < best.d) best = { d, i };
  }
  return best ? [s.slice(0, best.i), s.slice(best.i + 1)] : [s];
}
function drawCaption(t) {
  const c = F.captions.find(([a, b]) => t >= a && t < b);
  if (!c) return;
  const font = '700 48px SC', L = lines(c[2], font, W * 0.8 - 52), lh = 64;
  const bw = Math.max(...L.map(s => measure(ctx, s, font))) + 52, bh = L.length * lh + 18, by = H - 112 - bh;
  ctx.save(); ctx.fillStyle = 'rgba(5,8,11,.62)'; ctx.fillRect((W - bw) / 2, by, bw, bh);
  ctx.fillStyle = C.ink; ctx.fillRect((W - bw) / 2, by, 3, bh); ctx.restore();
  L.forEach((s, i) => text(ctx, s, W / 2, by + 58 + i * lh, { font, align: 'center', halo: 4 }));
}

// ------------------------------------------------------------------ 끝: 어두워진 지도 위 괄호 안 제목
function drawEnd(t) {
  const t0 = F.end_start;
  if (t < t0) return;
  const parts = F.title.split(/,\s*/), x = 112;
  const a1 = eo(seg(t, t0 + 0.5, t0 + 0.95)), a2 = eo(seg(t, t0 + 0.7, t0 + 1.1)), a3 = eo(seg(t, t0 + 0.9, t0 + 1.3));
  const font = '900 80px SC', tw = Math.max(...parts.map((p, i) => measure(ctx, p + (i < parts.length - 1 ? ',' : ''), font)));
  const u = eo(seg(t, t0 + 0.3, t0 + 0.9));
  brackets(ctx, x - 44, 300 - 30 * u, x + lerp(200, tw + 44, u), 640 + 30 * u, { len: 34, w: 2, alpha: ss(seg(t, t0 + 0.3, t0 + 0.5)) });
  parts.forEach((p, i) => text(ctx, p + (i < parts.length - 1 ? ',' : ''), x, 400 + i * 100 + 20 * (1 - a1), { font, alpha: a1, halo: 16, track: -1 }));
  text(ctx, F.subtitle, x + 2, 400 + parts.length * 100 + 6, { font: '700 42px SC', col: C.amber, alpha: a2, halo: 8 });
  text(ctx, '선을 긋다  ·  SATELLITE BRIEFING', x + 2, 400 + parts.length * 100 + 66, { font: '500 24px PM', alpha: a3 * 0.85, halo: 6, track: 2 });
  // 시리즈에 다음 편이 있으면 오른쪽 아래에 띄운다(film.json next)
  if (F.next) text(ctx, '다음 편에 계속', W - 112, H - 140, { font: '800 56px SC', col: C.amber, align: 'right', alpha: eo(seg(t, t0 + 1.2, t0 + 1.7)), halo: 12 });
}

window.render = t => render(t);
window.TEXTS = t => render(t);
window.EV = [];
init().catch(e => { console.error(e); throw e; });

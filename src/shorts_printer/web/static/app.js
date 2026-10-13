// 목록 화면(대시보드·주제 찾기): 글자 수·제출 스피너, 진행 중인 것이 있으면 3초마다 목록 조각만 다시 받는다.
// 상세 화면(작업·주제 분석): 1.5초마다 상태 API로 로그를 바꾸고, sig가 바뀌면 data-swap에 적힌 조각만 바꾼다.
const $ = (sel, el = document) => el.querySelector(sel);
const page = $('#page');

function toast(msg, bad = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('bad', bad);
  t.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove('show'), 2500);
}

// 포커스가 있던 요소를 새 조각에서 다시 찾을 열쇠
const keyOf = el => ['id', 'href', 'aria-label'].map(k => el.getAttribute(k) && `[${k}="${CSS.escape(el.getAttribute(k))}"]`).find(Boolean);

// 내용이 바뀐 조각만 갈아 끼운다(그대로면 재생 중인 음성·포커스·스크롤을 건드리지 않는다)
async function swap(url, ids) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.status);
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  const a = document.activeElement, key = a && a !== document.body && keyOf(a);
  for (const id of ids) {
    const cur = document.getElementById(id), fresh = doc.getElementById(id);
    if (cur?.querySelector('iframe')) continue;   // 재생 중인 미리보기는 끊지 않는다(수집이 끝난 뒤라 내용도 그대로다)
    if (cur && fresh && !cur.isEqualNode(fresh)) cur.replaceWith(fresh.cloneNode(true));   // 사본: doc의 바깥 조각은 다음 비교까지 온전히 둔다
  }
  // tabindex=-1 칸(진행 단계 등)은 한 번 옮긴 포커스라 다시 주지 않는다(바뀔 때마다 화면 읽기가 되풀이된다)
  if (key && !a.isConnected && a.tabIndex >= 0) document.querySelector(key)?.focus();
  return doc;
}

// 뒤로 가기로 돌아오면(bfcache) 비활성화된 버튼이 남지 않게 새로 그린다
addEventListener('pageshow', e => { if (e.persisted) location.reload(); });

// ── 글자 수(주제·키워드)
for (const count of document.querySelectorAll('[data-for]')) {
  const input = document.getElementById(count.dataset.for);
  const upd = () => { count.textContent = `${input.value.length}/${input.maxLength}`; };
  input.addEventListener('input', upd);
  upd();
}

// ── 제출 스피너(만들기·분석 시작·이 주제로 만들기)
document.addEventListener('submit', e => {
  const b = $('button[type=submit]', e.target);
  if (!b?.dataset.busy) return;
  b.disabled = true;
  b.setAttribute('aria-busy', 'true');
  $('span', b).textContent = b.dataset.busy;
});

// ── 목록 갱신: data-list="조각 id들"이 붙은 칸이 data-active="1"일 때만
const listId = $('[data-list]')?.id;
if (listId) {
  const ids = $('#' + listId).dataset.list.split(' ');
  const refresh = async () => {
    const el = document.getElementById(listId);
    if (el.dataset.active !== '1') return;
    try { await swap(location.pathname, ids); }
    catch {   // 다음 차례에 다시. 성공하면 목록 칸이 바뀌며 원래대로 돌아온다
      const l = $('.live', el);
      if (l) { l.textContent = '연결 끊김, 다시 시도 중'; l.classList.add('bad'); }
    }
    setTimeout(refresh, 3000);
  };
  setTimeout(refresh, 3000);
}

// ── 상세 화면(작업·주제 분석)
const api = page?.dataset.api;
let tick = () => {};
if (api) {
  const ids = page.dataset.swap.split(' ');
  const log = $('#log'), fresh = $('#fresh');
  let sig = page.dataset.sig, timer, notices = document.querySelectorAll('.banner-info').length;
  log.scrollTop = log.scrollHeight;
  // force: 다시 시도 직후처럼 sig가 같아 보여도 화면을 새로 받아야 할 때
  tick = async (force = false) => {
    clearTimeout(timer);
    let d;
    try {
      const r = await fetch(api);
      if (!r.ok) throw new Error(r.status);
      d = await r.json();
    } catch {
      if (!fresh.classList.contains('bad')) $('#say').textContent = '연결 끊김, 다시 시도 중';
      fresh.textContent = '연결 끊김, 다시 시도 중';
      fresh.classList.add('bad');
      timer = setTimeout(tick, 3000);
      return;
    }
    const text = d.log.join('\n');
    if (log.textContent !== text) {   // 그대로면 두어 사용자가 고른 글자를 지우지 않는다
      const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
      log.textContent = text;
      if (atBottom) log.scrollTop = log.scrollHeight;
    }
    fresh.classList.remove('bad');
    fresh.textContent = new Date().toLocaleTimeString('ko-KR', { hour12: false }) + ' 갱신';
    if (force || d.sig !== sig) {
      try {
        await swap(location.pathname, ids);
        sig = d.sig;
        $('#say').textContent = [d.say, ...d.notices.slice(notices)].join('. ');
        notices = d.notices.length;
      } catch { /* 다음 차례에 다시 */ }
    }
    const busy = st => st === 'queued' || st === 'running';
    if (busy(d.status) || busy(d.upload?.status) || d.sig !== sig) timer = setTimeout(tick, 1500);
  };
  if (page.dataset.active === '1') tick();
}

// ── 복사·미리보기·다시 시도·업로드 (조각이 바뀌어도 동작하게 위임)
document.addEventListener('click', async e => {
  const emb = e.target.closest('[data-embed]');
  if (emb) {   // 누를 때만 YouTube를 불러온다(쿠키 없는 주소)
    const f = document.createElement('iframe');
    f.className = 'v-frame';
    f.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(emb.dataset.embed)}?autoplay=1&playsinline=1&rel=0`;
    f.title = emb.getAttribute('aria-label').replace(/ 미리보기 재생$/, '');
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    emb.replaceWith(f);
    f.focus();
    return;
  }
  const copy = e.target.closest('[data-copy]');
  if (copy) {
    try { await navigator.clipboard.writeText(copy.dataset.copy); toast('복사했어요'); }
    catch { toast('복사하지 못했어요', true); }
    return;
  }
  const up = e.target.closest('[data-upload]');
  if (up) {
    up.disabled = true;
    try {
      const r = await fetch(`${api}/upload`, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'YouTube에 올리지 못했어요');
      toast('YouTube에 올리기 시작했어요');
      await tick(true);
      if (!up.isConnected) $('#upload-box')?.focus();   // 버튼이 스피너로 바뀌면 업로드 상태 칸으로
    } catch (err) {
      up.disabled = false;
      toast(err instanceof TypeError ? '서버에 닿지 않아요' : err.message, true);
      tick(true);
    }
    return;
  }
  const re = e.target.closest('[data-rethumb]');
  if (re) {
    re.disabled = true;
    try {
      const r = await fetch(`${api}/thumbnail`, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || '썸네일을 다시 만들지 못했어요');
      toast('썸네일을 다시 만들고 영상도 다시 렌더해요');
      await tick(true);
      if (!re.isConnected) $('#stepper').focus();
    } catch (err) {
      re.disabled = false;
      toast(err instanceof TypeError ? '서버에 닿지 않아요' : err.message, true);
      tick(true);
    }
    return;
  }
  const retry = e.target.closest('[data-retry]');
  if (!retry) return;
  retry.disabled = true;
  try {
    const r = await fetch(`${api}/retry`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || '다시 시도하지 못했어요');
    toast('이어서 다시 시작했어요');
    await tick(true);
    if (!retry.isConnected) ($('#retry') ?? $('#stepper')).focus();   // 버튼이 바뀌면 새 버튼, 없으면 진행 단계로
  } catch (err) {
    retry.disabled = false;
    toast(err instanceof TypeError ? '서버에 닿지 않아요' : err.message, true);
    tick(true);   // 409면 실제 상태로 화면을 맞춘다
  }
});

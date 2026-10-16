const isGerman = document.body.dataset.language === 'de';
// Only the match area changes; shelf radio, forms and page position stay intact.
(() => {
  const area = document.querySelector('[data-collection-matches][data-endpoint]');
  if (!area) return;
  let busy = false, stopped = false, timer, previous = area.innerHTML;
  const message = document.createElement('p');
  message.className = 'match-update-status';
  message.setAttribute('role', 'status');
  area.after(message);
  async function refresh() {
    clearTimeout(timer);
    if (busy || stopped || document.hidden) return;
    busy = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 10000);
    let delay = 30000;
    try {
      const response = await fetch(area.dataset.endpoint, {cache: 'no-store', signal: controller.signal, headers: {Accept: 'application/json'}});
      if (response.redirected || [401, 403].includes(response.status)) {
        area.replaceChildren(); stopped = true;
        message.textContent = isGerman ? 'Vergleiche sind pausiert oder deine Sitzung ist abgelaufen.' : 'Comparisons are paused or your session has expired.';
        return;
      }
      if (!response.ok) throw Error();
      const data = await response.json();
      if (previous !== data.html) {
        const moreOpen = area.querySelector('.more-collections')?.open;
        // Only escaped server-rendered templates from this site's authenticated endpoint.
        area.innerHTML = data.html;
        const more = area.querySelector('.more-collections');
        if (more && moreOpen) more.open = true;
        previous = data.html;
      }
      message.textContent = '';
      if (data.refreshing) delay = 5000;
    } catch (_) {
      message.textContent = isGerman ? 'Treffer konnten gerade nicht aktualisiert werden. Neuer Versuch folgt.' : 'Matches could not be updated. Retrying shortly.';
    } finally {
      clearTimeout(timeout); busy = false;
      if (!stopped) timer = setTimeout(refresh, delay);
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(timer); else refresh();
  });
  timer = setTimeout(refresh, 5000);
})();
const search = document.querySelector('#release-search');
search?.addEventListener('input', () => {
  const query = search.value.trim().toLocaleLowerCase();
  for (const section of document.querySelectorAll('.release-section')) {
    const rows = [...section.querySelectorAll('[data-release]')];
    for (const row of rows) row.hidden = !row.dataset.release.includes(query);
    const empty = section.querySelector('.filter-empty');
    if (empty) empty.hidden = !rows.length || rows.some(row => !row.hidden);
  }
});
const status = document.querySelector('[data-poll]');
if (status) {
  let failures = 0;
  async function poll() {
    try {
      const response = await fetch(status.dataset.poll, {headers: {Accept: 'application/json'}});
      if (!response.ok || response.redirected) return;
      const data = await response.json();
      if (['complete', 'failed', 'idle'].includes(data.state)) { location.reload(); return; }
      status.querySelector('[data-progress]').textContent = data.progress || (isGerman ? 'Import wartet auf den Importdienst.' : 'Import is waiting for the worker.');
      failures = 0;
    } catch (_) { failures++; }
    if (failures < 5) setTimeout(poll, 3000);
    else status.querySelector('[data-progress]').textContent = (isGerman ? 'Status derzeit nicht erreichbar. Bitte Seite neu laden.' : 'Status unavailable. Please reload the page.');
  }
  setTimeout(poll, 3000);
}

// Logo -> incoming records -> radial scan -> a real result, then the conversation.
for (const scene of document.querySelectorAll('[data-blackgold-link]')) {
  const target = Math.max(0, Math.min(100, Number(scene.dataset.target) || 0));
  const number = scene.querySelector('[data-link-number]');
  const masks = [...scene.querySelectorAll('[data-scan-inner]')];
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const render = (depth, value=depth) => {
    number.textContent = value === null ? '—' : value.toFixed(1);
    for (const mask of masks) mask.setAttribute('r', (121-77*depth/100).toFixed(3));
  };
  if (scene.dataset.interactive !== 'true') { render(target); continue; }
  const button = scene.querySelector('[data-link-start]'), comment = scene.querySelector('[data-link-comment]');
  const root = scene.closest('[data-link-results]') || scene;
  const groups = [...root.querySelectorAll('[data-link-reveal]')];
  const pool = JSON.parse(scene.dataset.comments || '[]');
  let previous='', frame=0, revealTimer;
  const finish = () => {
    render(target); scene.classList.remove('is-running','is-scanning'); scene.classList.add('is-complete');
    const choices=pool.filter(text=>text!==previous);
    previous=choices[Math.floor(Math.random()*choices.length)]||pool[0]||'Two collections. Plenty to explore.';
    comment.textContent=previous;
    for (const group of groups) {group.hidden=false; group.classList.add('revealing');}
    button.disabled=false; button.textContent=isGerman?'↻ NOCH EINMAL':'↻ PLAY IT AGAIN';
    scene.setAttribute('aria-busy','false');
    revealTimer=setTimeout(()=>document.dispatchEvent(new CustomEvent('bgl:complete',{detail:{score:target}})),reduced.matches?0:200);
  };
  button.addEventListener('click',()=>{
    clearTimeout(revealTimer); cancelAnimationFrame(frame);
    groups.forEach(group=>{group.hidden=true;group.classList.remove('revealing');});
    // Restart only the scene's CSS choreography, keeping the live conversation intact.
    scene.classList.remove('is-complete','is-running','is-scanning'); void scene.offsetWidth;
    scene.classList.add('is-running');scene.setAttribute('aria-busy','true');button.disabled=true;
    comment.textContent=isGerman?'Zwei Collections. Ein Nadelstich.':'Two collections. One needle drop.';
    render(0,null);
    if (reduced.matches) {finish();return;}
    const started=performance.now(), arrival=3000, scan=6200;
    const tick=now=>{
      const elapsed=now-started, progress=Math.max(0,Math.min(1,(elapsed-arrival)/scan));
      if (elapsed>=arrival) scene.classList.add('is-scanning');
      const eased=progress*progress*(3-2*progress);
      // A zero-result scan searches, then drains back to zero. Never show a fictitious score.
      if (target===0) render(18*Math.sin(Math.PI*progress),progress>.88?0:null);
      else render(target*eased,elapsed<arrival?null:target*eased);
      if (elapsed<arrival+scan+900) frame=requestAnimationFrame(tick); else finish();
    };
    frame=requestAnimationFrame(tick);
  });
  scene.classList.remove('is-complete');groups.forEach(group=>{group.hidden=true;});render(0,null);
  reduced.addEventListener('change',()=>{if(reduced.matches&&button.disabled){cancelAnimationFrame(frame);finish();}});
  if(scene.dataset.presentation==='true'||scene.dataset.autostart==='true')button.click();
}

// A soft warm light stays above the record spines while the collection moves beneath it.
for (const shelf of document.querySelectorAll('.record-shelf')) {
  const housing=shelf.closest('.shelf-bleed');if(!housing)continue;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let current=50,target=50,frame=0;
  const tick=()=>{current+=(target-current)*.075;housing.style.setProperty('--shelf-light',current.toFixed(2)+'%');if(Math.abs(target-current)>.05)frame=requestAnimationFrame(tick);else frame=0;};
  const move=value=>{target=value;if(reduced.matches){current=target;housing.style.setProperty('--shelf-light',target+'%');}else if(!frame)frame=requestAnimationFrame(tick);};
  shelf.addEventListener('pointermove',event=>{const bounds=shelf.getBoundingClientRect();move(Math.max(8,Math.min(92,(event.clientX-bounds.left)/bounds.width*100)));},{passive:true});
  shelf.addEventListener('pointerleave',()=>move(50));
  shelf.addEventListener('scroll',()=>move(50+Math.sin(shelf.scrollLeft/650)*22),{passive:true});
}

for (const image of document.querySelectorAll('img.release-cover')) {
  image.addEventListener('error', () => {
    if (!image.src.endsWith('/static/cover-unavailable.svg')) {
      image.src = '/static/cover-unavailable.svg';
      image.alt = 'Cover nicht verfügbar';
    }
  });
}

// Explicit feedback instead of an apparently inert native-validation button.
const connectForm = document.querySelector('[data-discogs-connect]');
if (connectForm) {
  const feedback = connectForm.querySelector('[data-connect-feedback]');
  const button = connectForm.querySelector('button');
  let submitted = false;
  connectForm.addEventListener('invalid', () => {
    feedback.textContent = isGerman
      ? 'Bitte zuerst beide Häkchen setzen und gegebenenfalls den Einladungscode eingeben.'
      : 'Please tick both checkboxes first and enter an invite code if required.';
  }, true);
  connectForm.addEventListener('change', () => {
    if (connectForm.checkValidity()) feedback.textContent = '';
  });
  connectForm.addEventListener('submit', event => {
    if (submitted) {event.preventDefault();return;}
    submitted = true;
    button.disabled = true;
    feedback.textContent = isGerman ? 'Verbindung zu Discogs wird aufgebaut …' : 'Connecting to Discogs …';
  });
  const initiallyDisabled = button.disabled;
  window.addEventListener('pageshow', () => {submitted=false;button.disabled=initiallyDisabled;});
}

// A personal record is a collection presentation, never a fabricated match score.
for (const scene of document.querySelectorAll('[data-collection-vinyl]')) {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let timer;
  const finish = () => { clearTimeout(timer); scene.classList.remove('is-running'); };
  if (!reduced.matches) { scene.classList.add('is-running'); timer = setTimeout(finish, 4000); }
  reduced.addEventListener('change', () => { if (reduced.matches) finish(); });
}

for (const button of document.querySelectorAll('[data-copy-friend]')) {
  button.addEventListener('click', async () => {
    const input = document.querySelector('[data-friend-link]');
    const status = document.querySelector('[data-copy-status]');
    try { await navigator.clipboard.writeText(input.value); status.textContent = isGerman ? 'Link kopiert.' : 'Link copied.'; }
    catch (_) { input.focus(); input.select(); status.textContent = isGerman ? 'Bitte den markierten Link kopieren.' : 'Please copy the selected link.'; }
  });
}

// One cover preview outside the clipping shelf, loaded only for the hovered record.
const shelfPreview = document.querySelector('[data-shelf-preview]');
if (shelfPreview) {
  let activeSpine;
  const image = shelfPreview.querySelector('img');
  image.addEventListener('error', () => { if (!image.src.endsWith('/static/cover-unavailable.svg')) image.src='/static/cover-unavailable.svg'; });
  const hide = () => { shelfPreview.hidden=true;activeSpine=null; };
  const show = spine => {
    activeSpine=spine;
    image.src=spine.dataset.cover;image.alt=spine.dataset.title;
    shelfPreview.querySelector('[data-shelf-title]').textContent=spine.dataset.title;
    shelfPreview.querySelector('[data-shelf-artist]').textContent=spine.dataset.artist;
    shelfPreview.hidden=false;
    const rect=spine.getBoundingClientRect();
    const bounds=document.querySelector('.record-shelf').getBoundingClientRect();
    const width=shelfPreview.offsetWidth,height=shelfPreview.offsetHeight;
    shelfPreview.style.left=Math.max(10,Math.min(innerWidth-width-10,rect.left-width/2))+'px';
    shelfPreview.style.top=Math.max(10,bounds.top-height-10)+'px';
  };
  for (const spine of document.querySelectorAll('[data-spine]')) {
    spine.addEventListener('pointerenter', event => { if(event.pointerType!=='touch')show(spine); });
    spine.addEventListener('pointerleave',hide);
    spine.addEventListener('focus',()=>show(spine));spine.addEventListener('blur',hide);
  }
  window.addEventListener('scroll',hide,{passive:true});
  document.querySelector('.record-shelf').addEventListener('scroll',hide,{passive:true});
  window.addEventListener('resize',hide);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
}

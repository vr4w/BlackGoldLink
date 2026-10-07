const isGerman = document.body.dataset.language === 'de';
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

// One renderer for fictional demos and consented real comparisons.
for (const scene of document.querySelectorAll('[data-blackgold-link]')) {
  const target = Math.max(0, Math.min(100, Number(scene.dataset.target) || 0));
  const number = scene.querySelector('[data-link-number]');
  const scanMasks = [...scene.querySelectorAll('[data-scan-inner]')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const render = value => {
    number.textContent = value.toFixed(1);
    for (const mask of scanMasks) {
      // Radial groove depth: 10% is a narrow outer band, 100% reaches the label.
      mask.setAttribute('r', (121 - 77 * value / 100).toFixed(3));
    }
  };
  if (scene.dataset.interactive !== 'true') { render(target); continue; }
  const button = scene.querySelector('[data-link-start]');
  const comment = scene.querySelector('[data-link-comment]');
  const root = scene.closest('[data-link-results]') || scene;
  const groups = [...root.querySelectorAll('[data-link-reveal]')];
  const cards = [...root.querySelectorAll('[data-discovery-card], [data-wanted-card]')];
  const pool = JSON.parse(scene.dataset.comments || '[]');
  let previousComment = '';
  const timers = [];
  let frame = 0;
  for (const group of groups) group.hidden = true;
  number.textContent = '—';
  render(0);
  number.textContent = '—';
  const later = (action, delay) => {
    if (reducedMotion.matches) action();
    else timers.push(setTimeout(action, delay));
  };
  const finish = () => {
    render(target);
    scene.classList.remove('is-running');
    scene.classList.add('is-complete');
    const choices = pool.filter(text => text !== previousComment);
    previousComment = choices.length ? choices[Math.floor(Math.random() * choices.length)] : (pool[0] || 'Two collections. Plenty to explore.');
    comment.textContent = previousComment;
    groups.forEach((group, index) => later(() => {
      group.hidden = false;
      group.classList.add('revealing');
    }, 200 + index * 220));
    cards.forEach((card, index) => later(() => {
      card.hidden = false;
      card.classList.add('revealing');
    }, 480 + index * 75));
    later(() => {
      button.disabled = false;
      button.textContent = isGerman ? 'BLACKGOLD LINK NOCHMAL' : 'BLACKGOLD LINK AGAIN';
      scene.setAttribute('aria-busy', 'false');
    }, 900);
  };
  button.addEventListener('click', () => {
    timers.splice(0).forEach(clearTimeout);
    cancelAnimationFrame(frame);
    groups.forEach(group => { group.hidden = true; group.classList.remove('revealing'); });
    cards.forEach(card => { card.hidden = true; card.classList.remove('revealing'); });
    scene.classList.remove('is-complete');
    scene.classList.add('is-running');
    scene.setAttribute('aria-busy', 'true');
    button.disabled = true;
    comment.textContent = isGerman ? 'Wir vergleichen die Regale …' : 'Comparing the shelves…';
    render(0);
    if (reducedMotion.matches) { finish(); return; }
    const start = performance.now();
    const tick = now => {
      const progress = Math.min(1, (now - start) / 4000);
      const eased = progress * progress * (3 - 2 * progress);
      render(target * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
      else finish();
    };
    frame = requestAnimationFrame(tick);
  });
  // Presentation plays once on arrival, never loops. Real comparisons remain click-triggered.
  if (scene.dataset.presentation === 'true') button.click();
  // If the preference changes mid-animation, complete immediately.
  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches && button.disabled) {
      cancelAnimationFrame(frame);
      timers.splice(0).forEach(clearTimeout);
      finish();
    }
  });
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

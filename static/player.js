// YouTube is contacted only after this page's explicit consent. No hidden audio.
const musicPanel = document.querySelector('[data-music]');
if (musicPanel) {
  const de = document.body.dataset.language === 'de';
  const say = (en, german) => de ? german : en;
  const title = musicPanel.querySelector('[data-music-title]');
  const message = musicPanel.querySelector('[data-music-status]');
  const frame = musicPanel.querySelector('[data-music-frame]');
  const controls = musicPanel.querySelector('[data-music-controls]');
  const consent = musicPanel.querySelector('[data-music-consent]');
  const volume = musicPanel.querySelector('[data-volume]');
  let player, previous = '', approved = false, busy = false, sdk, requestController;
  let generation = 0, visible = false;
  const showVolume = () => {
    musicPanel.querySelector('[data-volume-output]').textContent = `${volume.value}%`;
    volume.style.setProperty("--volume", `${volume.value}%`);
    player?.setVolume(Number(volume.value));
  };
  showVolume();
  volume.addEventListener('input', showVolume);
  volume.addEventListener('wheel', event => {
    if (!event.deltaY) return;
    event.preventDefault();
    volume.value = String(Math.max(0, Math.min(100, Number(volume.value) + (event.deltaY < 0 ? 5 : -5))));
    showVolume();
  }, {passive:false});
  function loadSDK() {
    if (window.YT?.Player) return Promise.resolve();
    if (sdk) return sdk;
    sdk = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(say('YouTube did not respond. Please try again.', 'YouTube antwortet nicht. Bitte erneut versuchen.'))), 15000);
      window.onYouTubeIframeAPIReady = () => {clearTimeout(timeout); resolve();};
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      script.onerror = () => {clearTimeout(timeout); sdk = undefined; reject(new Error(say('YouTube could not be loaded.', 'YouTube konnte nicht geladen werden.')));};
      document.head.append(script);
    });
    return sdk;
  }
  const observer = new IntersectionObserver(entries => {
    visible = entries[0].intersectionRatio >= .5;
    if (!visible && player?.pauseVideo) player.pauseVideo();
  }, {threshold:[0,.5,1]});
  observer.observe(frame);
  async function next() {
    if (!approved || busy || !musicPanel.open) return;
    busy = true;
    const current = generation;
    musicPanel.querySelector('[data-music-next]').disabled = true;
    message.textContent = say('Looking for a video linked to your records…', 'Suche nach einem Video zu deinen Platten…');
    try {
      requestController = new AbortController();
      const response = await fetch(musicPanel.dataset.endpoint, {method:'POST',headers:{'Accept':'application/json'},body:new URLSearchParams({csrf:musicPanel.dataset.csrf,consent:'yes',previous}),signal:requestController.signal});
      if (response.redirected) throw new Error(say('Please sign in again.', 'Bitte erneut anmelden.'));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || say('Music unavailable.', 'Musik nicht verfügbar.'));
      if (current !== generation) return;
      await loadSDK();
      if (current !== generation || !musicPanel.open) return;
      previous = data.video_id;
      title.textContent = `${data.artist} · ${data.release}`;
      title.title = data.title;
      player?.destroy();
      frame.replaceChildren();
      const iframe = document.createElement('iframe');
      iframe.width = '224'; iframe.height = '200'; iframe.title = 'YouTube · '+data.title;
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.allow = 'autoplay; encrypted-media; fullscreen';
      iframe.allowFullscreen = true;
      iframe.src = `https://www.youtube-nocookie.com/embed/${data.video_id}?enablejsapi=1&origin=${encodeURIComponent(location.origin)}&controls=1&playsinline=1`;
      frame.append(iframe);
      controls.hidden = false;
      player = new YT.Player(iframe, {events:{
        onReady(event) {
          event.target.setVolume(Number(volume.value));
          const bounds=iframe.getBoundingClientRect();
          visible=bounds.top>=0 && bounds.bottom<=innerHeight;
          if (musicPanel.open && !document.hidden && visible) event.target.playVideo();
          message.textContent = '';
        },
        onStateChange(event) {
          musicPanel.classList.toggle('is-playing',event.data === YT.PlayerState.PLAYING);
          if (event.data === YT.PlayerState.PLAYING) message.textContent = '';
          musicPanel.querySelector('[data-music-toggle]').textContent = event.data === YT.PlayerState.PLAYING ? 'Ⅱ' : '▶';
          if (event.data === YT.PlayerState.ENDED && musicPanel.open && visible && !document.hidden) next();
        },
        onError() {message.textContent=say('This video cannot be embedded. Choose another record.', 'Dieses Video ist hier nicht abspielbar. Wähle eine andere Platte.');}
      }});
    } catch (error) {
      if (current === generation && error.name !== 'AbortError') message.textContent = error.message;
    } finally {
      if (current === generation) {busy=false;musicPanel.querySelector('[data-music-next]').disabled=false;}
    }
  }
  musicPanel.querySelector('[data-music-ok]').addEventListener('click', () => {
    approved = true; musicPanel.classList.add('is-active'); consent.hidden = true; controls.hidden = false; volume.value = '10'; showVolume(); next();
  });
  musicPanel.querySelector('[data-music-no]').addEventListener('click', () => { musicPanel.open = false; });
  musicPanel.querySelector('[data-music-next]').addEventListener('click', next);
  musicPanel.querySelector('[data-music-toggle]').addEventListener('click', () => {
    if (!player) {next();return;}
    if (player.getPlayerState() === YT.PlayerState.PLAYING) player.pauseVideo();
    else {player.setVolume(Number(volume.value));player.playVideo();}
  });
  function stop() {
    musicPanel.classList.remove('is-playing', 'is-active');
    generation++;requestController?.abort();busy=false;approved=false;
    player?.destroy();player=undefined;frame.replaceChildren();title.textContent='';message.textContent='';
    controls.hidden=true;consent.hidden=false;
    musicPanel.querySelector('[data-music-next]').disabled=false;
  }
  musicPanel.querySelector('[data-music-stop]').addEventListener('click',stop);
  musicPanel.addEventListener('toggle',() => {if (!musicPanel.open) stop();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden) player?.pauseVideo();});
  // Show the invitation once per login session in this tab when a fresh import is available.
  try {
    const hintKey = 'bgl_music_hint_'+musicPanel.dataset.user+'_'+musicPanel.dataset.session;
    if (musicPanel.dataset.ready === 'true' && !sessionStorage.getItem(hintKey)) {
      sessionStorage.setItem(hintKey, 'shown'); musicPanel.open = true;
    }
  } catch (_) { /* Storage is optional; manual opening still works. */ }
}

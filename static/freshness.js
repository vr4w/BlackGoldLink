// Stop displaying expired imports without reloading or discarding a chat draft.
(() => {
  const main=document.querySelector('main[data-discogs-valid-ms]');
  if(!main)return;
  const lifetime=Number(main.dataset.discogsValidMs);
  if(!Number.isFinite(lifetime)||lifetime<0)return;
  const opened=performance.timeOrigin||Date.now(),started=0,de=document.body.dataset.language==='de';
  let expired=false,timer;
  const check=()=>{
    clearTimeout(timer);
    const elapsed=Math.max(Date.now()-opened,performance.now()-started);
    if(elapsed<lifetime){timer=setTimeout(check,Math.min(lifetime-elapsed,60000));return;}
    if(expired)return;expired=true;
    document.dispatchEvent(new CustomEvent('bgl:data-expired'));
    // Comparison chat is deliberately outside the data removed here.
    for(const element of main.querySelectorAll('.comparison-root > :not(.comparison-conversation),[data-collection-matches],.metrics,.compact-genres,.collection-shelf,.profile-lists,.media-toolbar,.match-update-status,.shelf-preview'))element.remove();
    const notice=document.createElement('p'),link=document.createElement('a');
    notice.className='notice';notice.setAttribute('role','status');
    notice.textContent=de?'Diese Discogs-Daten sind abgelaufen. Deine Nachrichten bleiben erhalten. ':'These Discogs imports have expired. Your messages are kept. ';
    link.href=main.dataset.discogsRefresh;link.className='button small';
    link.textContent=de?'Collection aktualisieren':'Refresh collection';
    notice.append(link);main.prepend(notice);
  };
  document.addEventListener('visibilitychange',check);
  window.addEventListener('pageshow',check);
  window.addEventListener('focus',check);
  check();
})();

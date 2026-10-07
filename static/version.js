// A new build never reloads someone else's active page or discards their draft.
(() => {
  const current=document.body.dataset.version;
  const endpoint=document.body.dataset.versionEndpoint;
  const notice=document.querySelector('[data-version-notice]');
  if(!current||!endpoint||!notice)return;
  const de=document.body.dataset.language==='de';
  let timer,busy=false;
  async function check(){
    if(document.hidden||busy)return;
    busy=true;
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),5000);
    try{
      const response=await fetch(endpoint,{cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});
      // A restart, login challenge or lost connection is not evidence of a new build.
      if(!response.ok||response.redirected)return;
      const data=await response.json();
      if(typeof data.version==='string'&&/^[a-f0-9]{24}$/.test(data.version))notice.hidden=data.version===current;
    }catch(_){}finally{clearTimeout(timeout);busy=false;}
  }
  const schedule=()=>{
    clearTimeout(timer);
    if(!document.hidden)timer=setTimeout(async()=>{await check();schedule();},15000);
  };
  const changedInput=()=>[...document.querySelectorAll('form input,form textarea,form select')].some(input=>{
    if(input.disabled||input.readOnly||['hidden','submit','button','reset','search','range'].includes(input.type))return false;
    if(['checkbox','radio'].includes(input.type))return input.checked!==input.defaultChecked;
    if(input.tagName==='SELECT')return [...input.options].some(option=>option.selected!==option.defaultSelected);
    if(input.type==='file')return Boolean(input.files.length);
    return input.value!==input.defaultValue;
  });
  notice.querySelector('[data-version-reload]').addEventListener('click',()=>{
    if(changedInput()&&!window.confirm(de?'Jetzt neu laden? Ungespeicherte Eingaben auf dieser Seite gehen dabei verloren.':'Reload now? Any unsaved input on this page will be lost.'))return;
    location.reload();
  });
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();schedule();});
  window.addEventListener('focus',()=>{check();schedule();});
  window.addEventListener('pageshow',()=>{check();schedule();});
  window.addEventListener('pagehide',()=>clearTimeout(timer));
  schedule();
})();

// Refresh only the owner table. Search fields and open confirmation forms stay untouched.
(() => {
  const content=document.querySelector('[data-admin-live]'),form=document.querySelector('.admin-search');
  if(!content||!form)return;
  const status=document.querySelector('[data-admin-status]'),de=document.body.dataset.language==='de';
  let busy=false,controller,generation=0,previousHTML='';
  async function refresh(search=false){
    if(document.hidden||(!search&&(busy||content.querySelector('.admin-user-actions[open]'))))return;
    if(search)controller?.abort();
    const token=++generation;busy=true;const currentController=new AbortController();controller=currentController;
    const timeout=setTimeout(()=>currentController.abort(),8000);
    const params=new URLSearchParams(new FormData(form));params.set('page',search?'1':content.dataset.page);
    try{
      const response=await fetch('/admin?'+params,{headers:{Accept:'application/json'},cache:'no-store',signal:currentController.signal});
      if(response.redirected||!response.ok){if(response.status===404)content.replaceChildren();throw Error();}
      const data=await response.json();if(token!==generation)return;
      if(previousHTML!==data.html){const historyOpen=content.querySelector('.admin-history')?.open;content.innerHTML=data.html;if(historyOpen)content.querySelector('.admin-history').open=true;previousHTML=data.html;}
      content.dataset.page=data.page;status.textContent='';
    }catch(error){if(token===generation&&error.name!=='AbortError')status.textContent=de?'Aktualisierung nicht erreichbar. Neuer Versuch folgt.':'Update unavailable. Retrying shortly.';}
    finally{clearTimeout(timeout);if(token===generation)busy=false;}
  }
  form.addEventListener('submit',event=>{event.preventDefault();refresh(true);});
  setInterval(()=>refresh(),10000);
  document.addEventListener('visibilitychange',()=>refresh());window.addEventListener('pageshow',()=>refresh());
})();

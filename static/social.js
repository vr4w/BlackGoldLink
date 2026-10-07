// Incremental, same-origin updates. Keep open panels, searches and chat drafts intact.
(() => {
  const de=document.body.dataset.language==='de', text=(en,ger)=>de?ger:en;
  const panel=document.querySelector('[data-friends]');
  const csrf=document.querySelector('.language-switch input[name="csrf"]')?.value;
  if(!panel||!csrf)return;
  const visible=()=>!document.hidden;
  async function api(url,options={}) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
    try {
      const response=await fetch(url,{...options,signal:controller.signal,cache:'no-store',headers:{Accept:'application/json',...options.headers}});
      if(!response.ok||response.redirected){const error=Error();error.status=response.status;throw error;}
      return await response.json();
    }finally{clearTimeout(timer);}
  }
  panel.querySelector('[data-friends-close]')?.addEventListener('click',()=>{panel.open=false;});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')panel.open=false;});
  document.addEventListener('pointerdown',event=>{if(panel.open&&!panel.contains(event.target))panel.open=false;});
  const searches=[...document.querySelectorAll('[data-friends-search]')];
  const feedback=panel.querySelector('[data-friends-status]');
  const contacts=panel.querySelector('[data-contacts-content]'),badge=panel.querySelector('[data-request-count]');
  let friendsBusy=false,mountBusy=false,heartbeatBusy=false,lastHeartbeat=0,typingAt=0,typingTimer,chatState;
  const replaceIfChanged=(node,html)=>{if(node&&node._renderedHTML!==html){node.innerHTML=html;node._renderedHTML=html;}};
  function renderSearch(form,html){replaceIfChanged(form.parentElement.querySelector('[data-friends-results]'),html);}
  async function mountChat(enabled){
    const shell=document.querySelector('[data-chat-shell]');
    if(!shell)return;
    if(!enabled){
      if(chatState){chatState.disable();chatState=null;}
      return;
    }
    if(shell.querySelector('[data-chat]')){if(!chatState)setupChat(shell.querySelector('[data-chat]'));return;}
    if(mountBusy)return;mountBusy=true;
    try{
      const data=await api('/api/chat/'+shell.dataset.peer+'/widget');
      // Only escaped markup from our own templates, never message HTML.
      const holder=document.createElement('div');holder.innerHTML=data.html;
      shell.replaceWith(holder.firstElementChild);
      setupChat(document.querySelector('[data-chat]'));heartbeat();
    }catch(_){}finally{mountBusy=false;}
  }
  async function refreshFriends(){
    if(friendsBusy||!visible())return;friendsBusy=true;
    const form=searches.find(item=>item.closest('[data-friends]'));
    const query=form?.querySelector('[name="q"]')?.value||'';
    const peer=document.querySelector('[data-chat-shell]')?.dataset.peer||'';
    try{
      const data=await api('/api/friends?q='+encodeURIComponent(query)+'&peer='+encodeURIComponent(peer));
      replaceIfChanged(contacts,data.contacts_html);badge.textContent=data.pending_count;badge.hidden=!data.pending_count;
      if(form&&form.querySelector('[name="q"]').value===query)renderSearch(form,data.html);
      if(!data.enabled)for(const search of searches)renderSearch(search,'');
      const slot=document.querySelector('[data-chat-shell] [data-friend-action-slot]');
      if(slot&&!data.chat_enabled&&slot._renderedHTML!==data.chat_action_html){
        if(data.chat_action_html){const holder=document.createElement('div');holder.innerHTML=data.chat_action_html;const replacement=holder.firstElementChild;replacement._renderedHTML=data.chat_action_html;slot.replaceWith(replacement);}
        else slot.replaceChildren();
      }
      feedback.textContent='';await mountChat(data.chat_enabled);
    }catch(error){
      if(error.status===403||error.status===401||error.status===302){replaceIfChanged(contacts,'');badge.hidden=true;}
      feedback.textContent=text('Connection interrupted. Retrying…','Verbindung unterbrochen. Neuer Versuch läuft …');
    }finally{friendsBusy=false;}
  }
  for(const form of searches){
    let generation=0,delay;
    async function search(){
      const token=++generation,query=form.querySelector('[name="q"]').value;
      try{const data=await api(form.dataset.endpoint+'?q='+encodeURIComponent(query));if(token===generation&&form.querySelector('[name="q"]').value===query)renderSearch(form,data.html);}
      catch(_){if(token===generation)form.parentElement.querySelector('[data-friends-results]').textContent=text('Search unavailable. Try again.','Suche nicht erreichbar. Bitte erneut versuchen.');}
    }
    form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(delay);search();});
    form.querySelector('[name="q"]').addEventListener('input',()=>{generation++;clearTimeout(delay);delay=setTimeout(search,250);});
    form.closest('.contact-discovery')?.addEventListener('toggle',event=>{if(event.target.open)search();});
  }
  document.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-friend-action]');if(!form)return;
    event.preventDefault();const button=form.querySelector('button');if(button.disabled)return;button.disabled=true;
    try{
      const data=await api(form.action,{method:'POST',body:new URLSearchParams(new FormData(form))});
      const slot=form.closest('[data-friend-action-slot]');if(slot)slot.outerHTML=data.html;
      await refreshFriends();
      // Also refresh the standalone discovery page, without replacing its search field.
      for(const search of searches)if(!search.closest('[data-friends]'))search.requestSubmit();
    }catch(_){feedback.textContent=text('Request could not be saved. Try again.','Anfrage konnte nicht gespeichert werden. Bitte erneut versuchen.');}
    finally{button.disabled=false;}
  });
  async function heartbeat(typing=false){
    if(!visible()||heartbeatBusy)return;heartbeatBusy=true;lastHeartbeat=Date.now();
    const form=new URLSearchParams({csrf});
    if(chatState&&chatState.details.open){form.set('peer',chatState.node.dataset.peer);form.set('typing',typing?'yes':'no');}
    try{await api('/api/presence',{method:'POST',body:form});}catch(_){}finally{heartbeatBusy=false;}
  }
  function setupChat(chat){
    const details=chat.closest('details'),log=chat.querySelector('[data-messages]'),form=chat.querySelector('[data-chat-form]');
    const input=form.querySelector('textarea'),button=form.querySelector('button'),status=chat.querySelector('[data-chat-status]'),older=chat.querySelector('[data-chat-older]');
    if(window.matchMedia('(max-width:600px)').matches)details.open=false;
    let after=0,first=0,busy=false,initial=true,sending=false,allowed=true,nonce='',draft='';const seen=new Set();
    function disable(){
      allowed=false;input.disabled=true;button.disabled=true;log.replaceChildren();seen.clear();after=0;first=0;initial=true;
      chat.querySelector('[data-online]').classList.remove('online');chat.querySelector('[data-presence]').textContent=text('Unavailable','Nicht verfügbar');
      status.textContent=text('Chat unavailable. Check sharing and friendship.','Chat nicht verfügbar. Freigabe und Freundschaft prüfen.');
    }
    const state={node:chat,details,disable,poll};chatState=state;
    const append=(messages,prepend=false)=>{
      const nearBottom=log.scrollHeight-log.scrollTop-log.clientHeight<45,oldHeight=log.scrollHeight,fragment=document.createDocumentFragment();
      for(const message of messages){
        if(seen.has(message.id))continue;seen.add(message.id);after=Math.max(after,message.id);first=first?Math.min(first,message.id):message.id;
        const bubble=document.createElement('div');bubble.className='chat-bubble'+(message.sender_id===Number(chat.dataset.self)?' own':'');bubble.textContent=message.body;
        const time=document.createElement('time'),date=new Date(message.created*1000);time.dateTime=date.toISOString();time.textContent=date.toLocaleString(de?'de-DE':'en-GB',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
        bubble.append(time);fragment.append(bubble);
      }
      if(prepend){log.prepend(fragment);log.scrollTop+=log.scrollHeight-oldHeight;}else{log.append(fragment);if(initial||nearBottom)log.scrollTop=log.scrollHeight;}
    };
    async function poll(before=0){
      if(busy||!visible()||!details.open||chatState!==state)return;busy=true;
      try{
        const data=await api(chat.dataset.endpoint+(before?'?before='+before:after?'?after='+after:''));
        if(chatState!==state)return;allowed=true;input.disabled=false;button.disabled=sending;
        append(data.messages,Boolean(before));if(initial||before)older.hidden=!data.older;
        chat.querySelector('[data-online]').classList.toggle('online',data.online);
        chat.querySelector('[data-presence]').textContent=data.typing?text('typing…','tippt gerade …'):data.online?'Online':'Offline';
        if(!sending)status.textContent='';initial=false;
      }catch(error){if([403,404,401,302].includes(error.status))disable();else status.textContent=text('Connection interrupted. Retrying…','Verbindung unterbrochen. Neuer Versuch läuft …');}
      finally{busy=false;}
    }
    older.addEventListener('click',()=>poll(first));
    input.addEventListener('input',()=>{
      typingAt=input.value.trim()?Date.now():0;
      if(Date.now()-lastHeartbeat>1500)heartbeat(Boolean(typingAt));
      clearTimeout(typingTimer);typingTimer=setTimeout(()=>heartbeat(false),5000);
    });
    input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();form.requestSubmit();}});
    form.addEventListener('submit',async event=>{
      event.preventDefault();const body=input.value.trim();if(!body||sending||!allowed)return;
      if(body!==draft||!nonce){nonce=crypto.randomUUID();draft=body;}sending=true;button.disabled=true;
      try{
        await api(chat.dataset.endpoint,{method:'POST',body:new URLSearchParams({csrf,body,nonce})});
        if(input.value.trim()===body){input.value='';typingAt=0;}draft='';nonce='';await heartbeat(false);await poll();
      }catch(_){status.textContent=text('Not sent. Your draft is still here; try again.','Nicht gesendet. Dein Entwurf bleibt erhalten; versuche es erneut.');}
      finally{sending=false;button.disabled=!allowed;input.focus();}
    });
    details.addEventListener('toggle',()=>{if(details.open){heartbeat();poll();}else heartbeat(false);});poll();
  }
  const initialChat=document.querySelector('[data-chat]');if(initialChat)setupChat(initialChat);
  const catchUp=()=>{if(visible()){refreshFriends();heartbeat(Boolean(typingAt&&Date.now()-typingAt<4000));chatState?.poll();}};
  // A visible second browser window receives updates even when the other window has focus.
  setInterval(refreshFriends,3000);
  setInterval(()=>chatState?.poll(),2000);
  setInterval(()=>{if(typingAt&&Date.now()-typingAt<4000&&Date.now()-lastHeartbeat>1500)heartbeat(true);},2000);
  setInterval(()=>heartbeat(Boolean(typingAt&&Date.now()-typingAt<4000)),20000);
  document.addEventListener('visibilitychange',catchUp);window.addEventListener('focus',catchUp);window.addEventListener('pageshow',catchUp);
  catchUp();
})();

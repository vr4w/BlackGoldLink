import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../static/freshness.js',import.meta.url),'utf8');
let now=0,removed=0,notice,dispatched=0,selector;
const listeners={},timers=new Map(),draft={value:'Unsaved hello',removed:false};
const main={dataset:{discogsValidMs:'5000',discogsRefresh:'/app'},querySelectorAll:s=>{selector=s;return [{remove:()=>removed++}];},prepend:n=>notice=n};
const context={Date:{now:()=>100000+now},performance:{timeOrigin:100000,now:()=>now},CustomEvent:class{},
 document:{body:{dataset:{language:'en'}},querySelector:()=>main,querySelectorAll:()=>[],dispatchEvent:()=>dispatched++,addEventListener:(n,fn)=>listeners[n]=fn,
 createElement:()=>({setAttribute:()=>{},append(child){this.child=child;}})},
 window:{addEventListener:(n,fn)=>listeners[n]=fn},setTimeout:(fn,ms)=>{timers.set(ms,fn);return ms;},clearTimeout:ms=>timers.delete(ms)};
vm.runInNewContext(source,context);
assert.equal(removed,0);assert(timers.has(5000));
now=5100;listeners.visibilitychange();
assert.equal(removed,1);assert.equal(dispatched,1);
assert(selector.includes(':not(.comparison-conversation)'));
assert.equal(notice.child.href,'/app');assert(notice.textContent.includes('expired'));
assert.equal(draft.value,'Unsaved hello');assert.equal(draft.removed,false);
listeners.pageshow();assert.equal(removed,1,'expiry is idempotent');
console.log('Open-tab expiry, tab return, one-time clearing and chat exclusion verified.');

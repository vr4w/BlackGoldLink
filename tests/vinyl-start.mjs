// Exercise the real scene controller with a delayed renderer, without a browser/GPU.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../static/app.js',import.meta.url),'utf8');
const controller=source.slice(source.indexOf('for (const scene of document.querySelectorAll(\'[data-blackgold-link]\'))'),source.indexOf('// A soft warm light'))
 .replace("import('./vinyl3d.js')","loadRenderer()");
function classes(...initial){const values=new Set(initial);return {add:(...v)=>v.forEach(x=>values.add(x)),remove:(...v)=>v.forEach(x=>values.delete(x)),contains:x=>values.has(x),toggle:(x,on)=>on?values.add(x):values.delete(x)};}
function fixture({forced=false}={}){
 const listeners={},docListeners={},buttonHandlers={},timers=new Map(),frames=[],updates=[];
 let resolveRenderer,rejectRenderer,created=0,bottom=800;
 const pending=new Promise((resolve,reject)=>{resolveRenderer=resolve;rejectRenderer=reject;});
 const button={disabled:false,addEventListener:(name,fn)=>buttonHandlers[name]=fn,click:()=>buttonHandlers.click()};
 const number={textContent:''},comment={textContent:''};
 const scene={dataset:{target:'70.7',interactive:'true',presentation:'true',comments:'["Done"]'},classList:classes('is-preparing'),offsetWidth:100,
  querySelector:s=>s==='[data-link-number]'?number:s==='[data-link-start]'?button:s==='[data-link-comment]'?comment:null,
  querySelectorAll:()=>[],closest:()=>null,setAttribute:()=>{},getBoundingClientRect:()=>({bottom})};
 const body={classList:classes()};
 const document={body,hidden:false,querySelectorAll:()=>[scene],addEventListener:(name,fn)=>docListeners[name]=fn,dispatchEvent:()=>{}};
 const context={document,isGerman:false,URLSearchParams,location:{search:forced?'?graphics=2d':''},matchMedia:()=>({matches:false,addEventListener:()=>{}}),
  performance:{now:()=>0},scrollY:0,innerHeight:720,window:{addEventListener:(name,fn)=>listeners[name]=fn},
  requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},cancelAnimationFrame:()=>{},
  setTimeout:(fn,ms)=>{timers.set(ms,fn);return ms;},clearTimeout:id=>timers.delete(id),
  loadRenderer:()=>pending,CustomEvent:class{}};
 vm.runInNewContext(controller,context);
 const ready=()=>resolveRenderer({createVinylScene:()=>{created++;return {update:state=>updates.push({...state}),dispose:()=>{}};}});
 return {scene,body,button,number,frames,updates,timers,ready,fail:()=>rejectRenderer(Error('GPU unavailable')),created:()=>created,expire:()=>docListeners['bgl:data-expired'](),scroll:y=>{bottom=y;listeners.scroll();}};
}
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
const cold=fixture();
assert(cold.scene.classList.contains('is-preparing'));
assert(!cold.scene.classList.contains('is-running'));
assert.equal(cold.frames.length,0,'no 2D timeline while 3D is loading');
cold.ready();await flush();
assert.equal(cold.created(),1);assert(cold.scene.classList.contains('is-running'));
assert.equal(cold.frames.length,1);assert.equal(cold.updates.at(-1).elapsedMs,0,'3D starts from frame zero');
cold.frames[0](12400);assert.equal(cold.button.textContent,'BlackGoldLink again, please!');
cold.scroll(650);assert(!cold.body.classList.contains('bgl-header-visible'),'small scroll keeps the cinematic header hidden');
cold.scroll(267);assert(cold.body.classList.contains('bgl-header-visible'));
cold.scroll(650);assert(!cold.body.classList.contains('bgl-header-visible'),'scrolling back restores central logo');
const expired=fixture();expired.expire();expired.ready();await flush();assert.equal(expired.frames.length,0);assert.equal(expired.created(),0,'an expired import cannot start a late renderer');
const timeout=fixture();timeout.timers.get(8000)();await flush();
assert(timeout.scene.classList.contains('is-running'));
timeout.ready();await flush();assert.equal(timeout.created(),0,'late renderer cannot replace the running fallback');
const failed=fixture();failed.fail();await flush();assert(failed.scene.classList.contains('is-running'));
const forced=fixture({forced:true});await flush();assert(forced.scene.classList.contains('is-running'));assert.equal(forced.created(),0);
console.log('Cold-load readiness, one timeline, fallback timeout/failure and scene-bound header verified.');

import * as THREE from './vendor/three/three.module.js';
import {ARM_LENGTH,RECORD_ANGULAR_SPEED,needlePoint,tonearmPivot} from './tonearm-motion.js';

// Enhances the existing score DOM. No data fetching, account state or prototype UI.
export function createVinylScene(element,{onFailure=()=>{}}={}) {
 const host=element.querySelector('[data-vinyl-3d]');
 const names=[element.dataset.nameA||'',element.dataset.nameB||''];
 const reduced={matches:false},armsEnabled=true;
 const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
 const ease=x=>{x=clamp(x);return x*x*(3-2*x)},mix=THREE.MathUtils.lerp;
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.95;
 renderer.shadowMap.enabled=false;renderer.debug.onShaderError=()=>{throw new Error('Vinyl shader unavailable');};host.append(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color('#101111');
const camera=new THREE.PerspectiveCamera(35,1,.05,80);
const key=new THREE.DirectionalLight('#fff1da',1.5);key.position.set(-3,7,6);scene.add(key);
const fill=new THREE.DirectionalLight('#b6cedd',.5);fill.position.set(6,3,-2);scene.add(fill);scene.add(new THREE.HemisphereLight('#b6c0bd','#111410',.22));
// A self-contained studio reflection environment. These are light sources in the
// material's environment, not transparent overlays or moving stripes on the page.
const room=new THREE.Scene();room.background=new THREE.Color('#080a09');
function softbox(x,y,z,w,h,color,intensity){
 const material=new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(intensity),side:THREE.DoubleSide,toneMapped:false});
 const panel=new THREE.Mesh(new THREE.PlaneGeometry(w,h),material);panel.position.set(x,y,z);panel.lookAt(0,0,0);room.add(panel);
}
softbox(-4,6,3,3,7,'#fff4de',5);softbox(5,4,-2,2,5,'#c7dfeb',2.7);softbox(0,7,-5,6,2,'#fff8eb',2.1);
const pmrem=new THREE.PMREMGenerator(renderer);const env=pmrem.fromScene(room,.12,.1,40);scene.environment=env.texture;scene.environmentIntensity=.45;pmrem.dispose();
room.traverse(object=>{if(object.isMesh){object.geometry.dispose();object.material.dispose();}});


// One shared 2k texture set: microscopic concentric grooves, paper variation,
// and circular anisotropy. Geometry stays flat; the record is never a domed disc.
function grooveTextures(){
 const size=2048, bump=new Uint8Array(size*size*4), rough=new Uint8Array(size*size*4), tangent=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const dx=(x-size/2)/(size/2),dy=(y-size/2)/(size/2),r=Math.hypot(dx,dy),a=Math.atan2(dy,dx),i=(y*size+x)*4;
  const music=r>.34&&r<.975, trackGap=Math.pow(.5+.5*Math.cos(r*57),36);
  const groove=music?Math.sin(r*1410+Math.sin(a*2)*.06)*.5+.5:0.5;
  const noise=((Math.imul(x+31,y+17)^Math.imul(x,73856093))>>>0)%101/101;
  const height=music?105+groove*26-trackGap*12+noise*1.5:126;
  bump[i]=bump[i+1]=bump[i+2]=height;bump[i+3]=255;
  const matte=music?155+groove*13+trackGap*18:115;
  rough[i]=rough[i+1]=rough[i+2]=matte;rough[i+3]=255;
  tangent[i]=128+Math.cos(a)*127;tangent[i+1]=128+Math.sin(a)*127;tangent[i+2]=255;tangent[i+3]=255;
 }
 function texture(data){const t=new THREE.DataTexture(data,size,size,THREE.RGBAFormat);t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.generateMipmaps=true;t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());t.needsUpdate=true;return t;}
 return {bump:texture(bump),rough:texture(rough),tangent:texture(tangent)};
}
const textures=grooveTextures();
// Place each glyph along a true arc; keep the name large and inside the paper.
function arcText(ctx,text,radius,centre,bottom,fontSize,weight='bold'){
 let size=fontSize,characters=[...text],widths,total;
 do{ctx.font=`${weight} ${size}px Arial`;widths=characters.map(ch=>ctx.measureText(ch).width+size*.045);total=widths.reduce((a,b)=>a+b,0);if(total<=radius*Math.PI*.9||size<=44)break;size-=2;}while(true);
 const direction=bottom?-1:1;let angle=centre-direction*total/(2*radius);
 ctx.textAlign='center';ctx.textBaseline='middle';
 for(let i=0;i<characters.length;i++){
  angle+=direction*widths[i]/(2*radius);ctx.save();ctx.translate(512+Math.cos(angle)*radius,512+Math.sin(angle)*radius);ctx.rotate(angle+(bottom?-Math.PI/2:Math.PI/2));ctx.fillText(characters[i],0,0);ctx.restore();angle+=direction*widths[i]/(2*radius);
 }
}
function paperTexture(name,side,color){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1024;const ctx=canvas.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,1024,1024);
 let seed=173;for(let i=0;i<18000;i++){seed=(seed*1664525+1013904223)>>>0;const x=seed%1024;seed=(seed*1664525+1013904223)>>>0;const y=seed%1024;ctx.fillStyle=i%2?'#ffffff0c':'#0000000a';ctx.fillRect(x,y,1.5,1.5);}
 ctx.strokeStyle='#171b1740';ctx.lineWidth=1;for(const radius of [443,451]){ctx.beginPath();ctx.arc(512,512,radius,0,Math.PI*2);ctx.stroke();}
 ctx.fillStyle='#252b27';
 arcText(ctx,name.toUpperCase(),340,-Math.PI/2,false,90);
 arcText(ctx,'33 ⅓ RPM  ·  STEREO',362,Math.PI/2,true,34,'normal');
 ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='bold 86px Arial';ctx.fillText(side,512,680);
 const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=4;return texture;
}
const records=[];
function makeRecord(name,side,color){
 const group=new THREE.Group();scene.add(group);const rotor=new THREE.Group();group.add(rotor);
 // Cross-section includes the centre hole, a tiny raised outer lip and a bevel.
 const section=[[.043,-.018],[1.695,-.018],[1.72,-.009],[1.724,0],[1.72,.015],[1.695,.021],[.043,.021],[.043,-.018]].map(([r,h])=>new THREE.Vector2(r,h));
 const body=new THREE.Mesh(new THREE.LatheGeometry(section,256),new THREE.MeshPhysicalMaterial({color:'#030404',roughness:.42,metalness:0,clearcoat:.06,clearcoatRoughness:.32,envMapIntensity:.3,specularIntensity:.3}));body.castShadow=false;body.receiveShadow=false;rotor.add(body);
 const uniforms={depth:{value:0},glow:{value:0}};
 const material=new THREE.MeshPhysicalMaterial({color:'#030404',metalness:0,specularIntensity:.28,roughness:.52,roughnessMap:textures.rough,bumpMap:textures.bump,bumpScale:.0045,clearcoat:.07,clearcoatRoughness:.32,anisotropy:.7,anisotropyMap:textures.tangent,envMapIntensity:.32});
 material.onBeforeCompile=shader=>{
  shader.uniforms.uDepth=uniforms.depth;shader.uniforms.uGlow=uniforms.glow;
  shader.vertexShader='varying vec2 vRecordUv;\n'+shader.vertexShader;
  shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>','#include <uv_vertex>\nvRecordUv=uv;');
  shader.fragmentShader='varying vec2 vRecordUv;uniform float uDepth;uniform float uGlow;\n'+shader.fragmentShader;
  shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
   float radius=length(vRecordUv-.5)*2.;
   float grooveArea=smoothstep(.34,.35,radius)*(1.-smoothstep(.97,.985,radius));
   float boundary=.975-uDepth*.63;
   float filled=smoothstep(boundary-.003,boundary+.003,radius)*grooveArea*step(.0001,uDepth);
   diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.052,.054,.050),filled*(1.-uGlow*.5));
   float grooveDetail=1.-smoothstep(1.,3.,fwidth(radius)*1410.);
   diffuseColor.rgb*=1.-grooveArea*(.04+.04*sin(radius*1410.)*grooveDetail);`);
  shader.fragmentShader=shader.fragmentShader.replace('#include <roughnessmap_fragment>','#include <roughnessmap_fragment>\nroughnessFactor=mix(roughnessFactor,.7,filled*(1.-uGlow*.5));');
  shader.fragmentShader=shader.fragmentShader.replace('#include <emissivemap_fragment>',`#include <emissivemap_fragment>
   float front=exp(-pow((radius-boundary)*110.,2.))*grooveArea*step(.001,uDepth);
   float fineGrooves=.65+.35*sin(radius*1410.)*grooveDetail;
   totalEmissiveRadiance+=vec3(1.1,.57,.13)*uGlow*(front*1.0+filled*.06)*fineGrooves;`);
 };
 const faceGeometry=new THREE.RingGeometry(.043,1.695,256,1);faceGeometry.rotateX(-Math.PI/2);faceGeometry.computeTangents();
 const face=new THREE.Mesh(faceGeometry,material);face.position.y=.022;face.receiveShadow=false;rotor.add(face);
 const labelGeo=new THREE.RingGeometry(.043,.525,128);labelGeo.rotateX(-Math.PI/2);
 const label=new THREE.Mesh(labelGeo,new THREE.MeshStandardMaterial({map:paperTexture(name,side,color),roughness:.92,metalness:0}));label.position.y=.027;rotor.add(label);
 records.push({group,rotor,uniforms,face,label});return group;
}
const a=makeRecord(names[0],'A','#d2c6a5'),b=makeRecord(names[1],'B','#89a2ac');
// Stationary tonearm assemblies sit above each spinning record. The stylus
// intersects a constant-length pivot circle and the current groove radius.
function makeTonearm(record,mount){
 const side=1; // Identical right-handed hardware on both records.
 const assembly=new THREE.Group();record.add(assembly);
 const chrome=new THREE.MeshPhysicalMaterial({color:'#a2aaa9',metalness:.92,roughness:.27,envMapIntensity:1.4,transparent:true});
 const graphite=new THREE.MeshStandardMaterial({color:'#141a18',metalness:.55,roughness:.5,transparent:true});
 const brass=new THREE.MeshStandardMaterial({color:'#b2924b',metalness:.8,roughness:.35,transparent:true});
 const materials=[chrome,graphite,brass];
 function mesh(geometry,material,parent,x,y,z){const part=new THREE.Mesh(geometry,material);part.position.set(x,y,z);parent.add(part);return part;}
 const {x:px,z:pz}=tonearmPivot(mount);
 mesh(new THREE.CylinderGeometry(.15,.18,.075,40),graphite,assembly,px,.055,pz);
 mesh(new THREE.CylinderGeometry(.1,.1,.14,32),chrome,assembly,px,.14,pz);
 const bearing=mesh(new THREE.TorusGeometry(.11,.014,10,48),chrome,assembly,px,.22,pz);bearing.rotation.x=Math.PI/2;
 const rig=new THREE.Group();rig.position.set(px,.16,pz);assembly.add(rig);
 const curve=new THREE.CatmullRomCurve3([new THREE.Vector3(0,.055,-.30),new THREE.Vector3(0,.055,0),new THREE.Vector3(side*.085,.05,.72),new THREE.Vector3(-side*.10,0,1.75),new THREE.Vector3(0,-.01,ARM_LENGTH-.20)]);
 mesh(new THREE.TubeGeometry(curve,54,.024,10,false),chrome,rig,0,0,0);
 const weight=mesh(new THREE.CylinderGeometry(.095,.095,.19,28),graphite,rig,0,.055,-.32);weight.rotation.x=Math.PI/2;
 const weightTrim=mesh(new THREE.CylinderGeometry(.098,.098,.015,28),chrome,rig,0,.055,-.41);weightTrim.rotation.x=Math.PI/2;
 mesh(new THREE.BoxGeometry(.145,.022,.30),graphite,rig,0,-.028,ARM_LENGTH-.13);
 for(const x of [-.043,.043])mesh(new THREE.BoxGeometry(.013,.008,.18),chrome,rig,x,-.013,ARM_LENGTH-.13);
 mesh(new THREE.BoxGeometry(.09,.055,.15),brass,rig,0,-.067,ARM_LENGTH-.04);
 const needle=mesh(new THREE.CylinderGeometry(.0025,.004,.035,8),chrome,rig,0,-.1195,ARM_LENGTH);
 mesh(new THREE.SphereGeometry(.006,8,6),brass,rig,0,-.137,ARM_LENGTH);
 const finger=mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(.06,-.018,ARM_LENGTH-.14),new THREE.Vector3(.14,.025,ARM_LENGTH-.12),new THREE.Vector3(.16,.07,ARM_LENGTH-.12)]),12,.008,6,false),chrome,rig,0,0,0);
 return {assembly,rig,materials,mount,pivot:{x:px,z:pz}};
}
const tonearms=[makeTonearm(a,1),makeTonearm(b,-1)];
function moveTonearms(depth,elapsed){
 const reveal=reduced.matches?1:ease((elapsed-3.05)/.75);
 const swing=reduced.matches?1:ease((elapsed-3.2)/.95);
 const lower=reduced.matches?1:ease((elapsed-4.05)/.75);
 for(const arm of tonearms){
  const point=needlePoint(arm.mount,depth);
  const angle=Math.atan2(point.x-arm.pivot.x,point.z-arm.pivot.z);
  arm.assembly.visible=armsEnabled&&reveal>0;
  for(const material of arm.materials)material.opacity=reveal;
  arm.rig.rotation.set(-.12*(1-lower),mix(arm.mount>0?0:-Math.PI,angle,swing),0,'YXZ');
 }
}
// A narrow platter rim with three dot rows and a local orange strobe lamp.
// Slow apparent dot drift simulates stroboscopic sampling without screen flashes.
function makeStrobe(record,side){
 const rim=new THREE.Group();record.add(rim);
 const metal=new THREE.MeshPhysicalMaterial({color:'#161c1b',metalness:.85,roughness:.38,envMapIntensity:.6});
 const rail=new THREE.Mesh(new THREE.RingGeometry(1.725,1.79,256),metal);rail.rotation.x=-Math.PI/2;rail.position.y=-.012;rim.add(rail);
 const lip=new THREE.Mesh(new THREE.CylinderGeometry(1.79,1.79,.023,192,1,true),metal);lip.position.y=-.023;rim.add(lip);
 const beam=new THREE.Vector3(side*1.742,-.007,.25),uLight={value:new THREE.Vector3()},uLevel={value:1},rows=[];
 const material=new THREE.ShaderMaterial({uniforms:{uLight,uLevel},vertexShader:`varying vec3 vWorld;
  void main(){vec4 p=instanceMatrix*vec4(position,1.);vec4 world=modelMatrix*p;vWorld=world.xyz;gl_Position=projectionMatrix*viewMatrix*world;}`,
  fragmentShader:`varying vec3 vWorld;uniform vec3 uLight;uniform float uLevel;
  void main(){float distanceToLamp=distance(vWorld,uLight);float illumination=exp(-distanceToLamp*distanceToLamp*23.);vec3 color=vec3(.017,.022,.020)+vec3(1.8,.28,.035)*illumination*uLevel;gl_FragColor=vec4(color,1.);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  }`});
 const dotGeometry=new THREE.SphereGeometry(.012,6,4);dotGeometry.scale(1,.35,1);
 const matrix=new THREE.Matrix4();
 for(let row=0;row<3;row++){
  const count=96+row*4,radius=1.737+row*.018;
  const dots=new THREE.InstancedMesh(dotGeometry,material,count);
  for(let i=0;i<count;i++){const angle=i/count*Math.PI*2;matrix.makeTranslation(Math.cos(angle)*radius,-.006,Math.sin(angle)*radius);dots.setMatrixAt(i,matrix);}
  dots.instanceMatrix.needsUpdate=true;rim.add(dots);rows.push(dots);
 }
 const housing=new THREE.Mesh(new THREE.BoxGeometry(.11,.055,.14),new THREE.MeshStandardMaterial({color:'#101514',metalness:.6,roughness:.45}));housing.position.set(side*1.88,.018,.32);rim.add(housing);
 const diode=new THREE.Mesh(new THREE.SphereGeometry(.014,12,8),new THREE.MeshBasicMaterial({color:'#ff6d28'}));diode.position.set(side*1.84,.038,.285);rim.add(diode);
 const lamp=new THREE.SpotLight('#ff7628',.1,.6,.5,.9,2);lamp.position.set(side*1.855,.095,.30);lamp.target.position.copy(beam);rim.add(lamp,lamp.target);
 return {record,rows,beam,uLight,uLevel,lamp};
}
const strobes=[makeStrobe(a,-1),makeStrobe(b,1)];

 let disposed=false,last=performance.now(),lastDraw=0,lastState=null,arrived=false;
 const geometries=new Set(),materials=new Set();
 function resize(){
  if(disposed)return;const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  if(lastState)update(lastState,true);
 }
 function update(state,force=false){
  if(disposed)return;lastState=state;reduced.matches=state.reduced;
  const now=performance.now();if(!force&&state.running&&now-lastDraw<1000/45)return;
  const dt=Math.min((now-last)/1000,.045);last=now;lastDraw=now;
  const elapsed=state.elapsedMs/1000,complete=state.complete,playing=state.running,depth=state.depth/100;
  for(const record of records){record.uniforms.depth.value=depth;record.uniforms.glow.value=playing?Math.sin(Math.PI*clamp((elapsed-4.8)/6.8)):0;}
  moveTonearms(depth,complete?13:elapsed);
  const arrival=complete||reduced.matches?1:ease((elapsed-1.6)/2.4);
  const mobile=host.clientWidth<700,offset=mobile?.9:1.48;
  a.position.set(mix(-7,-offset,arrival),.12,.13);b.position.set(mix(7,offset,arrival),-.02,-.05);
  a.rotation.x=b.rotation.x=.7;
  const speed=playing&&elapsed>2?RECORD_ANGULAR_SPEED*ease((elapsed-2)/1)*(1.-ease((elapsed-11.6)/.8)):0;
  if(!reduced.matches)for(const record of records)record.rotor.rotation.y-=dt*speed;
  const distance=mobile?7.9/(2*Math.tan(THREE.MathUtils.degToRad(17.5))*camera.aspect):Math.hypot(4.8,7.8);
  const wide=new THREE.Vector3(mobile?0:.12,Math.sin(.552)*distance,Math.cos(.552)*distance);
  const close=new THREE.Vector3(-1.7,3,2.7),look=new THREE.Vector3(0,0,0);
  if(complete||reduced.matches||elapsed>=4)camera.position.copy(wide);
  else{const t=ease((elapsed-.6)/3.4);camera.position.copy(close).lerp(wide,t);look.set(mix(-1.35,0,t),0,0);}
  camera.lookAt(look);camera.updateMatrixWorld();scene.updateMatrixWorld();
  for(const strobe of strobes){strobe.uLight.value.copy(strobe.beam).applyMatrix4(strobe.record.matrixWorld);strobe.uLevel.value=playing?1:.75;strobe.lamp.intensity=playing?.10:.025;if(!reduced.matches&&playing&&elapsed>2)strobe.rows.forEach((row,i)=>row.rotation.y+=dt*[.065,-.075,.12][i]);}
  renderer.render(scene,camera);
  if(!arrived){element.classList.add('has-vinyl-3d');arrived=true;}
 }
 function dispose(){
  if(disposed)return;disposed=true;observer.disconnect();element.classList.remove('has-vinyl-3d');
  renderer.domElement.removeEventListener('webglcontextlost',lost);
  scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);if(object.material)for(const material of [].concat(object.material))materials.add(material);});
  for(const material of materials){for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose();}
  for(const geometry of geometries)geometry.dispose();for(const texture of Object.values(textures))texture.dispose();
  env.dispose();renderer.dispose();renderer.domElement.remove();
 }
 function lost(event){event.preventDefault();dispose();onFailure();}
 renderer.domElement.addEventListener('webglcontextlost',lost);
 const observer=new ResizeObserver(resize);observer.observe(host);resize();
 return {update,dispose};
}

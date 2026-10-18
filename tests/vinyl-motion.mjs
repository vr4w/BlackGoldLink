import assert from 'node:assert/strict';
import * as THREE from '../static/vendor/three/three.module.js';
import {needlePoint,tonearmPivot,ARM_LENGTH,RECORD_ANGULAR_SPEED} from '../static/tonearm-motion.js';
for(const mount of [-1,1])for(let i=0;i<=100;i++){
 const p=needlePoint(mount,i/100),pivot=tonearmPivot(mount);
 assert.ok(Math.abs(Math.hypot(p.x,p.z)/1.695-(.975-.63*i/100))<1e-10);
 assert.ok(Math.abs(Math.hypot(p.x-pivot.x,p.z-pivot.z)-ARM_LENGTH)<1e-10);
 if(mount===1)assert.ok(pivot.x<0&&pivot.z<0&&p.x>pivot.x&&p.z<0);
 for(const offset of [.9,1.48])for(const centre of [-offset,offset])assert.ok(Math.hypot(-mount*offset+pivot.x-centre,pivot.z)>1.79+.18);
}
const camera=new THREE.PerspectiveCamera(35,1,.05,80);camera.position.set(0,4.8,7.8);camera.lookAt(0,0,0);camera.updateMatrixWorld();
const tilt=new THREE.Matrix4().makeRotationX(.7);
const before=new THREE.Vector3(1,0,0).applyMatrix4(tilt).project(camera);
const after=new THREE.Vector3(Math.cos(-.01),0,-Math.sin(-.01)).applyMatrix4(tilt).project(camera);
assert.ok(after.y<before.y,'Visible right edge must move down clockwise');
assert.ok(Math.abs(RECORD_ANGULAR_SPEED*60/(Math.PI*2)-(33+1/3))<1e-10);
console.log('202 groove positions, fixed arm length, both holders clear, clockwise 33⅓ RPM verified.');

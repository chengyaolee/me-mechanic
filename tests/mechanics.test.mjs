import{test}from'node:test';import assert from'node:assert/strict';import fs from'node:fs';
import{crankPose,blockers,revealProgress}from'../src/mechanics.mjs';
const {parts}=JSON.parse(fs.readFileSync(new URL('../src/aventador-parts.json',import.meta.url)));
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
test('every piston travels the 76.4 mm stroke and its rod keeps length',()=>{
 const pistons=parts.filter(p=>p.kin?.type==='piston');assert.equal(pistons.length,12);
 for(const p of pistons){const d=[];for(let t=0;t<Math.PI*2;t+=.01){const{pin,wrist}=crankPose(p.kin,t);assert.ok(Math.abs(dist(pin,wrist)-p.kin.rod)<1e-9);d.push(dist(wrist,p.kin.centre));}
  assert.ok(Math.abs(Math.max(...d)-Math.min(...d)-.0764)<1e-4,p.id);}
});
test('part ids are unique and removal prerequisites exist without cycles',()=>{
 const ids=new Map(parts.map(p=>[p.id,p]));assert.equal(ids.size,parts.length);
 for(const p of parts)for(const b of p.blockedBy)assert.ok(ids.has(b),`${p.id} -> ${b}`);
 const state=new Map();const visit=id=>{if(state.get(id)===2)return;assert.notEqual(state.get(id),1,`cycle at ${id}`);state.set(id,1);ids.get(id).blockedBy.forEach(visit);state.set(id,2);};
 parts.forEach(p=>visit(p.id));
});
test('removal checks only installed prerequisites',()=>{assert.deepEqual(blockers({blockedBy:['head','cover']},['head']),['cover']);assert.deepEqual(blockers({blockedBy:['head']},['head']),[]);});
test('upper engine layers lead the reveal and all return to rest',()=>{assert.equal(revealProgress(0,1.8),0);assert.equal(revealProgress(1,.3),1);assert.ok(revealProgress(.3,1.8)>revealProgress(.3,.3));});

test('focus keeps selected internals and glass solid through every peel layer', async()=>{
 const {partAppearance}=await import('../src/mechanics.mjs');
 for(const p of parts) {
  assert.deepEqual(partAppearance(p,p.id,true),{alpha:1,edgeOpacity:1});
  const faded=partAppearance(p,'other-component',false);
  assert.ok(faded.alpha>0&&faded.alpha<.05);
  assert.ok(faded.edgeOpacity>0&&faded.edgeOpacity<.1);
  assert.equal(partAppearance(p,null,false).alpha,p.tone==='glass'?.28:1);
 }
});

test('every listed component has unique nonempty GLB geometry and valid coverage', async()=>{
 await import('../scripts/verify-parts.mjs');
});

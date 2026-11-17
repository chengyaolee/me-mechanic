import{test}from'node:test';import assert from'node:assert/strict';import fs from'node:fs';
import{crankPose,blockers,revealProgress,ratios,finalDrive,frontRadius,rearRadius,drivetrain,advanceMotion}from'../src/mechanics.mjs';
const {parts}=JSON.parse(fs.readFileSync(new URL('../src/aventador-parts.json',import.meta.url)));
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
test('every piston travels the 76.4 mm stroke and its rod keeps length',()=>{
 const pistons=parts.filter(p=>p.kin?.type==='piston');assert.equal(pistons.length,12);
 for(const p of pistons){const d=[];for(let t=0;t<Math.PI*2;t+=.01){const{pin,wrist}=crankPose(p.kin,t);assert.ok(Math.abs(dist(pin,wrist)-p.kin.rod)<1e-9);d.push(dist(wrist,p.kin.centre));}
  assert.ok(Math.abs(Math.max(...d)-Math.min(...d)-.0764)<1e-4,p.id);}
});
test('crank, pistons and wheels match the readouts in real time, even at low frame rates',()=>{
 const blank=()=>({theta:0,shaft:0,frontWheel:0,rearWheel:0});
 const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-7,`${actual} != ${expected}`);
 for(const rpm of [0,10,900,3600,7500])for(let gear=0;gear<ratios.length;gear++){
  const speeds=drivetrain(rpm,gear);
  for(const frames of [1,12,60,144]){
   const motion=blank();
   for(let frame=0;frame<frames;frame++)advanceMotion(motion,1/frames,rpm,gear,false);
   near(motion.theta/(2*Math.PI)*60,rpm);
   near(-motion.shaft/(2*Math.PI)*60,speeds.shaftRPM);
   near(motion.frontWheel/(2*Math.PI)*60,speeds.frontWheelRPM);
   near(motion.rearWheel/(2*Math.PI)*60,speeds.rearWheelRPM);
  }
  near(speeds.frontWheelRPM*frontRadius,speeds.rearWheelRPM*rearRadius);
  near(speeds.roadSpeed,speeds.rearWheelRPM*2*Math.PI*rearRadius*60/1000);
  near(speeds.rearWheelRPM,gear?rpm/ratios[gear]/finalDrive:0);
  // Measure mean speed over a complete crank revolution (a partial cycle has a different average).
  for(const p of parts.filter(p=>p.kin?.type==='piston')){
   let previous=crankPose(p.kin,0).wrist,distance=0;
   const steps=2000,duration=rpm?60/rpm:1,motion=blank();
   for(let i=0;i<steps;i++){
    advanceMotion(motion,duration/steps,rpm,gear,false);
    const wrist=crankPose(p.kin,motion.theta).wrist;distance+=dist(wrist,previous);previous=wrist;
   }
   assert.ok(Math.abs(distance/duration-speeds.pistonSpeed)<.0001,`${p.id}: ${distance} vs ${speeds.pistonSpeed}`);
  }
 }
 const slow=blank();advanceMotion(slow,60,7500,3,true);
 near(slow.theta/(2*Math.PI),10);
 near(slow.rearWheel/(2*Math.PI),10/ratios[3]/finalDrive);
 const stopped={...slow};advanceMotion(slow,1,0,3,true);assert.deepEqual(slow,stopped);
 assert.ok(drivetrain(3600,7).roadSpeed>drivetrain(3600,1).roadSpeed);
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

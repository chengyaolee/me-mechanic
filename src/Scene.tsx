import {Suspense,useRef,useEffect,useMemo} from 'react';
import {Canvas,useFrame,events} from '@react-three/fiber';
import {CameraControls,Edges,Html,Line,PerspectiveCamera,OrthographicCamera,useGLTF} from '@react-three/drei';
import * as T from 'three';
import {parts,MODEL_URL,type Part} from './parts';
import {useStore} from './store';
import {ratios,revealProgress,crankPose,partAppearance,prioritizeFocusedHits} from './mechanics.mjs';
const vertex=`varying vec3 n; void main(){n=normalize(normalMatrix*normal);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const fragment=`varying vec3 n; uniform vec3 base; uniform float alpha; void main(){float l=abs(dot(normalize(n),normalize(vec3(.4,.8,1.))));float tone=floor((l*.5+.5)*4.)/4.;float hatch=step(.78,fract((gl_FragCoord.x+gl_FragCoord.y)*.14));vec3 c=base*mix(.53,1.,tone);c*=1.-hatch*(1.-tone)*.22;gl_FragColor=vec4(c,alpha);}`;
// Paper / blueprint colour per material tone from the Blender manifest.
const TONES:Record<string,[string,string]>={paint:['#D40000','#D40000'],dark:['#5f6662','#56717d'],glass:['#8aacae','#7fa3b3'],metal:['#d2d3ca','#a9bcc4'],rubber:['#474c49','#4a6470'],accent:['#d99a4a','#d9a36a']};
const ENGINE=new Set(['Engine','Internals']);
const X=new T.Vector3(1,0,0),Y=new T.Vector3(0,1,0);
// One clock for the whole drivetrain so every part shares the same crank angle.
const motion={theta:0,shaft:0,wheel:0};
function Driver(){useFrame((_,dt)=>{dt=Math.min(dt,.05);const s=useStore.getState();const w=(s.rpm?(s.slow?10:s.rpm):0)*Math.PI/30*dt;motion.theta+=w;motion.shaft+=w/ratios[s.gear];motion.wheel+=w/ratios[s.gear]/3.5;});return null;}
const ghostOf=(zone:string,peel:number,view:string)=>zone==='Body'?peel>=25||view!=='Isometric':['Aero','Interior','Chassis','Electrical'].includes(zone)?peel>=50||(zone==='Aero'&&view==='Undercarriage'):['Engine','Transmission'].includes(zone)?peel>=75:false;
const openOf=(s:ReturnType<typeof useStore.getState>,t?:string)=>t==='cover'?s.hoodOpen:t==='doors'?s.doorsOpen:t==='frontLid'?s.lidOpen:false;

function PartMesh({p,src}:{p:Part;src:T.Mesh}){
 const focusedId=useStore(s=>s.focused),selected=useStore(s=>s.selected===p.id),hovered=useStore(s=>s.hovered===p.id),removed=useStore(s=>s.removed.includes(p.id)),dark=useStore(s=>s.dark);
 const ghost=useStore(s=>ghostOf(p.zone,s.peel,s.view)),explode=useStore(s=>s.explode);
 const outer=useRef<T.Group>(null!),shrink=useRef<T.Group>(null!),m=useRef<T.Mesh>(null!),hinge=useRef(0),reveal=useRef(0);
 const k=p.kin,{alpha,edgeOpacity}=partAppearance(p,focusedId,ghost);
 const rest=useMemo(()=>{const pos=new T.Vector3(),q=new T.Quaternion(),sc=new T.Vector3();src.matrixWorld.decompose(pos,q,sc);src.geometry.computeBoundingSphere();return {pos,q,centre:src.geometry.boundingSphere!.center.clone().applyQuaternion(q).add(pos)};},[src]);
 const axis=useMemo(()=>k?.axis?new T.Vector3(...k.axis).normalize():X,[k]);
 const tmp=useMemo(()=>({v:new T.Vector3(),q:new T.Quaternion()}),[]);
 const uniforms=useMemo(()=>({base:{value:new T.Color(selected&&p.tone!=='paint'?'#e48c45':(TONES[p.tone]??TONES.paint)[dark?1:0])},alpha:{value:alpha}}),[selected,dark,alpha,p.tone]);
 useFrame((_,dt)=>{dt=Math.min(dt,.05);const s=useStore.getState();
  // Assembly motion: explode, staged engine reveal, removal.
  reveal.current=T.MathUtils.damp(reveal.current,s.engineReveal?1:0,3,dt);
  // Reveal lifts only the upward layers, at ~40% of the full explode so the V12 stays framed.
  const r=ENGINE.has(p.zone)&&p.vector[1]>0?revealProgress(reveal.current,p.vector[1])*.4:0,e=s.explode+(s.peel>=75?(s.peel-75)/25:0);
  outer.current.position.lerp(tmp.v.set(...p.vector).multiplyScalar(removed?3:Math.max(e,r)),1-Math.exp(-dt*9));
  shrink.current.scale.setScalar(T.MathUtils.damp(shrink.current.scale.x,removed?0:1,8,dt));
  // Kinematics about the part's own Blender pivot.
  const mesh=m.current;mesh.position.copy(rest.pos);mesh.quaternion.copy(rest.q);mesh.scale.set(1,1,1);
  const steer=s.steering*Math.PI/180;
  switch(k?.type){
   case 'spin':mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(axis,motion.theta*(k.rate??1)));break;
   case 'shaft':mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(axis,motion.shaft));break;
   case 'wheel':mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(axis,motion.wheel));if(k.steer)mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(Y,steer));break;
   case 'steer':mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(Y,steer));break;
   case 'hinge':hinge.current=T.MathUtils.damp(hinge.current,openOf(s,k.trigger)?1:0,5,dt);mesh.quaternion.premultiply(tmp.q.setFromAxisAngle(axis,(k.angle??1)*hinge.current));break;
   case 'piston':mesh.position.set(...crankPose(k,motion.theta).wrist as [number,number,number]);break;
   case 'rod':{const {pin,wrist}=crankPose(k,motion.theta);mesh.position.set(pin[0],pin[1],pin[2]);mesh.quaternion.setFromUnitVectors(Y,tmp.v.set(wrist[0]-pin[0],wrist[1]-pin[1],wrist[2]-pin[2]).normalize());break;}
   case 'spring':mesh.scale.x=1-s.travel*.25;break;
  }
 });
 const click=(e:{stopPropagation:()=>void})=>{e.stopPropagation();useStore.getState().clickPart(p.id);};
 return <><group ref={outer}><group ref={shrink} position={rest.centre}><group position={rest.centre.clone().negate()}>
  <mesh ref={m} name={p.id} geometry={src.geometry} onClick={click} onPointerOver={e=>{e.stopPropagation();useStore.getState().set({hovered:p.id});}} onPointerOut={()=>{const s=useStore.getState();if(s.hovered===p.id)s.set({hovered:null});}} renderOrder={selected?2:0} raycast={removed?()=>{}:undefined}>
   {p.tone==='paint'?<meshPhysicalMaterial color="#D40000" metalness={.05} roughness={.26} clearcoat={1} clearcoatRoughness={.18} transparent={alpha<1} opacity={alpha} depthWrite={alpha===1} side={T.DoubleSide}/>:<shaderMaterial vertexShader={vertex} fragmentShader={fragment} uniforms={uniforms} transparent={alpha<1} depthWrite={alpha===1} side={T.DoubleSide}/>}
   <Edges raycast={()=>{}} threshold={22} color={selected?'#d36928':hovered?'#c97542':dark?'#6e98aa':'#444b4d'} transparent depthWrite={false} opacity={p.tone==='paint'&&!selected&&!hovered&&alpha===1?0:edgeOpacity}/>
  </mesh></group></group>

 </group>{explode>0&&!removed&&<Line points={[rest.centre,rest.centre.clone().addScaledVector(new T.Vector3(...p.vector),explode)]} color="#a28e77" dashed dashSize={.05} gapSize={.05} lineWidth={1}/>}</>;
}

function Model(){
 const {scene}=useGLTF(MODEL_URL);
 const meshes=useMemo(()=>{scene.updateMatrixWorld(true);const map=new Map<string,T.Mesh>();scene.traverse(o=>{if((o as T.Mesh).isMesh)map.set(o.name,o as T.Mesh);});return map;},[scene]);
 const missing=parts.filter(p=>!meshes.has(p.id));
 if(missing.length)console.warn('Parts missing from GLB:',missing.map(p=>p.id));
 return <>{parts.filter(p=>meshes.has(p.id)).map(p=><PartMesh key={p.id} p={p} src={meshes.get(p.id)!}/>)}</>;
}
useGLTF.preload(MODEL_URL);

function Rig(){
 const c=useRef<CameraControls>(null!),saved=useRef<ReturnType<CameraControls['getPosition']>|null>(null),savedTarget=useRef(new T.Vector3()),savedZoom=useRef(1),pending=useRef(false);
 const {view,ortho,focused}=useStore();
 useEffect(()=>{const views:Record<string,number[]>={'Isometric':[5.4,3.4,5.6,0,.5,0],'Engine bay':[2.6,2.9,-3.4,0,.6,-.95],'Undercarriage':[3.2,-2.6,3.4,0,.3,0],'Front corner':[2.4,1.0,3.0,.86,.33,1.35]};const v=views[view];
  // A camera bookmark establishes the position to return to after focus.
  saved.current=null;
  c.current?.setLookAt(v[0],v[1],v[2],v[3],v[4],v[5],true);
  pending.current=!!useStore.getState().focused;
 },[view,ortho]);
 useEffect(()=>{
  if(focused){pending.current=true;return;}
  pending.current=false;
  if(saved.current){const p=saved.current,t=savedTarget.current;c.current?.setLookAt(p.x,p.y,p.z,t.x,t.y,t.z,true);c.current?.zoomTo(savedZoom.current,true);saved.current=null;}
 },[focused]);
 useFrame(({scene,camera})=>{
  if(!pending.current||!focused||!c.current)return;
  const mesh=scene.getObjectByName(focused);
  if(!mesh)return; // Retry while the GLB loads.
  mesh.updateWorldMatrix(true,false);
  const bounds=new T.Box3().setFromObject(mesh);
  if(bounds.isEmpty())return;
  if(!saved.current){saved.current=c.current.getPosition(new T.Vector3());c.current.getTarget(savedTarget.current);savedZoom.current=camera.zoom;}
  pending.current=false;
  void c.current.fitToBox(bounds,true,{paddingTop:.025,paddingBottom:.025,paddingLeft:.025,paddingRight:.025});
 });
 return <CameraControls ref={c} minPolarAngle={0} maxPolarAngle={Math.PI} minDistance={.08} maxDistance={15}/>;
}
export function Scene(){const dark=useStore(s=>s.dark),ortho=useStore(s=>s.ortho);return <Canvas events={state=>({...events(state),filter:hits=>prioritizeFocusedHits(hits,useStore.getState().focused)})} onPointerMissed={e=>{if(e.type==='click')useStore.getState().clearSelection();}} dpr={[1,2]} fallback={<p>WebGL is unavailable. Use the parts list to inspect components.</p>}><color attach="background" args={[dark?'#142733':'#eeede6']}/>{ortho?<OrthographicCamera makeDefault position={[5.4,3.4,5.6]} zoom={110}/>:<PerspectiveCamera makeDefault position={[5.4,3.4,5.6]} fov={40}/>}<hemisphereLight args={['#ffffff','#81796e',1.6]}/><directionalLight position={[4,7,5]} intensity={2.4}/><directionalLight position={[-5,3,1]} intensity={1}/><directionalLight position={[1,4,-5]} intensity={1.5}/><Rig/><Driver/><Suspense fallback={<Html center><span className="callout">Loading Aventador model…</span></Html>}><Model/></Suspense><gridHelper args={[10,40,dark?'#38505a':'#c1c2b9',dark?'#243c49':'#dddcd3']} position={[0,-.002,0]}/></Canvas>}

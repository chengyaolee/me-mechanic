import {useRef,useState} from 'react';

const timestamp=(seconds:number)=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;

export function EngineAudio(){
 const audio=useRef<HTMLAudioElement>(null);
 const [playing,setPlaying]=useState(false),[time,setTime]=useState(0),[duration,setDuration]=useState(0),[error,setError]=useState('');
 const progress=duration?Math.min(1,time/duration):0,angle=progress*2*Math.PI;
 const toggle=async()=>{
  const clip=audio.current;if(!clip)return;
  if(!clip.paused){clip.pause();return;}
  try{setError('');if(clip.ended)clip.currentTime=0;await clip.play();}
  catch{setError('Audio could not play. Try again.');}
 };
 return <div className="engine-audio">
  <audio ref={audio} src="/audio/aventador/driving.mp3" preload="metadata"
   onLoadedMetadata={e=>setDuration(e.currentTarget.duration)}
   onTimeUpdate={e=>setTime(e.currentTarget.currentTime)}
   onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)}
   onError={()=>setError('Audio could not load. Try again.')}/>
  <button className="sound-button" type="button" onClick={toggle} aria-pressed={playing}
   aria-label={`${playing?'Pause':'Play'} Aventador driving recording`}
   title={`${playing?'Pause':'Play'} · ${timestamp(time)} / ${timestamp(duration)}`}>
   <svg viewBox="-12 -12 112 112" aria-hidden="true">
    <circle className="sound-track" cx="44" cy="44" r="30"/>
    <circle className="sound-progress" cx="44" cy="44" r="30" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress} transform="rotate(-90 44 44)"/>
    {playing?<path className="sound-icon" d="M38 35v18m12-18v18"/>:<path className="sound-icon" d="M33 40h6l8-7v22l-8-7h-6zm20-4q9 8 0 16"/>}
    <text className="sound-time" x={44+30*Math.sin(angle)} y={44-30*Math.cos(angle)}>{timestamp(time)}</text>
   </svg>
  </button>
  <div><span>Aventador driving</span><small>FIELD RECORDING{duration?` · ${timestamp(duration)}`:''}</small><small>Playback independent of RPM</small>{error&&<small role="alert">{error}</small>}</div>
 </div>;
}

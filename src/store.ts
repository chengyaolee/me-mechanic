import {create} from 'zustand';
type State={hoodOpen:boolean;doorsOpen:boolean;lidOpen:boolean;engineReveal:boolean;hovered:string|null;selected:string|null;focused:string|null;removed:string[];explode:number;peel:number;rpm:number;slow:boolean;gear:number;steering:number;travel:number;dark:boolean;strict:boolean;view:string;ortho:boolean;message:string;clickPart:(id:string)=>void;clearSelection:()=>void;set:(v:Partial<State>)=>void};
export const useStore=create<State>(set=>({
 hoodOpen:false,doorsOpen:false,lidOpen:false,engineReveal:false,hovered:null,selected:null,focused:null,removed:[],explode:0,peel:0,rpm:0,slow:true,gear:1,steering:0,travel:0,dark:false,strict:true,view:'Isometric',ortho:false,message:'',
 clickPart:id=>set(s=>({selected:id,focused:s.selected===id&&s.focused!==id&&!s.removed.includes(id)?id:null,hovered:null,message:''})),
 clearSelection:()=>set({selected:null,focused:null,hovered:null,message:''}),
 set:v=>set(s=>{const focused=v.focused===undefined?s.focused:v.focused;return {...v,...(focused&&(v.removed??s.removed).includes(focused)?{focused:null}:{})};}),
}));

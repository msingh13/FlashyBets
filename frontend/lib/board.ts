/** Data boundaries shared by board rendering and refreshes. */
export function scoreState(type:{state?:string;completed?:boolean;name?:string}){
 const name=type.name||'';
 if(/POSTPONED|CANCELED|CANCELLED|SUSPENDED|DELAYED/.test(name))return 'unavailable';
 return type.state==='post'&&type.completed===false?'unavailable':type.state||'pre';
}
export function scoreValue(value:unknown){
 const raw=value!==null&&typeof value==='object'?(value as {value?:unknown}).value:value;
 if(raw==null||raw==='')return null;
 const n=Number(raw);return Number.isFinite(n)&&n>=0?n:null;
}
export function gameEmptyMessage(total:number,filter:string,sport:string){
 if(total&&filter!=='all')return {title:'No games match this filter.',detail:'Choose All games to see the full board.'};
 return {title:'No games on this date.',detail:sport==='nfl'?'NFL games are scheduled mainly Thursday, Sunday and Monday. Try another date.':'Try another date or switch sports.'};
}
export function ageLabel(timestamp:string,now=Date.now()){
 const time=Date.parse(timestamp);if(!Number.isFinite(time))return 'Update time unavailable';
 const minutes=Math.max(0,Math.floor((now-time)/60000));
 return minutes<1?'Updated just now':minutes<60?`Updated ${minutes} min ago`:`Updated ${Math.floor(minutes/60)}h ${minutes%60}m ago`;
}

export function evaluatePrice(probability:number,push:number,american:number,buffer=.03){
 if(![probability,push,american,buffer].every(Number.isFinite)||probability<0||push<0||probability+push>1+1e-8||push>=1||Math.abs(american)<100||buffer<0) return null;
 const decimal=1+(american>0?american/100:100/Math.abs(american));
 const conditional=probability/(1-push),breakEven=1/decimal;
 const conservative=Math.max(0,conditional-buffer)*(1-push);
 return {decimal,conditional,breakEven,edge:conditional-breakEven,
  ev:probability*(decimal-1)-(1-probability-push),
  stressEv:conservative*(decimal-1)-(1-conservative-push),
  fairDecimal:probability>0?(1-push)/probability:null};
}

export type BookReference={draw?:number;draw_odds?:number;home:number;away:number;home_odds:number;away_odds:number;open_home_odds:number|null;open_away_odds:number|null;source:string;fetched:string;price_updated:null;note:string};
export function bookReference(raw:any,fetched:string,requireDraw=false):BookReference|null{
 if(!Array.isArray(raw))return null;
 for(const o of raw){
  const ml=o?.moneyline,h=Number(ml?.home?.close?.odds),a=Number(ml?.away?.close?.odds);
  if(!Number.isFinite(h)||!Number.isFinite(a)||Math.abs(h)<100||Math.abs(a)<100)continue;
  const implied=(v:number)=>1/(1+(v>0?v/100:100/Math.abs(v))),hp=implied(h),ap=implied(a);
  const draw=Number(o.drawOdds?.moneyLine??ml?.draw?.close?.odds);
  const hasDraw=requireDraw&&Number.isFinite(draw)&&Math.abs(draw)>=100;
  if(requireDraw&&!hasDraw)continue;
  const dp=hasDraw?implied(draw):0,mass=hp+ap+dp;
  const open=(v:unknown)=>v!=null&&Number.isFinite(Number(v))&&Math.abs(Number(v))>=100?Number(v):null;
  return {...(hasDraw?{draw:dp/mass,draw_odds:draw}:{}),home:hp/mass,away:ap/mass,home_odds:h,away_odds:a,open_home_odds:open(ml?.home?.open?.odds),open_away_odds:open(ml?.away?.open?.odds),source:(o.provider?.name||'Bookmaker')+' via ESPN',fetched,price_updated:null,note:'Proportional no-vig book probability, not an independent model prediction or Bet365 quote. Pregame quote reference, not an in-play win model. Fetch time is not a bookmaker update timestamp.'};
 }
 return null;
}

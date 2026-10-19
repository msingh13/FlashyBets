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

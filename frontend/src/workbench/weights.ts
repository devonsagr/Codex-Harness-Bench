// Allocate integer basis points so displayed percentages always total exactly 100.
export function distribute(weights:Record<string,number>, units=10000):Record<string,number>{
  const entries=Object.entries(weights);if(!entries.length)return {};
  const sum=entries.reduce((n,[,v])=>n+Math.max(0,v),0);
  const shares=entries.map(([key,v],index)=>{const exact=units*(sum?Math.max(0,v)/sum:1/entries.length);return {key,index,units:Math.floor(exact),fraction:exact-Math.floor(exact)};});
  const remainder=units-shares.reduce((n,s)=>n+s.units,0);
  [...shares].sort((a,b)=>b.fraction-a.fraction||a.index-b.index).slice(0,remainder).forEach(s=>s.units++);
  return Object.fromEntries(shares.map(s=>[s.key,s.units/100]));
}
export function adjustWeight(weights:Record<string,number>,key:string,value:number){
  if(!(key in weights))return weights;
  const rest=Object.fromEntries(Object.entries(weights).filter(([k])=>k!==key));
  const units=Object.keys(rest).length?Math.round(Math.max(0,Math.min(100,value))*100):10000;
  const allocated=distribute(rest,10000-units);
  return Object.fromEntries(Object.keys(weights).map(k=>[k,k===key?units/100:allocated[k]]));
}

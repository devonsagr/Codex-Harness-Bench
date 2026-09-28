/** Draw without replacement, spreading each side across task origins first. */
function draw<T extends {id:string}>(items:T[],count:number,group:(item:T)=>string,random:()=>number):T[]{
  const buckets=new Map<string,T[]>();
  for(const item of [...items].sort((a,b)=>a.id.localeCompare(b.id))){const key=group(item);buckets.set(key,[...(buckets.get(key)||[]),item]);}
  const shuffle=<U,>(values:U[])=>{
    for(let i=values.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[values[i],values[j]]=[values[j],values[i]];}
    return values;
  };
  for(const values of buckets.values())shuffle(values);
  const keys=shuffle([...buckets.keys()].map(id=>({id}))).map(item=>item.id);
  const chosen:T[]=[];
  while(chosen.length<count){
    let added=false;
    for(const key of keys){const next=buckets.get(key)?.pop();if(next){chosen.push(next);added=true;if(chosen.length===count)break;}}
    if(!added)break;
  }
  return chosen;
}

export function balancedRandomIds<T extends {id:string}>(swe:T[],web:T[],perSide:number,sweGroup:(item:T)=>string,webGroup:(item:T)=>string,random:()=>number=Math.random):string[]{
  if(!Number.isInteger(perSide)||perSide<1||perSide>5||swe.length<perSide||web.length<perSide)throw new Error('可选题目不足，无法按两类等量抽题。');
  const left=draw(swe,perSide,sweGroup,random),right=draw(web,perSide,webGroup,random);
  return left.flatMap((item,index)=>[item.id,right[index].id]);
}

/** Persist the seed with the selection so a fixed catalog can reproduce it. */
export function seededRandom(seed:number):()=>number{
  let value=seed>>>0;
  return ()=>{value+=0x6D2B79F5;let t=value;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
}

/** Match the pinned source importer, including records imported by older builds. */
export function compactWebGenTask(task:{description?:string;inputPrompt?:string;criteria?:unknown[]}):boolean{
  const types=['Personal Portfolio Sites','Company Brochure Sites','Productivity Applications','Browser-Based Games'];
  const prompt=task.inputPrompt||'';
  return types.includes(task.description||'')&&prompt.length<850&&!!task.criteria?.length&&task.criteria.length<=7&&
    !/\b(api|database|payment|authentication|login|log in|stock|real.time|social network|e.commerce|multi.user|account|simulation|multiplayer|booking|reservation)\b/i.test(prompt);
}

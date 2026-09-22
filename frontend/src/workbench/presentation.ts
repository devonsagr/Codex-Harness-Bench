import type {Run,Task,Usage} from './types';

export const difficultyKey=(task:Task)=>task.difficulty?.trim().toLowerCase()||'未标注';
export function taskFacets(tasks:Task[],channel:string,difficulty:string){
  const count=(items:Task[],key:(t:Task)=>string)=>Object.entries(items.reduce<Record<string,number>>((a,t)=>{const k=key(t);a[k]=(a[k]||0)+1;return a;},{})).sort(([a],[b])=>a.localeCompare(b));
  return {channels:count(tasks.filter(t=>!difficulty||difficultyKey(t)===difficulty),t=>t.channel||'未标注'),difficulties:count(tasks.filter(t=>!channel||(t.channel||'未标注')===channel),difficultyKey)};
}
export function runProgress(run:Run){
  const trials=run.trials;
  if(trials.some(t=>t.state==='judging'))return '评分中';
  if(trials.some(t=>t.state==='checking'||t.nativeExecution?.status==='running'))return '验收中';
  if(run.state==='completed')return '交付结束';
  if(trials.some(t=>t.usage?.activity==='running'))return '执行中';
  const scored=trials.filter(t=>{
    const latest=t.captures[t.captures.length-1];
    const review=t.reviews.find(r=>r.id===t.score.machineReviewId);
    return !!latest&&(t.score.machine!=null||t.score.partialScore!=null||t.score.overall!=null)&&(!t.score.machineReviewId||review?.captureId===latest.id);
  }).length;
  if(scored)return scored===trials.length?'已评分 · 待结束':`部分已评分 · ${scored}/${trials.length}`;
  if(trials.some(t=>t.lastJobError&&t.captures.length))return '评分待处理';
  if(trials.some(t=>t.captures.length))return '已回收 · 待评分';
  if(trials.some(t=>t.usage?.activity==='completed'))return '执行已停 · 待回收';
  if(trials.some(t=>t.usage?.activity==='interrupted'))return '执行中断';
  return trials.some(t=>t.state==='working')?'等待执行记录':'待执行';
}

// OpenAI Standard short-context API rates, USD / 1M tokens, checked 2026-09-22.
// This is a comparison estimate, never a ChatGPT bill or subscription quota.
export const apiRates:Record<string,[number,number,number]>={
  'gpt-6-astra':[10,1,50],'gpt-5.6-sol':[4,.4,20],
  'gpt-5.6-terra':[2,.2,12],'gpt-5.6-luna':[.2,.02,1.2],
};
export function apiEquivalent(usage:Usage){
  if(usage.models.length!==1)return {reason:'多模型或模型未知；缺少逐模型用量，暂不换算。'};
  const rates=apiRates[usage.models[0]];
  if(!rates)return {reason:'该模型尚无已核对单价。'};
  const {inputTokens:input,cacheReadTokens:cache,outputTokens:output}=usage;
  if([input,cache,output].some(v=>v==null||!Number.isFinite(v)||v<0)||cache!>input!)return {reason:'等待完整、有效的输入 / 缓存 / 输出用量。'};
  const uncached=input!-cache!;
  const writes=usage.cacheWriteTokens;
  if(writes!=null&&(!Number.isFinite(writes)||writes<0||writes>uncached))return {reason:'缓存写入用量异常，暂不换算。'};
  const base=(uncached*rates[0]+cache!*rates[1]+output!*rates[2])/1e6;
  return {low:base+(writes??0)*rates[0]*.25/1e6,high:base+(writes??uncached)*rates[0]*.25/1e6,rates,model:usage.models[0]};
}

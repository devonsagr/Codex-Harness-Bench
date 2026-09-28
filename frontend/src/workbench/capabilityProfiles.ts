import type {ConfigResultEntry,TaskResult} from './configResults';
import type {Task} from './types';

export type CapabilityFacet={label:string;score:number;basis:string};
export type CapabilitySample={taskId:string;title:string;score:number;trials:number;runs:{id:string;score:number;basis:string;facets:CapabilityFacet[]}[]};
export type CapabilityAxis={id:string;label:string;score:number|null;tasks:number;trials:number;samples:CapabilitySample[]};
export type CapabilityProfile={id:string;title:string;description:string;axes:CapabilityAxis[]};

/** A diagnostic view of evidence, never a second total or a task-label estimate. */
const axes=[
  {id:'goal',label:'目标兑现',keys:['intent']},
  {id:'engineering',label:'工程实现',keys:['verification','robustness','maintainability']},
  {id:'web',label:'网页体验',keys:['ux','visual','originality','responsive','accessibility']},
  {id:'reasoning',label:'推理决策',keys:['reasoning','requirements','long-context']},
  {id:'collaboration',label:'协作沟通',keys:['communication','milestones','handoff']},
  {id:'reliability',label:'稳健交付',keys:['verification','robustness','security','performance','handoff']},
] as const;
const round=(value:number)=>Math.round(value*10)/10;
const mean=(values:number[])=>values.reduce((sum,value)=>sum+value,0)/values.length;
const numeric=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100;
const publicCardVersion='deepswe-local-v1';
const autoCardVersions=new Set(['project-tasktype-v2','project-tasktype-v3']);
const rubricsFor=(entry:ConfigResultEntry)=>entry.run.policy.taskOverrides?.[entry.task.id]?.rubrics||entry.run.policy.rubrics||{};

function publicRatio(entry:ConfigResultEntry,label:string){
  const card=entry.trial.score.taskScorecard;
  if(card?.version!==publicCardVersion)return null;
  const row=card.items.find(item=>item.label===label);
  return row&&numeric(row.ratio)&&row.ratio<=1?row.ratio*100:null;
}
function publicFunction(entry:ConfigResultEntry){
  const card=entry.trial.score.taskScorecard;
  if(card?.version!==publicCardVersion)return null;
  const rows=card.items.filter(item=>!['旧功能与边界回归','工程可维护性'].includes(item.label));
  if(!rows.length||rows.some(row=>!numeric(row.ratio)||row.ratio>1||!numeric(row.weight)||row.weight<=0))return null;
  return rows.reduce((sum,row)=>sum+row.ratio!*row.weight,0)/rows.reduce((sum,row)=>sum+row.weight,0)*100;
}
function reviewed(entry:ConfigResultEntry,key:string):{value:number;basis:string}|null{
  const {trial,run}=entry,score=trial.score;
  const latest=trial.captures[trial.captures.length-1];
  const report=trial.reviews?.find(row=>row.id===score.machineReviewId&&row.captureId===latest?.id);
  const rating=score.machineRatings?.[key],override=score.machineOverrides?.[key];
  const value=score.effectiveScores?.[key];
  if(!report||!numeric(value)||!(override&&numeric(override.score)||rating&&numeric(rating.score)&&rating.evidence?.length))return null;
  const card=score.taskScorecard;
  const frozen=card?.version==='project-policy-v1'&&card.qualityReviewId===report.id
    ?card.items.find(row=>row.key===key):null;
  if(card?.version==='project-policy-v1'){
    return frozen&&numeric(frozen.ratio)&&frozen.ratio<=1
      ?{value:frozen.ratio*100,basis:`冻结评分项「${frozen.label}」：${frozen.evidence}`}:null;
  }
  // The automatic card limits verification when configured checks fail.
  if(card?.version&&autoCardVersions.has(card.version)&&key==='verification'&&entry.task.checks?.length&&latest){
    if(!latest.checks.length||latest.checks.some(row=>!['passed','failed'].includes(row.status)))return null;
    if(latest.checks.some(row=>row.status==='failed'))return {value:0,basis:'已配置的程序检查失败，验证项按冻结评分卡限制为 0'};
  }
  const label=rubricsFor(entry)[key]?.label||key;
  return {value,basis:`${override?'人工修正':'AI 审查'}「${label}」；${rating?.evidence?.length||0} 条引用`};
}
function entryEvidence(entry:ConfigResultEntry,id:string):{value:number;basis:string;facets:CapabilityFacet[]}|null{
  if(entry.task.publicSource){
    if(id==='goal'||id==='engineering'){
      const functionValue=publicFunction(entry),maintenance=publicRatio(entry,'工程可维护性');
      if(id==='goal'){
        const rows=entry.trial.score.taskScorecard?.items.filter(item=>!['旧功能与边界回归','工程可维护性'].includes(item.label))||[];
        return functionValue==null?null:{value:functionValue,basis:'本地评分卡目标功能语义组；原题 0/1 另列',facets:rows.map(row=>({label:row.label,score:row.ratio!*100,basis:`原题测试语义组 · 占本地总分 ${row.weight}%`}))};
      }
      if(maintenance==null)return null;
      return {value:maintenance,basis:'本地评分卡工程可维护性审查',facets:[{label:'工程可维护性',score:maintenance,basis:'AI 取证或人工修正；本地参考项'}]};
    }
    if(id==='reliability'){
      const value=publicRatio(entry,'旧功能与边界回归');
      return value==null?null:{value,basis:'本地评分卡旧功能回归组；原题 0/1 另列',facets:[{label:'旧功能与边界回归',score:value,basis:'原题程序测试语义组'}]};
    }
    return null;
  }
  if(id==='web'&&!entry.task.hasFrontendUI)return null;
  const card=entry.trial.score.taskScorecard;
  if(id==='goal'&&card?.version&&autoCardVersions.has(card.version)){
    const row=card.items.find(item=>item.label==='用户目标与范围');
    const facets=(card.version==='project-tasktype-v3'?['intent','instruction','reasoning']:['intent','instruction']).flatMap(key=>{const result=reviewed(entry,key);return result?[{label:rubricsFor(entry)[key]?.label||key,score:result.value,basis:result.basis}]:[];});
    return row&&numeric(row.ratio)&&row.ratio<=1
      ?{value:row.ratio*100,basis:`本题目标组：${row.evidence}`,facets}:null;
  }
  const axis=axes.find(item=>item.id===id)!;
  const scored=axis.keys.flatMap(key=>{const result=reviewed(entry,key);return result?[{key,...result}]:[];});
  if(!scored.length)return null;
  return {value:mean(scored.map(item=>item.value)),basis:scored.map(item=>item.basis).join('；'),facets:scored.map(item=>({label:rubricsFor(entry)[item.key]?.label||item.key,score:item.value,basis:item.basis}))};
}

/** A rubric can inform several diagnostic views, but the task card counts it once. */
export function rubricRadarDestinations(key:string,tasks:Task[]):string[]{
  if(key==='instruction')return [];
  const targets=new Set<string>();
  for(const task of tasks){
    if(task.publicSource){
      if(key==='maintainability')targets.add('工程实现');
      continue;
    }
    for(const axis of axes){
      if(axis.id==='web'&&!task.hasFrontendUI)continue;
      if((axis.keys as readonly string[]).includes(key))targets.add(axis.label);
    }
  }
  return [...targets];
}

/** Same-task repeats average first; different tasks then receive equal weight. */
export function capabilityProfiles(tasks:TaskResult[]):CapabilityProfile[]{
  return [{id:'overview',title:'六项能力总览',description:'只用实际评分证据；同题重复先取均值，再按题等权。雷达不重新计算综合分，缺证据保留未测。',axes:axes.map(axis=>{
    const samples=tasks.flatMap(result=>{
      const values=result.entries.map(entry=>entryEvidence(entry,axis.id));
      if(!values.length||values.some(value=>value==null))return [];
      return [{taskId:result.task.id,title:result.task.title,score:mean(values.map(value=>value!.value)),
        trials:values.length,runs:values.map((value,index)=>({id:result.entries[index].run.id,score:value!.value,basis:value!.basis,facets:value!.facets}))}];
    });
    return {id:axis.id,label:axis.label,score:samples.length?round(mean(samples.map(sample=>sample.score))):null,
      tasks:samples.length,trials:samples.reduce((sum,sample)=>sum+sample.trials,0),samples};
  })}];
}

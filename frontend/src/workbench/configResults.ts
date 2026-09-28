import type {Config,Run,State,Task,Trial} from './types';

export type ConfigResultEntry={run:Run;trial:Trial;task:Task;archived:boolean;eligible:boolean;exclusion?:string};
export type TaskResult={task:Task;mean:number;entries:ConfigResultEntry[];protocolKey:string};
export type CollectionResult={key:string;label:string;tasks:TaskResult[];trials:number};
export type ConfigResult={key:string;config:Config;current:boolean;archivedConfig:boolean;entries:ConfigResultEntry[];tasks:TaskResult[];collections:CollectionResult[];score:number|null;referenceScore:number|null;referenceOnly:boolean;suiteRunId?:string;reason?:string;completed:number;recorded:number;finished:number;scored:number;pending:number;nativeScored:number;nativePassed:number;archivedRuns:number;policyCount:number;judgeCount:number};

const average=(values:number[])=>values.reduce((sum,value)=>sum+value,0)/values.length;
const stable=(value:unknown):unknown=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,stable(item)])):value;
const nativeReport=(entry:ConfigResultEntry)=>{
  const latest=entry.trial.captures[entry.trial.captures.length-1];
  return latest?.nativeVerifications?.find(report=>report.id===entry.trial.score.nativeVerificationId&&report.captureHash===latest.manifest.sha256);
};
export function entryScore(entry:ConfigResultEntry):number|null{
  const score=entry.trial.score;
  if(score.overall==null)return null;
  if(!entry.task.publicSource)return score.overall;
  const report=nativeReport(entry);
  const card=score.taskScorecard;
  return score.scoreSource==='task-scorecard'&&report&&card?.nativeVerificationId===report.id&&card.overall===score.overall?card.overall:null;
}
const policyKey=(entry:ConfigResultEntry)=>{
  if(entry.task.publicSource)return `local:${entry.trial.score.taskScorecard?.version||'unknown'} / native:${nativeReport(entry)?.adapter||'unknown'}`;
  const policy=entry.run.policy;
  const effective=policy.taskTypeAuto?policy.taskOverrides?.[entry.task.id]||{taskTypeAuto:true,taskFamily:entry.task.taskFamily,hasFrontendUI:entry.task.hasFrontendUI}:policy;
  return `${entry.trial.score.taskScorecard?.version||'legacy'} / ${JSON.stringify(stable(effective))}`;
};
const judgeKey=(entry:ConfigResultEntry)=>{
  const report=entry.trial.reviews?.find(r=>r.id===(entry.task.publicSource?entry.trial.score.taskScorecard?.qualityReviewId:entry.trial.score.machineReviewId));
  return report?`${report.model||'未知模型'} / ${report.reasoningEffort||'默认思考'} / ${report.judgePromptVersion||'旧版提示词'} / ${report.scoreSchema||'未知评分协议'} / ${report.scoringProtocol||'legacy-direct'}`:'无机器裁判报告';
};
const collection=(task:Task):[string,string]=>{
  if(task.publicSource||task.sourceKind==='deepswe')return ['deepswe','DeepSWE'];
  if(task.sourceKind==='webgen-bench-local')return ['webgen-local','WebGen-Bench · 本地适配'];
  if(task.sourceKind==='repository-original')return ['bundled','项目内置题包'];
  if(task.sourceKind==='prototype-prompt')return ['project-prompts','开放需求题'];
  if(task.sourceKind==='user-authored')return ['custom','自定义题'];
  return ['other','其他来源'];
};

/** Open-project quality and public-task verifier outcomes remain separate. */
export function configResults(state:Pick<State,'runs'|'archivedRuns'|'configs'|'archivedConfigs'>):ConfigResult[]{
  const groups=new Map<string,ConfigResult>();
  const current=new Set(state.configs.map(c=>`${c.id}:${c.revision}`));
  const archivedIds=new Set(state.archivedConfigs.map(c=>c.id));
  const retainedIds=new Set([...state.configs,...state.archivedConfigs].map(c=>c.id));
  for(const config of [...state.configs,...state.archivedConfigs]){
    const key=`${config.id}:${config.revision}`;
    groups.set(key,{key,config,current:current.has(key),archivedConfig:archivedIds.has(config.id),entries:[],tasks:[],collections:[],score:null,referenceScore:null,referenceOnly:false,completed:0,recorded:0,finished:0,scored:0,pending:0,nativeScored:0,nativePassed:0,archivedRuns:0,policyCount:0,judgeCount:0});
  }
  for(const [runs,archived] of [[state.runs,false],[state.archivedRuns,true]] as const){
    for(const run of runs)for(const trial of run.trials){
      if(run.historyHidden)continue;
      const config=run.configs.find(c=>c.id===trial.configId);
      const task=run.tasks.find(t=>t.id===trial.taskId);
      if(!config||!task||!retainedIds.has(config.id))continue;
      const key=`${config.id}:${config.revision}`;
      let group=groups.get(key);
      if(!group){group={key,config,current:current.has(key),archivedConfig:archivedIds.has(config.id),entries:[],tasks:[],collections:[],score:null,referenceScore:null,referenceOnly:false,completed:0,recorded:0,finished:0,scored:0,pending:0,nativeScored:0,nativePassed:0,archivedRuns:0,policyCount:0,judgeCount:0};groups.set(key,group);}
      const latest=trial.captures[trial.captures.length-1];
      if(task.publicSource){
        const native=latest?.nativeVerifications?.find(report=>report.id===trial.score.nativeVerificationId&&report.captureHash===latest.manifest.sha256);
        if(native){group.nativeScored++;group.nativePassed+=native.reward===1?1:0;}
      }
      let exclusion:string|undefined;
      if(task.publicSource&&trial.score.scoreSource!=='task-scorecard')exclusion='本题尚无已核对的本地连续评分卡';
      else if(task.publicSource&&(!latest||!latest.nativeVerifications?.some(report=>report.id===trial.score.nativeVerificationId&&report.captureHash===latest.manifest.sha256&&trial.score.taskScorecard?.nativeVerificationId===report.id)))exclusion='原题程序验收尚未完成';
      else if(config.preparationOverride)exclusion='本次临时改动了技能';
      else if((!task.publicSource&&trial.state!=='completed')||entryScore({run,trial,task,archived,eligible:false})==null)exclusion='交付或本地逐项评分未完成';
      else if(!latest)exclusion='缺少回收快照';
      const entry={run,trial,task,archived,eligible:!exclusion,exclusion};
      group.entries.push(entry);
      if(entryScore(entry)!=null)group.recorded++;
      if(trial.state==='completed')group.finished++;
      if(!task.publicSource&&trial.score.overall!=null)group.scored++;
      if(exclusion)group.pending++;else group.completed++;
    }
  }
  for(const group of groups.values()){
    group.archivedRuns=new Set(group.entries.filter(entry=>entry.archived).map(entry=>entry.run.id)).size;
    const eligible=group.entries.filter(e=>e.eligible);
    const pendingReason=group.recorded?`${group.pending} 次暂不纳入配置对比；全组 ${group.recorded} 次已有逐题分`:`还有 ${group.pending} 次待计分或条件待核对，尚无最终评分`;
    const batches=[...new Map(group.entries.filter(entry=>entry.run.trials.length>1).map(entry=>[entry.run.id,entry.run])).values()]
      .sort((a,b)=>b.createdAt.localeCompare(a.createdAt));
    const completeBatch=batches.find(run=>{const rows=group.entries.filter(entry=>entry.run.id===run.id);return rows.length>0&&rows.every(entry=>entry.eligible);});
    const selected=batches.length?(completeBatch?eligible.filter(entry=>entry.run.id===completeBatch.id):[]):eligible;
    if(completeBatch)group.suiteRunId=completeBatch.id;
    const policies=new Set(selected.map(policyKey));
    group.policyCount=policies.size;
    group.judgeCount=new Set(selected.map(judgeKey)).size;
    if(!selected.length){group.reason=group.pending?pendingReason:'尚无最终评分';continue;}
    const tasks=new Map<string,{task:Task;entries:ConfigResultEntry[]}>();
    for(const entry of selected){
      const key=`${entry.task.id}:${entry.task.revision}:${policyKey(entry)}:${judgeKey(entry)}`;
      const bucket=tasks.get(key)||{task:entry.task,entries:[]};
      bucket.entries.push(entry);tasks.set(key,bucket);
    }
    group.tasks=[...tasks].map(([protocolKey,v])=>({task:v.task,entries:v.entries,protocolKey,mean:average(v.entries.map(e=>entryScore(e)!))}));
    const collections=new Map<string,{label:string;tasks:TaskResult[]}>();
    for(const task of group.tasks){const [key,label]=collection(task.task);const bucket=collections.get(key)||{label,tasks:[]};bucket.tasks.push(task);collections.set(key,bucket);}
    group.collections=[...collections].map(([key,value])=>({key,label:value.label,tasks:value.tasks,trials:value.tasks.reduce((sum,t)=>sum+t.entries.length,0)}));
    const versions=new Map<string,Set<number>>();
    const protocols=new Map<string,Set<string>>();
    for(const task of group.tasks){
      const revisions=versions.get(task.task.id)||new Set<number>();revisions.add(task.task.revision);versions.set(task.task.id,revisions);
      const key=`${task.task.id}:${task.task.revision}`;const variants=protocols.get(key)||new Set<string>();variants.add(task.protocolKey);protocols.set(key,variants);
    }
    const conflict=[...versions.values()].some(v=>v.size>1)||[...protocols.values()].some(v=>v.size>1);
    group.referenceOnly=selected.some(entry=>!['native','task-check-pass'].includes(entry.trial.score.assurance||''));
    group.referenceScore=conflict||(!batches.length&&group.pending>0)?null:Math.round(average(group.tasks.map(task=>task.mean))*10)/10;
    group.score=(batches.length?false:group.pending>0)||conflict||group.referenceOnly?null:group.referenceScore;
    if(conflict)group.reason='同题混有不同版本或评分协议；保留逐题分，配置综合分待对齐';
    else if(!batches.length&&group.pending)group.reason=pendingReason;
    else if(group.referenceOnly)group.reason='题集中含通用烟检、未覆盖最新快照的任务验收、检查失败或旧版未标明证据级别的题；保留 AI 参考均值，不发布可用于配置对比的综合分';
    else if(batches.length&&completeBatch&&batches[0].id!==completeBatch.id)group.reason='最新批次尚未完整验收；显示上一次完整批次的题集分';
  }
  return [...groups.values()].sort((a,b)=>Number(b.current)-Number(a.current)||Number(a.archivedConfig)-Number(b.archivedConfig)||(b.entries[0]?.run.createdAt||'').localeCompare(a.entries[0]?.run.createdAt||''));
}

export function matchedComparison(baseline:ConfigResult,candidate:ConfigResult){
  if(baseline.key===candidate.key)return {reason:'请选择两套不同的配置版本。'};
  if([baseline,candidate].some(g=>g.referenceOnly))return {reason:'至少一套题集只有 AI 参考分或任务专属验收未通过，不能把数值差当作配置胜负。'};
  if([baseline,candidate].some(g=>!g.tasks.length||g.score==null))return {reason:'两套配置都需要完整、可核对的逐题分数。'};
  if([baseline,candidate].some(g=>g.tasks.some(t=>t.entries.some(e=>e.trial.captures.some(c=>!c.harnessUnchanged||!c.hostUnchanged)))))return {reason:'工作区规则或宿主配置曾变化；分数可看，但不能当作控制变量对照。'};
  const harnessOnly=(config:Config)=>[config.baseModel,config.reasoning,config.serviceTier||''];
  if(JSON.stringify(harnessOnly(baseline.config))!==JSON.stringify(harnessOnly(candidate.config)))return {reason:'模型、思考档位或速度不同，无法把差异归因于 Harness。'};
  const other=new Map(candidate.tasks.map(t=>[`${t.task.id}:${t.task.revision}:${t.protocolKey}`,t]));
  const tasks=baseline.tasks.flatMap(t=>{const match=other.get(`${t.task.id}:${t.task.revision}:${t.protocolKey}`);return match?[{task:t.task,baseline:t.mean,candidate:match.mean,baselineTrials:t.entries.length,candidateTrials:match.entries.length}]:[];});
  if(!tasks.length)return {reason:'没有共同题目及版本；先在两套配置上跑同一批题。'};
  const baselineScore=average(tasks.map(t=>t.baseline)),candidateScore=average(tasks.map(t=>t.candidate));
  return {tasks,baselineScore,candidateScore,delta:candidateScore-baselineScore};
}

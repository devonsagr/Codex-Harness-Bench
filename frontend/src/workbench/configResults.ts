import type {Config,Run,State,Task,Trial} from './types';

export type ConfigResultEntry={run:Run;trial:Trial;task:Task;archived:boolean;eligible:boolean;exclusion?:string};
export type TaskResult={task:Task;mean:number;entries:ConfigResultEntry[]};
export type ConfigResult={key:string;config:Config;current:boolean;archivedConfig:boolean;entries:ConfigResultEntry[];tasks:TaskResult[];score:number|null;reason?:string;completed:number;pending:number;archivedRuns:number;policyCount:number};

const average=(values:number[])=>Math.round(values.reduce((sum,value)=>sum+value,0)/values.length*100)/100;
const policyKey=(run:Run)=>JSON.stringify(run.policy);

/** A configuration revision is a contestant. Each task carries equal weight; repetitions first average within that task. */
export function configResults(state:Pick<State,'runs'|'archivedRuns'|'configs'|'archivedConfigs'>):ConfigResult[]{
  const groups=new Map<string,ConfigResult>();
  const current=new Set(state.configs.map(c=>`${c.id}:${c.revision}`));
  const archivedConfigs=new Set(state.archivedConfigs.map(c=>`${c.id}:${c.revision}`));
  for(const config of [...state.configs,...state.archivedConfigs]){
    const key=`${config.id}:${config.revision}`;
    groups.set(key,{key,config,current:current.has(key),archivedConfig:archivedConfigs.has(key),entries:[],tasks:[],score:null,completed:0,pending:0,archivedRuns:0,policyCount:0});
  }
  for(const [runs,archived] of [[state.runs,false],[state.archivedRuns,true]] as const){
    for(const run of runs)for(const trial of run.trials){
      const config=run.configs.find(c=>c.id===trial.configId);
      const task=run.tasks.find(t=>t.id===trial.taskId);
      if(!config||!task)continue;
      const key=`${config.id}:${config.revision}`;
      let group=groups.get(key);
      if(!group){group={key,config,current:current.has(key),archivedConfig:archivedConfigs.has(key),entries:[],tasks:[],score:null,completed:0,pending:0,archivedRuns:0,policyCount:0};groups.set(key,group);}
      const latest=trial.captures[trial.captures.length-1];
      let exclusion:string|undefined;
      if(config.preparationOverride)exclusion='本次临时改动了技能';
      else if(trial.state!=='completed'||trial.score.overall==null)exclusion='交付或评分未完成';
      else if(!latest||trial.captures.some(c=>!c.harnessUnchanged||!c.hostUnchanged))exclusion='运行条件发生变化';
      const entry={run,trial,task,archived,eligible:!exclusion,exclusion};
      group.entries.push(entry);
      if(archived)group.archivedRuns++;
      if(exclusion)group.pending++;else group.completed++;
    }
  }
  for(const group of groups.values()){
    const eligible=group.entries.filter(e=>e.eligible);
    const policies=new Set(eligible.map(e=>policyKey(e.run)));
    group.policyCount=policies.size;
    if(policies.size>1){group.reason='评分方案不同，不能合成均分';continue;}
    if(!eligible.length){group.reason='尚无已完成且条件可核对的成绩';continue;}
    const tasks=new Map<string,{task:Task;entries:ConfigResultEntry[]}>();
    for(const entry of eligible){
      const key=`${entry.task.id}:${entry.task.revision}`;
      const bucket=tasks.get(key)||{task:entry.task,entries:[]};
      bucket.entries.push(entry);tasks.set(key,bucket);
    }
    group.tasks=[...tasks.values()].map(v=>({task:v.task,entries:v.entries,mean:average(v.entries.map(e=>e.trial.score.overall!))}));
    group.score=average(group.tasks.map(t=>t.mean));
  }
  return [...groups.values()].sort((a,b)=>Number(b.current)-Number(a.current)||Number(a.archivedConfig)-Number(b.archivedConfig)||(b.entries[0]?.run.createdAt||'').localeCompare(a.entries[0]?.run.createdAt||''));
}

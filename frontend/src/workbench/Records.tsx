import {useState} from 'react';
import type {State,Act,Run} from './types';
import {Panel,Details,Empty,Json,num,date,labels} from './ui';
import {downloadRun} from './api';
export function History({state,act,onOpen,onError}:{state:State;act:Act;onOpen:(id:string)=>void;onError:(s:string)=>void}){
  const [archived,setArchived]=useState(false);const [query,setQuery]=useState('');
  const runs=(archived?state.archivedRuns:state.runs).filter(r=>(r.id+r.notes+r.tasks.map(t=>t.title).join()+r.configs.map(c=>c.name).join()).toLowerCase().includes(query.toLowerCase()));
  return <><div className="flex justify-between items-center"><h1 className="page-title">评测历史</h1><label className="check-row"><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>查看归档</label></div><input aria-label="搜索历史" placeholder="搜索题目、配置、备注或编号" value={query} onChange={e=>setQuery(e.target.value)}/>
    {runs.length?runs.map(r=><Panel key={r.id} title={r.tasks.map(t=>t.title).join('、')} aside={<span className="badge">{r.state==='completed'?'交付结束':'进行中'}</span>}><div className="grid md:grid-cols-3 gap-4 text-sm"><div><p className="muted">时间与编号</p><p>{date(r.createdAt)}</p><small>{r.id}</small></div><div><p className="muted">当时的配置</p>{r.configs.map(c=><p key={c.id}>{c.name} v{c.revision}{c.preparationOverride?' · 本次技能已调整':''} · {c.baseModel} / {c.reasoning}</p>)}</div><div><p className="muted">证据</p><p>{r.trials.length} 个独立工作区 · {r.trials.reduce((n,t)=>n+t.captures.length,0)} 份回收</p><p>{r.notes||'无备注'}</p></div></div><div className="flex gap-3 flex-wrap"><button className="btn-primary" onClick={()=>onOpen(r.id)}>查看记录与产物</button><button className="btn-secondary" onClick={()=>downloadRun(r.id).catch(e=>onError(e.message))}>导出 ZIP</button><button className="btn-ghost" onClick={()=>act(`/runs/${r.id}/archive`,{archived:!archived,revision:r.revision}).catch(()=>{})}>{archived?'恢复记录':'归档记录'}</button></div></Panel>):<Empty>{archived?'没有归档记录。':'还没有评测记录。到工作台准备一次评测，过程和结果都会保存在这里。'}</Empty>}
    <Details title={`独立保留的 CLI 历史 · ${state.legacyExperiments} 次实验`}><p className="muted">此前 Harbor/CLI 实验保存在项目 runs/，通过原有 chb report 或 analyze 命令查看。不会混入桌面评测。具体命令见项目 README 的 CLI 章节。</p></Details></>;
}
export function Comparison({state,onOpen}:{state:State;onOpen:(id:string)=>void}){
  const groups=new Map<string,{title:string;rows:{run:Run;name:string;score:number;input:number|null;seconds:number|null}[]}>();let incomplete=0;
  for(const run of state.runs)for(const t of run.trials){
    const c=run.configs.find(c=>c.id===t.configId)!;const task=run.tasks.find(q=>q.id===t.taskId)!;const last=t.captures[t.captures.length-1];
    if(t.score.overall==null||!last||t.captures.some(cap=>!cap.harnessUnchanged||!cap.hostUnchanged)||t.usage?.models.join()!==c.baseModel||t.usage?.reasoningLevels.join()!==c.reasoning||t.observations.length){incomplete++;continue;}
    const machine=run.policy.version==='arena-machine-v1';const judge=t.reviews.find(r=>r.id===t.score.machineReviewId);
    if(machine&&(!judge||judge.reviewEnvironment==='local'||t.score.machineCoverage!==100||!judge.model||!judge.reasoningEffort||!judge.imageId||!judge.codexVersion||Object.keys(t.score.machineOverrides||{}).length)){incomplete++;continue;}
    const key=JSON.stringify([machine?[judge?.model,judge?.reasoningEffort,judge?.imageId,judge?.codexVersion]:null,task,run.executionMode,c.baseModel,c.reasoning,run.policy,run.hostFingerprint,[...new Map(t.captures.flatMap(cap=>cap.checks.map(check=>[check.id,check.imageId] as const))).entries()].sort()]);
    const group=groups.get(key)||{title:task.title+' · '+c.baseModel+' / '+c.reasoning,rows:[]};
    group.rows.push({run,name:c.name+' v'+c.revision+(c.preparationOverride?' · 本次技能已调整':''),score:t.score.overall,input:t.usage.inputTokens,seconds:t.usage.activeSeconds});groups.set(key,group);
  }
  return <><h1 className="page-title">同条件结果</h1><p className="muted">按相同题目版本、执行方式、模型、推理档位、评分策略和已记录宿主指纹分组。机器方案还需同一裁判、完整机器覆盖且未经人工改分；修正后的成绩在单次结果页显示。本机裁判尚无完整环境指纹，暂不纳入严格比较。需有实际日志并补齐评分。{incomplete} 条证据不足或条件改变的记录仍在评测历史中。</p>
    {groups.size?[...groups.entries()].map(([key,g])=><Panel key={key} title={g.title}><div className="overflow-x-auto"><table><thead><tr><th>配置版本</th><th>综合分</th><th>输入 Token</th><th>活动秒数</th><th>原始记录</th></tr></thead><tbody>{g.rows.map((r,i)=><tr key={i}><td>{r.name}</td><td>{num(r.score)}</td><td>{num(r.input)}</td><td>{num(r.seconds)}</td><td><button className="btn-ghost" onClick={()=>onOpen(r.run.id)}>查看证据</button></td></tr>)}</tbody></table></div><p className="muted">{g.rows.length} 条记录。无预设排名与误差范围；单次差异不能说明 Harness 改动的可靠收益。</p></Panel>):<Empty>目前没有满足分组条件的已完成结果。不会为示例配置预设成绩。</Empty>}
    <Details title="比较仍有哪些限制"><p className="text-sm leading-7">桌面版本、其他全局技能、插件、人工介入和任务本身的随机性仍可能影响结果。即使条件记录一致，也不能由一次跑分证明因果。项目构建与 Bug 修复不合成一个总榜；多轮是同一题的连续工作，不能当成多道独立题。当前不计算置信区间或自动宣布胜者。</p></Details></>;
}
export {Guide} from './Guide';

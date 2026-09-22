import {ArrowUpRight,Archive,Download,Search,RotateCcw} from 'lucide-react';
import {useState} from 'react';
import type {State,Act,Run} from './types';
import {Panel,Details,Empty,num,date} from './ui';
import {downloadRun} from './api';
export function History({state,act,onOpen,onError}:{state:State;act:Act;onOpen:(id:string)=>void;onError:(s:string)=>void}){
  const [archived,setArchived]=useState(false);const [query,setQuery]=useState('');
  const runs=(archived?state.archivedRuns:state.runs).filter(r=>(r.id+r.notes+r.tasks.map(t=>t.title).join()+r.configs.map(c=>c.name).join()).toLowerCase().includes(query.toLowerCase()));
  const completed=state.runs.filter(r=>r.state==='completed').length;
  return <><header className="page-heading"><div><span className="eyebrow">实验档案</span><h1 className="page-title">每次交付，都有迹可循。</h1><p>保留当时的配置，回看产物与评分证据。</p></div><div className="history-count"><strong>{state.runs.length}</strong><span>次评测 · {completed} 次交付结束</span></div></header>
    <div className="history-toolbar"><div className="catalog-switch"><button className={!archived?'active':''} onClick={()=>setArchived(false)}>活动记录 <span className="tab-count">{state.runs.length}</span></button><button className={archived?'active':''} onClick={()=>setArchived(true)}>已归档 <span className="tab-count">{state.archivedRuns.length}</span></button></div><label className="search-field"><Search size={17}/><input aria-label="搜索历史" placeholder="搜索题目、配置或备注" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
    {runs.length?<section className="history-list" aria-label="评测记录"><div className="history-table-head"><span>任务 / 配置</span><span>状态与证据</span><span>创建时间</span><span>操作</span></div>{runs.map(r=><article className="history-row" key={r.id}><div className="history-task"><button onClick={()=>onOpen(r.id)}>{r.tasks.map(t=>t.title).join('、')}<ArrowUpRight size={16}/></button><p>{r.configs.map(c=>`${c.name} v${c.revision} · ${c.baseModel} / ${c.reasoning}${c.preparationOverride?' · 技能已调整':''}`).join('；')}</p>{r.notes&&<small>{r.notes}</small>}</div><div className="history-state"><span className={'status-pill '+(r.state==='completed'?'done':'pending')}><span/>{r.state==='completed'?'交付结束':'进行中'}</span><small>{r.trials.length} 个工作区 · {r.trials.reduce((n,t)=>n+t.captures.length,0)} 份回收</small></div><time title={r.id}>{date(r.createdAt)}</time><div className="history-actions"><button className="icon-button" aria-label={'导出 '+r.tasks.map(t=>t.title).join('、')} title="导出 ZIP" onClick={()=>downloadRun(r.id).catch(e=>onError(e.message))}><Download size={17}/></button><button className="icon-button" aria-label={(archived?'恢复 ':'归档 ')+r.tasks.map(t=>t.title).join('、')} title={archived?'恢复记录':'归档记录'} onClick={()=>act(`/runs/${r.id}/archive`,{archived:!archived,revision:r.revision}).catch(()=>{})}>{archived?<RotateCcw size={17}/>:<Archive size={17}/>}</button></div></article>)}</section>:<Empty><strong>{query?'没有匹配的记录':archived?'归档为空':'从第一次评测开始'}</strong><p>{query?'试试其他题目、配置名称或备注。':archived?'归档的评测可以随时恢复。':'在工作台完成一次评测，产物与过程将保留在这里。'}</p></Empty>}
    <Details title={`CLI 实验档案 · ${state.legacyExperiments} 次`}><p className="muted">CLI 实验单独保存在 runs/，使用 chb report 或 chb analyze 查看，不混入桌面评测。</p></Details></>;

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
  return <><header className="page-heading"><div><span className="eyebrow">同条件比较</span><h1 className="page-title">看清差异，再做选择。</h1><p>只比较题目、模型、评分与已记录环境条件一致的交付。</p></div><div className="history-count"><strong>{groups.size}</strong><span>组可比较结果</span></div></header><Details title={`比较条件 · ${incomplete} 条记录暂未纳入`}><p>机器方案需要相同裁判、完整机器覆盖且未经人工改分；修正成绩在单次结果页显示。本机裁判暂缺完整环境指纹，不纳入严格比较。需有实际日志并补齐评分；证据不足或条件变化的记录保留在评测历史中。</p></Details>
    {groups.size?[...groups.entries()].map(([key,g])=><Panel key={key} title={g.title}><div className="overflow-x-auto"><table><thead><tr><th>配置版本</th><th>综合分</th><th>输入 Token</th><th>活动秒数</th><th>原始记录</th></tr></thead><tbody>{g.rows.map((r,i)=><tr key={i}><td>{r.name}</td><td>{num(r.score)}</td><td>{num(r.input)}</td><td>{num(r.seconds)}</td><td><button className="btn-ghost" onClick={()=>onOpen(r.run.id)}>查看证据</button></td></tr>)}</tbody></table></div><p className="muted">{g.rows.length} 条记录。无预设排名与误差范围；单次差异不能说明 Harness 改动的可靠收益。</p></Panel>):<Empty>目前没有满足分组条件的已完成结果。不会为示例配置预设成绩。</Empty>}
    <Details title="比较仍有哪些限制"><p className="text-sm leading-7">桌面版本、其他全局技能、插件、人工介入和任务本身的随机性仍可能影响结果。即使条件记录一致，也不能由一次跑分证明因果。项目构建与 Bug 修复不合成一个总榜；多轮是同一题的连续工作，不能当成多道独立题。当前不计算置信区间或自动宣布胜者。</p></Details></>;
}
export {Guide} from './Guide';

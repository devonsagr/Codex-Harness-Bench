import {useState} from 'react';
import type {Act,Config,Run,State} from './types';
import {Details,Field} from './ui';

export type ExperimentSettings={hypothesis:string;repeats:number;activeMinutes:number;maxTokens:number|null};
export type ExperimentPlan=ExperimentSettings & {version:string;sha256:string;configIds:string[];taskIds:string[];changedFields:string[];plannedTrials:number};
type Evidence={status:string;reason:string;source:string};
type Attempt={trialId:string;title:string;repeat:number;state:string;outcome:string;overBudget:boolean;budgetKnown:boolean;delivery:Evidence;conditions:string[];tokens:number|null;activeSeconds:number|null;assessment:{requirements:number;met:number;unknown:number;notMet:number;referenceScore:number|null;calibrated:boolean}};
type Pair={pairId:string;taskId:string;repeat:number;a:Attempt;b:Attempt;conditions:string[];matched:boolean;successDelta:number|null;tokenDelta:number|null;secondsDelta:number|null};
type Resource={total:number|null;observedTotal:number;known:number;planned:number;perSuccess:number|null};
export type ExperimentReport={version:string;status:string;conclusion:string;limitations:string[];plannedPairs:number;matchedPairs:number;verifiedPairs:number;successDelta:number|null;observedSuccessDelta:number|null;medianTaskDelta:number|null;pairs:Pair[];arms:{arm:string;name:string;planned:number;passed:number;failed:number;unknown:number;interrupted:number;overBudget:number;rate:number|null;bounds:[number,number];metrics:{tokens:Resource;activeSeconds:Resource}}[]};

export const defaultExperiment:ExperimentSettings={hypothesis:'比较附加规则和技能是否改善交付，并减少完成同一任务所需的资源。',repeats:2,activeMinutes:30,maxTokens:null};
const fields:Record<string,string>={agentsPrompt:'规则正文',customConstraints:'个人约束',skills:'选用技能',skillMode:'技能调用方式',interactiveMode:'交互方式',nativeSettings:'原生设置',integrations:'工具开关'};
const count=(n:number|null)=>n==null?'未记录':Math.round(n).toLocaleString();
const minutes=(n:number|null)=>n==null?'未记录':`${(n/60).toFixed(1)} 分钟`;
const signed=(n:number|null,unit='')=>n==null?'—':`${n>0?'+':''}${n.toLocaleString(undefined,{maximumFractionDigits:1})}${unit}`;

export function ExperimentSetup({state,act,config,candidateId,onCandidate,settings,onChange,taskCount}:{state:State;act:Act;config:Config;candidateId:string;onCandidate:(id:string)=>void;settings:ExperimentSettings;onChange:(value:ExperimentSettings)=>void;taskCount:number}){
  const [error,setError]=useState('');
  const compatible=state.configs.filter(c=>c.id!==config.id&&c.baseModel===config.baseModel&&c.reasoning===config.reasoning&&(c.serviceTier||'')===(config.serviceTier||''));
  const candidate=compatible.find(c=>c.id===candidateId);
  const changed=candidate?Object.keys(fields).filter(k=>JSON.stringify(config[k as keyof Config])!==JSON.stringify(candidate[k as keyof Config])):[];
  const copy=async()=>{setError('');try{const next=await act<Config>('/configs/minimal-copy',{configId:config.id,revision:config.revision});onCandidate(next.id);}catch(e){setError((e as Error).message);}};
  return <section className="harness-setup" aria-label="Harness 对照设置">
    <div className="harness-heading"><div><h3>同模型，比较两套 Harness</h3><p>相同题目与预算，每次独立执行。A 为上方配置，B 为待比较配置。</p></div><button type="button" className="btn-secondary" onClick={()=>void copy()}>从 A 创建精简对照</button></div>
    <div className="harness-form-grid"><Field label="B · 待比较配置"><select value={candidate?.id||''} onChange={e=>onCandidate(e.target.value)}><option value="">选择同模型、档位和速度的配置</option>{compatible.map(c=><option key={c.id} value={c.id}>{c.name} · v{c.revision}</option>)}</select></Field><Field label="每题每套配置独立重复"><select value={settings.repeats} onChange={e=>onChange({...settings,repeats:Number(e.target.value)})}>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n} 次</option>)}</select></Field><Field label="每次活动时间预算"><select value={settings.activeMinutes} onChange={e=>onChange({...settings,activeMinutes:Number(e.target.value)})}>{[5,15,30,60,120,240].map(n=><option key={n} value={n}>{n} 分钟</option>)}</select></Field><Field label="每次 Token 预算（可留空）"><input type="number" min={1000} max={100000000} value={settings.maxTokens??''} onChange={e=>onChange({...settings,maxTokens:e.target.value?Number(e.target.value):null})} placeholder="输入与输出总量，含缓存输入"/></Field></div>
    <Field label="本次要验证什么"><textarea rows={2} maxLength={1000} value={settings.hypothesis} onChange={e=>onChange({...settings,hypothesis:e.target.value})}/></Field>
    {candidate&&<p>变化：{changed.map(k=>fields[k]).join('、')||'内容相同，请更换配置'}。共同模型：{config.baseModel} / {config.reasoning||'默认'}。</p>}
    <p className="muted">精简副本只移除附加规则、个人约束和选用技能，保留模型与工具设置，仍继承宿主。创建不会改写宿主配置。活动预算事后核对，不自动停止桌面任务。</p>
    <p className={taskCount*settings.repeats*2>60?'alert-error':'muted'}>{taskCount} 题 × 2 套配置 × {settings.repeats} 次 = {taskCount*settings.repeats*2} 个独立工作区（上限 60）。按 A/B、B/A 顺序执行，不自动调用模型。</p>
    {error&&<p role="alert" className="alert-error">{error}</p>}
  </section>;
}

function AttemptResult({attempt,onSelect}:{attempt:Attempt;onSelect?:(id:string)=>void}){
  const label=attempt.outcome==='passed'?'预算内验收通过':attempt.overBudget?'超过预算':attempt.outcome==='failed'?'验收失败':'待确认';
  return <div className="harness-attempt"><strong className={attempt.outcome==='failed'?'text-red-600':''}>{label}</strong><span>{attempt.delivery.reason}</span><small>{count(attempt.tokens)} Token · {minutes(attempt.activeSeconds)}</small>{attempt.assessment.requirements>0&&<small>AI 条款参考：{attempt.assessment.met}/{attempt.assessment.requirements} 成立，{attempt.assessment.unknown} 未验证</small>}{onSelect&&<button type="button" className="btn-ghost" onClick={()=>onSelect(attempt.trialId)}>查看执行与证据</button>}</div>;
}

export function HarnessReport({run,onSelect}:{run:Run;onSelect?:(id:string)=>void}){
  const plan=run.experiment,report=run.experimentReport;
  const [page,setPage]=useState(0);
  if(!plan||!report)return null;
  const pages=Math.max(1,Math.ceil(report.pairs.length/6)),current=Math.min(page,pages-1);
  return <section className="harness-report panel" aria-label="Harness 配对结果">
    <div className="harness-heading"><div><h2>Harness 交付与效率对照</h2><p>{plan.hypothesis}</p></div><span>{report.verifiedPairs}/{report.plannedPairs} 对证据齐全</span></div>
    <div className="harness-arm-grid">{report.arms.map(arm=><article className="harness-arm" key={arm.arm}><div><span>{arm.arm}</span><h3>{arm.name}</h3></div><strong className="harness-main-number">{arm.passed}<small> / {arm.planned} 次预算内验收通过</small></strong><p>{arm.failed} 次失败 · {arm.unknown} 次待验证 · {arm.interrupted} 次中断 · {arm.overBudget} 次超预算</p><p>{arm.rate==null?`通过率尚未完整；未知结果范围 ${(arm.bounds[0]*100).toFixed(0)}%–${(arm.bounds[1]*100).toFixed(0)}%`:`本题集通过率 ${(arm.rate*100).toFixed(1)}%`}</p><dl><dt>执行 Token（含失败）</dt><dd>{arm.metrics.tokens.total==null?`${count(arm.metrics.tokens.observedTotal)} 已知 · ${arm.metrics.tokens.known}/${arm.planned} 次记录`:count(arm.metrics.tokens.total)}</dd><dt>活动时间（含失败）</dt><dd>{minutes(arm.metrics.activeSeconds.total)}</dd><dt>每次有效交付 Token</dt><dd>{count(arm.metrics.tokens.perSuccess)}</dd></dl></article>)}</div>
    <div className="harness-conclusion"><strong>{report.conclusion}</strong><p>{report.successDelta==null?(report.observedSuccessDelta==null?'尚不计算整体提升率':`记录中的 B − A 通过率差：${signed(report.observedSuccessDelta*100,' 个百分点')}；条件未对齐，不能归因于 Harness`):`B − A 验收通过率：${signed(report.successDelta*100,' 个百分点')}`} · 实际条件齐全 {report.matchedPairs}/{report.plannedPairs} 对</p><p className="muted">变化：{plan.changedFields.map(k=>fields[k]||k).join('、')}；每次 {plan.activeMinutes} 分钟{plan.maxTokens?` / ${count(plan.maxTokens)} Token`:''}。AI 质量参考分不参与通过率。</p></div>
    <div className="harness-pairs">{report.pairs.slice(current*6,current*6+6).map(pair=><article className="harness-pair" key={pair.pairId}><header><h3>{pair.a.title}</h3><span>第 {pair.repeat} 次配对</span></header><div className="harness-pair-values"><div><small>A</small><AttemptResult attempt={pair.a} onSelect={onSelect}/></div><div><small>B</small><AttemptResult attempt={pair.b} onSelect={onSelect}/></div></div><p className="muted">B − A：{signed(pair.tokenDelta)} Token · {signed(pair.secondsDelta==null?null:pair.secondsDelta/60,' 分钟')}{!pair.matched?' · 条件未对齐，差值仅描述记录':''}</p>{pair.conditions.length>0&&<Details title={`比较条件 · ${pair.conditions.length} 项待核对`}>{pair.conditions.map(reason=><p key={reason}>{reason}</p>)}</Details>}</article>)}</div>
    {pages>1&&<div className="harness-pagination"><button className="btn-secondary" disabled={current===0} onClick={()=>setPage(current-1)}>上一页</button><span>{current+1} / {pages}</span><button className="btn-secondary" disabled={current===pages-1} onClick={()=>setPage(current+1)}>下一页</button></div>}
    <Details title="计算方式与范围"><p>原题或已验证的专属程序验收决定通过/失败；共用烟检、单张截图、AI 高分不构成整题通过。全部计划试次进入分母，未知时展示可能范围；只有完整且条件匹配的配对才计算总体差值。</p>{report.limitations.map(value=><p key={value}>{value}</p>)}<p>冻结协议：{plan.version} · {plan.sha256.slice(0,16)}。完整计划与报告包含在本次 ZIP 导出中。</p></Details>
  </section>;
}

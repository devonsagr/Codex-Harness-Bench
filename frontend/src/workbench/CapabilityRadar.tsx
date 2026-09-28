import {useId,useState} from 'react';
import type {ConfigResult,TaskResult} from './configResults';
import {matchedComparison} from './configResults';
import {capabilityProfiles} from './capabilityProfiles';
import type {CapabilityAxis,CapabilityProfile} from './capabilityProfiles';
import {apiEquivalent} from './presentation';

const taskKey=(task:TaskResult)=>`${task.task.id}:${task.task.revision}:${task.protocolKey}`;
const point=(index:number,total:number,radius:number)=>{
  const angle=-Math.PI/2+index*2*Math.PI/total;
  return {x:260+Math.cos(angle)*radius,y:260+Math.sin(angle)*radius};
};
const chartPoint=(index:number,total:number,value:number)=>point(index,total,150*value/100);
const coordinate=(value:{x:number;y:number})=>`${value.x.toFixed(1)},${value.y.toFixed(1)}`;
const polygon=(total:number,radius:number)=>Array.from({length:total},(_,index)=>coordinate(point(index,total,radius))).join(' ');
const scored=(axis:CapabilityAxis)=>axis.score!=null;

function RadarFigure({profile,compare,title}:{profile:CapabilityProfile;compare?:CapabilityProfile;title:string}){
  const id=useId().replace(/:/g,'');
  const total=profile.axes.length;
  const summary=(name:string,axes:CapabilityAxis[])=>`${name}：${axes.map(axis=>`${axis.label}${axis.score==null?'未测':axis.score.toFixed(1)+'分，'+axis.tasks+'题'}`).join('；')}`;
  const draw=(axes:CapabilityAxis[],kind:'primary'|'comparison')=>{
    const measured=axes.flatMap((axis,index)=>axis.score==null?[]:[{axis,index,position:chartPoint(index,total,axis.score)}]);
    return <g className={'radar-series '+kind}>
      {measured.length>=3&&<polygon points={measured.map(item=>coordinate(item.position)).join(' ')} className="radar-shape"/>}
      {axes.map((axis,index)=>{const next=(index+1)%total;return axis.score!=null&&axes[next].score!=null?<line key={'line-'+axis.id} className="radar-edge" x1={chartPoint(index,total,axis.score).x} y1={chartPoint(index,total,axis.score).y} x2={chartPoint(next,total,axes[next].score!).x} y2={chartPoint(next,total,axes[next].score!).y}/>:null;})}
      {measured.length>=3&&measured.map((item,index)=>{const next=measured[(index+1)%measured.length];return (item.index+1)%total===next.index?null:<line key={'gap-'+item.axis.id} className="radar-edge is-gap" x1={item.position.x} y1={item.position.y} x2={next.position.x} y2={next.position.y}/>;})}
      {axes.map((axis,index)=>axis.score!=null?<circle key={axis.id} className="radar-dot" cx={chartPoint(index,total,axis.score).x} cy={chartPoint(index,total,axis.score).y} r="4.5"/>:null)}
    </g>;
  };
  const any=profile.axes.some(scored);
  return <figure className="capability-figure"><svg viewBox="0 0 520 520" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>{title} · {profile.title}能力雷达</title>
    <desc id={`${id}-desc`}>{summary('当前配置',profile.axes)}{compare?`。${summary('匹配题目对照',compare.axes)}`:''}。空轴不按零分计算。</desc>
    <g className="radar-grid">{[.25,.5,.75,1].map(level=><polygon key={level} points={polygon(total,150*level)}/>)}{profile.axes.map((axis,index)=>{const end=point(index,total,150);return <line key={axis.id} x1="260" y1="260" x2={end.x} y2={end.y}/>;})}</g>
    {compare&&draw(compare.axes,'comparison')}{draw(profile.axes,'primary')}
    {profile.axes.map((axis,index)=>{const pos=point(index,total,196);const alignment=pos.x<215?'end':pos.x>305?'start':'middle';return <text key={axis.id} x={pos.x} y={pos.y-4} textAnchor={alignment}><tspan x={pos.x}>{axis.label}</tspan><tspan className="radar-label-value" x={pos.x} dy="16">{axis.score==null?'未测':`${axis.score.toFixed(1)} · ${axis.tasks} 题`}</tspan></text>;})}
    {!any&&<text className="radar-empty" x="260" y="262" textAnchor="middle">尚无可计分证据</text>}
  </svg><figcaption><span><i className="radar-legend-primary"/>当前配置</span>{compare&&<span><i className="radar-legend-comparison"/>匹配题目对照</span>}<small>阴影连接已测点；虚线跨未测轴，未测不计分</small></figcaption></figure>;
}

function AxisOverview({axis,compare,active,onSelect}:{axis:CapabilityAxis;compare?:CapabilityAxis;active:boolean;onSelect:()=>void}){
  return <button type="button" className={'capability-axis-card'+(active?' is-active':'')+(axis.score==null?' is-unmeasured':'')} aria-pressed={active} onClick={onSelect}>
    <span className="capability-axis-card-top"><strong>{axis.label}</strong><b>{axis.score==null?'未测':axis.score.toFixed(1)}</b></span>
    <span className="capability-axis-bar" aria-hidden="true"><span style={{width:`${axis.score??0}%`}}/></span>
    <small>{axis.score==null?'尚无独立评分证据':`${axis.tasks} 题 · ${axis.trials} 次`}{compare?.score!=null?` · 对照 ${compare.score.toFixed(1)}`:''}</small>
  </button>;
}

function AxisEvidence({axis,onOpen}:{axis:CapabilityAxis;onOpen:(id:string)=>void}){
  return <section className="capability-evidence" aria-live="polite"><header><span className="eyebrow">逐项证据</span><h4>{axis.label} <small>{axis.score==null?'未测':`${axis.score.toFixed(1)} 分 · ${axis.tasks} 道题`}</small></h4><p>{axis.score==null?'当前题集没有这一能力的有效细分项；不按零分处理，也不推断能力高低。':'每道题先平均本轴有证据的细分项；下方可继续展开原评测与引用依据。'}</p></header>
    {axis.samples.length>0&&<div className="capability-evidence-grid">{axis.samples.map(sample=><article key={`${sample.taskId}:${sample.runs[0]?.id}`}><div className="capability-evidence-title"><strong>{sample.title}</strong><b>{sample.score.toFixed(1)}</b></div><small>题目均值 · {sample.trials} 次试测</small><details><summary>查看评分细项与原始记录</summary><div className="capability-evidence-runs">{sample.runs.map((run,index)=><div key={`${run.id}:${index}`}><button type="button" onClick={()=>onOpen(run.id)}>第 {index+1} 次 · {run.score.toFixed(1)} 分 · 查看原始证据 ↗</button><ul className="capability-facets">{run.facets.map((facet,part)=><li key={`${part}:${facet.label}`}><strong>{facet.label} · {facet.score.toFixed(1)} 分</strong><small>{facet.basis}</small></li>)}</ul></div>)}</div></details></article>)}</div>}
  </section>;
}

function EfficiencyStrip({tasks}:{tasks:TaskResult[]}){
  const entries=tasks.flatMap(task=>task.entries),total=entries.length;
  const tokens=entries.map(entry=>entry.trial.usage?.totalTokens).filter((value):value is number=>typeof value==='number'&&Number.isFinite(value)&&value>=0);
  const seconds=entries.map(entry=>entry.trial.usage?.activeSeconds).filter((value):value is number=>typeof value==='number'&&Number.isFinite(value)&&value>=0);
  const costs=entries.map(entry=>entry.trial.usage?apiEquivalent(entry.trial.usage):null);
  const costReady=total>0&&costs.every(cost=>cost&&typeof cost.low==='number'&&typeof cost.high==='number');
  const low=costReady?costs.reduce((sum,cost)=>sum+cost!.low!,0):null;
  const high=costReady?costs.reduce((sum,cost)=>sum+cost!.high!,0):null;
  const repeated=tasks.filter(task=>task.entries.length>1);
  const spread=repeated.length?Math.max(...repeated.map(task=>{const values=task.entries.map(entry=>entry.trial.score.overall!);return Math.max(...values)-Math.min(...values);})):null;
  return <dl className="capability-efficiency"><div><dt>被测 Token</dt><dd>{tokens.length===total&&total?tokens.reduce((a,b)=>a+b,0).toLocaleString('zh-CN'):'—'}</dd><small>{tokens.length}/{total} 次有记录</small></div><div><dt>活动时长</dt><dd>{seconds.length===total&&total?`${(seconds.reduce((a,b)=>a+b,0)/60).toFixed(1)} 分`:'—'}</dd><small>{seconds.length}/{total} 次有记录</small></div><div><dt>API 等值估算</dt><dd>{low==null?'—':`$${low.toFixed(2)}–$${high!.toFixed(2)}`}</dd><small>估算值，非实际账单</small></div><div><dt>重复稳定性</dt><dd>{spread==null?'待重复':`最大分差 ${spread.toFixed(1)}`}</dd><small>{repeated.length}/{tasks.length} 道题有重复</small></div></dl>;
}

export function CapabilityRadar({group,all,onOpen}:{group:ConfigResult;all:ConfigResult[];onOpen:(id:string)=>void}){
  const [compareKey,setCompareKey]=useState('');
  const [axisId,setAxisId]=useState('');
  const options=all.filter(candidate=>candidate.key!==group.key&&matchedComparison(group,candidate).tasks?.length);
  const candidate=options.find(option=>option.key===compareKey);
  const pair=candidate?matchedComparison(group,candidate):null;
  const shared=pair?.tasks?.length?new Set(pair.tasks.map(item=>`${item.task.id}:${item.task.revision}`)):null;
  const candidateKeys=candidate?new Set(candidate.tasks.map(taskKey)):null;
  const baseTasks=shared&&candidateKeys?group.tasks.filter(task=>shared.has(`${task.task.id}:${task.task.revision}`)&&candidateKeys.has(taskKey(task))):group.tasks;
  const baseKeys=new Set(baseTasks.map(taskKey));
  const comparedTasks=candidate?candidate.tasks.filter(task=>baseKeys.has(taskKey(task))):[];
  const profiles=capabilityProfiles(baseTasks);
  const compared=candidate?capabilityProfiles(comparedTasks):null;
  const active=profiles[0];
  const other=compared?.[0];
  const measured=active.axes.filter(scored).length;
  const oldAutoRuns=baseTasks.flatMap(task=>task.entries).filter(entry=>entry.run.policy.taskTypeAuto&&entry.run.policy.autoScorecardVersion!=='project-tasktype-v3');
  const frontendOnly=baseTasks.length>0&&baseTasks.every(task=>task.task.hasFrontendUI&&!task.task.publicSource);
  const entries=baseTasks.flatMap(task=>task.entries);
  const highTasks=baseTasks.filter(task=>task.mean>=90).length;
  const repeatedTasks=baseTasks.filter(task=>task.entries.length>1).length;
  const humanReviews=entries.filter(entry=>entry.trial.reviews.some(review=>review.kind==='human')).length;
  const sameModelJudges=entries.filter(entry=>entry.trial.reviews.some(review=>review.id===entry.trial.score.machineReviewId&&review.model?.toLowerCase()===group.config.baseModel.toLowerCase())).length;
  const checkedTrials=entries.filter(entry=>entry.trial.captures[entry.trial.captures.length-1]?.checks.some(check=>check.status==='passed'||check.status==='failed')).length;
  const selectedAxis=active.axes.find(axis=>axis.id===axisId)||active.axes.find(scored)||active.axes[0];
  return <section className="capability-panel" aria-label="配置能力画像"><header className="capability-panel-head"><div><span className="eyebrow">有证据的能力画像</span><h3>六项能力，一眼看清</h3><p>每轴只取对应的实际评分证据；整组未齐时仅展示已测轴，不发布配置综合分。未测不算 0。</p></div>{options.length>0&&<label>同题对照<select value={compareKey} onChange={event=>setCompareKey(event.target.value)}><option value="">不对照</option>{options.map(option=><option key={option.key} value={option.key}>{option.config.name} v{option.config.revision}</option>)}</select></label>}</header>
    {candidate&&<p className="capability-match-note">仅用两套配置共同的 {baseTasks.length} 道同版本、同评分协议题绘制对照；上方的配置综合分仍来自各自完整题集。</p>}
    {oldAutoRuns.length>0&&active.axes.find(axis=>axis.id==='reasoning')?.score==null&&<p className="capability-match-note">这组有 {oldAutoRuns.length} 次评测使用旧版自动评分卡，未要求独立评估逻辑取舍；旧记录按冻结规则保留“未测”。新版默认评分卡会从交付物的可见决策证据评估此项。</p>}
    <div className="capability-content"><div className="capability-chart"><div className="capability-chart-heading"><div><h4>{active.title}</h4><p>{active.description}</p></div><strong>{measured}<small> / {active.axes.length} 轴已测</small></strong></div><RadarFigure profile={active} compare={other} title={group.config.name}/></div><div className="capability-overview"><div className="capability-overview-head"><h4>六项速览</h4><p>选择一项，在下方查看题目、细分分数与证据。</p></div><div className="capability-axis-grid">{active.axes.map(axis=><AxisOverview key={axis.id} axis={axis} compare={other?.axes.find(item=>item.id===axis.id)} active={selectedAxis.id===axis.id} onSelect={()=>setAxisId(axis.id)}/>)}</div><section className="capability-score-audit" aria-label="高分证据核查"><header><span className="eyebrow">高分证据核查</span><strong>{highTasks} / {baseTasks.length} 道题达 90 分</strong></header><p>这些是按冻结评分卡计算的单次 AI 参考分，90 分不代表需求或视觉质量已被 90% 验证。</p><dl><div><dt>重复试测的题</dt><dd>{repeatedTasks}/{baseTasks.length}</dd></div><div><dt>有人工评分记录的试测</dt><dd>{humanReviews}/{entries.length}</dd></div><div><dt>有程序检查结果的试测</dt><dd>{checkedTrials}/{entries.length}</dd></div></dl><p>{sameModelJudges>0?`${sameModelJudges} 次使用与被测配置同名的裁判模型；`:'裁判模型和提示词会影响质量判断；'}{frontendOnly?'网页通用检查只能覆盖启动、部分交互和窄屏，不能替代题意、视觉与完整流程验收。':'程序检查只覆盖题目预先配置的断言，不能证明未检查的需求。'} 点击能力项并展开下方题目，可逐条核对实际引用和检查记录。</p></section></div></div>
    <AxisEvidence axis={selectedAxis} onOpen={onOpen}/>
    <EfficiencyStrip tasks={baseTasks}/><details className="capability-method"><summary>六轴、细分项和综合分怎么算？</summary><p>每道题先按创建时冻结的评分项权重形成单题综合分；配置成绩对同题重复先求均值，再对不同题等权平均。雷达是另一种诊断视图：读取同一批有证据的细分项原始 0–100 分，同一轴内平均、同题重复平均、不同题等权平均；雷达轴不再乘单题权重，也不反过来改变综合分。</p><p>目标兑现看目标与范围，工程实现看验证、边界和维护，网页体验看实际交互与视觉，推理决策看推理与澄清，协作沟通看沟通与阶段推进，稳健交付看回归、边界、安全、性能与交接。每题只计适用且已评分的细项；同一细项可以解释多个诊断轴，但在单题综合分里只按冻结权重计一次。展开轴可查看该题真正有分的细项与依据；没测到的轴留空，不推断为 0。</p></details><p className="capability-footnote">成本、速度和重复波动单列，不换算进能力分；AI 参考项与程序验收项在证据里分别标明。不同题型的轴不能按图形面积比较成模型排名。</p>
  </section>;
}

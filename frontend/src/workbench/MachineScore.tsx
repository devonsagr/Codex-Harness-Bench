import {useState} from 'react';
import type {Trial,Run,State} from './types';
import {Panel,Details,Dialog,Field,ScoreSlider,num,date} from './ui';
import {verdicts} from './Contracts';

export function MachineScore({run,trial:t,state,act,disabled}:{run:Run;trial:Trial;state:State;act:(name:string,data?:unknown)=>Promise<unknown>;disabled:boolean}){
  const latest=t.captures[t.captures.length-1];
  const [model,setModel]=useState(state.models[0]?.id||'');
  const [editing,setEditing]=useState<string|null>(null);const [value,setValue]=useState('');const [reason,setReason]=useState('');
  const [editingEvidence,setEditingEvidence]=useState<{reviewId?:string|null;evidenceKey?:string|null}>({});
  const report=t.reviews.find(r=>r.id===t.score.machineReviewId);
  const busy=['checking','judging'].includes(t.state);
  const ratings=t.score.machineRatings||{};
  const task=run.tasks.find(task=>task.id===t.taskId)!;
  const correct=async(withdraw=false)=>{if(!editing)return;await act('machine-correction',{...editingEvidence,changes:{[editing]:{score:withdraw?null:Number(value),reason}}});setEditing(null);};
  return <Panel title="机器评分与人工修正">
    <div className="metric-grid"><div className="panel-subtle p-3"><p className="muted">机器原分{(t.score.machineCoverage||0)<100?' · 暂定':''}</p><strong className="text-xl">{num(t.score.machine??null)}</strong></div><div className="panel-subtle p-3"><p className="muted">机器已评分权重</p><strong className="text-xl">{t.score.machineCoverage||0}%</strong></div><div className="panel-subtle p-3"><p className="muted">最终分（含人工修正）</p><strong className="text-xl">{num(t.score.overall)}</strong></div></div>
    <p className="muted">缺证据的项保持未验证。完整总分需各项有分且交付结束；暂定分只代表已评分部分。</p>
    {(!latest.harnessUnchanged||!latest.hostUnchanged)&&<p className="alert-error">规则或宿主配置指纹变化，请核对比较条件。</p>}{t.lastJobError&&<p role="alert" className="alert-error">{t.lastJobError.message}</p>}
    <div className="config-select-row"><Field label="裁判模型"><input list="machine-models" value={model} onChange={e=>setModel(e.target.value)}/><datalist id="machine-models">{state.models.map(m=><option key={m.id} value={m.id}/>)}</datalist></Field><button className="btn-primary" disabled={disabled||busy||!model.trim()} onClick={()=>void act('judge',{captureId:latest.id,model}).catch(()=>{})}>{busy?'正在检查与评分…':report?'重新自动评分':'自动检查并评分'}</button>{busy&&<button className="btn-secondary" onClick={()=>void act('stop').catch(()=>{})}>停止</button>}</div>
    <p className="muted">使用模型额度 · 独立 Harbor 裁判 · 自动运行已有脚本并检查项目副本</p>
    {report?.summary&&<p className="text-sm whitespace-pre-wrap">{report.summary}</p>}
    <div className="rubric-list">{Object.entries(run.policy.rubrics||{}).filter(([key])=>run.policy.dimensions[key]>0&&(key!=='ux'||task.hasFrontendUI)).map(([key,item])=>{const rating=ratings[key];const override=t.score.machineOverrides?.[key];return <div key={key} className="py-4 border-b border-slate-200 space-y-2"><div className="flex items-center justify-between gap-4"><strong>{item.label}</strong><div className="flex items-center gap-3"><span>{num(rating?.score??null)}{override&&<> → <strong>{override.score}</strong></>}</span><button className="btn-secondary" disabled={disabled||busy||!report} onClick={()=>{setEditing(key);setEditingEvidence({reviewId:t.score.machineReviewId,evidenceKey:t.score.machineEvidenceKey});setValue(String(t.score.effectiveScores?.[key]??''));setReason('');}}>修正</button></div></div><p className="muted">{rating?({static:'代码静态判断',runtime:'有执行记录',unverified:'未验证'}[rating.method]||rating.method):'等待机器评分'}{override?' · 已人工修正':''}</p>{rating&&<Details title="评分依据与证据"><p>{rating.reason}</p>{rating.evidence.map((e,i)=><div key={i}><small>{e.path?`${e.path}:${e.line}`:e.command||e.checkId}</small><pre className="source">{e.quote}</pre></div>)}{override&&<p>人工修正：{override.reason}</p>}</Details>}</div>;})}</div>
    <Details title={`逐条需求 · ${t.score.acceptance.met}/${t.score.acceptance.required} 必要项满足`}>{task.criteria?.map(c=><div key={c.id}><strong>{c.label}</strong><p>{verdicts[report?.criteria?.[c.id]?.status||'unverified']}</p><p className="muted">{report?.criteria?.[c.id]?.notes}</p></div>)}<p className="muted">人工调分不会改写需求验收和程序通过状态。</p></Details>
    <Details title={`程序检查与裁判执行记录 · ${latest.checks.length} 项脚本`}><p>脚本检查分：{num(t.score.objective)}，作为独立事实与裁判依据，不重复加权。</p>{latest.checks.map(c=><div key={c.id}><strong>{c.label} · {c.status}</strong><pre className="source">{c.output}</pre></div>)}{report?.commands?.map((c,i)=><div key={i}><code>{c.command}</code><p className="muted">退出码 {c.exitCode??'未知'}</p><pre className="source">{c.output}</pre></div>)}</Details>
    {!!t.machineCorrections?.length&&<Details title="人工修正历史">{t.machineCorrections.slice().reverse().map(c=><div key={c.id}><p>{date(c.at)} · {c.reviewId===t.score.machineReviewId?'当前评分版本':'历史评分版本'}</p>{Object.entries(c.changes).map(([k,v])=><p key={k}>{run.policy.rubrics?.[k]?.label}：{v.score??'撤回修正'} · {v.reason}</p>)}</div>)}</Details>}
    <Dialog title={'修正：'+(editing?run.policy.rubrics?.[editing]?.label:'')} open={!!editing} onClose={()=>setEditing(null)}><form className="space-y-4" onSubmit={e=>{e.preventDefault();void correct().catch(()=>{});}}><fieldset disabled={disabled||busy} className="space-y-4"><ScoreSlider label="修正后分数" value={value} onChange={setValue}/><Field label="理由与复核证据"><textarea required value={reason} onChange={e=>setReason(e.target.value)} placeholder="说明实际结果及机器误判之处"/></Field><div className="flex gap-3"><button className="btn-primary">保存修正</button>{editing&&t.score.machineOverrides?.[editing]&&<button type="button" disabled={!reason.trim()} className="btn-secondary" onClick={()=>void correct(true).catch(()=>{})}>恢复机器原分</button>}</div></fieldset></form></Dialog>
  </Panel>;
}

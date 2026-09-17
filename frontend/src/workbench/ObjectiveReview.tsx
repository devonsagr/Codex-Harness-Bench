import {useState} from 'react';
import type {Trial} from './types';
import {Details,Field,date,num} from './ui';

export function ObjectiveReview({trial:t,act,disabled}:{trial:Trial;act:(data:unknown)=>Promise<unknown>;disabled:boolean}){
  const [value,setValue]=useState('');const [reason,setReason]=useState('');const [evidence,setEvidence]=useState('');
  const latest=t.captures[t.captures.length-1];
  return <section className="score-section space-y-3"><h3 className="font-semibold">自动结果与人工裁定</h3>
    <p>自动原分：<strong>{num(t.score.objective)}</strong>　人工裁定客观部分：<strong>{num(t.score.adjudicatedObjective)}</strong>　裁定后总分：<strong>{num(t.score.adjudicatedOverall)}</strong></p>
    <p className="muted">人工裁定单列显示，不修改脚本通过/失败、原始总分或必要条目结论。检查重跑或回收新产物后须重新裁定。历史比较继续使用原始总分。</p>
    <Details title="对自动结果有异议？提交人工裁定"><form className="space-y-3" onSubmit={e=>{e.preventDefault();void act({captureId:latest?.id,evidenceKey:t.score.objectiveEvidenceKey,score:Number(value),reason,evidence});}}><fieldset className="space-y-3" disabled={disabled||t.score.objective==null}>
      <Field label="裁定后客观部分分数（0–100）"><input type="number" required min={0} max={100} step="0.1" value={value} onChange={e=>setValue(e.target.value)}/></Field>
      <Field label="裁定理由"><textarea required value={reason} onChange={e=>setReason(e.target.value)} placeholder="说明检查为何误判、遗漏或不适用"/></Field><Field label="裁定证据"><textarea required value={evidence} onChange={e=>setEvidence(e.target.value)} placeholder="检查名称、输出、文件位置或复现步骤与实际结果"/></Field>
      <div className="flex gap-3 flex-wrap"><button className="btn-secondary">保存人工裁定</button>{t.score.objectiveReviewId&&<button type="button" className="btn-ghost" disabled={!reason.trim()||!evidence.trim()} onClick={()=>void act({captureId:latest?.id,evidenceKey:t.score.objectiveEvidenceKey,score:null,reason,evidence})}>撤回裁定（保留历史）</button>}</div>
    </fieldset>{t.score.objective==null&&<p className="muted">没有完整自动原分时不能裁定；缺失的检查证据仍是未知。</p>}</form></Details>
    {!!t.objectiveReviews?.length&&<Details title={`人工裁定历史 · ${t.objectiveReviews.length} 条`}>{t.objectiveReviews.slice().reverse().map(r=><div key={r.id} className="space-y-1"><p>{date(r.at)} · 自动原分 {r.originalScore} → {r.score==null?'撤回':r.score} · {r.id===t.score.objectiveReviewId?'当前有效':'历史记录'}</p><p className="text-sm whitespace-pre-wrap">{r.reason}</p><p className="muted whitespace-pre-wrap">{r.evidence}</p></div>)}</Details>}
  </section>;
}

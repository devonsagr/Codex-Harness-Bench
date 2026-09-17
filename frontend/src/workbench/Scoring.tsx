import type {Policy,State,Trial,Task} from './types';
import {verdicts} from './Contracts';
import {Field} from './ui';
import {ObjectivePlan,RatingGuide} from './ScorePlan';

export function percentPolicy(p:Policy):Policy{
  const entries=Object.entries(p.dimensions);const total=entries.reduce((n,[,w])=>n+w,0);
  const units=entries.map(([,w])=>Math.floor((total?w/total:1/entries.length)*10000));
  let remaining=10000-units.reduce((a,b)=>a+b,0);
  for(let i=0;remaining>0;i=(i+1)%entries.length){if(total&&entries[i][1]===0)continue;units[i]++;remaining--;}
  return {...p,dimensionUnit:'percent',requireDimensionEvidence:true,dimensions:Object.fromEntries(entries.map(([k],i)=>[k,units[i]/100]))};
}
export const validPercentPolicy=(p:Policy)=>Math.abs(Object.values(p.dimensions).reduce((a,b)=>a+b,0)-100)<.005;
export function ScoringSettings({state,tasks,policy,onChange}:{state:State;tasks:Task[];policy:Policy;onChange:(p:Policy)=>void}){
  const share=(key:string)=>{
    const weight=policy.dimensions[key]||0;const nonUiTotal=Object.entries(policy.dimensions).filter(([k])=>k!=='ux').reduce((n,[,w])=>n+w,0);
    const fmt=(v:number)=>(Math.round((v+Number.EPSILON)*100)/100).toFixed(2);
    const ui='折合总分约 '+fmt(weight*policy.humanWeight/100)+'%';
    const nonUi=key==='ux'?'无界面题不计此项':'无界面题折合总分约 '+fmt(nonUiTotal?weight/nonUiTotal*policy.humanWeight:0)+'%';
    return tasks.length&&tasks.every(t=>!t.hasFrontendUI)?nonUi:tasks.some(t=>!t.hasFrontendUI)?ui+'；'+nonUi:ui;
  };
  const items=policy.rubrics||{};const total=Object.values(policy.dimensions).reduce((a,b)=>a+b,0);
  const add=(key:string,label:string,description:string)=>onChange(percentPolicy({...policy,version:'arena-review-v2',dimensions:{...policy.dimensions,[key]:10},rubrics:{...items,[key]:{label,description}}}));
  return <section className="space-y-6"><h3 className="font-semibold">评分方案与依据</h3>
    <div className="grid sm:grid-cols-2 gap-4"><Field label="客观检查占总分（%）"><input type="number" min={0} max={100} step="0.1" value={policy.objectiveWeight} onChange={e=>onChange({...policy,objectiveWeight:Number(e.target.value),humanWeight:100-Number(e.target.value)})}/></Field><p className="self-center">人工评分占总分 <strong>{policy.humanWeight}%</strong> · 两者合计100%</p></div>
    <p className="muted">总分 = 客观检查分 × {policy.objectiveWeight}% + 人工评分分 × {policy.humanWeight}%。两部分各按0–100分计算；缺少所需证据时总分为空。</p>
    {tasks.some(t=>!t.checks.length)&&policy.objectiveWeight>0&&<div className="score-notice space-y-2"><p>所选题目中有题目未配置自动检查。当前方案无法得到完整总分。</p><button type="button" className="btn-secondary" onClick={()=>onChange({...policy,objectiveWeight:0,humanWeight:100})}>本次改用纯人工验收</button></div>}
    <ObjectivePlan tasks={tasks}/>
    <section className="score-section space-y-4"><h3 className="font-semibold">人工评分 · 查看真实交付后评分</h3><p className="muted">下面全是人工维度。输入的是人工部分内部的百分比，不是得分；内部合计100%。增删维度会按比例重新分配，也可手动填写后归一。默认等权仅是起点。</p>
      <div className="flex gap-3 flex-wrap items-center"><strong aria-live="polite">人工内部合计：{total.toFixed(2)}%</strong><button type="button" className="btn-secondary" onClick={()=>onChange(percentPolicy(policy))}>按当前比例归一到100%</button></div>
      {!validPercentPolicy(policy)&&<p role="alert" className="alert-error">内部占比必须合计100%，调整后才能创建评测。</p>}
      <div className="rubric-list">{Object.entries(items).map(([key,item])=><div className="rubric-row" key={key}><div><strong className="text-sm">{item.label}</strong><p className="muted">{item.description}</p><p className="text-sm">{share(key)}</p></div><Field label="人工内部（%）"><input aria-label={item.label+'：人工内部占比（%）'} type="number" min={0} max={100} step="0.01" value={policy.dimensions[key]??0} onChange={e=>onChange({...policy,dimensions:{...policy.dimensions,[key]:Number(e.target.value)}})}/></Field><button type="button" className="btn-ghost" aria-label={'移除评分项 '+item.label} disabled={Object.keys(items).length<=1} onClick={()=>{const dims={...policy.dimensions};const rubrics={...items};delete dims[key];delete rubrics[key];onChange(percentPolicy({...policy,dimensions:dims,rubrics}));}}>移除</button></div>)}</div>
      <div className="flex gap-3 flex-wrap"><Field label="添加人工评分项"><select disabled={Object.keys(items).length>=16} value="" onChange={e=>{const item=state.rubricCatalog[e.target.value];if(item)add(e.target.value,item.label,item.description);}}><option value="">选择适用维度</option>{Object.entries(state.rubricCatalog).filter(([k])=>!items[k]).map(([k,v])=><option value={k} key={k}>{v.label}</option>)}</select></Field><button type="button" className="btn-secondary" disabled={Object.keys(items).length>=16} onClick={()=>add('custom-'+crypto.randomUUID().slice(0,8),'自定义评分项','按本题的实际证据评分；请在创建前修改名称和依据。')}>添加自定义项</button></div>
      {Object.entries(items).filter(([k])=>k.startsWith('custom-')).map(([key,item])=><div className="grid sm:grid-cols-2 gap-3" key={key}><Field label="自定义评分名称"><input value={item.label} onChange={e=>onChange({...policy,rubrics:{...items,[key]:{...item,label:e.target.value}}})}/></Field><Field label="自定义评分依据"><input value={item.description} onChange={e=>onChange({...policy,rubrics:{...items,[key]:{...item,description:e.target.value}}})}/></Field></div>)}
      <RatingGuide/>
    </section>
    <section className="score-section space-y-3"><h3 className="font-semibold">AI 审查 · 辅助意见，不计总分</h3><p className="muted">回收后可单独启动一次 AI 审查：它读取冻结需求、产物、差异和检查回执，引用文件指出问题；不是再执行原任务，也不是客观检查。它会使用模型额度，不能代替实际运行和人工视觉验收。</p><p className="muted">对自动结果有异议时，可在结果页填写“人工裁定”，附理由与证据；保留自动原分并单列裁定后的分数，不把人工修正伪装成脚本通过。Token、耗时、介入与可靠性另列。</p></section>
  </section>;
}
export function EvaluationMetrics({trial:t}:{trial:Trial}){
  const latest=t.captures[t.captures.length-1];const review=t.reviews.filter(r=>r.kind==='human'&&r.captureId===latest?.id).slice(-1)[0];
  const rows=[['必要需求',`${t.score.acceptance.met}/${t.score.acceptance.required} 已满足（${verdicts[t.score.acceptance.status]||t.score.acceptance.status}）`],['本次快照检查',latest?`${latest.checks.filter(c=>c.status==='passed').length} 通过 / ${latest.checks.length} 已执行 / ${latest.checksConfigured} 已配置`:'尚无回收'],['规则与宿主条件',latest?(latest.harnessUnchanged&&latest.hostUnchanged?'已检查的文件指纹一致':'已检查的文件指纹发生变化'):'尚未核对'],['个人约束',review?`${Object.values(review.constraints||{}).filter(v=>v==='met').length} 已满足 / ${Object.keys(review.constraints||{}).length} 项`:'未复审'],['总 Token',t.usage?.totalTokens??'缺少有效原生日志'],['日志活动时长（秒）',t.usage?.activeSeconds??'未知'],['重复可靠性 / 每次成功成本','需要同条件独立重复与成本证据；当前不估算'],['人工介入次数','当前尚未完整采集，不用轮数代替']];
  return <section className="space-y-3"><h3 className="font-semibold">评测指标全貌</h3><div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{rows.map(([label,value])=><tr className="border-b border-slate-200 dark:border-zinc-800" key={label}><th className="text-left p-3 font-medium">{label}</th><td className="p-3">{value}</td></tr>)}</tbody></table></div></section>;
}

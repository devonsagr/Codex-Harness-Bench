import {useState} from 'react';
import {JudgeProgress} from './JudgeProgress';
import type {Trial,Run,State} from './types';
import {Panel,Details,Dialog,Field,ScoreSlider,num,date,ModelSelect} from './ui';
import {ScoreRing,ScoreBar} from './AssessmentCharts';
import {verdicts} from './Contracts';
import {isBenchmark} from './EvaluationTrack';

export function MachineScore({run,trial:t,state,act,disabled}:{run:Run;trial:Trial;state:State;act:(name:string,data?:unknown)=>Promise<unknown>;disabled:boolean}){
  const latest=t.captures[t.captures.length-1];
  const defaultJudgeModel='gpt-5.6-luna';
  const [model,setModel]=useState(state.models.some(m=>m.id==='gpt-5.6-luna')?'gpt-5.6-luna':state.models[0]?.id||'');
  const [reasoning,setReasoning]=useState(state.models.find(m=>m.id==='gpt-5.6-luna')?.reasoningLevels?.includes('max')?'max':'');
  const [serviceTier,setServiceTier]=useState<'standard'|'fast'>('standard');
  const [minutes,setMinutes]=useState(60);
  const modelInfo=state.models.find(m=>m.id===model);
  const [environment,setEnvironment]=useState('local');
  const efforts=(modelInfo?.reasoningLevels||[]).filter(level=>environment!=='docker'||level!=='ultra');
  const judgeSupported=!!model&&(!reasoning||efforts.includes(reasoning))&&(serviceTier!=='fast'||(environment==='local'&&!!modelInfo?.fastAvailable));
  const [editing,setEditing]=useState<string|null>(null);const [value,setValue]=useState('');const [reason,setReason]=useState('');
  const [editingEvidence,setEditingEvidence]=useState<{reviewId?:string|null;evidenceKey?:string|null}>({});
  const report=t.reviews.find(r=>r.id===t.score.machineReviewId);
  const busy=['checking','judging'].includes(t.state);
  const judging=t.state==='judging';
  const judgeError=t.lastJobError?.kind==='judge'?t.lastJobError:null;
  const ratings=t.score.machineRatings||{};
  const task=run.tasks.find(task=>task.id===t.taskId)!;
  const intermediate=latest.stageIndex+1<task.stages.length&&t.finalCaptureId!==latest.id;
  const correct=async(withdraw=false)=>{if(!editing)return;await act('machine-correction',{...editingEvidence,changes:{[editing]:{score:withdraw?null:Number(value),reason}}});setEditing(null);};
  const dimensions=Object.entries(run.policy.rubrics||{}).filter(([key])=>run.policy.dimensions[key]>0&&(key!=='ux'||task.hasFrontendUI));
  return <Panel title={intermediate?'阶段检查（可选）':isBenchmark(task)?'AI 质量参考 · 不计原题通过率':'AI 交付质量参考'} aside={<span className="muted">回收版本 {t.captures.length} · {judging?'正在评分':report?'已生成评分':judgeError?'评分未完成':'尚未评分'}</span>}>
    <p className="muted mb-3">{intermediate?`只检查第 ${latest.stageIndex+1} 阶段的已回收版本，不计整题最终成绩。整题已完成时，可直接在下方结束交付，再按完整需求评分。`:'按完整需求检查当前回收版本。对话次数不限；完整总分需各项有分并结束交付。'}</p>
    <div className="judge-toolbar">
      <Field label="裁判模型"><ModelSelect label="裁判模型" disabled={busy||disabled} value={model} onChange={id=>{setModel(id);const next=state.models.find(m=>m.id===id);setReasoning(next?.reasoningLevels?.includes(reasoning)?reasoning:next?.reasoningLevels?.includes('max')?'max':next?.defaultReasoning||'');if(!next?.fastAvailable)setServiceTier('standard');}} models={state.models}/></Field>
      <Field label="裁判思考档位"><select disabled={busy||disabled} value={reasoning} onChange={e=>setReasoning(e.target.value)}><option value="">模型默认（不强制档位）</option>{efforts.map(level=><option key={level}>{level}</option>)}</select></Field>
      <Field label="裁判速度"><select disabled={busy||disabled} value={serviceTier} onChange={e=>setServiceTier(e.target.value as 'standard'|'fast')}><option value="standard">标准</option><option value="fast" disabled={environment!=='local'||!modelInfo?.fastAvailable}>Fast · {environment!=='local'?'仅本机 CLI':modelInfo?.fastAvailable?'当前模型可用':'模型未声明支持'}</option></select></Field>
      <Field label="审查时间预算"><select disabled={busy||disabled} value={minutes} onChange={e=>setMinutes(Number(e.target.value))}>{[15,30,60,120,240,480].map(n=><option key={n} value={n}>{n<60?n+' 分钟':n/60+' 小时'}</option>)}</select></Field>
      <Field label="裁判环境"><select aria-label="裁判环境" value={environment} disabled={busy||disabled} onChange={e=>{setEnvironment(e.target.value);if(e.target.value==='docker'){if(reasoning==='ultra')setReasoning('');setServiceTier('standard');}}}><option value="local">本机 · 无需 Docker</option><option value="docker">Docker · Harbor 隔离</option></select></Field>
      <button className="btn-primary" disabled={disabled||busy||!judgeSupported} onClick={()=>void act('judge',{captureId:latest.id,model,reasoningEffort:reasoning,serviceTier,timeoutSeconds:minutes*60,environment}).catch(()=>{})}>{judging?'检查中…':intermediate?`检查第 ${latest.stageIndex+1} 阶段`:report?'重新评分':judgeError?'重试评分':'评估最终产物'}</button>
      {judging&&<button disabled={disabled} className="btn-secondary" onClick={()=>void act('stop').catch(()=>{})}>停止</button>}
    </div>
    <p className="muted">新建独立裁判会话 · 只检查当前快照 · 预算用完保留为未完成</p>
    <Details title="裁判、账号与检查范围"><p>默认裁判为 {defaultJudgeModel} · max；模型与档位来自本机目录，未知档位不强制设置。</p><p>当前连接：{state.reviewConnection?.provider||'待读取'} · {state.reviewConnection?.billing||'请核对 Codex CLI 登录'}。新审查读取启动时的凭据；运行中不换号。</p><ol className="storage-flow"><li>读取原始需求、适用评分标准与当前回收快照。</li><li>查看代码，尝试构建与测试，收集命令和文件证据。</li><li>按标准评分；未验证项保持空值，原测试通过率另外记录。</li><li>返回结构化报告，工作台核对引用后保存。实际提示词见“评分过程”。</li></ol><p>{environment==='local'?'本机使用 Codex 原生沙箱，需先安装 CLI 并检查 codex login status。Windows 浏览器取证暂不可用，交互与视觉项保留未验证。':'容器使用 Harbor 固定镜像，需准备 Docker；当前仅支持官方连接。'}</p><p>预算是本次审查允许的运行时间，不代表项目正确性。环境阻断、额度不足和预算用尽均不能当作产物失败。</p></Details>
    {!judgeSupported&&<p className="alert-error">当前模型档位不匹配，请重新选择；不会自动换模型。</p>}
    <JudgeProgress runId={run.id} trialId={t.id} busy={judging}/>
    {judgeError&&<div role="alert" className="alert-error"><strong>本次评分未完成{report?'，保留上次结果':''}</strong><details className="mt-2"><summary>查看失败原因</summary><p className="mt-2">{judgeError.message}</p></details>{judgeError.message.includes('评分报告未通过校验')&&<button type="button" className="btn-secondary mt-3" disabled={disabled||busy} onClick={()=>void act('judge-revalidate').catch(()=>{})}>重新校验已保存报告 · 不调用模型</button>}</div>}
    {!!report?.validationWarnings?.length&&<Details title={`引用校验 · ${report.validationWarnings.length} 项未计分`}><p className="muted">有效项正常计分；以下引用无法核实，保留为未验证。原报告保留在本地。</p>{report.validationWarnings.map((w,i)=><p key={i} className="text-sm">{run.policy.rubrics?.[w.key]?.label||task.criteria?.find(c=>c.id===w.key)?.label||w.key}：{w.message}</p>)}</Details>}
    {report?<><div className="score-overview"><ScoreRing value={t.score.overall??t.score.partialScore} label={intermediate?'阶段参考分':t.score.overall==null?'暂定分':'最终分'} detail={t.score.overall==null?'未验证项不按零分计算':'含已保存的人工修正'}/><dl className="run-stats"><div><dt>机器原分</dt><dd>{num(t.score.machine??null)}</dd></div><div><dt>已评分权重</dt><dd>{t.score.machineCoverage||0}%</dd></div></dl></div><p className="muted">本次裁判：{report.model||'未知模型'} · 推理 {report.reasoningEffort||'模型默认'} · {report.serviceTier==='fast'?'请求 Fast':'标准/原速度'} · {report.reviewEnvironment==='local'?'本机 CLI':'Docker/Harbor'} · {report.judgeIsolation?'新进程/临时配置':'旧记录未记录隔离标记'}{report.revalidatedFrom?' · 使用已保存报告重新校验':''}</p>
      {t.score.overall==null&&!intermediate&&<p className="muted">{t.state!=='completed'?'交付尚未标记结束。':''}{(t.score.machineCoverage||0)<100?'仍有未验证项，可查看依据并人工复核。':''}完整总分需各项有分且交付结束。</p>}
      <div className="machine-ratings">{dimensions.map(([key,item])=>{const rating=ratings[key];const override=t.score.machineOverrides?.[key];return <div key={key} className="machine-rating"><details><summary><strong>{item.label}</strong><ScoreBar value={t.score.effectiveScores?.[key]}/><span className="muted">{rating?({static:'静态判断',runtime:'运行证据',unverified:'未验证'}[rating.method]||rating.method):'未验证'} · 查看依据</span></summary><div className="space-y-3 mt-3">{rating&&<><p className="text-sm">{rating.reason}</p>{rating.evidence.map((e,i)=><div key={i}><small>{e.path?`${e.path}:${e.line}`:e.command||e.checkId}{e.reportedLine!=null?`（原报 ${e.reportedLine} 行，按唯一原文定位）`:null}</small><pre className="source">{e.quote}</pre></div>)}</>}{override&&<p className="text-sm">人工修正：{override.reason}</p>}</div></details><div className="rating-actions"><span>{num(rating?.score??null)}{override&&<> → <strong>{override.score}</strong></>}</span><button className="btn-secondary" disabled={disabled||busy} onClick={()=>{setEditing(key);setEditingEvidence({reviewId:t.score.machineReviewId,evidenceKey:t.score.machineEvidenceKey});setValue(String(t.score.effectiveScores?.[key]??''));setReason('');}}>修正</button></div></div>;})}</div>
      {report.summary&&<Details title="裁判结论"><p className="text-sm whitespace-pre-wrap">{report.summary}</p></Details>}
    </>:!judging&&!judgeError?<div className="score-empty"><p>回收已就绪，可以开始评分。</p><p className="muted">机器按本题要求检查产物；有结果后可逐项人工修正。</p></div>:judging?<p role="status" className="muted">正在检查产物并收集评分证据，可以切换页签查看记录。</p>:null}
    <Details title={`评分标准 · ${dimensions.length} 项`}><dl className="score-rules">{dimensions.map(([key,item])=><div key={key}><dt>{item.label}<span>设置权重 {run.policy.dimensions[key]}%</span></dt><dd>{item.description}</dd></div>)}</dl><p className="muted">按适用维度加权；未知项不计作0。人工修正替换对应项，保留机器原分。本机裁判主动检查副本；Docker 模式额外运行已配置的容器脚本。实际执行与静态判断分别标注。</p></Details>
    {!!task.criteria?.length&&<Details title={t.score.acceptance.required?`需求验收 · ${t.score.acceptance.met}/${t.score.acceptance.required} 必要项满足`:`需求对照 · ${task.criteria.length} 项（未设必要项）`}>{task.criteria.map(c=><div key={c.id}><strong>{c.label}</strong><p>{verdicts[report?.criteria?.[c.id]?.status||'unverified']}</p><p className="muted">{report?.criteria?.[c.id]?.notes}</p></div>)}<p className="muted">人工调分不会改写需求验收和程序通过状态。</p></Details>}
    {(!!latest.checks.length||!!report?.commands?.length)&&<Details title={`执行证据 · ${latest.checks.length} 项检查 / ${report?.commands?.length||0} 条裁判命令`}><p className="muted">脚本检查分 {num(t.score.objective)}，不重复加权。</p>{latest.checks.map(c=><div key={c.id}><strong>{c.label} · {c.status}</strong><pre className="source">{c.output}</pre></div>)}{report?.commands?.map((c,i)=><div key={i}><code>{c.command}</code><p className="muted">退出码 {c.exitCode??'未知'}</p><pre className="source">{c.output}</pre></div>)}</Details>}
    {!!t.machineCorrections?.length&&<Details title="人工修正历史">{t.machineCorrections.slice().reverse().map(c=><div key={c.id}><p>{date(c.at)} · {c.reviewId===t.score.machineReviewId?'当前评分版本':'历史评分版本'}</p>{Object.entries(c.changes).map(([k,v])=><p key={k}>{run.policy.rubrics?.[k]?.label}：{v.score??'撤回修正'} · {v.reason}</p>)}</div>)}</Details>}
    <Dialog title={'修正：'+(editing?run.policy.rubrics?.[editing]?.label:'')} open={!!editing} onClose={()=>setEditing(null)}><form className="space-y-4" onSubmit={e=>{e.preventDefault();void correct().catch(()=>{});}}><fieldset disabled={disabled||busy} className="space-y-4"><ScoreSlider label="修正后分数" value={value} onChange={setValue}/><Field label="理由与复核证据"><textarea required value={reason} onChange={e=>setReason(e.target.value)} placeholder="说明实际结果及机器误判之处"/></Field><div className="flex gap-3"><button className="btn-primary">保存修正</button>{editing&&t.score.machineOverrides?.[editing]&&<button type="button" disabled={!reason.trim()} className="btn-secondary" onClick={()=>void correct(true).catch(()=>{})}>恢复机器原分</button>}</div></fieldset></form></Dialog>
  </Panel>;
}

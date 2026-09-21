import {useState} from 'react';
import {JudgeProgress} from './JudgeProgress';
import type {Trial,Run,State} from './types';
import {Panel,Details,Dialog,Field,ScoreSlider,num,date,ModelSelect} from './ui';
import {ScoreRing,ScoreBar} from './AssessmentCharts';
import {verdicts} from './Contracts';

export function MachineScore({run,trial:t,state,act,disabled}:{run:Run;trial:Trial;state:State;act:(name:string,data?:unknown)=>Promise<unknown>;disabled:boolean}){
  const latest=t.captures[t.captures.length-1];
  const defaultJudgeModel='gpt-5.6-luna';
  const [model,setModel]=useState('gpt-5.6-luna');
  const modelInfo=state.models.find(m=>m.id===model);
  const judgeSupported=!!modelInfo?.reasoningLevels?.includes('max');
  const [environment,setEnvironment]=useState('local');
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
  return <Panel title={intermediate?'阶段检查（可选）':'最终产物评分'} aside={<span className="muted">回收版本 {t.captures.length} · {judging?'正在评分':report?'已生成评分':judgeError?'评分未完成':'尚未评分'}</span>}>
    <p className="muted mb-3">{intermediate?`只检查第 ${latest.stageIndex+1} 阶段的已回收版本，不计整题最终成绩。整题已完成时，可直接在下方结束交付，再按完整需求评分。`:'按完整需求检查当前回收版本。对话次数不限；完整总分需各项有分并结束交付。'}</p><div className="judge-toolbar"><Field label="裁判模型"><ModelSelect label="裁判模型" disabled={busy||disabled} value={model} onChange={setModel} models={state.models}/></Field><Field label="裁判环境"><select aria-label="裁判环境" value={environment} disabled={busy||disabled} onChange={e=>setEnvironment(e.target.value)}><option value="local">本机 · 无需 Docker</option><option value="docker">Docker · Harbor 隔离</option></select></Field><button className="btn-primary" disabled={disabled||busy||!judgeSupported} onClick={()=>void act('judge',{captureId:latest.id,model,reasoningEffort:'max',environment}).catch(()=>{})}>{judging?'检查中…':intermediate?`检查第 ${latest.stageIndex+1} 阶段`:report?'重新评分':judgeError?'重试评分':'评估最终产物'}</button>{judging&&<button disabled={disabled} className="btn-secondary" onClick={()=>void act('stop').catch(()=>{})}>停止</button>}</div>
    <p className="muted">每次评分都是新的 Codex CLI 审查进程，默认裁判为 {defaultJudgeModel} · max；使用当前 Codex 登录账户额度，不继承上次会话。检查当前回收副本。{environment==='local'?'本机使用 Codex 原生沙箱；开源用户需先安装并运行 codex login status。Windows 浏览器取证暂不可用，交互与视觉项会保留未验证；无需 Docker 的完整浏览器评分仍待接通。':'容器使用固定镜像，首次需准备 Docker。'}</p>
    {!judgeSupported&&<p className="alert-error">当前模型未确认支持 max；请刷新模型列表或选择支持 max 的裁判，不会自动换模型。</p>}
    <JudgeProgress runId={run.id} trialId={t.id} busy={judging}/>
    {judgeError&&<div role="alert" className="alert-error"><strong>本次评分未完成{report?'，保留上次结果':''}</strong><details className="mt-2"><summary>查看失败原因</summary><p className="mt-2">{judgeError.message}</p></details></div>}
    {!!report?.validationWarnings?.length&&<Details title={`引用校验 · ${report.validationWarnings.length} 项未计分`}><p className="muted">有效项正常计分；以下引用无法核实，保留为未验证。原报告保留在本地。</p>{report.validationWarnings.map((w,i)=><p key={i} className="text-sm">{run.policy.rubrics?.[w.key]?.label||task.criteria?.find(c=>c.id===w.key)?.label||w.key}：{w.message}</p>)}</Details>}
    {report?<><div className="score-overview"><ScoreRing value={t.score.overall??t.score.partialScore} label={intermediate?'阶段参考分':t.score.overall==null?'暂定分':'最终分'} detail={t.score.overall==null?'未验证项不按零分计算':'含已保存的人工修正'}/><dl className="run-stats"><div><dt>机器原分</dt><dd>{num(t.score.machine??null)}</dd></div><div><dt>已评分权重</dt><dd>{t.score.machineCoverage||0}%</dd></div></dl></div><p className="muted">本次裁判：{report.model||'未知模型'} · 推理 {report.reasoningEffort||'未知'} · {report.reviewEnvironment==='local'?'本机 CLI':'Docker/Harbor'} · {report.judgeIsolation?'新进程/临时配置':'旧记录未记录隔离标记'}</p>
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

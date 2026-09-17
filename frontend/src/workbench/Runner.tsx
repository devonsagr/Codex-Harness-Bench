import {CodexApply} from './Codex';
import {EvaluationMetrics} from './Scoring';
import {ObjectivePlan,RatingGuide} from './ScorePlan';
import {ObjectiveReview} from './ObjectiveReview';
import {useState} from 'react';
import type {State,Act,Run,Trial,Task,Config,Capture,Review,CriterionReview} from './types';
import {Field,Panel,Details,Empty,Json,labels,num,date} from './ui';
import {request,downloadRun} from './api';
import {ContractView,verdicts,ReviewItems} from './Contracts';

export {Prepare} from './Prepare';

export function RunDetail({run,state,act,onBack,onError,archived}:{run:Run;state:State;act:Act;onBack:()=>void;onError:(s:string)=>void;archived:boolean}){
  const [tid,setTid]=useState(run.trials[0].id);const t=run.trials.find(x=>x.id===tid)||run.trials[0];
  const task=run.tasks.find(x=>x.id===t.taskId)!;const config=run.configs.find(c=>c.id===t.configId)!;
  return <><div className="flex flex-wrap items-center justify-between gap-4"><div><button className="btn-ghost mb-2" onClick={onBack}>← 新建评测</button><h1 className="page-title">本次评测{archived?' · 已归档':''}</h1><p className="muted mt-2">{date(run.createdAt)} · {run.id} · 桌面执行</p></div><button className="btn-secondary" onClick={()=>downloadRun(run.id).catch(e=>onError(e.message))}>导出记录与产物 ZIP</button></div>
    {run.comparisonWarnings.map(w=><p className="alert-error" key={w}>{w}</p>)}
    <div className="work-layout"><aside className="space-y-3">{run.trials.map(v=><button key={v.id} className={'list-card '+(v.id===t.id?'selected':'')} onClick={()=>setTid(v.id)}><strong>{run.tasks.find(x=>x.id===v.taskId)?.title}</strong><span>{run.configs.find(c=>c.id===v.configId)?.name} · {labels[v.state]}</span><small>第 {v.stageIndex+1} 轮 · 综合分 {num(v.score.overall)}</small></button>)}
      <Details title="本次冻结的条件"><Json value={{mode:run.executionMode,policy:run.policy,hostFingerprint:run.hostFingerprint}}/><p className="muted">宿主指纹仅覆盖全局 AGENTS 与 config.toml，不代表所有桌面插件和技能已完全隔离。</p></Details>
    </aside><div className="space-y-5"><TrialView key={t.id+'-'+t.stageIndex} run={run} trial={t} task={task} config={config} state={state} act={act} onError={onError} archived={archived}/>
    <Details title={`活动记录 · ${run.events.length} 条`}><ol className="space-y-3">{[...run.events].reverse().map((e,i)=><li className="text-sm" key={i}><time className="muted mr-3">{date(e.at)}</time>{e.message}</li>)}</ol></Details></div></div></>;
}

function TrialView({run,trial:t,task,config,state,act,onError,archived}:{run:Run;trial:Trial;task:Task;config:Config;state:State;act:Act;onError:(s:string)=>void;archived:boolean}){
  const [confirmed,setConfirmed]=useState(false);const [response,setResponse]=useState('');const [reason,setReason]=useState('');const [model,setModel]=useState(config.baseModel);const [copied,setCopied]=useState('');
  const latest=t.captures[t.captures.length-1];const busy=['checking','judging'].includes(t.state);
  const action=(name:string,data:unknown={})=>act(`/runs/${run.id}/trials/${t.id}/${name}`,data).catch(()=>{});
  const prompt=t.currentStage.executionPrompt;
  const copy=(value:string,label:string)=>navigator.clipboard.writeText(value).then(()=>setCopied(label+'已复制')).catch(()=>onError('复制失败，请在文本框中手动复制。'));
  return <><Panel title={task.title} aside={<span className="badge">{labels[t.state]}</span>}>
    <div className="flex gap-2 flex-wrap">{task.stages.map((s,i)=><span className={'stage-chip '+(i===t.stageIndex?'selected':'')} key={i}>{i+1}. {s.title}</span>)}</div>
    <p className="muted">配置 {config.name} v{config.revision}{config.preparationOverride?' · 本次技能已调整':''} · {config.baseModel} · {config.reasoning} · {config.skills.length} 个选定技能</p>
    <p className="muted">工作区已自动准备好，无需另外新建文件夹或复制项目。</p>
    <CodexApply config={config} act={act} trialRoute={`/runs/${run.id}/trials/${t.id}/apply-config`} disabled={archived||t.state!=='prepared'}/>
    <Field label="已创建的工作区"><input readOnly value={t.workspacePath}/></Field>
    <div className="flex gap-2 flex-wrap"><button className="btn-primary" disabled={archived} onClick={()=>void action('open')}>在 Codex 桌面打开</button><button className="btn-secondary" onClick={()=>void copy(t.workspacePath,'工作区路径')}>复制路径</button><button className="btn-secondary" onClick={()=>void copy(prompt,'本轮提示词')}>复制本轮提示词</button></div>
    {copied&&<p role="status" className="muted">{copied}</p>}
    <Details title={`本轮提示词：${t.currentStage.title}`}><pre className="source">{prompt}</pre><p className="muted break-all">{t.currentStage.promptSource.startsWith('frozen-')?'准备时冻结的提示词':'旧记录原提示词；未追加新版契约'} · SHA-256 {t.currentStage.promptSha256}</p></Details>
    {!!t.skills?.length&&<Details title={`已装载 Skills · ${t.skills.length} 个`}>{t.skills.map(s=><div key={s.id}><strong className="text-sm">{s.name}</strong><p className="muted break-all">来源：{s.sourceLabel||'手动导入'} · {s.sourcePath}</p><p className="muted break-all">本次位置：.agents/skills/{s.name}/SKILL.md · {s.manifest.sha256.slice(0,12)}</p></div>)}<p className="muted">{t.skillMode==='explicit'?'每轮提示词明确请求使用。':'按任务需要使用。'}这里只确认文件已装载，实际使用需查看桌面执行记录。</p></Details>}
    <Details title={`本题冻结项目契约 · 题目 v${task.revision}`}><ContractView task={task}/></Details>
    <p className="muted">在桌面选择该目录与上述模型、推理档位。第一轮新建任务；后续轮次在同一任务粘贴提示词。工作台不代替你确认或发送。</p>
    <fieldset disabled={archived||busy} className="space-y-4">
      {['prepared','waiting_confirmation'].includes(t.state)&&<><label className="check-row"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已核对桌面工作区、模型和推理档位</label><button className="btn-primary" disabled={!confirmed} onClick={()=>void action('start',{settingsConfirmed:confirmed})}>记录本轮开始</button></>}
      {!['prepared','waiting_confirmation'].includes(t.state)&&<><Field label="本轮回复或执行说明（可选）"><textarea rows={3} value={response} onChange={e=>setResponse(e.target.value)} placeholder="保留交付说明、澄清、确认和异常，不用把 Token 手填成真实用量。"/></Field><button className="btn-primary" onClick={()=>action('capture',{response}).then(result=>{if(result)setResponse('');})}>回收当前工作区产物</button><p className="muted">先等待桌面本轮停止写入。回收保存新的完整快照，旧快照和旧评分继续保留。</p></>}
      {t.state==='captured'&&<div className="flex flex-wrap gap-3">{t.stageIndex+1<task.stages.length?<button className="btn-secondary" onClick={()=>void action('continue')}>确认进入第 {t.stageIndex+2} 轮</button>:<button className="btn-secondary" onClick={()=>void action('complete')}>标记本次交付结束</button>}</div>}
      <Details title="记录中断 / 额度问题"><Field label="中断原因"><textarea value={reason} onChange={e=>setReason(e.target.value)} placeholder="例如：额度用完、需要澄清、手工停止"/></Field><button disabled={!reason.trim()} className="btn-secondary" onClick={()=>void action('interrupt',{reason})}>保存中断状态</button><p className="muted">这不会停止桌面中的任务。需要停止时请在 Codex 桌面操作。</p></Details>
    </fieldset>
  </Panel>
  <Panel title="用量与执行证据"><div className="metric-grid"><Metric label="输入 Token" value={num(t.usage?.inputTokens)}/><Metric label="输出 Token" value={num(t.usage?.outputTokens)}/><Metric label="缓存输入" value={num(t.usage?.cacheReadTokens)}/><Metric label="缓存命中" value={num(t.usage?.cacheHitRate,'%')}/><Metric label="原生日志活动时长" value={num(t.usage?.activeSeconds,' 秒')}/></div>
    {t.observations.map(s=><p className="alert-error" key={s}>{s}</p>)}
    <Details title="导入本题原生 JSONL 日志"><p className="muted">明确选择对应桌面任务的原生日志文件；不扫描所有会话。服务核对 cwd 与 session ID，读取最终累计用量。未提供日志时保持未知，费用不估算。</p><Field label="选择 JSONL 文件"><input type="file" accept=".jsonl,.json" disabled={archived} onChange={async e=>{const f=e.target.files?.[0];if(!f)return;if(f.size>15_000_000){onError('日志超过 15 MB。');return;}await action('trace',{raw:await f.text()});e.target.value='';}}/></Field>{t.usage&&<Json value={t.usage}/>}</Details>
  </Panel>
  <EvaluationMetrics trial={t}/>
  <ObjectivePlan tasks={[task]}/>
  {latest?<><Panel title={`验收与评分 · 最近回收为第 ${latest.stageIndex+1} 轮`}><div className="metric-grid"><Metric label="客观检查" value={num(t.score.objective)}/><Metric label="人工复审" value={num(t.score.human)}/><Metric label="综合分" value={num(t.score.overall)}/></div><p className="muted">评分策略：{run.policy.objectiveWeight===0?'纯人工':run.policy.humanWeight===0?'仅客观检查':'客观检查 + 人工复审'}（客观 {run.policy.objectiveWeight}% / 人工 {run.policy.humanWeight}%）。</p><p className="muted">综合分需完成交付并补齐策略要求的证据。各分项有各自依据，个人约束另列；空值不是零分。</p>
    {(!latest.harnessUnchanged||!latest.hostUnchanged)&&<p className="alert-error">规则文件或宿主配置指纹发生变化，需核对；本结果不能视作条件保持一致。</p>}
    {t.lastJobError&&<p role="alert" className="alert-error">{t.lastJobError.message}</p>}
    <div className="flex gap-3 flex-wrap"><button className="btn-secondary" disabled={archived||busy||!latest.checksConfigured} onClick={()=>void action('check',{captureId:latest.id})}>检查此快照 ({latest.checksConfigured})</button>{busy&&<button className="btn-secondary" disabled={archived} onClick={()=>void action('stop')}>停止后台检查 / 审查</button>}</div>
    {!latest.checksConfigured&&<p className="muted">本阶段未配置脚本验收；可以人工复审，也可以由 AI 辅助定位问题。</p>}
    {latest.checks.map(c=><Details key={c.id} title={`${c.label} · ${labels[c.status]||c.status} · ${c.seconds}s`}><p className="muted">退出码 {c.exitCode??'未知'} · 镜像 {c.imageId}</p><pre className="source">{c.output||'没有输出'}</pre></Details>)}
    <Details title="独立 AI 复审"><p className="muted">点击后使用所选模型额度，在 Harbor 容器运行 CLI 审查器。只审查封存的材料，结果归为辅助意见，不是桌面任务的分数或用量。意见必须引用实际文件与行。</p><Field label="审查模型"><input list="review-models" value={model} onChange={e=>setModel(e.target.value)}/><datalist id="review-models">{state.models.map(m=><option key={m.id} value={m.id}/>)}</datalist></Field><button disabled={archived||busy} className="btn-secondary" onClick={()=>void action('judge',{captureId:latest.id,model})}>使用模型额度启动复审</button></Details>
    <p className={['not_met','needs_review'].includes(t.score.acceptance.status)?'alert-error':'muted'}>必要条目验收：{verdicts[t.score.acceptance.status]} · {t.score.acceptance.met}/{t.score.acceptance.required} 项。此结论与数值分数分开。</p>
    <ObjectiveReview trial={t} act={data=>action('objective-review',data)} disabled={archived||busy}/>
    <ManualReview key={latest.id+'-'+t.reviews.filter(r=>r.captureId===latest.id&&r.kind==='human').slice(-1)[0]?.id} previous={t.reviews.filter(r=>r.captureId===latest.id&&r.kind==='human').slice(-1)[0]} capture={latest} config={config} task={task} requireEvidence={run.policy.requireDimensionEvidence} rubrics={run.policy.rubrics} dimensions={run.policy.rubrics?Object.fromEntries(Object.entries(run.policy.rubrics).filter(([k])=>run.policy.dimensions[k]>0).map(([k,v])=>[k,v.label])):state.dimensions} act={data=>action('review',data)} disabled={archived||busy}/>
  </Panel><Evidence key={t.id} run={run} trial={t} onError={onError} disabled={archived||busy} check={captureId=>action('check',{captureId})}/></>:<Empty>尚未回收产物。完成桌面本轮后，回到这里查看文件、测试和评分。</Empty>}
  <Details title="本题冻结配置 / 恢复副本"><pre className="source">{config.agentsPrompt}</pre><Json value={{model:config.baseModel,reasoning:config.reasoning,skills:config.skills,customConstraints:config.customConstraints}}/><button className="btn-secondary" onClick={()=>act(`/runs/${run.id}/restore-config`,{configId:config.id}).catch(()=>{})}>恢复为新的配置副本</button></Details></>;
}
function Metric({label,value}:{label:string;value:string}){return <div className="panel-subtle p-3"><p className="muted mb-2">{label}</p><strong className="text-xl font-semibold">{value}</strong></div>;}
function ManualReview({capture,task,config,dimensions,act,disabled,previous,rubrics,requireEvidence}:{capture:Capture;task:Task;config:Config;dimensions:Record<string,string>;act:(data:unknown)=>Promise<unknown>;disabled:boolean;previous?:Review;rubrics?:Record<string,{description:string}>;requireEvidence?:boolean}){
  const [dimensionEvidence,setDimensionEvidence]=useState<Record<string,string>>(previous?.dimensionEvidence||{});
  const [scores,setScores]=useState<Record<string,string>>(Object.fromEntries(Object.entries(previous?.scores||{}).map(([k,v])=>[k,String(v)])));
  const [notes,setNotes]=useState(previous?.notes||'');const [readiness,setReadiness]=useState(previous?.readiness||'');const [reason,setReason]=useState('');
  const [constraints,setConstraints]=useState<Record<string,string>>(previous?.constraints||Object.fromEntries(config.customConstraints.filter(c=>c.isActive).map(c=>[c.id,'unverified'])));
  const [constraintNotes,setConstraintNotes]=useState<Record<string,string>>(previous?.constraintNotes||{});
  const [criteria,setCriteria]=useState<Record<string,CriterionReview>>(Object.fromEntries((task.criteria||[]).map(c=>[c.id,previous?.criteria?.[c.id]||{status:'unverified',notes:''}])));
  const criterion=(id:string,patch:Partial<CriterionReview>)=>setCriteria({...criteria,[id]:{...criteria[id],...patch}});
  const dims=Object.entries(dimensions).filter(([k])=>k!=='ux'||task.hasFrontendUI);
  return <Details title="人工验收与细粒度评分"><form className="space-y-4" onSubmit={e=>{e.preventDefault();void act({captureId:capture.id,scores:Object.fromEntries(dims.map(([k])=>[k,Number(scores[k])])),notes,readiness,constraints,constraintNotes,criteria,dimensionEvidence,revisionReason:reason});}}><fieldset disabled={disabled} className="space-y-4">
    <p className="muted">先实际查看交付物与检查记录。每条要求从未核实开始；选择其他结论需写依据。必要条目与数值分数分开，AI 意见不会自动填入。</p>
    {task.criteria?.map(c=><div key={c.id} className="panel-subtle p-3 space-y-3"><h3 className="text-sm font-semibold">{c.required?'必要项':'观察项'} · {c.label}</h3>{c.description&&<p className="muted">{c.description}</p>}<Field label={`${c.label}：验收状态`}><select value={criteria[c.id].status} onChange={e=>criterion(c.id,{status:e.target.value})}>{['unverified','met','partial','unmet','not_applicable'].map(v=><option value={v} key={v}>{verdicts[v]}</option>)}</select></Field><Field label={`${c.label}：验收依据`} hint="记录实际操作、预期与实际结果；未满足和不适用也需说明。"><textarea required={criteria[c.id].status!=='unverified'} value={criteria[c.id].notes} onChange={e=>criterion(c.id,{notes:e.target.value})}/></Field><div className="grid sm:grid-cols-2 gap-3"><Field label={`${c.label}：证据文件（可选）`}><select value={criteria[c.id].filePath||''} onChange={e=>criterion(c.id,{filePath:e.target.value||undefined})}><option value="">无文件引用</option>{Object.keys(capture.manifest.files).sort().map(path=><option key={path}>{path}</option>)}</select></Field><Field label={`${c.label}：已运行检查（可选）`}><select value={criteria[c.id].checkId||''} onChange={e=>criterion(c.id,{checkId:e.target.value||undefined})}><option value="">无检查引用</option>{capture.checks.map(check=><option value={check.id} key={check.id}>{check.label} · {labels[check.status]}</option>)}</select></Field></div></div>)}
    <RatingGuide/>
    <div className="grid sm:grid-cols-2 gap-4">{dims.map(([k,label])=><div key={k} className="space-y-2"><Field label={label} hint={rubrics?.[k]?.description}><input type="number" required min={0} max={100} step="0.1" value={scores[k]??''} onChange={e=>setScores({...scores,[k]:e.target.value})}/></Field>{requireEvidence&&<Field label={label+'：实际评分依据'}><textarea required value={dimensionEvidence[k]||''} onChange={e=>setDimensionEvidence({...dimensionEvidence,[k]:e.target.value})} placeholder="实际操作、预期与结果、文件或检查证据"/></Field>}</div>)}</div>
    <Field label="交付可用程度"><select required value={readiness} onChange={e=>setReadiness(e.target.value)}><option value="">请选择</option><option value="ready_to_merge">可以采用</option><option value="minor_polish">少量修改后可用</option><option value="major_rework">需要较大修改</option><option value="rejected">当前不可用</option></select></Field>
    {config.customConstraints.filter(c=>c.isActive).map(c=><div key={c.id}><Field label={c.title} hint={c.ruleDesc}><select value={constraints[c.id]} onChange={e=>setConstraints({...constraints,[c.id]:e.target.value})}><option value="unverified">未核实</option><option value="met">已满足</option><option value="unmet">未满足</option><option value="not_applicable">本题不适用</option></select></Field>{task.schemaVersion===2&&<Field label={c.title+'：约束依据'}><textarea required={constraints[c.id]!=='unverified'} value={constraintNotes[c.id]||''} onChange={e=>setConstraintNotes({...constraintNotes,[c.id]:e.target.value})}/></Field>}</div>)}
    <Field label="评分依据" hint="说明实际体验、文件位置、未满足项。视觉评分需实际查看页面，不依据源码猜测。"><textarea required rows={4} value={notes} onChange={e=>setNotes(e.target.value)}/></Field>
    {previous&&task.schemaVersion===2&&<Field label="本次复审修订原因"><textarea required value={reason} onChange={e=>setReason(e.target.value)}/></Field>}<button className="btn-primary">保存人工复审版本</button>
  </fieldset></form></Details>;
}
function Evidence({run,trial:t,onError,disabled,check}:{run:Run;trial:Trial;onError:(s:string)=>void;disabled:boolean;check:(id:string)=>Promise<unknown>}){
  const [selected,setSelected]=useState('');const [file,setFile]=useState<{path:string;content:string}|null>(null);
  const c=t.captures.find(c=>c.id===selected)||t.captures[t.captures.length-1];
  const read=async(path:string)=>{try{setFile(await request(`/runs/${run.id}/trials/${t.id}/files/${c.id}/${path.split('/').map(encodeURIComponent).join('/')}`));}catch(e){onError((e as Error).message);}};
  return <Panel title="产物与证据"><Field label="回收版本"><select value={c.id} onChange={e=>{setSelected(e.target.value);setFile(null);}}>{[...t.captures].reverse().map(c=><option key={c.id} value={c.id}>第 {c.stageIndex+1} 轮 · {date(c.at)} · {c.id}</option>)}</select></Field>
    <p className="muted break-all">SHA-256 {c.manifest.sha256}</p><Details title={`此版本的客观检查 · ${c.checks.length}/${c.checksConfigured}`}>
    {c.checks.map(check=><div key={check.id}><p className="text-sm">{check.label} · {labels[check.status]} · {check.seconds}s</p><pre className="source">{check.output}</pre></div>)}
    {!c.checks.length&&<p className="muted">此版本尚无已执行检查。</p>}{!!c.checksConfigured&&<><button className="btn-secondary" disabled={disabled} onClick={()=>void check(c.id)}>运行所选版本的检查</button><p className="muted">可补验前一轮已封存的文件。每轮只有最新回收版本的检查参与总分。</p></>}</Details><Details title={`文件列表 · ${Object.keys(c.manifest.files).length} 个`}><div className="max-h-64 overflow-auto space-y-1">{Object.keys(c.manifest.files).sort().map(name=><button key={name} className="block text-left text-sm underline break-all" onClick={()=>void read(name)}>{name}</button>)}</div>{file&&<><h3 className="text-sm font-medium">{file.path}</h3><pre className="source">{file.content}</pre></>}{!!c.manifest.excluded.length&&<p className="muted">已排除：{c.manifest.excluded.join('、')}</p>}</Details>
    <Details title={`相对起点的变更 · ${c.facts.changes.length} 个文件`}><p className="muted">{c.facts.note}</p><pre className="source">{c.facts.diffPatch||'没有文本变更'}</pre>{c.facts.diffTruncated&&<p className="muted">差异显示已截断；导出包含完整文件。</p>}</Details>
    {c.response&&<Details title="本轮回复记录"><pre className="source">{c.response}</pre></Details>}
    <Details title="此快照的历次复审">{t.reviews.filter(r=>r.captureId===c.id).length?t.reviews.filter(r=>r.captureId===c.id).slice().reverse().map(r=><div key={r.id} className="panel p-4 space-y-3"><h3 className="text-sm font-medium">{r.kind==='ai'?'AI 辅助审查':'人工复审'} · {date(r.at)}</h3>{r.kind==='ai'?<><p className="text-sm whitespace-pre-wrap">{r.summary}</p>{r.findings?.map((f,i)=><div key={i} className="panel-subtle p-3 text-sm"><button className="underline" onClick={()=>void read(f.path)}>{f.path}:{f.line}</button><pre className="source">{f.quote}</pre><p>{f.comment}</p></div>)}<p className="muted">引用不成立的意见已排除 {r.rejectedFindings||0} 项；未覆盖文件 {r.omittedFiles?.length||0} 个。引用成立不代表意见必然正确。</p></>:<ReviewItems task={run.tasks.find(task=>task.id===t.taskId)!} review={r}/>}</div>):<p className="muted">此版本尚无复审。</p>}</Details>
  </Panel>;
}

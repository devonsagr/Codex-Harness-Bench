import {ArrowRight,Check,FileCode2,Layers3,SlidersHorizontal} from 'lucide-react';
import {ScoringSettings,percentPolicy,validPercentPolicy} from './Scoring';
import {useRef,useState} from 'react';
import type {State,Act,Run,Config} from './types';
import {Field,Panel,Details,Empty,Dialog} from './ui';
import {ContractView,TaskFilters,matchTask} from './Contracts';
import {TaskEnvironment,canStartTask,needsBaseline} from './TaskEnvironment';
import {SkillPicker} from './Skills';

type Selection={revision:number;skills:string[];skillMode:'auto'|'explicit'};

export function Prepare({state,act,onCreated,selectedTaskId,selectedConfigId}:{state:State;act:Act;onCreated:(id:string)=>void;selectedTaskId:string|null;selectedConfigId?:string|null}){
  const [pane,setPane]=useState<'tasks'|'config'|'scoring'>('tasks');
  const [configIds,setConfigs]=useState<string[]>(selectedConfigId&&state.configs.some(c=>c.id===selectedConfigId)?[selectedConfigId]:state.configs.slice(0,1).map(c=>c.id));
  const initial=state.tasks.find(t=>t.id===selectedTaskId);
  const [taskIds,setTasks]=useState<string[]>(initial?[initial.id]:[]);
  const [paradigm,setParadigm]=useState(initial?.taskParadigm||'open-ended-project');const [query,setQuery]=useState('');
  const [showPending,setShowPending]=useState(false);
  const [deliveryMode,setDeliveryMode]=useState('single-delivery');
  const [openDraft,setOpenDraft]=useState(true);const [compare,setCompare]=useState(false);const [batch,setBatch]=useState(false);
  const [channel,setChannel]=useState('');const [difficulty,setDifficulty]=useState('');
  const [policy,setPolicy]=useState(percentPolicy(structuredClone(state.defaultPolicy)));const [notes,setNotes]=useState('');
  const [selections,setSelections]=useState<Record<string,Selection>>({});
  const [editId,setEditId]=useState('');
  const configs=configIds.map(id=>state.configs.find(c=>c.id===id)).filter((c):c is Config=>!!c);
  const editing=configs.find(c=>c.id===editId)||configs[0];
  const effective=(c:Config):Selection=>selections[c.id]||{revision:c.revision,skills:c.skills,skillMode:c.skillMode||'auto'};
  const changeSkills=(c:Config,patch:Partial<Selection>)=>setSelections(current=>({...current,[c.id]:{...(current[c.id]?.revision===c.revision?current[c.id]:{revision:c.revision,skills:c.skills,skillMode:c.skillMode||'auto'}),...patch}}));
  const [preview,setPreview]=useState<Config|null>(null);
  const stale=configs.some(c=>effective(c).revision!==c.revision);
  const invalid=configs.some(c=>{const ids=effective(c).skills;return ids.length>30||new Set(state.skills.filter(s=>ids.includes(s.id)).map(s=>s.name.toLowerCase())).size!==ids.length;});
  const matches=state.tasks.filter(t=>matchTask(t,paradigm,query,channel,difficulty));
  const pendingTasks=matches.filter(t=>!canStartTask(t,state.baselines));
  const tasks=matches.filter(t=>showPending?!canStartTask(t,state.baselines):canStartTask(t,state.baselines));
  const selected=state.tasks.filter(t=>taskIds.includes(t.id));
  const pending=useRef<{payload:string;requestId:string}|null>(null);
  const create=async()=>{
    const data={configIds,taskIds,policy,notes,deliveryMode,configOverrides:configs.map(c=>({configId:c.id,...effective(c)}))};
    const payload=JSON.stringify(data);if(pending.current?.payload!==payload)pending.current={payload,requestId:crypto.randomUUID()};
    try{const run=await act<Run>('/runs/prepare',{...data,requestId:pending.current.requestId});pending.current=null;onCreated(run.id);if(openDraft&&run.trials.length===1)await act(`/runs/${run.id}/trials/${run.trials[0].id}/open`,{draft:true});}catch{/* Keep selections and request ID for a safe retry. */}
  };
  return <><header className="page-heading"><div><span className="eyebrow">评测工作台</span><h1 className="page-title">让配置，用结果说话。</h1><p>选一个真实任务，看看你的 Harness 如何交付。</p></div><div className="workspace-inventory"><div><SlidersHorizontal size={17}/><strong>{state.configs.length}</strong><span>套配置</span></div><div><FileCode2 size={17}/><strong>{state.tasks.filter(t=>canStartTask(t,state.baselines)).length}</strong><span>可开始题目</span></div><div><Layers3 size={17}/><strong>{state.runs.length}</strong><span>评测记录</span></div></div></header>
    <nav className="prepare-tabs" aria-label="评测准备步骤">{([['tasks','选择题目','确定需求与起点'],['config','配置与 Skills','选用本次工作方式'],['scoring','评分方案','确认后创建工作区']] as const).map(([id,label,hint],index)=><span aria-current={pane===id?'step':undefined} className={pane===id?'selected':index<['tasks','config','scoring'].indexOf(pane)?'is-complete':''} key={id}><i>{index<['tasks','config','scoring'].indexOf(pane)?<Check size={16}/>:String(index+1).padStart(2,'0')}</i><span><strong>{label}</strong><small>{hint}</small></span></span>)}</nav>
    <div className="prepare-grid">
      <div className="prepare-tasks" hidden={pane!=='tasks'}><Panel title="选择题目" aside={<label className="check-row"><input type="checkbox" checked={batch} onChange={e=>{setBatch(e.target.checked);setTasks(taskIds.slice(0,1));}}/>批量选择</label>}>
        <div className="task-filter-bar"><div className="task-primary-filters"><select aria-label="评测类别" value={paradigm} onChange={e=>{setParadigm(e.target.value);setTasks([]);setShowPending(false);}}><option value="open-ended-project">项目构建</option><option value="deterministic-bugfix">Bug 修复</option></select><input aria-label="搜索评测题目" placeholder="搜索需求或题目" value={query} onChange={e=>setQuery(e.target.value)}/></div>
        <TaskFilters channel={channel} difficulty={difficulty} onChannel={setChannel} onDifficulty={setDifficulty}/></div>
        <div className="catalog-switch"><button type="button" className={!showPending?'active':''} onClick={()=>setShowPending(false)}>可开始 · {matches.length-pendingTasks.length}</button><button type="button" className={showPending?'active':''} onClick={()=>setShowPending(true)}>待补全题面 · {pendingTasks.length}</button></div>
        <div className="task-browser"><div><div className="prepare-task-list">{tasks.map(t=><label key={t.id} className={'list-card '+(taskIds.includes(t.id)?'selected':'')}><div className="flex items-start gap-3"><input className="mt-1" type={batch?'checkbox':'radio'} name="task" checked={taskIds.includes(t.id)} onChange={e=>setTasks(batch?(e.target.checked?[...taskIds,t.id].slice(-10):taskIds.filter(id=>id!==t.id)):[t.id])}/><strong>{t.title}</strong></div><span>{t.difficulty} · {t.sourceKind==='repository-original'?'内置题包':t.hasFrontendUI?'含界面':'工程或文档'}</span><small>{t.baselineId?'源码自动复制':needsBaseline(t)?'缺少源码 · 暂不可开始':'从零构建'}</small></label>)}</div>
        {!tasks.length&&<Empty>没有符合筛选的题目。</Empty>}
        </div><aside className="task-preview">{selected.length?selected.map(t=><section key={t.id}><h3>{t.title}</h3><TaskEnvironment task={t} baselines={state.baselines}/><Details title="完整需求"><p className="reading-copy task-prompt">{t.inputPrompt}</p><ContractView task={t}/></Details></section>):<div className="preview-empty"><FileCode2 size={36} strokeWidth={1.2}/><h3>从一个真实问题开始</h3><p>选择左侧题目，预览完整需求、源码起点与环境。</p></div>}</aside></div>
        <div className="delivery-row"><Field label="交付方式"><select value={deliveryMode} onChange={e=>setDeliveryMode(e.target.value)}><option value="single-delivery">完整需求 · 不限定对话轮数</option><option value="staged">按题目预设步骤分阶段（可选）</option></select></Field>
        <p className="muted">{deliveryMode==='single-delivery'?'一次提供全部需求。由模型和你的配置决定实施过程，完成后回收评分。':'只有需要分步实验时选用。每步提示词需在原对话发送，也可以提前结束并评估整题。'}</p>
        </div>

      </Panel></div>
      <section className="prepare-session panel" aria-label="本次评测设置" hidden={pane==='tasks'}>
        <div className="prepare-session-heading"><h2 className="font-semibold">本次评测</h2><p className="muted prepare-selection" title={selected.map(t=>t.title).join('、')}>{selected.length?selected.map(t=>t.title).join('、'):'先选择一道题目'}</p></div>
        <div className="prepare-controls space-y-4">
          <div hidden={pane!=='config'} className="preparation-config-grid">
          <div className="config-select-row"><Field label="使用配置"><select value={configIds[0]||''} onChange={e=>{setConfigs([e.target.value,...configIds.slice(1).filter(id=>id!==e.target.value)]);setEditId(e.target.value);}}><option value="" disabled>选择已有配置</option>{state.configs.map(c=><option value={c.id} key={c.id}>{c.name} · v{c.revision}</option>)}</select></Field><button type="button" className="btn-secondary" disabled={!configs[0]} onClick={()=>setPreview(configs[0])}>预览配置</button></div>
          <label className="check-row"><input type="checkbox" checked={compare} onChange={e=>{setCompare(e.target.checked);setConfigs(configIds.slice(0,1));}}/>与另一套配置对比</label>
          {compare&&<div className="config-select-row"><Field label="对比配置"><select value={configIds[1]||''} onChange={e=>setConfigs([configIds[0],e.target.value])}><option value="" disabled>选择另一套配置</option>{state.configs.filter(c=>c.id!==configIds[0]).map(c=><option value={c.id} key={c.id}>{c.name} · v{c.revision}</option>)}</select></Field><button type="button" className="btn-secondary" disabled={!configs[1]} onClick={()=>setPreview(configs[1])}>预览对比配置</button></div>}
          {configs.length>1&&<div className="flex gap-2 flex-wrap" aria-label="调整哪套配置的技能">{configs.map(c=><button type="button" className={'stage-chip '+(editing?.id===c.id?'selected':'')} key={c.id} onClick={()=>setEditId(c.id)}>{c.name}</button>)}</div>}
          {editing&&<section className="prepare-skills space-y-4" key={editing.id}>
            <SkillPicker act={act} library={state.skills} value={effective(editing).skills} onChange={skills=>changeSkills(editing,{skills})}/>
            <div className="config-select-row"><Field label="调用方式"><select value={effective(editing).skillMode} onChange={e=>changeSkills(editing,{skillMode:e.target.value as 'auto'|'explicit'})}><option value="auto">按任务需要使用</option><option value="explicit">每轮明确请求使用</option></select></Field><button type="button" className="btn-ghost" onClick={()=>changeSkills(editing,{skills:editing.skills,skillMode:editing.skillMode||'auto'})}>恢复配置默认</button></div>
          </section>}
          </div>
          <div hidden={pane!=='scoring'}><ScoringSettings state={state} tasks={selected} policy={policy} onChange={setPolicy}/><Field label="本次备注"><input value={notes} onChange={e=>setNotes(e.target.value)}/></Field></div>
        </div>
      </section>
      <footer className="prepare-action">
        {pane==='scoring'&&<div className="space-y-2">{configs.length===1&&taskIds.length===1&&<label className="check-row"><input type="checkbox" checked={openDraft} onChange={e=>setOpenDraft(e.target.checked)}/>创建后打开 Codex 新对话并预填提示词</label>}
          {policy.objectiveWeight>0&&selected.some(t=>!t.checks.length)&&<p className="score-notice">所选题目缺少脚本检查，可新建机器评分方案。</p>}
          {!validPercentPolicy(policy)&&<p role="alert" className="alert-error">人工内部占比须合计100%。</p>}
        </div>}
        {invalid&&<p role="alert" className="alert-error">技能同名、不可用或超过30个，请调整选择。</p>}
        {stale&&<p role="alert" className="alert-error">原配置已更新，请恢复配置默认后重新核对。</p>}
        <div className="prepare-footer-row"><div className="selection-summary"><span>{taskIds.length?`${taskIds.length} 道题已选`:'尚未选择题目'}</span><small>{configs.length} 套配置 · {deliveryMode==='single-delivery'?'完整交付':'分步交付'}</small></div><div className="prepare-footer-buttons">
          {pane!=='tasks'&&<button type="button" className="btn-secondary" onClick={()=>setPane(pane==='scoring'?'config':'tasks')}>上一步</button>}
          {pane==='tasks'?<button type="button" className="btn-primary" disabled={!taskIds.length||selected.some(t=>!canStartTask(t,state.baselines))} onClick={()=>setPane('config')}>配置与 Skills <ArrowRight size={16}/></button>:pane==='config'?<button type="button" className="btn-primary" disabled={!configs.length||invalid||stale||(compare&&configs.length!==2)} onClick={()=>setPane('scoring')}>确认评分方案 <ArrowRight size={16}/></button>:<button type="button" className="btn-primary" disabled={!taskIds.length||!configs.length||invalid||stale||(policy.objectiveWeight>0&&selected.some(t=>!t.checks.length))||!validPercentPolicy(policy)||(compare&&configs.length!==2)} onClick={()=>void create()}>创建评测工作区</button>}
        </div></div>
      </footer>
      <Dialog title={preview?preview.name+' · v'+preview.revision:'配置预览'} open={!!preview} onClose={()=>setPreview(null)}>{preview&&<div className="space-y-4"><dl className="config-facts"><dt>模型</dt><dd>{preview.baseModel}</dd><dt>推理档位</dt><dd>{preview.reasoning}</dd><dt>交互</dt><dd>{preview.interactiveMode}</dd><dt>Skills</dt><dd>{preview.skills.map(id=>state.skills.find(s=>s.id===id)?.name||'不可用').join('、')||'未选择'}</dd></dl><h3>规则正文</h3><pre className="source">{preview.agentsPrompt||'未附加规则'}</pre><h3>原生设置与工具开关</h3><pre className="source">{JSON.stringify({settings:preview.nativeSettings||{},tools:preview.integrations||{}},null,2)}</pre>{preview.customConstraints.filter(c=>c.isActive).map(c=><p key={c.id}>{c.title}：{c.ruleDesc}</p>)}</div>}</Dialog>
    </div></>;
}

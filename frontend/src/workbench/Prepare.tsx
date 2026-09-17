import {ScoringSettings,percentPolicy,validPercentPolicy} from './Scoring';
import {useRef,useState} from 'react';
import type {State,Act,Run,Config,Imported} from './types';
import {Field,Panel,Details,Empty} from './ui';
import {ContractView,TaskFilters,matchTask} from './Contracts';
import {SkillLibrary,SkillChoice} from './Skills';

type Selection={revision:number;skills:string[];skillMode:'auto'|'explicit'};

export function Prepare({state,act,onCreated,selectedTaskId,selectedConfigId}:{state:State;act:Act;onCreated:(id:string)=>void;selectedTaskId:string|null;selectedConfigId?:string|null}){
  const [pane,setPane]=useState<'tasks'|'config'|'scoring'>('tasks');
  const [configIds,setConfigs]=useState<string[]>(selectedConfigId&&state.configs.some(c=>c.id===selectedConfigId)?[selectedConfigId]:state.configs.slice(0,1).map(c=>c.id));
  const initial=state.tasks.find(t=>t.id===selectedTaskId);
  const [taskIds,setTasks]=useState<string[]>(initial?[initial.id]:[]);
  const [paradigm,setParadigm]=useState(initial?.taskParadigm||'open-ended-project');const [query,setQuery]=useState('');
  const [compare,setCompare]=useState(false);const [batch,setBatch]=useState(false);
  const [channel,setChannel]=useState('');const [difficulty,setDifficulty]=useState('');
  const [policy,setPolicy]=useState(percentPolicy(structuredClone(state.defaultPolicy)));const [notes,setNotes]=useState('');
  const [selections,setSelections]=useState<Record<string,Selection>>({});
  const [editId,setEditId]=useState('');
  const configs=configIds.map(id=>state.configs.find(c=>c.id===id)).filter((c):c is Config=>!!c);
  const editing=configs.find(c=>c.id===editId)||configs[0];
  const effective=(c:Config):Selection=>selections[c.id]||{revision:c.revision,skills:c.skills,skillMode:c.skillMode||'auto'};
  const changeSkills=(c:Config,patch:Partial<Selection>)=>setSelections(current=>({...current,[c.id]:{...(current[c.id]?.revision===c.revision?current[c.id]:{revision:c.revision,skills:c.skills,skillMode:c.skillMode||'auto'}),...patch}}));
  const addSkills=(c:Config,imported:Imported[])=>setSelections(current=>{
    const base=current[c.id]?.revision===c.revision?current[c.id]:{revision:c.revision,skills:c.skills,skillMode:c.skillMode||'auto' as const};
    return {...current,[c.id]:{...base,skills:[...new Set([...base.skills,...imported.map(s=>s.id)])]}};
  });
  const stale=configs.some(c=>effective(c).revision!==c.revision);
  const invalid=configs.some(c=>{const ids=effective(c).skills;return ids.length>30||new Set(state.skills.filter(s=>ids.includes(s.id)).map(s=>s.name.toLowerCase())).size!==ids.length;});
  const tasks=state.tasks.filter(t=>matchTask(t,paradigm,query,channel,difficulty));
  const selected=state.tasks.filter(t=>taskIds.includes(t.id));
  const pending=useRef<{payload:string;requestId:string}|null>(null);
  const create=async()=>{
    const data={configIds,taskIds,policy,notes,configOverrides:configs.map(c=>({configId:c.id,...effective(c)}))};
    const payload=JSON.stringify(data);if(pending.current?.payload!==payload)pending.current={payload,requestId:crypto.randomUUID()};
    try{const run=await act<Run>('/runs/prepare',{...data,requestId:pending.current.requestId});pending.current=null;onCreated(run.id);}catch{/* Keep selections and request ID for a safe retry. */}
  };
  return <><div className="space-y-2"><h1 className="page-title">开始一次评测</h1><p className="muted">选题、选配置，在这里准备好本次工作区。</p></div>
    <nav className="prepare-tabs" aria-label="评测准备步骤">{([['tasks','选择题目'],['config','配置与 Skills'],['scoring','评分方案']] as const).map(([id,label])=><button type="button" aria-current={pane===id?'step':undefined} className={pane===id?'selected':''} onClick={()=>setPane(id)} key={id}>{label}</button>)}<span className="muted">已选 {taskIds.length} 道题 · {configs.length} 套配置</span></nav>
    <div className="prepare-grid">
      <div className="prepare-tasks" hidden={pane!=='tasks'}><Panel title="选择题目" aside={<label className="check-row"><input type="checkbox" checked={batch} onChange={e=>{setBatch(e.target.checked);setTasks(taskIds.slice(0,1));}}/>批量选择</label>}>
        <div className="grid sm:grid-cols-2 gap-3"><select aria-label="评测类别" value={paradigm} onChange={e=>{setParadigm(e.target.value);setTasks([]);}}><option value="open-ended-project">项目构建</option><option value="deterministic-bugfix">Bug 修复</option></select><input aria-label="搜索评测题目" placeholder="搜索需求或题目" value={query} onChange={e=>setQuery(e.target.value)}/></div>
        <TaskFilters channel={channel} difficulty={difficulty} onChannel={setChannel} onDifficulty={setDifficulty}/>
        <div className="prepare-task-list">{tasks.map(t=><label key={t.id} className={'list-card '+(taskIds.includes(t.id)?'selected':'')}><div className="flex items-start gap-3"><input className="mt-1" type={batch?'checkbox':'radio'} name="task" checked={taskIds.includes(t.id)} onChange={e=>setTasks(batch?(e.target.checked?[...taskIds,t.id].slice(-10):taskIds.filter(id=>id!==t.id)):[t.id])}/><strong>{t.title}</strong></div><span>{t.difficulty} · {t.stages.length} 阶段 · {t.checks.length} 项检查</span><small>{t.baselineId?'从已冻结起点开始':'从空文件夹开始'} · {t.hasFrontendUI?'含界面':'工程或文档'}</small></label>)}</div>
        {!tasks.length&&<Empty>没有符合筛选的题目。</Empty>}
        {selected.map(t=><Details key={t.id} title={'题目详情：'+t.title}><pre className="source">{t.inputPrompt}</pre><ContractView task={t}/></Details>)}
        <button type="button" className="btn-primary" disabled={!taskIds.length} onClick={()=>setPane('config')}>继续配置本次评测</button>
      </Panel></div>
      <section className="prepare-session panel" aria-label="本次评测设置" hidden={pane==='tasks'}>
        <div className="prepare-session-heading"><h2 className="font-semibold">本次评测</h2><p className="muted prepare-selection" title={selected.map(t=>t.title).join('、')}>{selected.length?selected.map(t=>t.title).join('、'):'先选择一道题目'}</p></div>
        <div className="prepare-controls space-y-4">
          <div hidden={pane!=='config'} className="space-y-4">
          <Field label="使用配置"><select value={configIds[0]||''} onChange={e=>{setConfigs([e.target.value,...configIds.slice(1).filter(id=>id!==e.target.value)]);setEditId(e.target.value);}}><option value="" disabled>选择已有配置</option>{state.configs.map(c=><option value={c.id} key={c.id}>{c.name} · v{c.revision}</option>)}</select></Field>
          <p className="muted">这里只选用已有配置。新增、导入或编辑配置请到顶部“配置管理”。</p>
          <label className="check-row"><input type="checkbox" checked={compare} onChange={e=>{setCompare(e.target.checked);setConfigs(configIds.slice(0,1));}}/>与另一套配置对比</label>
          {compare&&<Field label="对比配置"><select value={configIds[1]||''} onChange={e=>setConfigs([configIds[0],e.target.value])}><option value="" disabled>选择另一套配置</option>{state.configs.filter(c=>c.id!==configIds[0]).map(c=><option value={c.id} key={c.id}>{c.name} · v{c.revision}</option>)}</select></Field>}
          {configs.length>1&&<div className="flex gap-2 flex-wrap" aria-label="调整哪套配置的技能">{configs.map(c=><button type="button" className={'stage-chip '+(editing?.id===c.id?'selected':'')} key={c.id} onClick={()=>setEditId(c.id)}>{c.name}</button>)}</div>}
          {editing&&<div className="space-y-3" key={editing.id}>
            <p className="muted">{editing.baseModel} · {editing.reasoning} · {editing.name}</p>
            <div className="flex gap-2 flex-wrap" aria-label="本次选定技能">{effective(editing).skills.length?effective(editing).skills.map(id=>{const s=state.skills.find(s=>s.id===id);return <span className="skill-chip" key={id} title={s?.sourcePath}>{s?.name||'技能不可用'}<button type="button" aria-label={`移除技能 ${s?.name||id}`} onClick={()=>changeSkills(editing,{skills:effective(editing).skills.filter(x=>x!==id)})}>×</button></span>}):<p className="muted">尚未选择 Skills</p>}</div>
            <section className="space-y-3"><h3 className="font-semibold">本次 Skills</h3>
              <p className="muted">仅用于这次评测，原配置保持不变。未选的全局技能仍可能由桌面继承。</p>
              <Details title={`从已导入技能调整 · ${state.skills.length} 个可选`}><div className="skill-options">{state.skills.map(s=><SkillChoice key={s.id} skill={s} checked={effective(editing).skills.includes(s.id)} onChange={checked=>changeSkills(editing,{skills:checked?[...effective(editing).skills,s.id]:effective(editing).skills.filter(id=>id!==s.id)})}/>)}</div></Details>
              <Field label="技能使用方式"><select value={effective(editing).skillMode} onChange={e=>changeSkills(editing,{skillMode:e.target.value as 'auto'|'explicit'})}><option value="auto">按任务需要使用</option><option value="explicit">每轮明确请求使用</option></select></Field>
              <SkillLibrary act={act} onImported={skills=>addSkills(editing,skills)} context="trial"/>
              <button type="button" className="btn-ghost" onClick={()=>changeSkills(editing,{skills:editing.skills,skillMode:editing.skillMode||'auto'})}>恢复原配置的技能选择</button>
            </section>
            <Details title="预览配置内容"><p className="muted">原生设置：{Object.entries(editing.nativeSettings||{}).map(([k,v])=>k+' = '+v).join('；')||'继承宿主'}；工具开关：{Object.entries(editing.integrations||{}).flatMap(([g,items])=>Object.entries(items).map(([k,v])=>g+'/'+k+'：'+(v?'启用':'停用'))).join('；')||'继承宿主'}</p><p className="muted">交互：{editing.interactiveMode==='adaptive'?'按任务判断':editing.interactiveMode==='step-by-step-confirm'?'分阶段等待确认':'一次交付'}</p><pre className="source">{editing.agentsPrompt||'没有附加规则'}</pre>{editing.customConstraints.filter(c=>c.isActive).map(c=><p className="muted" key={c.id}>{c.title}：{c.ruleDesc}</p>)}</Details>
          </div>}
          <button type="button" className="btn-secondary" onClick={()=>setPane('scoring')}>调整评分方案</button>
          </div>
          <div hidden={pane!=='scoring'}><ScoringSettings state={state} tasks={selected} policy={policy} onChange={setPolicy}/><Field label="本次备注"><input value={notes} onChange={e=>setNotes(e.target.value)}/></Field></div>
        </div>
        <div className="prepare-action space-y-2"><p className="muted">{configs.length} 套配置 × {taskIds.length} 道题 · 创建 {configs.length*taskIds.length} 个工作区</p>
          {policy.objectiveWeight>0&&selected.some(t=>!t.checks.length)&&<p className="score-notice">当前题目缺少自动检查，请到评分方案选择纯人工验收，或到题库配置检查。</p>}
          {!validPercentPolicy(policy)&&<p role="alert" className="alert-error">请到评分方案将人工内部占比调整到100%。</p>}
          {invalid&&<p role="alert" className="alert-error">技能同名、不可用或超过30个，请调整选择。</p>}
          {stale&&<p role="alert" className="alert-error">原配置已更新。请在技能设置恢复原配置选择，再核对本次调整。</p>}
          <button type="button" className="btn-primary w-full" disabled={!taskIds.length||!configs.length||invalid||stale||(policy.objectiveWeight>0&&selected.some(t=>!t.checks.length))||!validPercentPolicy(policy)||(compare&&configs.length!==2)} onClick={()=>void create()}>应用到新工作区并创建</button>
          <p className="muted">自动放入规则与 Skills；模型、档位及发送在 Codex 桌面核对。</p>
        </div>
      </section>
    </div></>;
}

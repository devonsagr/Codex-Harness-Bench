import {useEffect,useState} from 'react';
import type {State,Act,Config,Task,Check,Imported} from './types';
import {SkillLibrary,ProjectConfigImport} from './Skills';
import {Field,Panel,Details,Empty} from './ui';
import {ContractEditor,TaskFilters,TaskImport,matchTask} from './Contracts';

const newConfig=():Config=>({id:'',revision:0,name:'',agentsPrompt:'',baseModel:'gpt-6-astra',reasoning:'medium',interactiveMode:'adaptive',skills:[],customConstraints:[]});
export function ConfigManager({state,act,onUse}:{state:State;act:Act;onUse:(id:string)=>void}){
  const [draft,setDraft]=useState<Config>(state.configs[0]||newConfig());
  const addSkills=(imported:Imported[])=>setDraft(current=>({...current,skills:[...new Set([...current.skills,...imported.map(s=>s.id)])]}));
  const change=(patch:Partial<Config>)=>setDraft({...draft,...patch});
  const save=async(copy=false)=>{try{setDraft(await act<Config>('/configs/save',{...draft,...(copy?{id:undefined,revision:undefined,name:draft.name+' · 副本'}:{})}));}catch{/* App displays error */}};
  return <div className="work-layout"><aside className="space-y-3"><div className="flex justify-between items-center"><h1 className="page-title">配置管理</h1><button className="btn-secondary" onClick={()=>setDraft(newConfig())}>新建</button></div>
    {state.configs.map(c=><button key={c.id} className={'list-card '+(draft.id===c.id?'selected':'')} onClick={()=>setDraft(structuredClone(c))}><strong>{c.name}</strong><span>{c.baseModel} · {c.reasoning}</span><small>版本 {c.revision} · {c.skills.length} 个选定技能</small></button>)}
    <button className="btn-secondary w-full" onClick={()=>act<Config>('/configs/import-current',{}).then(setDraft).catch(()=>{})}>导入当前全局规则副本</button>
    <Details title="恢复归档配置">{state.archivedConfigs.map(c=><button key={c.id} className="btn-secondary mr-2" onClick={()=>act<Config>(`/configs/${c.id}/archive`,{revision:c.revision,archived:false}).then(setDraft).catch(()=>{})}>{c.name} · 恢复</button>)}</Details>
    <p className="muted">导入只读取全局规则及模型、推理档位。技能需明确选择；不修改宿主配置。</p>
    <ProjectConfigImport act={act} onImported={setDraft}/>
  </aside><div className="space-y-5"><Panel title={draft.id?'编辑配置 · v'+draft.revision:'新建配置'}>
    <form onSubmit={e=>{e.preventDefault();void save();}} className="space-y-4">
      <Field label="配置名称"><input required value={draft.name} onChange={e=>change({name:e.target.value})}/></Field>
      <div className="grid sm:grid-cols-3 gap-4"><Field label="模型" hint="来自本机模型缓存；正式执行前在桌面核对。"><input list="models" required value={draft.baseModel} onChange={e=>change({baseModel:e.target.value})}/><datalist id="models">{state.models.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</datalist></Field>
      <Field label="推理档位"><select value={draft.reasoning} onChange={e=>change({reasoning:e.target.value})}>{['none','minimal','low','medium','high','xhigh','max','ultra'].map(s=><option key={s}>{s}</option>)}</select></Field>
      <Field label="交互约定"><select value={draft.interactiveMode} onChange={e=>change({interactiveMode:e.target.value})}><option value="adaptive">按任务自行判断</option><option value="one-shot-direct">一次交付</option><option value="step-by-step-confirm">分阶段等我确认</option></select></Field></div>
      <Field label="AGENTS 规则" hint="在独立工作区写入 AGENTS.override.md；桌面全局规则仍会继承。"><textarea rows={12} value={draft.agentsPrompt} onChange={e=>change({agentsPrompt:e.target.value})}/></Field>
      {draft.importSource&&<Details title="配置导入来源"><p className="muted break-all">{draft.importSource.root}</p>{draft.importSource.files.map(f=><p className="muted break-all" key={f.path}>{f.path} · {f.sha256.slice(0,12)}</p>)}{draft.importSource.warnings.map(w=><p className="muted" key={w}>{w}</p>)}<p className="muted">{draft.importSource.note}</p></Details>}
      <Details title={`选定技能 · ${draft.skills.length} 个`}>
        {state.skills.length?state.skills.map(s=><label className="check-row" key={s.id}><input type="checkbox" checked={draft.skills.includes(s.id)} onChange={e=>change({skills:e.target.checked?[...draft.skills,s.id]:draft.skills.filter(id=>id!==s.id)})}/><span>{s.name}<small className="block muted break-all">{s.sourceLabel||'手动导入'} · {s.sourcePath} · {Object.keys(s.manifest.files).length} 文件 · {s.manifest.sha256.slice(0,12)}</small></span></label>):<p className="muted">使用下方技能库读取列表并批量选择。</p>}
      </Details>
      <Field label="选定技能的使用方式" hint="未选中的全局技能仍可能被桌面继承。文件已装载不代表模型已使用。"><select value={draft.skillMode||'auto'} onChange={e=>change({skillMode:e.target.value as 'auto'|'explicit'})}><option value="auto">按任务需要使用</option><option value="explicit">在每轮提示词中明确请求使用</option></select></Field>
      {new Set(state.skills.filter(s=>draft.skills.includes(s.id)).map(s=>s.name.toLowerCase())).size!==draft.skills.length&&<p role="alert" className="alert-error">当前选择有同名或不可用技能，请在上方取消重复选择后保存。</p>}
      <Details title={`个人约束 · ${draft.customConstraints.length} 项`}>
        <p className="muted">例如需要等待确认、特定文档同步。单独记录是否满足，不把人人不同的要求换成通用加分。</p>
        {draft.customConstraints.map((c,i)=><div key={c.id} className="panel-subtle p-3 space-y-2"><div className="flex gap-3"><input aria-label="约束名称" placeholder="约束名称" value={c.title} onChange={e=>change({customConstraints:draft.customConstraints.map((v,j)=>i===j?{...v,title:e.target.value}:v)})}/><button type="button" className="btn-ghost" onClick={()=>change({customConstraints:draft.customConstraints.filter((_,j)=>j!==i)})}>移除</button></div><textarea aria-label="约束说明" placeholder="明确要求与验证依据" value={c.ruleDesc} onChange={e=>change({customConstraints:draft.customConstraints.map((v,j)=>i===j?{...v,ruleDesc:e.target.value}:v)})}/><label className="check-row"><input type="checkbox" checked={c.isActive} onChange={e=>change({customConstraints:draft.customConstraints.map((v,j)=>i===j?{...v,isActive:e.target.checked}:v)})}/>本配置启用</label></div>)}
        <button type="button" className="btn-secondary" onClick={()=>change({customConstraints:[...draft.customConstraints,{id:'rule-'+crypto.randomUUID(),title:'',ruleDesc:'',isActive:true}]})}>添加个人约束</button>
      </Details>
      <div className="flex gap-3"><button className="btn-primary" type="submit">保存配置版本</button>{draft.id&&<><button type="button" className="btn-secondary" onClick={()=>void save(true)}>另存副本</button><button type="button" className="btn-ghost" onClick={()=>act(`/configs/${draft.id}/archive`,{revision:draft.revision,archived:true}).then(()=>setDraft(newConfig())).catch(()=>{})}>归档配置</button></>}</div>
    </form>
    <button type="button" className="btn-secondary" onClick={async()=>{try{const c=await act<Config>('/configs/save',draft);setDraft(c);onUse(c.id);}catch{/* App displays validation. */}}}>保存并用于评测</button>
  </Panel><SkillLibrary act={act} onImported={addSkills}/></div></div>;
}

const newTask=():Task=>({id:'',revision:0,title:'',difficulty:'medium',taskParadigm:'open-ended-project',channel:'frontend-ui',inputPrompt:'',stages:[{title:'完成需求',prompt:''}],checks:[],hasFrontendUI:true,sourceKind:'user-authored',sourceNote:'本地自定义题',license:'用户自有内容'});
export function TaskManager({state,act,onUse}:{state:State;act:Act;onUse:(id:string)=>void}){
  const [draft,setDraft]=useState<Task>(structuredClone(state.tasks.find(t=>t.taskParadigm==='open-ended-project')||newTask()));const [query,setQuery]=useState('');const [kind,setKind]=useState('open-ended-project');const [path,setPath]=useState('');
  const change=(patch:Partial<Task>)=>setDraft({...draft,...patch});
  const [channel,setChannel]=useState('');const [difficulty,setDifficulty]=useState('');
  const check=(i:number,patch:Partial<Check>)=>change({checks:draft.checks.map((c,j)=>i===j?{...c,...patch}:c)});
  const save=async(copy=false)=>{try{setDraft(await act<Task>('/tasks/save',{...draft,...(copy?{id:undefined,revision:undefined,title:draft.title+' · 副本'}:{})}));}catch{/* App displays error */}};
  const list=state.tasks.filter(t=>matchTask(t,kind,query,channel,difficulty));
  return <div className="work-layout"><aside className="space-y-3"><div className="flex justify-between"><h1 className="page-title">题库中心</h1><button className="btn-secondary" onClick={()=>setDraft(newTask())}>新建题目</button></div><input aria-label="搜索题目" placeholder="搜索题目" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="题库类别" value={kind} onChange={e=>setKind(e.target.value)}><option value="open-ended-project">项目构建</option><option value="deterministic-bugfix">Bug 修复</option></select>
    <TaskFilters channel={channel} difficulty={difficulty} onChannel={setChannel} onDifficulty={setDifficulty}/>
    <button className="btn-secondary w-full" onClick={()=>act('/tasks/import-originals',{}).catch(()=>{})}>导入项目的 3 道完整原创题</button><p className="muted">原创题自带起点和独立验收定义；镜像按 README 准备。</p><Details title="恢复归档题目">{state.archivedTasks.map(t=><button key={t.id} className="btn-secondary mr-2" onClick={()=>act<Task>(`/tasks/${t.id}/archive`,{revision:t.revision,archived:false}).then(setDraft).catch(()=>{})}>{t.title} · 恢复</button>)}</Details>
    <p className="muted">{list.length} 道题 · 题面、起点文件、验收检查分别声明。</p><div className="scroll-list">{list.map(t=><button className={'list-card '+(t.id===draft.id?'selected':'')} key={t.id} onClick={()=>{setDraft(structuredClone(t));}}><strong>{t.title}</strong><span>{t.difficulty} · {t.stages.length} 阶段 · {t.checks.length} 项检查</span><small>{t.baselineId?'已绑定起点快照':'从空工作区开始'}</small></button>)}</div>
  </aside><div className="space-y-5"><Panel title={draft.id?'题目定义 · v'+draft.revision:'新建题目'}>
    <form className="space-y-4" onSubmit={e=>{e.preventDefault();void save();}}>
      <Field label="题目名称"><input required value={draft.title} onChange={e=>change({title:e.target.value})}/></Field>
      <div className="grid sm:grid-cols-3 gap-4"><Field label="题目类别"><select value={draft.taskParadigm} onChange={e=>change({taskParadigm:e.target.value})}><option value="open-ended-project">项目构建</option><option value="deterministic-bugfix">Bug 修复</option></select></Field><Field label="难度"><select value={draft.difficulty} onChange={e=>change({difficulty:e.target.value})}>{[...new Set([draft.difficulty,'Easy','Medium','Hard','Nightmare'])].map(v=><option key={v}>{v}</option>)}</select></Field><Field label="任务方向"><select value={draft.channel} onChange={e=>change({channel:e.target.value})}><option value="frontend-ui">应用与界面</option><option value="deepswe-core">功能与工程</option><option value="architecture-constraint">架构与约束</option><option value="interactive-confirm">协作与多轮</option></select></Field></div>
      <Field label="总体需求"><textarea required rows={8} value={draft.inputPrompt} onChange={e=>change({inputPrompt:e.target.value,...(draft.stages.length===1?{stages:[{...draft.stages[0],prompt:e.target.value}]}:{})})}/></Field>
      <ContractEditor task={draft} onChange={change}/>
      <label className="check-row"><input type="checkbox" checked={draft.hasFrontendUI} onChange={e=>change({hasFrontendUI:e.target.checked})}/>包含界面，人工复审需评价交互与视觉</label>
      <Details title={`逐轮提示词 · ${draft.stages.length} 阶段`}>
        <p className="muted">每轮提示词都包含总体需求和完整项目契约；后续轮次在同一桌面任务发送。每轮回收后手动确认继续。</p>
        {draft.stages.map((s,i)=><div key={i} className="panel-subtle p-3 space-y-2"><Field label={`第 ${i+1} 轮名称`}><input required value={s.title} onChange={e=>change({stages:draft.stages.map((v,j)=>i===j?{...v,title:e.target.value}:v)})}/></Field><Field label="本轮提示词"><textarea required rows={4} value={s.prompt} onChange={e=>change({stages:draft.stages.map((v,j)=>i===j?{...v,prompt:e.target.value}:v)})}/></Field>{draft.stages.length>1&&<button className="btn-ghost" type="button" onClick={()=>change({stages:draft.stages.filter((_,j)=>j!==i)})}>移除此轮</button>}</div>)}
        <button className="btn-secondary" type="button" onClick={()=>change({stages:[...draft.stages,{title:'下一阶段',prompt:''}]})}>增加阶段</button>
      </Details>
      <Field label="起点文件快照"><select value={draft.baselineId||''} onChange={e=>change({baselineId:e.target.value||undefined})}><option value="">空工作区</option>{state.baselines.map(b=><option key={b.id} value={b.id}>{b.name} · {b.manifest.sha256.slice(0,8)}</option>)}</select></Field>
      <Details title={`容器验收检查 · ${draft.checks.length} 项`}>
        <p className="muted">镜像必须预先在本机准备；检查在无网络容器的产物副本执行。可用自有测试镜像保护验收逻辑，不把答案放进题目起点。</p>
        {draft.checks.map((c,i)=><div className="panel-subtle p-3 space-y-3" key={i}><div className="grid sm:grid-cols-2 gap-3"><Field label="检查名称"><input required value={c.label} onChange={e=>check(i,{label:e.target.value})}/></Field><Field label="Docker 镜像"><input required value={c.image} onChange={e=>check(i,{image:e.target.value})}/></Field></div>
        <Field label="命令参数数组（JSON）" hint={'例如 ["python","-I","/tests/verify.py","/app"]。不执行宿主命令。'}><CommandArgs key={draft.id+'-'+draft.revision+'-'+i} label={`检查 ${i+1} 命令参数`} value={c.argv} onChange={argv=>check(i,{argv})}/></Field>
        <div className="grid grid-cols-3 gap-3"><Field label="权重"><input type="number" min={1} max={100} value={c.weight} onChange={e=>check(i,{weight:Number(e.target.value)})}/></Field><Field label="超时秒数"><input type="number" min={1} max={600} value={c.timeout||120} onChange={e=>check(i,{timeout:Number(e.target.value)})}/></Field><Field label="验收阶段"><select value={c.stageIndex??'final'} onChange={e=>check(i,{stageIndex:e.target.value==='final'?undefined:Number(e.target.value)})}><option value="final">最终交付</option>{draft.stages.map((s,j)=><option key={j} value={j}>{j+1}. {s.title}</option>)}</select></Field></div><Field label="检查类别"><select value={c.kind||'other'} onChange={e=>check(i,{kind:e.target.value})}><option value="functional">功能</option><option value="build">构建 / 类型</option><option value="rule">规则</option><option value="other">其他（未分类）</option></select></Field><label className="check-row"><input type="checkbox" checked={c.runOnFinal||false} onChange={e=>check(i,{runOnFinal:e.target.checked})}/>最终交付时重新运行此检查</label><Details title="关联验收条目">{draft.criteria?.map(row=><label key={row.id} className="check-row"><input type="checkbox" checked={c.criterionIds?.includes(row.id)||false} onChange={e=>check(i,{criterionIds:e.target.checked?[...(c.criterionIds||[]),row.id]:(c.criterionIds||[]).filter(id=>id!==row.id)})}/>{row.label}</label>)}</Details><button className="btn-ghost" type="button" onClick={()=>change({checks:draft.checks.filter((_,j)=>i!==j)})}>移除检查</button></div>)}
        <button className="btn-secondary" type="button" onClick={()=>change({checks:[...draft.checks,{id:'check-'+crypto.randomUUID(),label:'',image:'',argv:[],weight:1,timeout:120}]})}>添加检查</button>
      </Details>
      <Details title="来源与许可"><Field label="来源说明"><textarea value={draft.sourceNote||''} onChange={e=>change({sourceNote:e.target.value})}/></Field><Field label="参考链接（不会自动下载）"><input value={draft.referenceUrl||''} onChange={e=>change({referenceUrl:e.target.value})}/></Field><Field label="许可声明"><input value={draft.license||''} onChange={e=>change({license:e.target.value})}/></Field><p className="muted">Gemini 导入题目保留题面；其中参考仓库和测试建议尚未证明可执行。不以题目数量宣称覆盖率。</p></Details>
      <div className="flex gap-3"><button className="btn-primary">保存题目版本</button><button type="button" className="btn-secondary" onClick={async e=>{if(!e.currentTarget.form?.reportValidity())return;try{const t=await act<Task>('/tasks/save',draft);setDraft(t);onUse(t.id);}catch{/* Global error */}}}>保存并用于评测</button>{draft.id&&<><button type="button" className="btn-secondary" onClick={e=>{if(e.currentTarget.form?.reportValidity())void save(true);}}>另存新题</button><button type="button" className="btn-ghost" onClick={()=>act(`/tasks/${draft.id}/archive`,{revision:draft.revision,archived:true}).then(()=>setDraft(newTask())).catch(()=>{})}>归档题目</button></>}</div>
    </form>
  </Panel><TaskImport act={act} onImported={t=>{setDraft(t);setKind(t.taskParadigm);setQuery('');setChannel('');setDifficulty('');}}/><Panel title="导入题目起点"><form className="space-y-3" onSubmit={e=>{e.preventDefault();act<{id:string}>('/baselines/import',{path}).then(b=>{change({baselineId:b.id});setPath('');}).catch(()=>{});}}><Field label="源文件夹绝对路径" hint="导入为新快照，原文件夹不会被修改。凭据、依赖目录及 Git 元数据不会复制。"><input required value={path} onChange={e=>setPath(e.target.value)}/></Field><button className="btn-secondary">导入并选作起点</button></form></Panel></div></div>;
}

function CommandArgs({label,value,onChange}:{label:string;value:string[];onChange:(argv:string[])=>void}){
  const [raw,setRaw]=useState(JSON.stringify(value));const [error,setError]=useState('');
  useEffect(()=>{setRaw(JSON.stringify(value));setError('');},[value]);
  return <><input aria-label={label} value={raw} required ref={el=>el?.setCustomValidity(error)} onChange={e=>{
    setRaw(e.target.value);let message='';
    try{const argv:unknown=JSON.parse(e.target.value);if(!Array.isArray(argv)||!argv.length||!argv.every(v=>typeof v==='string')||!argv[0].trim())throw new Error();onChange(argv);}
    catch{message='命令需为非空 JSON 字符串数组，请修正后保存。';}
    e.target.setCustomValidity(message);setError(message);
  }}/>{error&&<small role="alert" className="alert-error">{error}</small>}</>;
}

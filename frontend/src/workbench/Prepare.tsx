import {ArrowRight,BookOpen,Check,Code2,ExternalLink,Filter,Lightbulb,Search,ShieldCheck} from 'lucide-react';
import {ScoringSettings,percentPolicy,validPercentPolicy} from './Scoring';
import {useEffect,useRef,useState} from 'react';
import {availableTasks,PublicPrompt,publicCategories,nativeTaskIds,upstreamDockerTaskIds} from './PublicCatalog';
import type {State,Act,Config,PreparationJob,Task,Run} from './types';
import {Field,Details,Empty,Dialog} from './ui';
import {ContractView,TaskFilters,matchTask} from './Contracts';
import {TaskEnvironment,canStartTask,needsBaseline} from './TaskEnvironment';
import {CodexApply} from './Codex';
import {capabilityLabels,creativeTaskDrawGroup,familyGroups,familyLabels,inFamilyGroup,taskFamily,taskLibraryOrder} from './TaskTaxonomy';
import {balancedRandomIds,seededRandom,compactWebGenTask} from './balancedSelection';
import publicSources from '../../../catalog/public-task-sources.json';

const publicRepositories=new Map(publicSources.tasks.map(task=>[task.id,task.repositoryUrl]));
const repositoryUrl=(task:Task)=>task.publicSource?publicRepositories.get(task.publicSource.id):undefined;
const sourceName=(task:Task)=>{
  const repository=task.publicSource?publicRepositories.get(task.publicSource.id):task.description;
  if(repository?.startsWith('https://github.com/')){
    try{return new URL(repository).pathname.replace(/^\//,'').replace(/\/$/,'');}catch{/* Keep the known source label. */}
  }
  return task.sourceKind==='webgen-bench-local'?'WebGen-Bench · 本地适配':task.sourceKind==='deepswe'?'DeepSWE 固定仓库':task.id.startsWith('original-creative-')?'原创网页与视觉题':task.id.startsWith('original-open-')?'原创跨类型实践题':task.sourceKind==='repository-original'?'项目内置题包':'自定义需求';
};
const taskKind=(task:Task)=>familyLabels[taskFamily(task)]||publicCategories[task.publicSource?.category||'']||'其他任务';

export function Prepare({state,act,onCreated,onEditConfig,selectedTaskId,selectedConfigId,initialRun}:{state:State;act:Act;onCreated:(id:string)=>void;onEditConfig:(id:string)=>void;selectedTaskId:string|null;selectedConfigId?:string|null;initialRun?:Run|null}){
  const [pane,setPane]=useState<'tasks'|'config'|'scoring'>('tasks');
  const seedConfigId=initialRun?.configs[0]?.id;
  const [configId,setConfigId]=useState<string>(seedConfigId&&state.configs.some(c=>c.id===seedConfigId)?seedConfigId:selectedConfigId&&state.configs.some(c=>c.id===selectedConfigId)?selectedConfigId:state.configs[0]?.id||'');
  const catalog=availableTasks(state);
  const initial=catalog.find(t=>t.id===selectedTaskId);
  const coreTasks=catalog.filter(t=>inFamilyGroup(t,'core')&&canStartTask(t,state.baselines)).sort(taskLibraryOrder);
  const seedTaskIds=initialRun?.tasks.map(t=>t.id).filter(id=>catalog.some(item=>item.id===id))||[];
  const [taskIds,setTasks]=useState<string[]>(seedTaskIds.length?seedTaskIds:initial?[initial.id]:(coreTasks.length?coreTasks:catalog.filter(t=>canStartTask(t,state.baselines))).slice(0,1).map(t=>t.id));
  const [focusedTaskId,setFocusedTaskId]=useState<string|null>(seedTaskIds[0]||initial?.id||null);
  const seedCategory=familyGroups.find(([id])=>id&&seedTaskIds.length&&seedTaskIds.every(taskId=>{const task=catalog.find(item=>item.id===taskId);return task&&inFamilyGroup(task,id);}))?.[0]||'';
  const initialCategory=initial?(inFamilyGroup(initial,'core')?'core':familyGroups.find(([id])=>id&&id!=='core'&&inFamilyGroup(initial,id))?.[0]||''):'core';
  const [paradigm,setParadigm]=useState('all');const [query,setQuery]=useState('');
  const [showPending,setShowPending]=useState(false);
  const [sourceFilter,setSourceFilter]=useState('all');const [category,setCategory]=useState(seedTaskIds.length?seedCategory:initialCategory);const [family,setFamily]=useState('');const [language,setLanguage]=useState('');
  const [showFullPrompt,setShowFullPrompt]=useState(false);
  const filterRef=useRef<HTMLDetailsElement>(null);
  const categoryRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{const close=(event:PointerEvent)=>{if(filterRef.current?.open&&!filterRef.current.contains(event.target as Node))filterRef.current.open=false;};const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&filterRef.current?.open)filterRef.current.open=false;};document.addEventListener('pointerdown',close);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',escape);};},[]);
  const [jobId,setJobId]=useState<string|null>(null);const delivered=useRef<string|null>(null);
  const [createError,setCreateError]=useState('');
  const [deliveryMode,setDeliveryMode]=useState<string>(initialRun?.tasks[0]?.deliveryMode||'single-delivery');
  const [batch,setBatch]=useState(seedTaskIds.length>1);
  const [randomCount,setRandomCount]=useState(2);
  const [randomNotice,setRandomNotice]=useState('');
  const [randomSeed,setRandomSeed]=useState<number|null>(null);
  const [channel,setChannel]=useState('');const [difficulty,setDifficulty]=useState('');
  const [policy,setPolicy]=useState(percentPolicy(structuredClone(initialRun?.policy||state.defaultPolicy)));const [notes,setNotes]=useState(initialRun?.notes||'');
  const config=state.configs.find(c=>c.id===configId);
  const [preview,setPreview]=useState<Config|null>(null);
  const invalid=!!config&&(config.skills.length>30||new Set(state.skills.filter(s=>config.skills.includes(s.id)).map(s=>s.name.toLowerCase())).size!==config.skills.length);
  const sourceCandidates=catalog.filter(t=>matchTask(t,paradigm,query,'','')&&(sourceFilter==='all'||(sourceFilter==='deepswe'?!!t.publicSource:sourceFilter==='webgen'?t.sourceKind==='webgen-bench-local':!t.publicSource&&t.sourceKind!=='webgen-bench-local')));
  const candidates=sourceCandidates.filter(t=>inFamilyGroup(t,category)&&(!family||taskFamily(t)===family)&&(!language||(t.publicSource?.language||t.language)===language));
  const matches=candidates.filter(t=>matchTask(t,paradigm,query,channel,difficulty));
  const facetTasks=candidates.filter(t=>showPending?!canStartTask(t,state.baselines):canStartTask(t,state.baselines));
  const pendingTasks=matches.filter(t=>!canStartTask(t,state.baselines));
  const tasks=matches.filter(t=>showPending?!canStartTask(t,state.baselines):canStartTask(t,state.baselines)).sort(taskLibraryOrder);
  const readyTasks=catalog.filter(t=>canStartTask(t,state.baselines));
  const readyPublic=new Set([...nativeTaskIds,...upstreamDockerTaskIds]);
  const shortEnough=(task:Task)=>!['long','hard'].includes(task.difficulty?.toLowerCase()||'');
  const swePool=readyTasks.filter(t=>!t.hasFrontendUI&&shortEnough(t)&&
    (t.publicSource?readyPublic.has(t.publicSource.id):t.checks.length>0));
  const webPool=readyTasks.filter(t=>taskFamily(t)==='web-interface'&&t.hasFrontendUI&&shortEnough(t)&&
    (t.id.startsWith('original-creative-')||(t.sourceKind==='webgen-bench-local'&&compactWebGenTask(t))||t.checks.length>0));
  const maxRandomCount=Math.min(5,swePool.length,webPool.length);
  const randomize=()=>{
    try{
      const count=Math.min(randomCount,maxRandomCount);
      const seed=crypto.getRandomValues(new Uint32Array(1))[0];
      const ids=balancedRandomIds(swePool,webPool,count,
        task=>repositoryUrl(task)||taskFamily(task),
        creativeTaskDrawGroup,seededRandom(seed));
      setRandomSeed(seed);
      setBatch(true);setTasks(ids);setFocusedTaskId(ids[0]);setRandomNotice(`已选 ${count*2} 道：代码与逻辑 ${count} 道、界面与交互 ${count} 道。先分散题型和来源，再随机抽取，不重复。`);
      setCategory('');setParadigm('all');setSourceFilter('all');setFamily('');setLanguage('');setQuery('');setChannel('');setDifficulty('');setShowPending(false);
    }catch(error){setRandomNotice((error as Error).message);}
  };
  const visibleTaskIds=tasks.map(t=>t.id).join('|');
  const selectedIds=taskIds.join('|');
  useEffect(()=>{
    if(batch)return;
    if(!tasks.length){if(taskIds.length)setTasks([]);return;}
    if(taskIds.length!==1||!tasks.some(t=>t.id===taskIds[0]))setTasks([tasks[0].id]);
  },[visibleTaskIds,selectedIds,batch]);
  const categoryOptions=familyGroups;
  const languages=[...new Set(sourceCandidates.map(t=>t.publicSource?.language||t.language).filter((value):value is string=>!!value))].sort();
  const selected=taskIds.map(id=>catalog.find(t=>t.id===id)).filter((task):task is Task=>!!task);
  const publicQualityMissing=policy.version==='arena-machine-v1'&&selected.some(t=>!!t.publicSource)&&(policy.dimensions.maintainability||0)<=0;
  const lastFailed=state.preparationJobs?.[0]?.status==='failed'&&state.preparationJobs[0].taskIds?.length?state.preparationJobs[0]:null;
  const previewTasks=batch&&selected.length>1?[selected.find(t=>t.id===focusedTaskId)||selected[selected.length-1]]:selected;
  const canStage=selected.length>0&&selected.every(t=>t.stages.length>1);
  const effectiveDelivery=canStage?deliveryMode:'single-delivery';
  const pending=useRef<{payload:string;requestId:string}|null>(null);
  const recover=(previous:PreparationJob)=>{
    const ids=previous.taskIds.filter(id=>catalog.some(t=>t.id===id));
    if(!ids.length)return;
    setTasks(ids);setBatch(ids.length>1);setFocusedTaskId(ids[0]);setShowPending(false);
    const request=previous.requestData;
    const usable=!!request&&request.configIds?.length===1&&request.taskIds.length===ids.length&&state.configs.some(config=>config.id===request.configIds[0]);
    if(usable){
      setConfigId(request.configIds[0]);setPolicy(request.policy);setNotes(request.notes||'');setDeliveryMode(request.deliveryMode||'single-delivery');
      pending.current={requestId:previous.id,payload:JSON.stringify({configIds:request.configIds,taskIds:request.taskIds,policy:request.policy,notes:request.notes||'',deliveryMode:request.deliveryMode||'single-delivery'})};
    }else pending.current=null;
    setJobId(previous.id);setPane(usable?'scoring':'config');
  };
  const create=async()=>{
    setCreateError('');
    const frozenPolicy=policy.taskTypeAuto?{...policy,taskOverrides:Object.fromEntries(Object.entries(policy.taskOverrides||{}).filter(([id])=>taskIds.includes(id)))}:policy;
    const selectionNote=randomSeed===null?'':`\n抽题记录 balanced-v2：种子 ${randomSeed}；代码池 ${swePool.length}，界面池 ${webPool.length}；创建时选题 ${taskIds.join(',')}（可含手动调整）。`;
    const data={configIds:[configId],taskIds,policy:frozenPolicy,notes:notes+selectionNote,deliveryMode:effectiveDelivery};
    const payload=JSON.stringify(data);if(pending.current?.payload!==payload)pending.current={payload,requestId:crypto.randomUUID()};
    try{const job=await act<PreparationJob>('/runs/prepare-async',{...data,requestId:pending.current.requestId});setJobId(job.id);}catch(error){setCreateError((error as Error).message);}
  };
  const job=state.preparationJobs?.find(j=>j.id===jobId)||(jobId?undefined:state.preparationJobs?.find(j=>j.status==='running'||j.status==='interrupted'));
  const preparing=job?.status==='running';
  const blockedTaskId=job?.failedTaskId||(job?.status==='failed'&&job.stage==='source'?job.taskIds[job.completedTasks||0]:null);
  const blockedTask=blockedTaskId?catalog.find(t=>t.id===blockedTaskId):null;
  useEffect(()=>{
    if(job?.status!=='completed'||!job.runId||!jobId||delivered.current===job.id)return;
    delivered.current=job.id;pending.current=null;onCreated(job.runId);
  },[job,jobId,onCreated]);
  return <>{initialRun&&<p className="score-notice" role="status">已带回 {initialRun.tasks.length} 道题和原评分方案，可在步骤 1–3 修改后创建新评测；原评测记录不变。</p>}<section className="editorial-hero"><div className="editorial-hero-copy"><h1 className="page-title">{pane==='tasks'?'让每次评测，都有证据。':pane==='config'?'选好这次的工作方式。':'核对评分，再创建工作区。'}</h1><p>{pane==='tasks'?'从真实任务出发，在可复现的条件下，验证模型与个人配置的交付能力。':pane==='config'?'选择已保存配置；模型、规则与 Skills 按该版本冻结。':'评分依据与运行条件会随评测保存，交付后仍可复查。'}</p></div><div className="editorial-hero-art" aria-hidden="true"><span>REAL<br/>TASKS<br/>REAL<br/>PROGRESS</span></div>
    <nav className="prepare-tabs" aria-label="评测准备步骤">{([['tasks','选题','从任务库选择合适的任务'],['config','配置','选择模型与运行参数'],['scoring','创建工作区','核对评分并准备环境']] as const).map(([id,label,hint],index)=><button type="button" aria-current={pane===id?'step':undefined} disabled={preparing||(id==='config'&&!taskIds.length)||(id==='scoring'&&(!taskIds.length||!config))} className={pane===id?'selected':index<['tasks','config','scoring'].indexOf(pane)?'is-complete':''} key={id} onClick={()=>setPane(id)}><i>{index<['tasks','config','scoring'].indexOf(pane)?<Check size={16}/>:index+1}</i><span><strong>{label}</strong><small>{hint}</small></span></button>)}</nav></section>
    <fieldset className="prepare-grid" disabled={preparing}>
      <div className="prepare-tasks" hidden={pane!=='tasks'}>{lastFailed&&<section className="preparation-resume"><div><strong>上次批次准备中断 · 已准备 {lastFailed.completedTasks||0}/{lastFailed.totalTasks||lastFailed.taskIds.length} 道题</strong><p>{lastFailed.taskIds.length} 道题的选择已保留在准备记录中；已下载的源码会校验复用。</p></div><button type="button" className="btn-secondary" onClick={()=>recover(lastFailed)}>继续这批题</button></section>}<section className="balanced-pick" aria-label="快速组卷"><div><strong>快速组卷</strong><p>代码与逻辑、界面与交互等量搭配。优先分散题型，默认排除大型项目。</p></div><div className="balanced-pick-controls"><label>本次题数<select aria-label="随机选题总数" value={Math.min(randomCount,Math.max(1,maxRandomCount))} onChange={e=>setRandomCount(Number(e.target.value))} disabled={!maxRandomCount}>{Array.from({length:maxRandomCount},(_,index)=><option key={index+1} value={index+1}>{(index+1)*2} 道</option>)}</select></label><button type="button" className="btn-primary" disabled={!maxRandomCount} onClick={randomize}>随机选题</button></div><details className="draw-explanation"><summary>如何抽题 · 可抽 {swePool.length+webPool.length} 道</summary><p>代码与逻辑 {swePool.length} 道：已有程序验收入口；界面与交互 {webPool.length} 道：短、中型网页，按工具、数据、游戏、三维等机制分散抽样。每类先随机取不同组，再补足；不重复，不是全库等概率抽签。每次最多10道，题库数量不受此限制。</p>{randomSeed!==null&&<p>抽题版本 balanced-v2 · 种子 {randomSeed}；记录随本次评测保存。</p>}</details>{randomNotice&&<p className="balanced-pick-notice" role="status">{randomNotice}</p>}</section><div className="task-board">
        <section className="task-library" aria-label="任务库"><header className="task-library-heading"><h2>任务库</h2><label className="task-search"><Search size={17}/><input aria-label="搜索评测题目" placeholder="搜索任务关键词…" value={query} onChange={e=>setQuery(e.target.value)}/></label></header>

          <div className="task-library-toolbar"><div className="category-navigation"><button type="button" className="category-scroll" aria-label="向左查看题型" onClick={()=>categoryRef.current?.scrollBy({left:-240,behavior:'smooth'})}>‹</button><div ref={categoryRef} className="editorial-category-tabs" role="group" aria-label="任务类型">{categoryOptions.map(([id,label])=><button type="button" key={id} className={category===id?'active':''} aria-pressed={category===id} onClick={()=>setCategory(id)}>{label}<span>（{sourceCandidates.filter(t=>inFamilyGroup(t,id)&&matchTask(t,paradigm,query,channel,difficulty)&&(showPending?!canStartTask(t,state.baselines):canStartTask(t,state.baselines))).length}）</span></button>)}</div><button type="button" className="category-scroll" aria-label="向右查看题型" onClick={()=>categoryRef.current?.scrollBy({left:240,behavior:'smooth'})}>›</button></div><label className="check-row batch-toggle"><input type="checkbox" checked={batch} onChange={e=>{setBatch(e.target.checked);setTasks(taskIds.slice(0,1));}}/>批量选题（最多 10 道）</label><details ref={filterRef} className="task-filter-details"><summary><Filter size={16}/>筛选</summary><div className="task-filter-bar"><Field label="评测类别"><select aria-label="评测类别" value={paradigm} onChange={e=>{setParadigm(e.target.value);if(!batch)setTasks([]);setShowPending(false);}}><option value="all">全部评测类别</option><option value="open-ended-project">从零构建</option><option value="repository">已有仓库任务</option><option value="deterministic-bugfix">仅 Bug 修复</option></select></Field><Field label="题目来源"><select value={sourceFilter} onChange={e=>setSourceFilter(e.target.value)}><option value="all">全部来源</option><option value="deepswe">DeepSWE 公开题</option><option value="webgen">WebGen-Bench 网页题</option><option value="local">本地与内置题目</option></select></Field><Field label="细分类别"><select aria-label="按细分类别筛选" value={family} onChange={e=>setFamily(e.target.value)}><option value="">全部细分类别</option>{Object.entries(familyLabels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></Field><Field label="项目语言"><select aria-label="按项目语言筛选" value={language} onChange={e=>setLanguage(e.target.value)}><option value="">全部语言</option>{languages.map(value=><option key={value} value={value}>{value}</option>)}</select></Field><TaskFilters tasks={facetTasks} channel={channel} difficulty={difficulty} onChannel={setChannel} onDifficulty={setDifficulty}/><div className="editorial-list-mode"><button type="button" className={!showPending?'active':''} onClick={()=>setShowPending(false)}>可选题目 · {matches.length-pendingTasks.length}</button><button type="button" className={showPending?'active':''} onClick={()=>setShowPending(true)}>待补全题面 · {pendingTasks.length}</button></div></div></details></div>
          <div className="prepare-task-list">{category==='core'&&<p className="core-curation-note">这组跨网页、业务数据、工程、长期项目和协作，优先展示不同能力路径；其余同类变体仍可在“全部题目”或对应类型找到。精选只影响浏览顺序，不改变评分。</p>}{tasks.map((t,index)=><label key={t.id} className={'editorial-task-card '+(taskIds.includes(t.id)?'selected':'')}><input className="sr-only" type={batch?'checkbox':'radio'} name="task" checked={taskIds.includes(t.id)} disabled={batch&&taskIds.length>=10&&!taskIds.includes(t.id)} onChange={e=>{setShowFullPrompt(false);setFocusedTaskId(e.target.checked?t.id:null);setTasks(batch?(e.target.checked?[...taskIds,t.id]:taskIds.filter(id=>id!==t.id)):[t.id]);}}/><span className="task-card-icon">{needsBaseline(t)?<Code2 size={25} strokeWidth={1.5}/>:<Lightbulb size={25} strokeWidth={1.5}/>}</span><span className="task-card-content"><strong>{t.title}</strong><span className="task-card-description">{t.publicSource?`${t.publicSource.language||'开源'}项目 · 固定源码起点${state.baselines.some(b=>b.id===t.baselineId)?'已缓存':'创建时按题准备'}`:t.inputPrompt?.trim().slice(0,100)||'查看完整需求与项目起点'}</span><span className="task-card-meta"><em>{taskKind(t)}</em>{t.id.startsWith('original-creative-')&&<em>{t.description}</em>}{t.difficulty&&t.difficulty!=='未标注'&&<em className="task-difficulty">{t.difficulty}</em>}{t.publicSource?.language&&<em>{t.publicSource.language}</em>}<span>{sourceName(t)}</span></span></span><span className="task-card-index">#{String(index+1).padStart(3,'0')}</span></label>)}</div>
          {!tasks.length&&<Empty>没有符合筛选的题目。</Empty>}
        </section>
        <aside className="task-preview" aria-label="任务详情"><header className="preview-heading"><h2>任务详情</h2>{previewTasks.length===1&&previewTasks[0].referenceUrl&&<a href={previewTasks[0].referenceUrl} target="_blank" rel="noopener noreferrer">查看题目来源 <ExternalLink size={15}/></a>}</header>{batch&&selected.length>1&&<div className="batch-picked"><strong>本次题单 · {selected.length} 道</strong><div>{selected.map(item=><span className="batch-picked-item" key={item.id}><button type="button" className={previewTasks[0]?.id===item.id?'active':''} title={item.title} onClick={()=>{setFocusedTaskId(item.id);setShowFullPrompt(false);}}>{item.title}</button><button type="button" aria-label={'移除 '+item.title} onClick={()=>{setTasks(taskIds.filter(id=>id!==item.id));if(focusedTaskId===item.id)setFocusedTaskId(null);}}>×</button></span>)}</div></div>}{previewTasks.length?previewTasks.map(t=><section key={t.id} className="preview-selected"><div className="preview-title"><h3>{t.title}</h3><small>{sourceName(t)}</small></div><div className="preview-tags"><span>{taskKind(t)}</span>{t.id.startsWith('original-creative-')&&<span>{t.description}</span>}{t.capabilityTags?.map(tag=><span key={tag}>{capabilityLabels[tag]||tag}</span>)}{t.difficulty&&t.difficulty!=='未标注'&&<span>{t.difficulty}</span>}{t.publicSource?.language&&<span>{t.publicSource.language}</span>}{t.hasFrontendUI&&<span>包含界面</span>}</div>{t.publicSource?<div className="preview-source"><h4>源代码仓库</h4><div className="preview-source-row"><Code2 size={24}/><div><a href={repositoryUrl(t)} target="_blank" rel="noopener noreferrer">{sourceName(t)} <ExternalLink size={13}/></a><small>固定源码版本 · {state.baselines.some(b=>b.id===t.baselineId)?'已缓存源码':'创建时按题下载'}</small></div><span className="source-verified"><ShieldCheck size={15}/> 来源有记录</span></div><details className="preview-environment"><summary>查看准备状态与文件位置</summary><TaskEnvironment task={t} baselines={state.baselines}/></details></div>:<TaskEnvironment task={t} baselines={state.baselines}/>}<div className="preview-requirements"><h4>任务要求</h4><div className={'preview-prompt '+(showFullPrompt?'expanded':'')}><PublicPrompt task={t}/>{!t.publicSource&&<ContractView task={t}/>}</div><button type="button" onClick={()=>setShowFullPrompt(!showFullPrompt)}>{showFullPrompt?'收起任务描述':'查看完整任务描述'} ↓</button></div></section>):<div className="preview-empty"><BookOpen size={34} strokeWidth={1.4}/><h3>选择一道真实任务</h3><p>在这里核对题面、源码起点与运行环境。</p></div>}
          <div className="preview-bottom"><div className="preview-facts"><div><BookOpen size={25}/><strong>{matches.filter(t=>canStartTask(t,state.baselines)).length} 道题</strong><span>当前可选</span></div><div><ShieldCheck size={25}/><strong>{state.runs.length} 次评测</strong><span>本机记录</span></div></div><button type="button" className="btn-primary preview-continue" disabled={!taskIds.length||selected.some(t=>!canStartTask(t,state.baselines))} onClick={()=>setPane('config')}>继续选择配置 <ArrowRight size={19}/></button><p>{batch?'批量创建待办队列，每题独立目录；仍需逐项在桌面手动执行。':'创建时只准备所选题目；相同源码校验后复用缓存。'}</p></div>
        </aside>
      </div><div className="delivery-row">{canStage?<Details title="可选实验：分步提供需求"><Field label="需求提供方式"><select value={deliveryMode} onChange={e=>setDeliveryMode(e.target.value)}><option value="single-delivery">完整需求 · 不限定对话轮数</option><option value="staged">按题目预设步骤分阶段（可选）</option></select></Field><p className="muted">{deliveryMode==='single-delivery'?'一次提供全部需求。由模型和你的配置决定实施过程，完成后回收评分。':'逐步提供题目预先编写的提示词；同一对话继续。每步可回收版本，最终仍按整题需求评分。区别在提供需求的时机，不是限制模型回复次数。'}</p></Details>:<p className="muted">提供完整需求 → 在 Codex 持续完成 → 回收产物并评分。不限对话次数，无需选择轮数。</p>}</div></div>
      <section className="prepare-session panel" aria-label="本次评测设置" hidden={pane==='tasks'}>
        <div className="prepare-session-heading"><h2 className="font-semibold">本次评测</h2><p className="muted prepare-selection" title={selected.map(t=>t.title).join('、')}>{selected.length?selected.map(t=>t.title).join('、'):'先选择一道题目'}</p></div>
        <div className="prepare-controls space-y-4">
          <div hidden={pane!=='config'} className="preparation-config-grid">
          <div className="config-select-row"><Field label="使用配置"><select value={configId} onChange={e=>setConfigId(e.target.value)}><option value="" disabled>选择已有配置</option>{state.configs.map(c=><option value={c.id} key={c.id}>{c.name} · v{c.revision}</option>)}</select></Field><button type="button" className="btn-secondary" disabled={!config} onClick={()=>setPreview(config||null)}>预览配置</button></div>
          {config&&<section className="prepare-config-summary"><div><strong>{config.name} · v{config.revision}</strong><p>{config.baseModel} · {config.reasoning||'模型默认'} · {config.serviceTier==='fast'?'Fast':config.serviceTier==='standard'?'标准速度':'沿用速度'}</p><p>{config.skills.length} 个 Skills · {config.skillMode==='explicit'?'每轮明确请求':'按任务需要使用'}</p></div><button type="button" className="btn-secondary" onClick={()=>onEditConfig(config.id)}>到配置库修改模型、规则或 Skills</button></section>}
          <p className="muted">这里仅选择已保存的配置版本。改动请到配置库保存新版本；创建后本次版本会冻结。</p>
          </div>
          {pane==='config'&&config&&<CodexApply config={config} act={act}/>}
          <div hidden={pane!=='scoring'}><ScoringSettings state={state} tasks={selected} policy={policy} onChange={setPolicy}/><Field label="本次备注"><input value={notes} onChange={e=>setNotes(e.target.value)}/></Field></div>
        </div>
      </section>
      <footer className="prepare-action" hidden={pane==='tasks'}>
        {createError&&<p role="alert" className="alert-error">{createError}</p>}
        {job&&<div className="preparation-status" role="status"><strong>{job.phase}</strong>{job.totalTasks!=null&&<><progress aria-label="题目源码准备进度" max={job.totalTasks+1} value={job.status==='completed'?job.totalTasks+1:job.completedTasks||0}/><p>{job.stage==='workspace'?'源码与环境已准备，正在复制独立工作区':`已准备 ${job.completedTasks||0}/${job.totalTasks} 道题${job.status==='running'?'；当前题目可能正在下载或配置环境':''}`}</p></>}{job.error&&<><p role="alert" className="alert-error">{blockedTask?`第 ${(job.completedTasks||0)+1} 道“${blockedTask.title}”准备失败：`:''}{job.error}</p><p className="muted">前面已完成的源码缓存会校验复用；本次尚未创建评测工作区，也没有生成分数。{!job.requestData&&'这份旧准备记录未保存原配置；重试前请重新选择当时使用的配置与评分方案。'}</p><div className="source-actions">{pane==='scoring'?<button type="button" className="btn-primary" onClick={()=>void create()}>重试这批题</button>:<span className="muted">先核对配置和评分方案，再重试。</span>}<button type="button" className="btn-secondary" onClick={()=>setPane('tasks')}>返回选题调整批次</button></div></>}{!job.error&&<p className="muted">只下载缺失的固定源码与必要环境，校验缓存后复制到每题独立目录。这个进度按题计数，不代表当前下载的字节百分比。</p>}{job.runId&&<button className="btn-secondary" onClick={()=>onCreated(job.runId!)}>进入已创建的评测</button>}{job.status==='interrupted'&&<p>重新选择题目后创建即可；已下载文件会校验复用。</p>}</div>}

        {pane==='scoring'&&<div className="space-y-2"><p className="score-notice">创建时会自动冻结本次配置版本。若希望新 Codex 对话也默认使用所选模型和档位，可在上一步显式点击“应用到 Codex”；这会备份并写入全局配置。每道题的项目配置仍会写入独立工作区，打开后请核对桌面实际设置。</p>
          {taskIds.length>1&&<p className="score-notice">将创建 {taskIds.length} 个独立工作区，列成待办队列。准备过程顺序处理源码，不自动运行；每题的项目配置已写入各自目录，可分别打开 Codex 对话。每题分别回收与评分；打开时仍要核对桌面实际模型和工作区。</p>}
          {policy.objectiveWeight>0&&selected.some(t=>!t.checks.length)&&<p className="score-notice">所选题目缺少脚本检查，可新建机器评分方案。</p>}
          {!validPercentPolicy(policy)&&<p role="alert" className="alert-error">人工内部占比须合计100%。</p>}
          {publicQualityMissing&&<p role="alert" className="alert-error">公开题本地连续分需要“可维护性”评分项；请换一套适用方案或添加该项。</p>}
        </div>}
        {invalid&&<p role="alert" className="alert-error">技能同名、不可用或超过30个，请调整选择。</p>}
        <div className="prepare-footer-row"><div className="selection-summary"><span>{taskIds.length?`${taskIds.length} 道题已选`:'尚未选择题目'}</span><small>{config?'配置 '+config.name+' v'+config.revision:'未选配置'} · {effectiveDelivery==='single-delivery'?'完整需求':'分步提供需求'}</small></div><div className="prepare-footer-buttons">
          {pane!=='tasks'&&<button type="button" className="btn-secondary" onClick={()=>setPane(pane==='scoring'?'config':'tasks')}>上一步</button>}
          {pane==='tasks'?<button type="button" className="btn-primary" disabled={!taskIds.length||selected.some(t=>!canStartTask(t,state.baselines))} onClick={()=>setPane('config')}>选择已保存配置 <ArrowRight size={16}/></button>:pane==='config'?<button type="button" className="btn-primary" disabled={!config||invalid} onClick={()=>setPane('scoring')}>确认评分方案 <ArrowRight size={16}/></button>:<button type="button" className="btn-primary" disabled={preparing||!taskIds.length||!config||invalid||publicQualityMissing||(policy.objectiveWeight>0&&selected.some(t=>!t.checks.length))||!validPercentPolicy(policy)} onClick={()=>void create()}>{preparing?'正在准备所选题目…':'创建评测工作区'}</button>}
        </div></div>
      </footer>
      <Dialog title={preview?preview.name+' · v'+preview.revision:'配置预览'} open={!!preview} onClose={()=>setPreview(null)}>{preview&&<div className="space-y-4"><dl className="config-facts"><dt>模型</dt><dd>{preview.baseModel}</dd><dt>推理档位</dt><dd>{preview.reasoning||'模型默认'}</dd><dt>执行速度</dt><dd>{preview.serviceTier==='fast'?'Fast':preview.serviceTier==='standard'?'标准':'沿用已有设置'}</dd><dt>交互</dt><dd>{preview.interactiveMode}</dd><dt>Skills</dt><dd>{preview.skills.map(id=>state.skills.find(s=>s.id===id)?.name||'不可用').join('、')||'未选择'}</dd></dl><h3>规则正文</h3><pre className="source">{preview.agentsPrompt||'未附加规则'}</pre><h3>原生设置与工具开关</h3><pre className="source">{JSON.stringify({settings:preview.nativeSettings||{},tools:preview.integrations||{}},null,2)}</pre>{preview.customConstraints.filter(c=>c.isActive).map(c=><p key={c.id}>{c.title}：{c.ruleDesc}</p>)}</div>}</Dialog>
    </fieldset></>;
}

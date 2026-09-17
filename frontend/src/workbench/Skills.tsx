import {useEffect,useRef,useState,useId} from 'react';
import {createPortal} from 'react-dom';
import type {Act,Config,Imported} from './types';
import {request} from './api';
import {Details,Field} from './ui';

type Candidate={id:string;name:string;description:string;sourcePath:string;scope:string;sourceLabel:string;sha256?:string;fileCount?:number;error:string|null;warnings:string[];duplicateName:boolean};
type Scan={scanId:string;sources:{path:string;label:string;exists:boolean}[];candidates:Candidate[]};

export function SkillLibrary({act,onImported,context='config'}:{act:Act;onImported:(skills:Imported[])=>void;context?:'config'|'trial'}){
  const [scope,setScope]=useState('global');const [path,setPath]=useState('');
  const [scan,setScan]=useState<Scan|null>(null);const [selected,setSelected]=useState<string[]>([]);
  const [query,setQuery]=useState('');const [loading,setLoading]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [expanded,setExpanded]=useState(false);const resultsId=useId();
  const generation=useRef(0);
  const discover=async()=>{
    const current=++generation.current;setLoading(true);setError('');setScan(null);setSelected([]);setNotice('');
    try{const result=await request<Scan>('/skills/scan',{scope,path});if(current===generation.current){setScan(result);setExpanded(true);}}
    catch(e){if(current===generation.current)setError((e as Error).message);}
    finally{if(current===generation.current)setLoading(false);}
  };
  useEffect(()=>()=>{generation.current++;},[]);
  const invalidate=()=>{generation.current++;setScan(null);setSelected([]);setLoading(false);setError('');setNotice('');};
  const visible=scan?.candidates.filter(s=>(s.name+' '+s.description+' '+s.sourcePath).toLowerCase().includes(query.toLowerCase()))||[];
  const chosen=scan?.candidates.filter(s=>selected.includes(s.id))||[];
  const conflict=new Set(chosen.map(s=>s.name.toLowerCase())).size!==chosen.length;
  const importBatch=async()=>{
    if(!scan)return;setError('');setNotice('');
    try{const result=await act<{imported:Imported[]}>('/skills/import-selected',{scanId:scan.scanId,candidateIds:selected});onImported(result.imported);setNotice(context==='trial'?`已加入本次评测：${result.imported.length} 个技能。`:`已导入 ${result.imported.length} 个技能并加入配置草稿，请保存配置。`);setSelected([]);}
    catch(e){setError((e as Error).message);}
  };
  return <section className={context==='trial'?'space-y-3':'panel p-5 space-y-4'}>{context!=='trial'?<h2 className="font-semibold">Skills 技能库</h2>:<h4 className="font-medium">从本地添加技能</h4>}<p className="muted">选择来源并勾选；悬停名称查看说明，点击详情查看路径。</p>
    <div className="grid sm:grid-cols-2 gap-3"><Field label="技能来源"><select value={scope} onChange={e=>{setScope(e.target.value);invalidate();}}><option value="global">本机用户级技能</option><option value="project">某个项目的技能</option><option value="custom">指定技能库 / 插件技能目录</option></select></Field>
      {scope!=='global'&&<Field label={scope==='project'?'项目根目录':'技能库目录'} hint={scope==='project'?'只读取这个项目的 .agents/skills 与兼容目录。':'选择一次根目录，列出其下技能；不会安装插件或外部工具。'}><input value={path} onChange={e=>{setPath(e.target.value);invalidate();}} placeholder="D:\我的项目"/></Field>}</div>
    <button type="button" className="btn-secondary" disabled={loading||(scope!=='global'&&!path.trim())} onClick={()=>void discover()}>{loading?'正在读取技能…':'读取技能列表'}</button>
    {error&&<p role="alert" className="alert-error">{error}</p>}{notice&&<p role="status" className="muted">{notice}</p>}
    {scan&&<section className="skill-results space-y-3"><div className="flex items-center justify-between gap-3"><h4 className="font-semibold">读取结果 · {scan.candidates.length} 个技能</h4><button type="button" className="btn-secondary" aria-expanded={expanded} aria-controls={resultsId} onClick={()=>setExpanded(!expanded)}>{expanded?'收起技能列表':'展开技能列表'}</button></div><p className="muted">已勾选 {selected.length} 个；收起不会清空选择或重新读取。</p><div id={resultsId} hidden={!expanded} className="space-y-3">{expanded&&<>
      <Field label="搜索技能"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="名称、用途或路径"/></Field>
      <div className="flex gap-3 flex-wrap items-center"><span className="muted">显示 {visible.length} / {scan.candidates.length} 个 · 已选 {selected.length} 个</span><button type="button" className="btn-ghost" onClick={()=>setSelected([...new Set([...selected,...visible.filter(s=>!s.error&&!s.duplicateName).map(s=>s.id)])].slice(0,30))}>选中筛选结果（跳过重名）</button><button type="button" className="btn-ghost" onClick={()=>setSelected([])}>清空选择</button></div>
      <div className="skill-options">{visible.map(s=><SkillChoice key={s.id} skill={s} checked={selected.includes(s.id)} disabled={!!s.error||(!selected.includes(s.id)&&selected.length>=30)} onChange={checked=>setSelected(current=>checked?[...current,s.id]:current.filter(id=>id!==s.id))}/>)}</div>
      {!visible.length&&<p className="muted">没有找到符合条件的技能；可切换来源或搜索词。</p>}
      {conflict&&<p role="alert" className="alert-error">所选技能存在同名，请保留一个来源。</p>}
      <button type="button" className="btn-primary" disabled={!selected.length||conflict} onClick={()=>void importBatch()}>{context==='trial'?'添加到本次评测':'导入并选中'} {selected.length} 个技能</button>
      <Details title="来源路径（仅核对读取位置）">{scan.sources.map(s=><p className="muted break-all" key={s.path}>{s.label} · {s.path} · {s.exists?'存在':'不存在'}</p>)}</Details></>}</div></section>}
  </section>;
}

export function ProjectConfigImport({act,onImported}:{act:Act;onImported:(config:Config)=>void}){
  const [path,setPath]=useState('');const [preview,setPreview]=useState<Config|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const generation=useRef(0);
  const inspect=async()=>{const n=++generation.current;setBusy(true);setError('');setPreview(null);try{const c=await request<Config>('/configs/import-preview',{scope:'project',path});if(n===generation.current)setPreview(c);}catch(e){if(n===generation.current)setError((e as Error).message);}finally{if(n===generation.current)setBusy(false);}};
  useEffect(()=>()=>{generation.current++;},[]);
  return <Details title="从其他项目导入规则"><Field label="配置来源项目目录"><input value={path} onChange={e=>{generation.current++;setBusy(false);setPath(e.target.value);setPreview(null);setError('');}}/></Field><button type="button" className="btn-secondary" disabled={!path.trim()||busy} onClick={()=>void inspect()}>{busy?'正在读取…':'读取项目配置'}</button>
    {error&&<p role="alert" className="alert-error">{error}</p>}
    {preview&&<><p className="muted">{preview.baseModel} · {preview.reasoning}；仅导入本层规则和设置。</p><pre className="source">{preview.agentsPrompt||'没有规则正文'}</pre>{preview.importSource?.warnings.map(w=><p className="muted" key={w}>{w}</p>)}<button type="button" className="btn-primary" onClick={()=>act<Config>('/configs/import-source',{scope:'project',path,expectedFiles:preview.importSource?.files}).then(onImported).catch(e=>setError(e.message))}>创建配置副本</button></>}
  </Details>;
}

type SkillInfo={id:string;name:string;description?:string;sourceLabel?:string;sourcePath?:string;sha256?:string;fileCount?:number;manifest?:Imported['manifest'];duplicateName?:boolean;error?:string|null;warnings?:string[]};
export function SkillChoice({skill:s,checked,onChange,disabled=false}:{skill:SkillInfo;checked:boolean;onChange:(checked:boolean)=>void;disabled?:boolean}){
  const [position,setPosition]=useState<{left:number;top:number}|null>(null);const [pinned,setPinned]=useState(false);const id=useId();
  const anchor=useRef<HTMLButtonElement>(null);const timer=useRef<ReturnType<typeof setTimeout>>();
  const show=()=>{clearTimeout(timer.current);const r=anchor.current?.getBoundingClientRect();if(r)setPosition({left:Math.max(16,Math.min(r.left,window.innerWidth-376)),top:Math.max(16,Math.min(r.bottom+8,window.innerHeight*.42))});};
  const leave=()=>{if(!pinned)timer.current=setTimeout(()=>setPosition(null),180);};
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  const close=()=>{clearTimeout(timer.current);anchor.current?.focus();setPosition(null);setPinned(false);};
  useEffect(()=>{if(!position)return;const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')close();};document.addEventListener('keydown',escape);return()=>document.removeEventListener('keydown',escape);},[position]);
  return <div className={'skill-option '+(checked?'skill-option-selected':'')} onMouseEnter={show} onMouseLeave={leave}>
    <label className="check-row"><input type="checkbox" aria-label={`选择技能 ${s.name} ${s.sourceLabel||''}`} checked={checked} disabled={disabled} onChange={e=>onChange(e.target.checked)}/><span className="break-words">{s.name}</span>{s.duplicateName&&<small className="muted">{s.sourceLabel}</small>}{s.error&&<small className="text-rose-600">不可导入</small>}</label>
    <button type="button" className="btn-ghost" ref={anchor} aria-label={`${s.name} 详情`} aria-expanded={!!position} aria-controls={position?id:undefined} onFocus={show} onBlur={leave} onClick={()=>{setPinned(true);show();}}>详情</button>
    {position&&createPortal(<aside id={id} className="skill-popover space-y-3" role="dialog" aria-label={s.name+' 技能详情'} style={position} onMouseEnter={()=>clearTimeout(timer.current)} onMouseLeave={leave}><div className="flex justify-between gap-3"><strong>{s.name}</strong><button type="button" className="btn-ghost" aria-label="关闭技能详情" onClick={close}>关闭</button></div><p className="text-sm whitespace-pre-wrap">{s.description||'未提供用途说明'}</p><p className="muted">{s.sourceLabel||'已导入技能'} · {s.sourcePath}</p><p className="muted">{s.fileCount??Object.keys(s.manifest?.files||{}).length} 文件 · {(s.sha256||s.manifest?.sha256)?.slice(0,12)}</p>{s.error&&<p>{s.error}</p>}{s.warnings?.map(w=><p className="muted" key={w}>{w}</p>)}<p className="muted">点击详情可固定阅读；Esc 关闭。</p></aside>,document.body)}
  </div>;
}

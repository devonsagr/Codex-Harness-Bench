import {useEffect,useRef,useState} from 'react';
import type {Act,Config,Imported} from './types';
import {request} from './api';
import {Details,Field,Panel} from './ui';

type Candidate={id:string;name:string;description:string;sourcePath:string;scope:string;sourceLabel:string;sha256?:string;fileCount?:number;error:string|null;warnings:string[];duplicateName:boolean};
type Scan={scanId:string;sources:{path:string;label:string;exists:boolean}[];candidates:Candidate[]};

export function SkillLibrary({act,onImported}:{act:Act;onImported:(skills:Imported[])=>void}){
  const [scope,setScope]=useState('global');const [path,setPath]=useState('');
  const [scan,setScan]=useState<Scan|null>(null);const [selected,setSelected]=useState<string[]>([]);
  const [query,setQuery]=useState('');const [loading,setLoading]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const generation=useRef(0);
  const discover=async()=>{
    const current=++generation.current;setLoading(true);setError('');setScan(null);setSelected([]);setNotice('');
    try{const result=await request<Scan>('/skills/scan',{scope,path});if(current===generation.current)setScan(result);}
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
    try{const result=await act<{imported:Imported[]}>('/skills/import-selected',{scanId:scan.scanId,candidateIds:selected});onImported(result.imported);setNotice(`已导入 ${result.imported.length} 个技能并加入配置草稿，请保存配置。`);setSelected([]);}
    catch(e){setError((e as Error).message);}
  };
  return <Panel title="Skills 技能库"><p className="muted">选择来源后批量勾选。保存配置后，所选技能会自动复制到每次评测工作区。</p>
    <div className="grid sm:grid-cols-2 gap-3"><Field label="技能来源"><select value={scope} onChange={e=>{setScope(e.target.value);invalidate();}}><option value="global">本机用户级技能</option><option value="project">某个项目的技能</option><option value="custom">指定技能库 / 插件技能目录</option></select></Field>
      {scope!=='global'&&<Field label={scope==='project'?'项目根目录':'技能库目录'} hint={scope==='project'?'只读取这个项目的 .agents/skills 与兼容目录。':'选择一次根目录，列出其下技能；不会安装插件或外部工具。'}><input value={path} onChange={e=>{setPath(e.target.value);invalidate();}} placeholder="D:\我的项目"/></Field>}</div>
    <button type="button" className="btn-secondary" disabled={loading||(scope!=='global'&&!path.trim())} onClick={()=>void discover()}>{loading?'正在读取技能…':'读取技能列表'}</button>
    {error&&<p role="alert" className="alert-error">{error}</p>}{notice&&<p role="status" className="muted">{notice}</p>}
    {scan&&<><Details title="本次读取的目录">{scan.sources.map(s=><p className="muted break-all" key={s.path}>{s.label} · {s.path} · {s.exists?'存在':'不存在'}</p>)}</Details>
      <Field label="搜索技能"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="名称、用途或路径"/></Field>
      <div className="flex gap-3 flex-wrap items-center"><span className="muted">显示 {visible.length} / {scan.candidates.length} 个 · 已选 {selected.length} 个</span><button type="button" className="btn-ghost" onClick={()=>setSelected([...new Set([...selected,...visible.filter(s=>!s.error&&!s.duplicateName).map(s=>s.id)])].slice(0,30))}>选中筛选结果（跳过重名）</button><button type="button" className="btn-ghost" onClick={()=>setSelected([])}>清空选择</button></div>
      <div className="max-h-96 overflow-y-auto space-y-2">{visible.map(s=><label key={s.id} className={'list-card '+(selected.includes(s.id)?'selected':'')}><div className="flex gap-3 items-start"><input type="checkbox" aria-label={`选择技能 ${s.name} ${s.sourceLabel}`} disabled={!!s.error||(!selected.includes(s.id)&&selected.length>=30)} checked={selected.includes(s.id)} onChange={e=>setSelected(e.target.checked?[...selected,s.id]:selected.filter(id=>id!==s.id))}/><div className="min-w-0"><strong>{s.name}</strong><p className="text-sm whitespace-pre-wrap">{s.description}</p><small className="block muted break-all">{s.sourceLabel} · {s.sourcePath}</small><small className="muted">{s.fileCount??'—'} 文件 · {s.sha256?.slice(0,12)}{s.duplicateName?' · 同名多来源，请选其中一个':''}</small>{s.error&&<p className="alert-error">{s.error}</p>}{s.warnings.map(w=><p className="muted" key={w}>{w}</p>)}</div></div></label>)}</div>
      {!visible.length&&<p className="muted">没有找到符合条件的技能；可切换来源或搜索词。</p>}
      {conflict&&<p role="alert" className="alert-error">所选技能存在同名，请保留一个来源。</p>}
      <button type="button" className="btn-primary" disabled={!selected.length||conflict} onClick={()=>void importBatch()}>导入并选中 {selected.length} 个技能</button>
    </>}
  </Panel>;
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

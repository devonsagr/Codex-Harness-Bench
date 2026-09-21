import {useCallback,useEffect,useState} from 'react';
import {RefreshCw, Radio, ChevronRight} from 'lucide-react';
import {ArenaHeader, arenaPages, type ArenaTab} from './components/ArenaHeader';
import {request,submitAndRefresh} from './workbench/api';
import type {State,Act} from './workbench/types';
import {Prepare,RunDetail} from './workbench/Runner';
import {ConfigManager,TaskManager} from './workbench/Editors';
import {History,Comparison,Guide} from './workbench/Records';

export function App(){
  const [tab,setTab]=useState<ArenaTab>('workbench');
  const [theme,setTheme]=useState<'light'|'dark'>(()=>localStorage.getItem('chb_theme')==='dark'?'dark':'light');
  const [state,setState]=useState<State|null>(null);
  const [runId,setRunId]=useState<string|null>(null);
  const [selectedTaskId,setSelectedTaskId]=useState<string|null>(null);
  const [selectedConfigId,setSelectedConfigId]=useState<string|null>(null);
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
  const [connectionError,setConnectionError]=useState('');
  const refresh=useCallback(async()=>{try{const s=await request<State>('/state');setState(s);setConnectionError('');}catch(e){setConnectionError((e as Error).message);throw e;}},[]);
  useEffect(()=>{document.documentElement.classList.toggle('dark',theme==='dark');localStorage.setItem('chb_theme',theme);},[theme]);
  useEffect(()=>{refresh().catch(()=>{});},[refresh]);
  const activeJob=state?.runs.some(r=>r.trials.some(t=>['prepared','working','waiting_confirmation','checking','judging'].includes(t.state)));
  useEffect(()=>{if(!activeJob)return;let live=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const s=await request<State>('/state');if(live){setState(s);setConnectionError('');}}catch(e){if(live)setConnectionError((e as Error).message);}finally{if(live)timer=setTimeout(poll,1800);}};
    timer=setTimeout(poll,1800);return()=>{live=false;clearTimeout(timer);};},[activeJob]);
  const act:Act=async<T,>(path:string,data?:unknown)=>{setBusy(true);setError('');setNotice('');try{const {result,refreshed}=await submitAndRefresh<T>(path,data??{},refresh);setNotice(!refreshed?'操作已成功提交，但记录刷新失败。请恢复连接后刷新记录，无需重复提交。':path.endsWith('/open')?'已请求打开 Codex，请在桌面核对目录与提示词。':'已保存。');return result;}catch(e){setError((e as Error).message);throw e;}finally{setBusy(false);}};
  const go=(id:string)=>{setRunId(id);setTab('workbench');};
  const run=state?.runs.find(r=>r.id===runId)||state?.archivedRuns.find(r=>r.id===runId);
  return <div className="app-shell"><a className="skip-link" href="#workspace-content">跳到主要内容</a><ArenaHeader activeTab={tab} onTabChange={setTab} theme={theme} onToggleTheme={()=>setTheme(theme==='light'?'dark':'light')}/>
    <main id="workspace-content" className="arena-main" tabIndex={-1}>
      <div className="workspace-topbar"><div className="breadcrumb"><span>工作空间</span><ChevronRight size={14}/><strong>{arenaPages[tab].label}</strong></div><div className="workspace-tools"><span className={'connection-indicator '+(connectionError?'offline':'')}><Radio size={14}/>{connectionError?'连接中断':'本机服务'}</span><button className="icon-button" title="刷新记录" aria-label="刷新记录" onClick={()=>refresh().then(()=>{setError('');setNotice('');}).catch(()=>{})}><RefreshCw size={16}/></button></div></div>
      <div className="workspace-body">
      {connectionError&&<div role="alert" className="alert-error">{connectionError}<button className="ml-4 underline" onClick={()=>window.location.reload()}>重新加载页面</button></div>}
      {error&&<div role="alert" className="alert-error">{error}<button className="ml-4 underline" onClick={()=>setError('')}>关闭</button></div>}
      {notice&&!error&&<p role="status" className="text-xs text-slate-500">{notice}</p>}
      {!state?<div className="panel p-8">{connectionError?'暂时无法连接本地后端，请确认启动命令和端口。':'正在读取本地配置与评测记录…'}</div>:<fieldset disabled={busy} className={"page-content page-"+tab}>
        {tab==='workbench'&&(run?<RunDetail key={run.id} run={run} state={state} act={act} onBack={()=>setRunId(null)} onError={setError} archived={state.archivedRuns.some(r=>r.id===run.id)}/>:<Prepare state={state} act={act} onCreated={go} selectedTaskId={selectedTaskId} selectedConfigId={selectedConfigId}/>)}
        {tab==='configs'&&<ConfigManager state={state} act={act} onUse={id=>{setSelectedConfigId(id);setRunId(null);setTab('workbench');}}/>}
        {tab==='tasks'&&<TaskManager state={state} act={act} onUse={id=>{setSelectedTaskId(id);setRunId(null);setTab('workbench');}}/>}
        {tab==='history'&&<History state={state} act={act} onOpen={go} onError={setError}/>}
        {tab==='leaderboard'&&<Comparison state={state} onOpen={go}/>}
        {tab==='spec'&&<Guide state={state}/>}
      </fieldset>}
      <footer className="app-footer"><span>Codex 桌面 · 个人 Harness 评测</span><span>以证据判断每一次改动</span></footer></div>
    </main></div>;
}

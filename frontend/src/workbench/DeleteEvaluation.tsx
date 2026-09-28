import {useState} from 'react';
import type {Act} from './types';
import {request} from './api';
import {Dialog,Field} from './ui';

type LinkedSession={id:string;title:string;projectId:string|null};
type StorageStatus={workspaces:{runId:string;revision:number;workspacePath:string;codexSessions:LinkedSession[];codexSessionError?:string|null;workspaceDeletion?:{status:string}|null}[]};
type Step='workspace'|'record';

export function DeleteEvaluation({runId,revision:initialRevision,workspaceDeletion,canDelete,act,onDeleted}:{runId:string;revision:number;workspaceDeletion?:{status:string}|null;canDelete:boolean;act:Act;onDeleted:()=>void}){
  const [open,setOpen]=useState<Step|null>(null),[stopped,setStopped]=useState(false),[text,setText]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false);
  const [linkedSessions,setLinkedSessions]=useState<LinkedSession[]>([]),[sessionError,setSessionError]=useState<string|null>(null);
  const [workspaces,setWorkspaces]=useState<string[]>([]),[stage,setStage]=useState(workspaceDeletion?.status||''),[revision,setRevision]=useState(initialRevision);
  const currentStage=workspaceDeletion?.status||stage;
  const workspaceDone=currentStage==='deleted';
  const phrase=(open==='workspace'?'删除工作区 ':'永久删除评测 ')+runId;
  const load=async()=>{
    setLoading(true);setSessionError(null);
    try{
      const inventory=await request<StorageStatus>('/storage/status',{});
      const rows=inventory.workspaces.filter(row=>row.runId===runId);
      if(!rows.length)throw new Error('这次评测已不存在；请刷新历史列表。');
      setRevision(rows[0].revision);setStage(rows[0].workspaceDeletion?.status||'');
      setWorkspaces(rows.map(row=>row.workspacePath));
      setLinkedSessions(rows.flatMap(row=>row.codexSessions).filter((session,index,all)=>all.findIndex(item=>item.id===session.id)===index));
      setSessionError(rows.find(row=>row.codexSessionError)?.codexSessionError||null);
    }catch(e){setSessionError((e as Error).message);}
    finally{setLoading(false);}
  };
  const show=(step:Step)=>{setOpen(step);setText('');setStopped(false);setError('');void load();};
  const apply=async()=>{
    if(!open)return;
    setBusy(true);setError('');
    try{
      await act(open==='workspace'?'/storage/delete-workspaces':'/storage/delete-run',{
        runId,revision,confirmation:text,
        ...(open==='workspace'?{desktopStopped:stopped,sessionIds:linkedSessions.map(session=>session.id)}:{}),
      },{localError:true,silentSuccess:true});
      if(open==='workspace'){setStage('deleted');await load();}
      setOpen(null);onDeleted();
    }catch(e){setError((e as Error).message);await load();}
    finally{setBusy(false);}
  };
  return <>
    <div className="evaluation-delete-actions">
      {workspaceDone?<span className="muted">工作区文件已删除</span>:<button className="btn-danger" disabled={!canDelete} onClick={()=>show('workspace')}>{currentStage==='deleting'||currentStage==='recheck'?'继续删除工作区文件':'删除工作区文件'}</button>}
      <button className="btn-danger" disabled={!canDelete||!workspaceDone} title={workspaceDone?'删除剩余评测记录与证据':'先删除工作区文件'} onClick={()=>show('record')}>删除整次评测</button>
      {!canDelete&&<small className="muted">检查或裁判仍在运行，请先停止。</small>}
    </div>
    <Dialog title={open==='workspace'?'删除工作区文件':'删除整次评测'} open={open!==null} onClose={()=>setOpen(null)}><div className="evaluation-delete-copy">
      {open==='workspace'?<>
        <p>删除这次评测的开发工作区，以及精确关联的 Codex 对话。<strong>评测记录、快照和评分继续保留。</strong></p>
        {loading?<p role="status">正在核对删除范围…</p>:<>
          {sessionError&&<p role="alert" className="alert-error">{sessionError} 请刷新后重试。</p>}
          <p>{workspaces.length} 个工作区 · {linkedSessions.length} 条关联对话</p>
        </>}
        <p className="muted">Codex 保存的项目文件夹是独立项目记录，删除对话后可能仍显示。</p>
        <Field label={'输入“'+phrase+'”确认'}><input value={text} onChange={event=>setText(event.target.value)}/></Field>
        <label className="check-row"><input type="checkbox" checked={stopped} onChange={event=>setStopped(event.target.checked)}/>关联的 Codex 对话已停止写入</label>
      </>:open==='record'?<>
        <p><strong>工作区文件已删除。</strong>这一步会永久删除剩余的快照、评分、日志和整次评测记录。可以晚些再操作。</p>
        {loading&&<p role="status">正在核对记录状态…</p>}
        {sessionError&&<p role="alert" className="alert-error">{sessionError} 请刷新后重试。</p>}
        <Field label={'输入“'+phrase+'”确认'}><input value={text} onChange={event=>setText(event.target.value)}/></Field>
      </>:null}
      {error&&<p className="alert-error" role="alert">{error}</p>}
      <button className="btn-danger" disabled={busy||loading||!!sessionError||text!==phrase||(open==='workspace'&&!stopped)||(open==='record'&&!workspaceDone)} onClick={()=>void apply()}>{busy?'正在删除…':open==='workspace'?'确认删除工作区文件':'确认永久删除整次评测'}</button>
    </div></Dialog>
  </>;
}

import {useState} from 'react';
import type {Act} from './types';
import {request} from './api';
import {Dialog,Field} from './ui';

type LinkedSession={id:string;title:string;projectId:string|null};
type StorageStatus={workspaces:{runId:string;codexSessions:LinkedSession[];codexSessionError?:string|null}[]};

export function DeleteEvaluation({runId,revision,canDelete,deletionPending=false,act,onDeleted}:{runId:string;revision:number;canDelete:boolean;deletionPending?:boolean;act:Act;onDeleted:()=>void}){
  const [open,setOpen]=useState(false),[stopped,setStopped]=useState(false),[text,setText]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[deleteSessions,setDeleteSessions]=useState(false);
  const [linkedSessions,setLinkedSessions]=useState<LinkedSession[]>([]),[sessionError,setSessionError]=useState<string|null>(null),[loadingSessions,setLoadingSessions]=useState(false);
  const phrase='永久删除评测 '+runId;
  const show=async()=>{
    setOpen(true);setText('');setStopped(false);setError('');setDeleteSessions(false);
    setLinkedSessions([]);setSessionError(null);setLoadingSessions(true);
    try{
      const status=await request<StorageStatus>('/storage/status');
      const rows=status.workspaces.filter(row=>row.runId===runId);
      const problem=rows.find(row=>row.codexSessionError)?.codexSessionError;
      setSessionError(problem||null);
      setLinkedSessions(rows.flatMap(row=>row.codexSessions).filter((session,index,all)=>all.findIndex(item=>item.id===session.id)===index));
    }catch(e){setSessionError((e as Error).message);}
    finally{setLoadingSessions(false);}
  };
  return <>
    <button className="btn-danger" disabled={!canDelete} onClick={()=>void show()}>{deletionPending?'继续删除整次评测':'删除整次评测与文件'}</button>
    {!canDelete&&<small className="muted">后台检查或裁判仍在运行；停止后刷新再删除。</small>}
    <Dialog title="永久删除整次评测" open={open} onClose={()=>setOpen(false)}>
      <p>将删除这次评测的所有试次：工作区（包括待删除区）、回收快照、AI 提示词与日志、评分和修正、人工审查副本与评价、原生用量副本、数据库历史版本，以及能由回执定位的裁判临时残留。此操作不可恢复。</p>
      <p>共享源码缓存、配置库和配置备份继续保留。手动导出的 ZIP 不受影响。</p>
      <p className="break-all">记录：{runId}</p>
      {loadingSessions?<p role="status">正在核对本次评测关联的 Codex 对话…</p>:<>
        {sessionError&&<p role="alert" className="alert-error">{sessionError} 当前无法保证侧栏对话清单完整；如需一并删除，请先刷新核对。</p>}
        {linkedSessions.length>0?<><label className="check-row"><input type="checkbox" disabled={!!sessionError} checked={deleteSessions} onChange={e=>setDeleteSessions(e.target.checked)}/>同时永久删除这次评测工作区关联的 {linkedSessions.length} 个 Codex 侧栏对话</label><ul>{linkedSessions.map(session=><li key={session.id} className="break-all">{session.title||'未命名对话'} · {session.id}</li>)}</ul></>:!sessionError&&<p className="muted">本机索引中尚未找到这些工作区的 Codex 对话；如曾在别的工作区打开，请在 Codex 中另行核对。</p>}
      </>}
      <p className="muted">Codex 侧栏项目文件夹与对话分别管理。删除对话后，如项目仍在侧栏，可在其项目菜单选择“移除”；本工具不会直接改写 Codex 项目索引。</p>
      <Field label={'输入“'+phrase+'”确认'}><input value={text} onChange={e=>setText(e.target.value)}/></Field>
      <label className="check-row"><input type="checkbox" checked={stopped} onChange={e=>setStopped(e.target.checked)}/>我已确认这次评测的所有 Codex 对话停止写入工作区</label>
      <p role="status" className="muted">{text!==phrase?'还需完整输入上方确认文字。':!stopped?'确认文字已匹配；还需勾选“Codex 对话停止写入”，按钮才会启用。':'两项确认已完成，可以永久删除。'}</p>
      {error&&<p className="alert-error" role="alert">{error} 若删除中断，刷新后点击“继续删除整次评测”。</p>}
      <button className="btn-danger" disabled={busy||loadingSessions||!stopped||text!==phrase} onClick={async()=>{setBusy(true);try{await act('/storage/delete-run',{runId,revision,desktopStopped:stopped,confirmation:text,deleteCodexSessions:deleteSessions,sessionIds:deleteSessions?linkedSessions.map(s=>s.id):[]});setOpen(false);onDeleted();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>{deletionPending?'继续永久删除':'永久删除这次评测'}</button>
    </Dialog>
  </>;
}

import {useState} from 'react';
import type {Act} from './types';
import {Dialog,Field} from './ui';
export function DeleteEvaluation({runId,revision,canDelete,act,onDeleted}:{runId:string;revision:number;canDelete:boolean;act:Act;onDeleted:()=>void}){
  const [open,setOpen]=useState(false),[stopped,setStopped]=useState(false),[text,setText]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const phrase='永久删除评测 '+runId;
  return <><button className="btn-danger" disabled={!canDelete} onClick={()=>{setOpen(true);setText('');setStopped(false);setError('');}}>删除整次评测与文件</button><Dialog title="永久删除整次评测" open={open} onClose={()=>setOpen(false)}><p>将删除这次评测的所有试次：工作区（包括待删除区）、回收快照、AI 提示词与日志、评分和修正、人工审查副本与评价、原生用量副本、数据库历史版本，以及能由回执定位的裁判临时残留。此操作不可恢复。</p><p>共享源码缓存、配置库和配置备份继续保留。Codex 原应用中的对话与日志、你手动导出的 ZIP 不在本工具管理范围。</p><p className="break-all">记录：{runId}</p><label className="check-row"><input type="checkbox" checked={stopped} onChange={e=>setStopped(e.target.checked)}/>这次评测的所有 Codex 对话已停止写入</label><Field label={'输入“'+phrase+'”确认'}><input value={text} onChange={e=>setText(e.target.value)}/></Field>{error&&<p className="alert-error">{error} 若删除中断，请关闭并刷新后重试。</p>}<button className="btn-danger" disabled={busy||!stopped||text!==phrase} onClick={async()=>{setBusy(true);try{await act('/storage/delete-run',{runId,revision,desktopStopped:stopped,confirmation:text});setOpen(false);onDeleted();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>永久删除这次评测</button></Dialog></>;
}

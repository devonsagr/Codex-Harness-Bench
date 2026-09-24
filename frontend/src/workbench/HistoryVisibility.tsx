import {useState} from 'react';
import type {Act,Run} from './types';
import {Dialog,Field} from './ui';

export function HistoryVisibility({run,act}:{run:Run;act:Act}){
  const [open,setOpen]=useState(false);
  const [confirmation,setConfirmation]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  if(run.historyHidden)return <button type="button" className="btn-secondary" onClick={()=>void act(`/runs/${run.id}/history-visibility`,{revision:run.revision,hidden:false})}>恢复到历史列表</button>;
  const phrase='移出历史 '+run.id;
  return <><button type="button" className="btn-secondary" onClick={()=>{setOpen(true);setConfirmation('');setError('');}}>移出历史列表</button><Dialog title="移出历史列表" open={open} onClose={()=>setOpen(false)}><p>这会把本次评测从活动和归档列表移到“已移出”页，并停止计入配置成绩。工作区、回收快照、评分与必要的内部索引都保留，可在“已移出”页恢复或再彻底删除。</p><p className="break-all">记录：{run.id}</p><Field label={'输入“'+phrase+'”确认'}><input value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></Field>{error&&<p className="alert-error" role="alert">{error}</p>}<button type="button" className="btn-danger" disabled={busy||confirmation!==phrase} onClick={async()=>{setBusy(true);try{await act(`/runs/${run.id}/history-visibility`,{revision:run.revision,hidden:true,confirmation});setOpen(false);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>移出历史列表</button></Dialog></>;
}

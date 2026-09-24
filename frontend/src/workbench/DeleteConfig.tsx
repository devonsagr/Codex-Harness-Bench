import {useState} from 'react';
import type {Act,Config} from './types';
import {Dialog,Field} from './ui';

export function DeleteConfig({config,act,onDeleted}:{config:Config;act:Act;onDeleted?:()=>void}){
  const [open,setOpen]=useState(false),[confirmation,setConfirmation]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const phrase='永久删除配置 '+config.name;
  return <><button type="button" className="btn-danger" disabled={config.id.startsWith('initial-')} onClick={()=>{setConfirmation('');setError('');setOpen(true);}}>永久删除配置</button>
    <Dialog title="永久删除已归档配置" open={open} onClose={()=>setOpen(false)}><p>删除配置库中的“{config.name}”及其配置版本记录，并从配置成绩中移除。已经创建的评测保留当时冻结的配置副本、产物与评分；已应用的 Codex 设置也不会自动撤销。需要删除评测请到“评测历史”。此操作不可恢复。</p><Field label={'输入“'+phrase+'”确认'}><input value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></Field>{error&&<p role="alert" className="alert-error">{error}</p>}<button type="button" className="btn-danger" disabled={busy||confirmation!==phrase} onClick={async()=>{setBusy(true);try{await act(`/configs/${config.id}/delete`,{revision:config.revision});setOpen(false);onDeleted?.();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>永久删除</button></Dialog></>;
}

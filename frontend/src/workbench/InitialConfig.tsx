import {useState} from 'react';
import type {Act,State} from './types';
import {Dialog,Field} from './ui';
export function InitialConfig({state,act}:{state:State;act:Act}){
  const [open,setOpen]=useState(false),[confirmation,setConfirmation]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const saved=state.initialConfig;
  return <section className="initial-config"><strong>{saved?.status==='saved'?'最初配置已保护':'最初配置保护'}</strong><p className="muted">{saved?.status==='saved'?'规则与 config.toml 的原文件单独备份，修改其他预设不会覆盖。':saved?.note||'读取中…'}</p>{saved?.status==='saved'&&<button className="btn-secondary" onClick={()=>setOpen(true)}>查看与恢复原配置</button>}<Dialog title="恢复最初配置" open={open} onClose={()=>setOpen(false)}><p>备份时间：{saved?.at&&new Date(saved.at).toLocaleString('zh-CN')}</p><p className="break-all">{saved?.path}</p><p>{saved?.note}</p><p>恢复会替换 config.toml、AGENTS.md、AGENTS.override.md；备份时不存在的文件会移除。当前文件会另存一份撤销备份。插件安装、技能文件和账号登录不会被恢复或切换。</p><Field label="输入“恢复最初配置”确认"><input value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></Field>{error&&<p className="alert-error">{error}</p>}<button className="btn-primary" disabled={busy||confirmation!=='恢复最初配置'} onClick={async()=>{setBusy(true);try{await act('/codex/restore-initial',{confirmation});setOpen(false);setConfirmation('');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>恢复原文件（先备份当前文件）</button></Dialog></section>;
}

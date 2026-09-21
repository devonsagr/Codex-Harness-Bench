import {useEffect,useState} from 'react';
import {request} from './api';
type Progress={execution:{jobId?:string;model?:string;reasoning?:string;status?:string;logDirectory?:string};commands:{id:string;status:string;command:string;output:string;exitCode:number|null}[];truncated:boolean;error?:string};
export function JudgeProgress({runId,trialId,busy}:{runId:string;trialId:string;busy:boolean}){
  const [open,setOpen]=useState(false);const [data,setData]=useState<Progress|null>(null);const [error,setError]=useState('');
  useEffect(()=>{if(!open)return;let live=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const value=await request<Progress>(`/runs/${runId}/trials/${trialId}/judge-progress`,{});if(live){setData(value);setError('');}}catch(e){if(live)setError((e as Error).message);}finally{if(live&&busy)timer=setTimeout(poll,1500);}};
    void poll();return()=>{live=false;clearTimeout(timer);};
  },[open,busy,runId,trialId]);
  return <details className="panel-subtle p-3" open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>评分过程{busy?' · 实时更新':''}</summary><div className="space-y-3 mt-3">
    <p className="muted">实际工具执行记录；不是模型内部思考。展开时自动刷新，输出可能在命令结束后才出现。</p>
    {error&&<p role="alert" className="alert-error">{error}</p>}
    {data&&<><p>{[data.execution.model,data.execution.reasoning,({preparing:'准备环境',running:'执行取证',completed:'报告已保存',failed:'执行失败',cancelled:'已取消',interrupted:'服务中断'} as Record<string,string>)[data.execution.status||'']||'历史记录'].filter(Boolean).join(' · ')}</p>
      {data.execution.logDirectory&&<p className="muted break-all">本机日志：{data.execution.logDirectory}</p>}
      {data.commands.map(c=><details key={c.id}><summary>{c.status==='running'?'执行中':`已结束 · 退出码 ${c.exitCode??'未知'}`} · {c.command.slice(0,100)}</summary><pre className="source">{c.command}</pre><pre className="source">{c.output||'尚无输出'}</pre></details>)}
      {!data.commands.length&&<p className="muted">尚无命令记录；环境准备或模型响应阶段可能没有工具事件。</p>}
      {data.error&&<p className="alert-error">{data.error}</p>}{data.truncated&&<p className="muted">仅展示最近30条及末尾输出；完整日志保存在上述本机目录。</p>}</>}
  </div></details>;
}

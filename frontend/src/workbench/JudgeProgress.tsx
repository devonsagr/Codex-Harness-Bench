import {useEffect,useState} from 'react';
import {request} from './api';
type Progress={execution:{jobId?:string;model?:string;reasoning?:string;serviceTier?:string;status?:string;logDirectory?:string;elapsedSeconds?:number;timeoutSeconds?:number;lastActivitySecondsAgo?:number};commands:{id:string;status:string;command:string;output:string;exitCode:number|null}[];truncated:boolean;instruction?:string;instructionTruncated?:boolean;messages?:string[];runtime?:{workspace?:string;temporaryHome?:string;cleanup?:string};error?:string};
export function JudgeProgress({runId,trialId,busy}:{runId:string;trialId:string;busy:boolean}){
  const [open,setOpen]=useState(false);const [data,setData]=useState<Progress|null>(null);const [error,setError]=useState('');
  useEffect(()=>{if(!open)return;let live=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const value=await request<Progress>(`/runs/${runId}/trials/${trialId}/judge-progress`,{});if(live){setData(value);setError('');}}catch(e){if(live)setError((e as Error).message);}finally{if(live&&busy)timer=setTimeout(poll,1500);}};
    void poll();return()=>{live=false;clearTimeout(timer);};
  },[open,busy,runId,trialId]);
  return <details className="panel-subtle p-3" open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>评分过程{busy?' · 实时更新':''}</summary><div className="space-y-3 mt-3">
    <p className="muted">实际工具执行记录；不是模型内部思考。展开时自动刷新，输出可能在命令结束后才出现。</p>
    {error&&<p role="alert" className="alert-error">{error}</p>}
    {data&&<><p>{[data.execution.model,data.execution.reasoning,data.execution.serviceTier==='fast'?'请求 Fast':null,({preparing:'准备环境',running:'执行取证',completed:'报告已保存',failed:'执行失败',cancelled:'已取消',interrupted:'服务中断',budget_exhausted:'预算用完 · 审查未完成'} as Record<string,string>)[data.execution.status||'']||'历史记录'].filter(Boolean).join(' · ')}</p>
      {data.execution.logDirectory&&<p className="muted break-all">本机日志：{data.execution.logDirectory}</p>}
      {data.execution.elapsedSeconds!=null&&<p>已用 {Math.floor(data.execution.elapsedSeconds/60)} 分钟 / 预算 {data.execution.timeoutSeconds?data.execution.timeoutSeconds/60+' 分钟':'旧记录未记载'}{busy&&data.execution.lastActivitySecondsAgo!=null?` · 最近日志 ${data.execution.lastActivitySecondsAgo} 秒前更新`:''}</p>}
      {data.instruction&&<details><summary>实际发送给裁判的提示词与冻结材料</summary><pre className="source">{data.instruction}</pre>{data.instructionTruncated&&<p>显示前 20 万字符；完整内容在日志目录 task/instruction.md。</p>}</details>}
      {!!data.messages?.length&&<details><summary>裁判公开说明 · {data.messages.length} 条</summary>{data.messages.map((m,i)=><pre className="source" key={i}>{m}</pre>)}</details>}
      {data.runtime?.workspace&&<details><summary>CLI 工作文件位置与清理范围</summary><p className="break-all">临时工作副本：{data.runtime.workspace}</p><p className="break-all">临时配置目录：{data.runtime.temporaryHome}</p><p>正常结束、停止或超时均自动清理临时目录。日志、原始报告与取证附件保留在本次 reviews 目录；删除评测历史时一并清理。用户原 Codex 会话由 Codex 管理。</p></details>}
      {!!data.commands.length&&<div className="judge-command-list" aria-label="裁判命令记录">{data.commands.map((c,i)=><details key={c.id}><summary>命令 {i+1} · {c.status==='running'?'执行中':`已结束 · 退出码 ${c.exitCode??'未知'}`}</summary><pre className="source">{c.command}</pre><pre className="source">{c.output||'尚无输出'}</pre></details>)}</div>}
      {!data.commands.length&&<p className="muted">尚无命令记录；环境准备或模型响应阶段可能没有工具事件。</p>}
      {data.error&&<p className="alert-error">{data.error}</p>}{data.truncated&&<p className="muted">仅展示最近30条及末尾输出；完整日志保存在上述本机目录。</p>}</>}
  </div></details>;
}

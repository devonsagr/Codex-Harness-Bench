import {useEffect,useState} from 'react';
import {request} from './api';
import type {JudgeUsage,AutomaticRepair} from './types';
import {Details} from './ui';
type Progress={execution:{automaticRepair?:AutomaticRepair;jobId?:string;model?:string;reasoning?:string;serviceTier?:string;status?:string;logDirectory?:string;elapsedSeconds?:number;timeoutSeconds?:number;lastActivitySecondsAgo?:number};usage?:JudgeUsage|null;commands:{id:string;status:string;command:string;output:string;exitCode:number|null}[];truncated:boolean;instruction?:string;instructionTruncated?:boolean;packet?:{path:string;bytes:number;sha256?:string}|null;messages?:string[];runtime?:{workspace?:string;temporaryHome?:string;cleanup?:string};error?:string};
const statuses:Record<string,string>={preparing:'准备环境',running:'执行取证',completed:'报告已保存',partial:'部分报告已保存，仍有未验证项',failed:'执行失败',cancelled:'已取消',interrupted:'服务中断',budget_exhausted:'预算用完，审查未完成'};
export function JudgeProgress({runId,trialId,busy}:{runId:string;trialId:string;busy:boolean}){
  const [open,setOpen]=useState(false);const [data,setData]=useState<Progress|null>(null);const [error,setError]=useState('');
  useEffect(()=>{setData(null);setError('');},[runId,trialId]);
  useEffect(()=>{if(!open)return;let live=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const value=await request<Progress>(`/runs/${runId}/trials/${trialId}/judge-progress`,{});if(live){setData(value);setError('');}}catch(e){if(live)setError((e as Error).message);}finally{if(live&&busy)timer=setTimeout(poll,1500);}};
    void poll();return()=>{live=false;clearTimeout(timer);};
  },[open,busy,runId,trialId]);
  return <section className="judge-progress">
    <Details title={`评分过程${busy?' · 实时更新':''}`} open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
      <p className="judge-progress-intro">这里记录裁判实际执行的工具和公开说明。展开时自动刷新；命令输出可能在执行结束后才出现。</p>
      {error&&<div role="alert" className="alert-error"><strong>暂时无法更新评分记录</strong><p>{error}</p><p>{busy?'页面会继续尝试更新。':'重新展开这一区域可以再次读取。'}</p></div>}
      {!data&&!error&&<p role="status">正在读取本次审查记录…</p>}
      {data&&<>
        <dl className="judge-progress-status">
          <div><dt>当前状态</dt><dd>{statuses[data.execution.status||'']||'历史记录'}</dd></div>
          {data.execution.automaticRepair&&<div><dt>自动补查</dt><dd>{data.execution.automaticRepair.attempts?`${data.execution.automaticRepair.attempts.length} 次取证尝试 · ${data.execution.automaticRepair.note||''}`:`第 ${data.execution.automaticRepair.attempt||1} 次 / 最多 ${data.execution.automaticRepair.maxAttempts} 次 · ${data.execution.automaticRepair.phase||''}`}</dd></div>}
          <div><dt>裁判配置</dt><dd>{[data.execution.model,data.execution.reasoning].filter(Boolean).join(' · ')||'旧记录未记载'}{data.execution.serviceTier?` · ${data.execution.serviceTier==='fast'?'请求 Fast':data.execution.serviceTier==='standard'?'请求标准速度':`请求 ${data.execution.serviceTier}`}`:''}</dd></div>
          <div><dt>已用时间 / 时间预算</dt><dd>{data.execution.elapsedSeconds!=null?`${Math.floor(data.execution.elapsedSeconds/60)} 分钟`:'未记载'} / {data.execution.timeoutSeconds?`${data.execution.timeoutSeconds/60} 分钟`:'旧记录未记载'}</dd></div>
          {busy&&data.execution.lastActivitySecondsAgo!=null&&<div><dt>最近日志更新</dt><dd>{data.execution.lastActivitySecondsAgo} 秒前</dd></div>}
        </dl>
        {data.error&&<div role="alert" className="alert-error"><strong>本次审查未正常完成</strong><p>{data.error}</p></div>}
        {data.usage&&<section className="judge-progress-usage" aria-label="裁判 CLI 用量">
          <h4>本次裁判用量</h4>
          <dl><div><dt>输入 Token</dt><dd>{data.usage.inputTokens.toLocaleString()}</dd></div><div><dt>其中缓存读取</dt><dd>{data.usage.cachedInputTokens.toLocaleString()}</dd></div><div><dt>输出 Token</dt><dd>{data.usage.outputTokens.toLocaleString()}</dd></div><div><dt>其中推理输出</dt><dd>{data.usage.reasoningOutputTokens.toLocaleString()}</dd></div></dl>
          <p>这是 CLI 会话累计计数，运行中仍会增长，不等于订阅额度扣除或实际账单。</p>
        </section>}
        <section className="judge-progress-commands" aria-label="裁判命令记录">
          <h4>执行命令 · {data.commands.length} 条</h4>
          {data.commands.length?data.commands.map((command,i)=><Details key={command.id} title={`命令 ${i+1} · ${command.status==='running'?'执行中':`已结束 · 退出码 ${command.exitCode??'未知'}`}`}>
            <div className="judge-progress-command"><h5>命令</h5><pre className="source">{command.command}</pre><h5>输出</h5><pre className="source">{command.output||'尚无输出'}</pre></div>
          </Details>):<p>尚无命令记录。准备环境或等待模型响应时，可能没有工具事件。</p>}
          {data.truncated&&<p>页面显示最近 30 条命令及末尾输出，完整记录保存在本机日志目录。</p>}
        </section>
        {(data.instruction||data.packet)&&<Details title="裁判收到的指令与冻结材料">
          {data.instruction&&<><h4>实际指令</h4><pre className="source">{data.instruction}</pre>{data.instructionTruncated&&<p>页面显示前 20 万字符；完整指令保存在日志目录的 task/instruction.md。</p>}</>}
          {data.packet&&<dl className="judge-progress-record"><div><dt>冻结题面与评分维度</dt><dd>{data.packet.path}</dd></div><div><dt>材料大小</dt><dd>{data.packet.bytes.toLocaleString()} 字节</dd></div>{data.packet.sha256&&<div><dt>SHA-256</dt><dd>{data.packet.sha256}</dd></div>}</dl>}
          {data.packet&&<p>裁判从文件读取冻结材料，不占用启动命令长度。</p>}
        </Details>}
        {!!data.messages?.length&&<Details title={`裁判公开说明 · ${data.messages.length} 条`}>
          <ol className="judge-progress-messages">{data.messages.map((message,i)=><li key={i}><pre className="source">{message}</pre></li>)}</ol>
        </Details>}
        <Details title="日志位置与临时文件清理">
          <dl className="judge-progress-record">
            {data.execution.jobId&&<div><dt>作业编号</dt><dd>{data.execution.jobId}</dd></div>}
            {data.execution.logDirectory&&<div><dt>完整日志目录</dt><dd>{data.execution.logDirectory}</dd></div>}
            {data.runtime?.workspace&&<div><dt>临时工作副本</dt><dd>{data.runtime.workspace}</dd></div>}
            {data.runtime?.temporaryHome&&<div><dt>临时配置目录</dt><dd>{data.runtime.temporaryHome}</dd></div>}
            {data.runtime?.cleanup&&<div><dt>清理状态</dt><dd>{data.runtime.cleanup}</dd></div>}
          </dl>
          {data.runtime?.workspace&&<p>正常结束、停止或超时后自动清理临时目录。本次 reviews 目录保留日志、原始报告和取证附件；删除评测历史时一并清理。用户原 Codex 会话由 Codex 管理。</p>}
          <p>这些记录是实际工具事件与公开输出，不包含模型内部思考。</p>
        </Details>
      </>}
    </Details>
  </section>;
}

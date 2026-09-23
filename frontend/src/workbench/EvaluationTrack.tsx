import type {Task,Trial} from './types';
import {Details,Panel} from './ui';
import {nativeTaskIds} from './PublicCatalog';
export function isBenchmark(task:Task){return !!task.publicSource||!!task.checks?.length;}
export function EvaluationTrack({task,trial,disabled,action}:{task:Task;trial:Trial;disabled:boolean;action:(name:string,data?:unknown)=>Promise<unknown>}){
  const benchmark=isBenchmark(task),capture=trial.captures[trial.captures.length-1],native=nativeTaskIds.includes(task.publicSource?.id||'');
  return <Panel title={benchmark?'基准验证 · 原题验收优先':'真实项目 · 需求与交付质量'} aside={<span className="badge">结果仅供参考</span>}>
    <p>{benchmark?'以固定起点、原题测试和运行条件解释通过结果；下方 AI 质量评价只作补充，不替代原题验收。':'从产品意图到实际交付，结合运行证据、AI 量表与人的实际体验；没有唯一正确实现。'}</p>
    {benchmark&&!native&&!capture?.checksConfigured&&<p className="score-notice">当前版本尚无已接通的原题验收器。可以审查产物，但不能据此生成原榜单通过率。</p>}
    {!!capture?.checksConfigured&&!native&&<><button className="btn-secondary" disabled={disabled||['checking','judging'].includes(trial.state)} onClick={()=>void action('check',{captureId:capture.id})}>运行题目程序验收 · {capture.checksConfigured} 项</button>{capture.checks.map(c=><Details key={c.id} title={`${c.label} · ${c.status}`}><pre className="source">{c.output||'暂无输出'}</pre></Details>)}</>}
    <Details title="如何理解这份结果"><p>这是特定模型、Codex 桌面、个人配置、任务和审查条件下的记录，不代表模型的全面能力或未来真实表现。AI 和人工评分可能波动；环境异常、超时与缺失证据不等于产物得零分。</p><p>程序通过率、AI 质量分、人工参考分与资源用量分别解释。只有题目版本、环境、预算和统计协议一致的结果才适合比较；当前 Windows 适配不等同上游官方成绩。</p></Details>
  </Panel>;
}

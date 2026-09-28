import type {Task,Trial} from './types';
import {Details,Panel} from './ui';
import {nativeTaskIds,upstreamDockerTaskIds} from './PublicCatalog';
import {BehaviorAcceptance} from './BehaviorAcceptance';
export function isBenchmark(task:Task){return !!task.publicSource;}
export function EvaluationTrack({task,trial,disabled,action,runId}:{task:Task;trial:Trial;disabled:boolean;action:(name:string,data?:unknown)=>Promise<unknown>;runId:string}){
  const benchmark=isBenchmark(task),capture=trial.captures[trial.captures.length-1],native=[...nativeTaskIds,...upstreamDockerTaskIds].includes(task.publicSource?.id||'');
  const hasChecks=!!capture?.checksConfigured&&!native;
  return <Panel title={benchmark?'基准验证 · 原题验收优先':'真实项目 · 需求与交付质量'} aside={<span className="badge">结果仅供参考</span>}>
    <p>{benchmark?'以固定起点、原题测试和运行条件解释通过结果；下方 AI 质量评价只作补充，不替代原题验收。':'从产品意图到实际交付，结合运行证据、AI 量表与人的实际体验；没有唯一正确实现。'}</p>
    {trial.score.behaviorAcceptance&&capture&&<BehaviorAcceptance key={trial.score.behaviorAcceptance.attemptId||capture.id} report={trial.score.behaviorAcceptance} route={`/runs/${runId}/trials/${trial.id}`} disabled={disabled||['checking','judging'].includes(trial.state)} run={()=>void action('behavior',{captureId:capture.id})}/>}
    {benchmark&&!native&&!capture?.checksConfigured&&<p className="score-notice">当前版本尚无已接通的原题验收器。可以审查产物，但不能据此生成原榜单通过率。</p>}
    {hasChecks&&<><button className="btn-secondary" disabled={disabled||['checking','judging'].includes(trial.state)} onClick={()=>void action('check',{captureId:capture.id})}>{benchmark?'运行原题程序验收':'运行程序检查'} · {capture.checksConfigured} 项</button>{capture.checks.map(c=><Details key={c.id} title={`${c.label} · ${c.status}`}><pre className="source">{c.output||'暂无输出'}</pre></Details>)}{!benchmark&&trial.score.assurance==='ai-reference'&&<p className="score-notice">当前检查尚不足以证明本题语义和视觉质量；运行通过不等于取得配置对比资格。</p>}</>}
    <Details title="如何理解这份结果"><p>这是特定模型、Codex 桌面、个人配置、任务和审查条件下的记录，不代表模型的全面能力或未来真实表现。AI 和人工评分可能波动；环境异常、超时与缺失证据不等于产物得零分。</p><p>程序通过率、AI 质量分、人工参考分与资源用量分别解释。只有题目版本、环境、预算和统计协议一致的结果才适合比较；当前 Windows 适配不等同上游官方成绩。</p></Details>
  </Panel>;
}

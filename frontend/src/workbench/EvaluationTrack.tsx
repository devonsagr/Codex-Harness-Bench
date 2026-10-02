import type {Task,Trial} from './types';
import {Details,Panel} from './ui';
import {nativeTaskIds,upstreamDockerTaskIds} from './PublicCatalog';
import {BehaviorAcceptance} from './BehaviorAcceptance';
import {taskCheckScope} from './presentation';
export function isBenchmark(task:Task){return !!task.publicSource||task.sourceKind==='evalplus-local';}
export function hasProgramVerifier(task:Task,trial:Trial){return [...nativeTaskIds,...upstreamDockerTaskIds].includes(task.publicSource?.id||'')||taskCheckScope(task)==='task'||!!trial.score.behaviorAcceptance;}
export function EvaluationTrack({task,trial,disabled,action,runId,onReview}:{task:Task;trial:Trial;disabled:boolean;action:(name:string,data?:unknown)=>Promise<unknown>;runId:string;onReview?:()=>void}){
  const benchmark=isBenchmark(task),capture=trial.captures[trial.captures.length-1],native=[...nativeTaskIds,...upstreamDockerTaskIds].includes(task.publicSource?.id||'');
  const hasChecks=!!capture?.checksConfigured&&!native;
  const available=hasProgramVerifier(task,trial),basic=taskCheckScope(task)==='basic'&&!available;
  const checks=<><button className="btn-secondary" disabled={disabled||['checking','judging'].includes(trial.state)} onClick={()=>void action('check',{captureId:capture.id})}>{basic?'复查基础运行':benchmark?'运行原题程序验收':'运行任务检查'} · {capture?.checksConfigured} 项</button>{capture?.checks.map(c=><Details key={c.id} title={`${c.label} · ${c.status}`}><pre className="source">{c.output||'暂无输出'}</pre></Details>)}</>;
  return <Panel title={benchmark?'基准验证 · 原题验收优先':available?'本题程序验收与检查':'程序验收：无'} aside={<span className="badge">结果仅供参考</span>}>
    <p>{benchmark?'以固定起点、原题测试和运行条件解释通过结果；AI 质量评价只作补充，不替代原题验收。':'从产品意图到实际交付，结合运行证据、AI 量表与人的实际体验；没有唯一正确实现。'}</p>
    {trial.score.programAcceptance&&<section className="panel p-4" aria-label="固定程序验收"><div className="source-heading"><div><h3>{trial.score.programAcceptance.scope}</h3><p>{trial.score.programAcceptance.passed}/{trial.score.programAcceptance.total} 通过 · {trial.score.programAcceptance.failed} 失败 · {trial.score.programAcceptance.unverified} 未验证</p></div><strong>{trial.score.programAcceptance.score===null?'待验证':`${trial.score.programAcceptance.score}%`}</strong></div>{trial.score.programAcceptance.inputCount&&<p>本题含 {trial.score.programAcceptance.inputCount} 个固定扩展输入；全部满足才能判整套通过。</p>}<p className="muted">固定测试决定结果，不调用裁判模型；无需先结束交付。通过比例仅指这套测试，AI 高分不能覆盖失败。</p>{trial.score.programAcceptance.version==='community-engine-v1'&&<p className="score-notice">这里只认证功能核心。页面连接检查另列；视觉质量和完整游戏流程没有因为核心通过就获得认证。</p>}<Details title="查看全部固定用例">{trial.score.programAcceptance.rows.map(row=><div key={row.id}><strong>{row.id} · {row.status}</strong><p>{row.detail}</p></div>)}</Details></section>}
    {trial.score.behaviorAcceptance&&capture&&<BehaviorAcceptance key={trial.score.behaviorAcceptance.attemptId||capture.id} report={trial.score.behaviorAcceptance} route={`/runs/${runId}/trials/${trial.id}`} disabled={disabled||['checking','judging'].includes(trial.state)} run={()=>void action('behavior',{captureId:capture.id})}/>}
    {benchmark&&!native&&!capture?.checksConfigured&&<p className="score-notice">当前版本尚无已接通的原题验收器。可以审查产物，但不能据此生成原榜单通过率。</p>}
    {!benchmark&&!available&&<section className="acceptance-unavailable"><h3>本题按需求评估作品</h3><p>{basic?'仅有基础运行检查：确认页面能打开、没有脚本异常等。它不验收本题要求，也不评视觉效果，不能作为程序通过分。':'没有冻结的独立自动验收脚本，已有源码不等于已经验证。'} AI 裁判会按原始需求运行项目、检查流程和边界，再给出质量参考。</p><p>评分缺项会自动反馈给裁判补查。网页题请选择 Docker 裁判，以便打开浏览器取证。</p>{onReview&&<button type="button" className="btn-primary" onClick={onReview}>去 AI 评分</button>}</section>}
    {hasChecks&&(basic?<Details title={`基础运行检查 · ${capture.checks.filter(c=>c.status==='passed').length}/${capture.checksConfigured} 通过（不计整题验收）`}><p>只列基础运行事实；重查会保存新记录，原 AI 报告和评分保留。</p>{checks}</Details>:<>{checks}{!benchmark&&trial.score.assurance==='ai-reference'&&<p className="score-notice">这些检查只覆盖已声明的要求；运行通过不代表整份作品都已验收。</p>}</>)}
    <Details title="如何理解这份结果"><p>这是特定模型、Codex 桌面、个人配置、任务和审查条件下的记录，不代表模型的全面能力或未来真实表现。AI 和人工评分可能波动；环境异常、超时与缺失证据不等于产物得零分。</p><p>程序通过率、AI 质量分、人工参考分与资源用量分别解释。只有题目版本、环境、预算和统计协议一致的结果才适合比较；当前 Windows 适配不等同上游官方成绩。</p></Details>
  </Panel>;
}

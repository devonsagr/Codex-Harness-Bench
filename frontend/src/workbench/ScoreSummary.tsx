import type {Run,Task,Trial} from './types';
import {Details} from './ui';
import {batchScoreSummary,currentTrialAxes,programScoreExplanation,totalScoreExplanation} from './scoreExplanation';

const display=(value:number|null|undefined)=>value==null?'—':Number.isInteger(value)?String(value):value.toFixed(1);

export function ScoreSummary({run,trial,task,onSection,onResults}:{run:Run;trial:Trial;task:Task;onSection:(section:string)=>void;onResults?:()=>void}){
  const total=totalScoreExplanation(run,trial,task),program=programScoreExplanation(trial,task);
  const batch=batchScoreSummary(run),axes=currentTrialAxes(run,trial,task),card=trial.score.taskScorecard;
  const corrections=Object.keys(trial.score.machineOverrides||{}).length;
  const programFailed=program.value==='未通过'||!!trial.score.programAcceptance?.failed;
  return <section className="score-summary" aria-label="评分总览">
    <header className="score-summary-heading"><div><h2>本题评分总览</h2><p>{trial.captures.length?`回收版本 ${trial.captures.length}`:'尚未回收'} · {trial.state==='completed'?'交付结束':'交付进行中'}</p></div><div className="run-actions"><button type="button" className="btn-secondary" onClick={()=>onSection('checks')}>查看程序验收</button>{onResults&&<button type="button" className="btn-primary" onClick={onResults}>查看配置总评</button>}</div></header>
    <div className="score-summary-metrics">
      <article className="score-summary-total"><h3>{trial.score.overall==null?'单题总分待形成':task.publicSource||trial.state==='completed'?'本地单题总分':'暂定单题总分'}</h3><p className="score-summary-number">{display(trial.score.overall)}<span> / 100</span></p><p>{total.status}</p></article>
      <article className={programFailed?'score-summary-failed':undefined}><h3>{program.label}</h3><p className="score-summary-number">{program.value}</p><p>{program.detail}</p></article>
      <article><h3>AI原始均值</h3><p className="score-summary-number">{display(trial.score.machine)}<span> / 100</span></p><p>已评分项的加权均值，缺项不填0。{corrections?`另有 ${corrections} 项人工修正；总分使用修正后的有效分项。`:'程序结果与AI评价分别保存。'}</p><button type="button" className="btn-text" onClick={()=>onSection('quality')}>查看逐项分数与依据 →</button></article>
    </div>
    {programFailed&&<p className="alert-error" role="status">程序验收已发现失败。质量参考分不能把程序失败改成通过；请在“程序验收”查看失败项。</p>}
    <Details title="单题总分怎么计算"><p>{total.formula}</p>{card&&<table className="score-summary-contributions"><thead><tr><th scope="col">冻结评分组</th><th scope="col">权重</th><th scope="col">本次贡献</th></tr></thead><tbody>{card.items.map((row,index)=><tr key={row.key||`${row.label}:${index}`}><th scope="row">{row.label}</th><td>{row.weight}%</td><td>{row.points==null?'待验证':`${display(row.points)} 分`}</td></tr>)}</tbody></table>}<p>评分版本：{total.version}。高分是本地参考值；已评分不代表原题程序验收通过，AI引用存在也不证明判断正确。</p>{trial.score.human!=null&&<p>独立人工参考分：{display(trial.score.human)} / 100。按本记录冻结方案决定是否计入总分。</p>}<button type="button" className="btn-text" onClick={()=>onSection('human')}>打开作品并人工复核 →</button></Details>
    <section className="score-summary-axes" aria-label="本题六轴来源"><header><h3>这道题如何进入雷达图</h3><p>下列是本题有证据的轴分；配置雷达会先平均同题重复，再按题等权。雷达不另算综合总分。</p></header><ul>{axes.map(axis=><li key={axis.id}><div><strong>{axis.label}</strong><span>{axis.score==null?'未测':`${display(axis.score)} / 100`}</span></div><p>{axis.samples[0]?.runs[0]?.basis||'当前快照没有此轴对应的有效评分证据，不按0分处理。'}</p></li>)}</ul>{task.publicSource&&<p>原题通过或未通过不会复制到六个轴。当前公开题评分卡只可能提供目标功能、工程可维护性和旧功能回归；网页体验、推理决策、协作与交付保持未测。</p>}<p>逐回合对话观察只报告切题、落实纠正与必要追问，不自动计入本题总分或雷达。只有冻结评分卡中的相关评分项，才可能映射到对应轴。</p><button type="button" className="btn-text" onClick={()=>onSection('dialogue')}>查看人机对话判断与原话 →</button></section>
    <Details title="整批、SWE通过率与配置综合分怎么看">{batch.total>1&&<p>本批参考均值：{batch.mean==null?'待全部形成单题分':`${display(batch.mean)} / 100`}，已有 {batch.scored}/{batch.total} 次试测形成单题分。这里按本批每次试测等权；含多配置时不代表某套配置的成绩。</p>}{batch.nativeTotal>0&&<p>本批公开题原题通过率：{batch.nativeRate==null?'待验收':`${display(batch.nativeRate)}%`}（{batch.nativePassed}/{batch.nativeVerified} 次已验收通过）；另有 {batch.nativeTotal-batch.nativeVerified} 次待验收。分母不包含未验收记录，待验收不会填0。</p>}<p>SWE原题看验收器的reward（0或1）和F2P/P2P明细。跨题通过率 = 通过的试测数 ÷ 已取得有效原题结果的试测数；这是测试通过率，不能直接变成六轴能力分。</p><p>“配置成绩”页的综合分 = 同题、同版本、同协议的重复试测先求均值，再对各题均值等权平均。完整批次优先，缺失、协议混用、临时改技能或只有AI参考证据时，综合分可能暂不发布。</p><p>开放项目须结束交付，并核对当前快照的任务验收证据；公开题须有绑定当前快照的原题报告与本地连续评分卡。单题分可先查看，配置对比还要同模型、同档位、同速度、共同题目与协议。</p></Details>
  </section>;
}

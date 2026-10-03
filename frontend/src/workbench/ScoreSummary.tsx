import type {Run,Task,Trial} from './types';
import {Details} from './ui';
import {ScoreCoverage} from './ScoreCoverage';
import {ScoreCalculation} from './ScoreCalculation';
import {batchScoreSummary,currentTrialAxes,nativeTestProgress,programScoreExplanation,totalScoreExplanation} from './scoreExplanation';

const display=(value:number|null|undefined)=>value==null?'—':Number.isInteger(value)?String(value):value.toFixed(1);

export function ScoreSummary({run,trial,task,onSection,onResults}:{run:Run;trial:Trial;task:Task;onSection:(section:string)=>void;onResults?:()=>void}){
  const total=totalScoreExplanation(run,trial,task),program=programScoreExplanation(trial,task);
  const batch=batchScoreSummary(run),axes=currentTrialAxes(run,trial,task),card=trial.score.taskScorecard;
  const corrections=Object.keys(trial.score.machineOverrides||{}).length;
  const programFailed=program.value==='未通过'||!!trial.score.programAcceptance?.failed;
  const progress=trial.score.scoreProgress,native=nativeTestProgress(trial);
  const partial=!!progress&&progress.coverage>0&&progress.unknownWeight>0;
  const nativeOnly=!!task.publicSource&&run.policy.version==='arena-machine-v1'&&!card;
  const localQuality=!!task.publicSource&&!!card;
  const assessment=trial.assessmentExecution?.captureId===trial.captures[trial.captures.length-1]?.id?trial.assessmentExecution:null;
  return <section className="score-summary" aria-label="评分总览">
    <header className="score-summary-heading"><div><h2>本题评测结果</h2><p>{trial.captures.length?`回收版本 ${trial.captures.length}`:'尚未回收'} · {trial.state==='completed'?'交付结束':'交付进行中'}</p></div><div className="run-actions">{run.policy.version==='arena-machine-v1'&&trial.captures.length>0&&!assessment&&!['checking','judging'].includes(trial.state)&&trial.score.overall==null&&!(nativeOnly&&native)&&<button type="button" className="btn-primary" onClick={()=>onSection('review')}>评测此交付</button>}<button type="button" className="btn-secondary" onClick={()=>onSection('checks')}>{program.value==='无'?'程序验收：无':'查看程序验收'}</button>{onResults&&<button type="button" className="btn-primary" onClick={onResults}>查看配置总评</button>}</div></header>
    {assessment&&<p role="status" className="score-notice">{assessment.phase}{trial.lastJobError?`：${trial.lastJobError.message}`:''}</p>}
    <div className="score-summary-metrics">
      <article className="score-summary-total"><h3>{nativeOnly?'原题结果':trial.score.overall==null?(partial?'当前总分范围':'单题总分待形成'):task.publicSource||trial.state==='completed'?'本地单题总分':'暂定单题总分'}</h3><p className="score-summary-number">{nativeOnly?native?`${native.result.reward} / 1`:assessment?'未能完成验收':'尚未评测':trial.score.overall==null&&partial?`${display(progress.minimum)}–${display(progress.maximum)}`:display(trial.score.overall)}{!nativeOnly&&<span> / 100</span>}</p><p>{nativeOnly?total.status:trial.score.overall==null&&partial?`已确认 ${display(progress.knownPoints)} 分，剩余 ${display(progress.unknownWeight)} 分权重待核实。`:total.status}</p></article>
      <article className={programFailed?'score-summary-failed':undefined}><h3>{program.label}</h3><p className="score-summary-number">{program.value}</p><p>{program.detail}</p></article>
      <article><h3>{localQuality?'AI 可维护性分 · 占 10%':'AI 分项均值'}</h3><p className="score-summary-number">{display(localQuality?trial.score.effectiveScores?.maintainability:trial.score.machine)}<span> / 100</span></p><p>{localQuality?'该分数乘 10%，再加程序贡献，得到本地总分。':'AI 分项按本题冻结权重形成总分，具体贡献见下方。'}{corrections?`含 ${corrections} 项人工修正，原 AI 分保留。`:''}</p><button type="button" className="btn-text" onClick={()=>onSection('quality')}>查看 AI 分项与依据 →</button></article>
    </div>
    <ScoreCalculation run={run} trial={trial} task={task}/>
    {native&&<Details title="原题测试明细与通过比例"><section className="score-native-progress" aria-label="SWE单题程序进展"><dl><div><dt>目标测试完成比例</dt><dd>{display(native.target)}%<span>{native.result.f2p_passed} / {native.result.f2p_total} 通过</span></dd></div><div><dt>旧功能回归通过比例</dt><dd>{display(native.regression)}%<span>{native.result.p2p_passed} / {native.result.p2p_total} 通过</span></dd></div><div><dt>原题结果</dt><dd>{native.result.reward} / 1<span>{native.result.reward?'整题通过':'整题未通过'}</span></dd></div></dl><p>目标与回归比例由程序统计。连续评分卡按预先定义的功能组给分，某组全部通过才得到该组权重；因此其贡献不等同把所有测试数量直接平均。</p></section></Details>}
    <ScoreCoverage trial={trial} task={task} onSection={section=>onSection(section==='quality'?'review':section)}/>
    <section className="score-config-link" aria-label="配置分汇总"><h3>这道题怎样计入配置成绩</h3><p>本地单题分先按同题、同版本、同评分协议合并重复试测，再对不同题的均分等权平均。未完成题不填 0；配置页显示已评分题数及其参考均分，完整题集分与跨配置对比资格另列。</p>{onResults&&<button type="button" className="btn-secondary" onClick={onResults}>查看本配置的计算明细</button>}</section>
    <Details title="雷达图的分数来源"><p>雷达读取对应的已评分细项；同题重复先平均，再按不同题等权。它展示能力分布，不重新生成单题或配置总分。</p><ul className="score-axis-sources">{axes.map(axis=><li key={axis.id}><div><strong>{axis.label}</strong><span>{axis.score==null?'未测':`${display(axis.score)} / 100`}</span></div><p>{axis.samples[0]?.runs[0]?.basis||'当前快照没有此轴的有效证据。'}</p></li>)}</ul><p>“协作与交付”轴取冻结评分项中的沟通、阶段推进和交接分；逐回合附件中的符合/偏离次数不直接转换成轴分。</p></Details>
    <Details title="批次与原题通过率">{batch.total>1&&<p>本批完整单题均值：{batch.mean==null?'尚未全部计分':`${display(batch.mean)} / 100`}，已有 {batch.scored}/{batch.total} 次试测形成单题分。</p>}{batch.nativeTotal>0&&<p>原题通过率 {batch.nativeRate==null?'待验收':`${display(batch.nativeRate)}%`}（{batch.nativePassed}/{batch.nativeVerified} 次有效结果通过），另有 {batch.nativeTotal-batch.nativeVerified} 次待验收。</p>}<p>原题通过率 = 原题通过次数 ÷ 有效原题结果次数；该统计与本地质量分分别保留。</p></Details>
  </section>;
}

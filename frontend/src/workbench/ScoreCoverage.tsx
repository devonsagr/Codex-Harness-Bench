import type {Task,Trial} from './types';
import {missingScoreEvidence} from './scoreExplanation';
import {num} from './ui';

export function ScoreCoverage({trial,task,onSection}:{trial:Trial;task:Task;onSection?:(section:string)=>void}){
  const progress=trial.score.scoreProgress;
  const capture=trial.captures[trial.captures.length-1];
  const assessment=trial.assessmentExecution?.captureId===capture?.id?trial.assessmentExecution:null;
  if(!progress||!progress.unknownWeight||(!trial.score.machineReviewId&&!assessment))return null;
  const missing=missingScoreEvidence(trial,task);
  const report=trial.reviews.find(row=>row.id===trial.score.machineReviewId);
  return <section className="score-coverage" aria-label="已确认贡献与缺项">
    <header><h3>已确认 {num(progress.knownPoints)} 分，还有 {num(progress.unknownWeight)} 分权重待验证</h3><span>{num(progress.coverage)}% 权重已测</span></header>
    <p>按现有分项，总分可能在 {num(progress.minimum)}–{num(progress.maximum)} 分之间。未测项保留空值；这是缺项的算术范围，不是最终分或裁判误差。</p>
    <ul>{missing.map((row,index)=><li key={row.key||index}><div><strong>{row.label} · {num(row.weight)}%</strong><p>{row.reason}</p></div></li>)}</ul>
    {['checking','judging'].includes(trial.state)?<p role="status">本次评测正在自动处理检查与补查，完成后更新结果。</p>:<>{report&&!report.assessmentVersion&&<p>这是原先分开验收的报告。新的一次评测会自动串起验收、评分和补查，不需要逐项补分。</p>}{onSection&&<button type="button" className="btn-secondary" onClick={()=>onSection('quality')}>{assessment?'查看本次评测过程':'评测此交付'}</button>}</>}
  </section>;
}

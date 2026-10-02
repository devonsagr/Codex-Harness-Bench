import type {Task,Trial} from './types';
import {missingScoreEvidence} from './scoreExplanation';
import {num} from './ui';
import {taskCheckScope} from './presentation';

export function ScoreCoverage({trial,task,onSection}:{trial:Trial;task:Task;onSection?:(section:string)=>void}){
  const progress=trial.score.scoreProgress;
  if(!progress||!progress.unknownWeight)return null;
  const missing=missingScoreEvidence(trial,task);
  const report=trial.reviews.find(row=>row.id===trial.score.machineReviewId);
  return <section className="score-coverage" aria-label="已确认贡献与缺项">
    <header><h3>已确认 {num(progress.knownPoints)} 分，还有 {num(progress.unknownWeight)} 分权重待验证</h3><span>{num(progress.coverage)}% 权重已测</span></header>
    <p>按现有分项，总分可能在 {num(progress.minimum)}–{num(progress.maximum)} 分之间。未测项保留空值；这是缺项的算术范围，不是最终分或裁判误差。</p>
    <ul>{missing.map((row,index)=><li key={row.key||index}><div><strong>{row.label} · {num(row.weight)}%</strong><p>{row.reason}</p></div>{onSection&&<button type="button" className="btn-secondary" onClick={()=>onSection(row.section)}>{row.section==='checks'?(taskCheckScope(task)==='basic'?'补基础检查':'去运行验收'):'去取证与补查'}</button>}</li>)}</ul>
    {report&&!report.automaticRepair&&<p>这是此前保存的裁判报告，未自动改分或重评。下一次审查会按新流程反馈可补查的缺项；启动时会说明模型用量。</p>}
  </section>;
}

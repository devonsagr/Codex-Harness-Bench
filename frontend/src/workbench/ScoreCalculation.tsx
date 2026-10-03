import type {Run,Task,Trial} from './types';
import {Details,num} from './ui';
import {scoreComposition} from './scoreExplanation';

export function ScoreCalculation({run,trial,task}:{run:Run;trial:Trial;task:Task}){
  const result=scoreComposition(run,trial,task),progress=trial.score.scoreProgress;
  const total=trial.score.overall;
  const fmt=(value:number|null)=>value==null?'待评分':num(Math.round(value*100)/100);
  const groups=trial.score.taskScorecard?.items||[];
  const projectFormula=total!=null&&groups.length>0&&groups.length<=3&&groups.every(row=>row.points!=null)?`${groups.map(row=>fmt(row.points)).join(' + ')} = ${fmt(total)} / 100`:result.formula;
  const verificationFailed=result.rows.some(row=>row.source==='程序失败，限制为 0');
  return <section className="score-calculation" aria-label="单题总分计算">
    <h3>单题总分计算</h3>
    <p className="score-calculation-formula">{result.kind==='public'&&result.rows.length?`${fmt(result.programPoints)}（程序） + ${fmt(result.qualityPoints)}（可维护性） = ${fmt(total)} / 100`:projectFormula}</p>
    {result.kind==='project'&&groups.length>0&&groups.length<=3&&<p>{groups.map(row=>`${row.label}：${fmt(row.points)} / ${num(row.weight)} 分`).join('；')}</p>}
    {result.kind==='public'?<p>{result.rows.length?'目标功能语义组占 70 分、旧功能回归占 20 分，均由原题测试决定；AI 可维护性分 × 10% 得到其余贡献。原题是否整题通过仍单独显示。':'原题只有通过 / 未通过；当前没有对应的本地连续评分卡，不把通过率与 AI 均值拼成总分。'}</p>:result.kind==='project'?<p>创建时配置的程序检查不另占一份均分。若本题设置了“验证与回归”项，检查失败将该项限制为 0，检查未完成则留空；通过后仍由 AI 按证据评价验证质量。各项按本题冻结权重汇总。</p>:<p>此记录使用创建时的程序与人工混合方案，权重保持原样。</p>}
    {total==null&&progress&&<p>已确认贡献 {num(progress.knownPoints)} / 100，剩余 {num(progress.unknownWeight)} 分权重待验证。</p>}
    {verificationFailed&&<p>本次检查存在失败，“验证与回归”以 0 分参与汇总。原 AI 评分保留在 AI 分项记录中。</p>}
    {result.rows.length>0&&<Details title="查看每项来源、分数、权重与贡献" open={verificationFailed}>
      <div className="score-table-scroll"><table className="score-summary-contributions"><thead><tr><th scope="col">评分项</th><th scope="col">来源</th><th scope="col">分数</th><th scope="col">权重</th><th scope="col">总分贡献</th></tr></thead><tbody>{result.rows.map((row,index)=><tr key={row.key||index}><th scope="row">{row.label}</th><td>{row.source}</td><td>{fmt(row.value)}</td><td>{num(row.weight)}%</td><td>{fmt(row.points)}</td></tr>)}</tbody></table></div>
      <p>每项贡献 = 分数 × 权重；缺项留空。合计使用服务器按本题冻结规则计算的结果。</p>
      {result.kind==='legacy'&&trial.score.adjudicatedOverall!=null&&<p>另存的人工裁定参考总分：{num(trial.score.adjudicatedOverall)} / 100。该裁定与以上原分分别保留。</p>}
    </Details>}
  </section>;
}

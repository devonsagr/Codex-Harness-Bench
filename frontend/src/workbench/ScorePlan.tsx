import type {Task} from './types';
import {Details} from './ui';

export function ObjectivePlan({tasks}:{tasks:Task[]}){
  return <section className="score-section space-y-4"><h3 className="font-semibold">客观检查 · 自动运行程序</h3><p className="muted">点击“检查快照”后，后端在无网络 Docker 容器的产物副本执行下面的命令。退出码 0 为通过，非 0 为失败；超时、环境错误或未运行保持未知。不会调用 AI 打这个分。</p>
    {!tasks.length&&<p className="muted">先选题，这里显示该题实际配置的检查。</p>}
    {tasks.map(task=>{
      const slots=task.checks.flatMap(c=>{const stage=c.stageIndex??task.stages.length-1;return [{check:c,stage},...(c.runOnFinal&&stage!==task.stages.length-1?[{check:c,stage:task.stages.length-1}]:[])];});
      const sum=slots.reduce((n,x)=>n+x.check.weight,0);
      return <div className="space-y-3" key={task.id}><h4 className="font-medium">{task.title} · v{task.revision}</h4>{!slots.length?<p className="score-notice">本题没有自动检查，客观分不会产生。准备时可选择纯人工验收；需要自动检查时在题库配置或复用已有检查方案。</p>:<ul className="space-y-3">{slots.map(({check:c,stage},i)=><li className="score-check" key={i}><div className="flex justify-between gap-3"><strong>{c.label}</strong><span>客观分内 {(c.weight/sum*100).toFixed(2)}%</span></div><p className="muted">第 {stage+1} 轮 · {{build:'构建 / 类型',functional:'功能',rule:'规则',other:'其他'}[c.kind||'other']} · 通过得该项全部权重，失败得0</p><p className="muted">验证要求：{(c.criterionIds||[]).map(id=>task.criteria?.find(x=>x.id===id)?.label||id).join('；')||'未关联逐条需求；通过此检查不能证明整题需求已满足。'}</p><Details title={'执行细节：'+c.label}><p className="muted break-all">镜像：{c.image} · 超时 {c.timeout||120} 秒</p><pre className="source">{JSON.stringify(c.argv)}</pre></Details></li>)}</ul>}
      <p className="muted">需求验收：{task.criteria?.length||0} 条，其中 {task.criteria?.filter(c=>c.required).length||0} 条必要项；自动检查之外仍需按需求查看真实产物。</p></div>;
    })}
    <p className="muted">复用方式：通用构建、类型与测试命令可以跨题复用；业务功能按题目契约补充断言或人工操作步骤。开放式项目可用逐条需求 + 人工证据验收，不必每题从零写脚本，也不能用“构建通过”代替业务成功。</p>
  </section>;
}

export function RatingGuide(){return <div className="score-guide space-y-2"><h4 className="font-medium">人工评分规则</h4><p className="muted">每项填0–100分，并记录实际操作、预期与结果、文件或检查证据；没有检查过的维度保持未评分，不用0代替未知。所有计分维度有证据后才形成完整人工分。</p><p className="muted">0–39：核心要求失败或结果不可用；40–59：部分成立但有重大缺口；60–79：主流程可用，仍有明确问题；80–94：主要要求与关键边界有验证；95–100：完整要求和关键边界有可复现证据，不能只凭观感。高分不能抵销必要条目未满足。</p></div>;}

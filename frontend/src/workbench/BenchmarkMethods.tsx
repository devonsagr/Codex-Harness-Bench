import {Details} from './ui';

export function BenchmarkMethods(){return <div className="guide-content">
  <section className="reading-copy"><h2>先问“这是什么分”，再看数字</h2><p>截图中的百分比、Elo 和指数不是同一单位。任务、工具、执行预算和判分器不同，不能把不同榜单直接相加。本工作台把原题程序验收、项目质量、人工体验与用量分别记录。</p></section>
  <div className="guide-two-column"><section><h2>已有工程的基准任务</h2><p>DeepSWE、Terminal-Bench 等按固定题目与验收器计算单次成功率。DeepSWE 以提交补丁后的程序验证为主；本机仅有少量 Windows 适配，未接通的题没有原题通过分。AI 质量评价单列。</p></section><section><h2>开放需求的真实交付</h2><p>先把产品目标写成可观察的必要验收条目，再检查实际产物、运行证据和人工体验。允许多种合理实现。缺少运行或界面证据时留空，不把其余项目放大成总分。</p></section></div>
  <Details title="截图中的榜单分别怎么算"><ul className="guide-facts">
    <li><strong>DeepSWE / Terminal-Bench / SWE-Atlas-QnA：</strong>按各自固定题目判整题通过与否，重复运行后估计 pass@1。DeepSWE 看补丁的程序验收；QnA 用逐条标准判答案。</li>
    <li><strong>GDPval-AA / AA-Briefcase / Code Arena WebDev：</strong>比较同题两份交付的质量，再把成对胜负汇总为相对 Elo/BT 尺度。分数不是百分比。</li>
    <li><strong>AutomationBench-AA：</strong>检查跨应用任务终态：完成多少目标，以及是否违反约束；违反守则的任务该项为零。它与“全部目标完成的任务比例”是两个指标。</li>
    <li><strong>Artificial Analysis Intelligence Index：</strong>按公开权重汇总十项不同评测，是该机构定义的综合指数；与单独软件工程榜单的百分比不同。价格和 Token 另列，不算进能力分。</li>
  </ul><p><a href="https://artificialanalysis.ai/methodology/coding-agents-benchmarking" target="_blank" rel="noreferrer">Coding Agent Index 方法 ↗</a> · <a href="https://artificialanalysis.ai/methodology/intelligence-benchmarking" target="_blank" rel="noreferrer">Intelligence Index 方法 ↗</a> · <a href="https://arena.ai/blog/webdev-arena" target="_blank" rel="noreferrer">WebDev Arena 方法 ↗</a></p></Details>
  <Details title="项目经理式任务怎样设指标"><ol className="guide-steps"><li><strong>先写结果和边界</strong><p>用户是谁、完成什么流程、输入输出是什么、哪些限制绝不能违反。</p></li><li><strong>冻结必要验收</strong><p>把关键流程、错误恢复和交付物列成可观察条目；能自动测的用程序测，不能测的指定操作和证据。</p></li><li><strong>只启用适用维度</strong><p>默认从需求完成、验证与回归、健壮性、规则遵守、交互、交付和可维护性起步。无界面题自动排除交互；性能、安全在题目需要时加入。</p></li><li><strong>分数带覆盖率</strong><p>所有适用项有证据、交付结束才形成整题质量分。程序通过率与 AI 质量分分别显示；未验证不作零分，也不能只用已评分的 5% 冒充总分。</p></li></ol></Details>
  <Details title="配置历史怎样阅读"><p>开放项目同题多次有效评分先取均值，再按已验证题目等权显示质量参考均分。公开基准题另列本机程序通过数；AI 意见不混入通过率。它们描述已测样本，不自动推断全部任务的能力。比较两套配置仍要对齐同题同版本、模型、起点、环境和裁判协议。</p></Details>
  <p className="score-notice">公开题目与任务链接在“题库与公开来源”中，可直接选择题目进入评测。榜单分数只在各自协议内解释；本机 Windows 适配不等同官方 Linux 成绩。</p>
</div>;}

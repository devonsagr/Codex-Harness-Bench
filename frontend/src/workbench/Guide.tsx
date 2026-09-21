import {useState} from 'react';
import type {State} from './types';
import {Details} from './ui';
import {PublicTaskSources} from './PublicTaskSources';

export function Guide({state}:{state:State}){
  const [section,setSection]=useState('purpose');
  const dimensions=Object.entries(state.defaultPolicy.dimensions);
  const total=dimensions.reduce((sum,[,weight])=>sum+weight,0);
  return <div className="guide-page">
    <header className="guide-heading"><span className="eyebrow">CODEX HARNESS BENCH</span><h1>你的配置，是否让 Codex 更好用？</h1><p>在 Codex 桌面既有底座上，评测模型与个人配置共同产生的真实交付。</p></header>
    <nav className="section-nav" aria-label="原理说明分区">{[['purpose','项目定位'],['workflow','使用与评分'],['sources','题库与公开来源']].map(([id,label])=><button key={id} className={section===id?'active':''} aria-current={section===id?'page':undefined} onClick={()=>setSection(id)}>{label}</button>)}</nav>
    {section==='purpose'&&<div className="guide-content">
      <section className="guide-intro reading-copy"><h2>模型榜单回答不了你的全部问题</h2><p>同一个模型，加上不同的规则、Skills、工具和交互约定，可能交付不同的结果。我们想回答的是：你每天使用的这一套配置，是否更能完成你的需求，是否值得保留这次改动。</p><p>编码榜单通常也包含指定的运行框架。本项目进一步固定到 Codex 桌面场景，重点比较你能调整的那一层。</p></section>
      <div className="harness-layers" aria-label="评测对象三层结构"><section><span>01 · 基础条件</span><h2>Codex 桌面底座</h2><p>桌面提供的执行循环、工具、上下文管理与产品行为。记录版本及宿主条件。</p></section><section><span>02 · 模型条件</span><h2>模型与推理档位</h2><p>比较个人配置时尽量保持相同；换模型时，结果解释为组合差异。</p></section><section className="personal-layer"><span>03 · 主要比较变量</span><h2>你的个人配置</h2><p>AGENTS 规则、Skills、交互约定，以及工作台支持的原生设置和工具开关。</p></section></div>
      <section className="guide-two-column"><div><h2>怎样比较一次改动</h2><p>保存配置 A，复制成 B，只改你想验证的部分。同一题目、同一源码起点和评分方案分别执行，查看交付质量、资源使用和具体证据。</p></div><div><h2>结果告诉你什么</h2><p>哪项需求完成得更好、哪里出错、花了多少可核实的用量。重复多题后再判断收益；一次高分只是一条实验记录。</p></div></section>
      <Details title="哪些条件会影响比较"><p>模型、推理档位、桌面版本、源码和依赖版本、继承的全局规则与工具、人工介入、裁判及评分标准都会影响结果。独立工作区保存起点和产物，但仍可能继承桌面的全局设置。当前严格分组只接纳条件证据齐备的记录，本机裁判结果暂未纳入严格比较。</p></Details>
    </div>}
    {section==='workflow'&&<div className="guide-content">
      <div className="guide-two-column"><section><h2>一次评测，四步完成</h2><ol className="guide-steps"><li><strong>选配置和任务</strong><p>配置管理保存版本；题库说明任务、源码起点与环境要求。</p></li><li><strong>准备并在桌面执行</strong><p>工作台创建独立目录和任务草稿。核对配置后发送完整需求，按实际进度继续，不预设必须对话几轮。</p></li><li><strong>回收并机器评分</strong><p>完成后停止文件写入，回收产物，启动独立裁判。评分过程可查看实际命令、输出和失败原因。</p></li><li><strong>按需修正，保存结果</strong><p>有异议就按项修正并注明依据。标记交付结束，保留机器原分、修正与历次产物。</p></li></ol></section><section><h2>机器怎样给分</h2><div className="grading-methods"><article><h3>程序验证 · 行为证据</h3><p>运行已有测试或题包验收器，记录通过、失败和输出。用于确认具体行为，不能单独代表完整质量。</p></article><article><h3>独立 AI · 质量评价</h3><p>默认 Luna / max 在新的裁判任务中读取需求和产物副本，调用工具取证，按量表给分并引用证据。每次结果可能波动。</p></article><article><h3>人工修正 · 处理分歧</h3><p>保留机器原分，修正指定维度并记录理由；不会把未通过的程序检查改成通过。</p></article></div></section></div>
      <Details title="分数、权重与未验证项"><p>当前默认方案按适用维度加权；以下权重可在准备时调整并冻结，属于产品约定。人工修正替换对应维度后重算。所有适用项有分且交付结束才显示最终分，缺项保留暂定分和机器覆盖率。</p><div className="guide-weights">{dimensions.map(([id,weight])=><div key={id}><span>{state.defaultPolicy.rubrics?.[id]?.label||state.rubricCatalog[id]?.label||id}</span><strong>{total?Math.round(weight/total*100):0}%</strong></div>)}</div><p>必要需求的验收结论单列。程序通过率、AI质量分和用量分别展示，不混成一种“官方跑分”。</p></Details>
      <Details title="实际使用中需要知道的事"><ul className="guide-facts"><li><strong>配置应用：</strong>导入到工作台只保存副本；点击应用到 Codex 才备份并写入设置，新任务中仍需核对实际模型及覆盖关系。</li><li><strong>Docker：</strong>网站、桌面工作区和本机裁判不要求 Docker。外部题包若依赖 Linux 镜像和独立验收器，则按它的环境要求准备。</li><li><strong>界面评分：</strong>交互与视觉需要真实操作和截图证据。当前 Windows 本机裁判的浏览器取证尚未打通，无法验证时留空。</li><li><strong>资源统计：</strong>从匹配工作区的原生日志读取 Token、缓存和活动时间；等待时间不冒充推理时间，缺失数据留空。</li><li><strong>中断与数据：</strong>环境错误、额度不足不记为任务得零分。记录保存在本机，导出可能包含个人配置与产物。</li></ul></Details>
    </div>}
    {section==='sources'&&<div className="guide-content"><section className="guide-two-column"><div><h2>题库要提供可执行的任务</h2><p>从零开发需要完整需求；修复、重构和扩展需要固定源码起点、依赖与验收方法。内置题由工作台自动准备，不能让用户自己拼环境。</p></div><div><h2>当前接入情况</h2><p>已有三套带源码的原创题包及需求构建题。公开题库目前完成来源索引，桌面环境适配和原生验收结果接入仍在开发；缺源码的任务不能启动。</p></div></section>
      <PublicTaskSources state={state}/>
      <Details title="DRadar 与本项目有什么不同"><p>DRadar 的公开客户端通过 Pier / Docker 执行任务，上传产物后由服务端判分。我们固定正式执行入口为 Codex 桌面，比较个人配置。可借鉴它的版本固定、环境预检和独立验收，但不把 CLI 结果冒充桌面结果。</p><p>DRadar 服务端完整评分实现未公开在该客户端仓库中。</p><a href="https://github.com/codex-radar/dradar/blob/39e7567dc4e76db12748bb17a0ea9b12d6c68294/src/dradar/runner.py" target="_blank" rel="noreferrer">查看核对过的客户端源码 ↗</a></Details>
      <Details title="其他公开方案与用途"><ul className="guide-facts"><li><a href="https://github.com/SWE-bench/SWE-bench" target="_blank" rel="noreferrer">SWE-bench ↗</a>：已有工程修复，按任务测试验证修复与回归。</li><li><a href="https://github.com/harbor-framework/harbor" target="_blank" rel="noreferrer">Harbor / Terminal-Bench ↗</a>：复用任务、环境和验收器格式。</li><li><a href="https://github.com/WebPAI/DesignBench" target="_blank" rel="noreferrer">DesignBench ↗</a>：前端生成、编辑和修复的专项评测参考。</li><li><a href="https://github.com/metauto-ai/agent-as-a-judge" target="_blank" rel="noreferrer">Agent-as-a-Judge ↗</a>：开放需求的工具取证与判定参考。</li></ul></Details>
    </div>}
  </div>;
}

import type {Task,Imported} from './types';
import {Details} from './ui';
export const needsBaseline=(task:Task)=>task.requiresBaseline||task.taskParadigm==='deterministic-bugfix';
export const canStartTask=(task:Task,baselines:Imported[])=>!needsBaseline(task)||baselines.some(b=>b.id===task.baselineId);
export function TaskEnvironment({task,baselines}:{task:Task;baselines:Imported[]}){
  const source=baselines.find(b=>b.id===task.baselineId);
  const files=source?Object.keys(source.manifest.files):[];
  return <section className="task-environment" aria-label="项目起点与环境"><div className="environment-heading"><h3>项目起点</h3><span className={'readiness '+(canStartTask(task,baselines)?'ready':'pending')}>{source?'源码已打包':needsBaseline(task)?'待补全源码':'从零构建'}</span></div>
    <p className="reading-copy">{source?'创建评测时，源码与已有测试会自动复制到独立工作区。':needsBaseline(task)?'此题目前只有题面，不能开始修改已有工程。':'这是需求实现题，创建空项目目录，由模型实现项目并准备所需依赖。'}</p>
    {source&&<><dl className="environment-facts"><div><dt>起点快照</dt><dd>{source.name}</dd></div><div><dt>文件</dt><dd>{files.length} 个</dd></div><div><dt>来源</dt><dd>{task.sourceKind==='repository-original'?'本项目原创':source.sourceUrl?'公开仓库固定提交':'导入的源码副本'}</dd></div></dl>
      <p className="reading-copy">{task.environmentNote||(task.sourceKind==='repository-original'?'原始题包使用 Python 标准库；运行方式与修改限制见题面及已有测试。':'依赖未自动安装；按源码中的 README 和依赖清单准备。')}</p>
      {source.sourceCommit&&<p className="muted">提交 <code>{source.sourceCommit}</code></p>}
      <Details title={`查看源码清单 · ${files.length} 个文件`}><ul className="file-manifest">{files.map(f=><li key={f}><code>{f}</code></li>)}</ul></Details></>}
  </section>;
}

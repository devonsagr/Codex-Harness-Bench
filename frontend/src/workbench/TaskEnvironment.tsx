import type {Task,Imported} from './types';
import {Details} from './ui';
import {nativeTaskIds,publicCategories} from './PublicCatalog';
export const needsBaseline=(task:Task)=>task.requiresBaseline||task.taskParadigm==='deterministic-bugfix';
export const canStartTask=(task:Task,baselines:Imported[])=>!!task.publicSource||!needsBaseline(task)||baselines.some(b=>b.id===task.baselineId);
export function TaskEnvironment({task,baselines}:{task:Task;baselines:Imported[]}){
  const source=baselines.find(b=>b.id===task.baselineId);
  const files=source?Object.keys(source.manifest.files):[];
  if(task.publicSource)return <section className="task-environment" aria-label="项目起点与环境"><div className="environment-heading"><h3>{publicCategories[task.publicSource.category]||'已有工程任务'}</h3><span className="readiness ready">{source?'已缓存源码':'创建时下载'}</span></div>
    <p>{source?'复用固定源码缓存，复制到本次新的工作区。':'创建评测时自动下载此题的固定源码，再生成独立工作区。'}</p>
    <p className="muted">{nativeTaskIds.includes(task.publicSource.id)?'支持自动准备 Windows 环境与程序测试验收。':'目标源码自动准备；本机依赖和原测试尚未适配，需在工作区按项目说明准备。'}</p>
    <Details title="文件放在哪里？会重复下载吗？"><ol className="storage-flow"><li><strong>选题后创建</strong><span>仅准备本次选择的题目与固定版本源码。</span></li><li><strong>下载一份缓存</strong><code>.local/arena/baselines/{source?.id||'源码编号'}/files/</code></li><li><strong>复制到本次工作区</strong><code>.local/arena/runs/评测编号/试次编号/workspace/</code></li></ol><p>同一仓库、同一提交校验后复用。做 10 次测试 = 10 个独立工作区，通常只下载 1 次源码；本地副本会各自占空间。缓存损坏或缺失时需重新准备。</p><p>结束交付后，在数据管理清理工作区，仍保留回收版本、评分与源码缓存。缓存目前按共享起点保留，不能跟随一次工作区清理一起删除。</p>{source&&<p className="muted">{files.length} 个源码文件 · 提交 {source.sourceCommit}</p>}</Details></section>;
  return <section className="task-environment" aria-label="项目起点与环境"><div className="environment-heading"><h3>项目起点</h3><span className={'readiness '+(canStartTask(task,baselines)?'ready':'pending')}>{source?'源码已打包':needsBaseline(task)?'待补全源码':'从零构建'}</span></div>
    <p className="reading-copy">{source?'创建评测时，源码与已有测试会自动复制到独立工作区。':needsBaseline(task)?'此题目前只有题面，不能开始修改已有工程。':'这是需求实现题，创建空项目目录，由模型实现项目并准备所需依赖。'}</p>
    {source&&<><dl className="environment-facts"><div><dt>起点快照</dt><dd>{source.name}</dd></div><div><dt>文件</dt><dd>{files.length} 个</dd></div><div><dt>来源</dt><dd>{task.sourceKind==='repository-original'?'本项目原创':source.sourceUrl?'公开仓库固定提交':'导入的源码副本'}</dd></div></dl>
      <p className="reading-copy">{task.environmentNote||(task.sourceKind==='repository-original'?'原始题包使用 Python 标准库；运行方式与修改限制见题面及已有测试。':'依赖未自动安装；按源码中的 README 和依赖清单准备。')}</p>
      {source.sourceCommit&&<p className="muted">提交 <code>{source.sourceCommit}</code></p>}
      <Details title={`查看源码清单 · ${files.length} 个文件`}><ul className="file-manifest">{files.map(f=><li key={f}><code>{f}</code></li>)}</ul></Details></>}
  </section>;
}

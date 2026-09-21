import {useState} from 'react';
import source from '../../../catalog/public-task-sources.json';
import type {State,Act} from './types';
import {Field,Details} from './ui';
const categories:Record<string,string>={bugfix:'修复 Bug',feature_request:'已有工程增加功能',enhancement:'已有工程改进'};
export function PublicTaskSources({state,act,onUse}:{state?:State;act?:Act;onUse?:(id:string)=>void}){
  const [error,setError]=useState('');const [query,setQuery]=useState('');const [language,setLanguage]=useState('');const [category,setCategory]=useState('bugfix');
  const rows=source.tasks.filter(t=>(!language||t.language===language)&&(!category||t.category===category)&&[t.id,t.title,t.repositoryUrl].some(s=>s.toLowerCase().includes(query.trim().toLowerCase())));
  const job=state?.sourceJobs?.find(j=>j.id==='deepswe-download');const running=job?.status==='running';
  const prepare=(taskIds:string[])=>{setError('');return act?.('/sources/prepare',{taskIds}).catch(e=>setError((e as Error).message));};
  return <section className="public-sources space-y-4" aria-label="DeepSWE 题包">
    <div className="source-heading"><div><h3>DeepSWE · {source.tasks.length} 道已有仓库任务</h3><p>4 道 Bug 修复，109 道工程扩展。每题使用固定源码起点。</p></div><a href={source.repository} target="_blank" rel="noreferrer">上游 ↗</a></div>
    <div className="source-filters"><Field label="搜索公开题目"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="任务、编号或仓库"/></Field><Field label="任务类型"><select value={category} onChange={e=>setCategory(e.target.value)}><option value="">全部类型</option>{Object.entries(categories).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></Field><Field label="项目语言"><select value={language} onChange={e=>setLanguage(e.target.value)}><option value="">全部语言</option>{[...new Set(source.tasks.map(t=>t.language))].sort().map(l=><option key={l}>{l}</option>)}</select></Field></div>
    {act&&<div className="source-actions"><button className="btn-primary" disabled={running} onClick={()=>prepare(source.tasks.filter(t=>t.category==='bugfix').map(t=>t.id))}>准备 4 道 Bug 修复源码</button><button className="btn-secondary" disabled={running} onClick={()=>prepare([])}>下载全部题面与验收包</button></div>}
    {error&&<p className="alert-error" role="alert">{error}</p>}
    {job&&<div className="source-progress" role="status"><strong>{running?'正在准备':job.status==='completed'?'下载完成':'准备结果'}</strong><span>{job.phase}</span>{!!job.taskIds.length&&<span>{job.completed.length} / {job.taskIds.length} 份源码已保存</span>}{job.errors.map(e=><p className="alert-error" key={e.taskId}>{e.taskId}：{e.message}</p>)}</div>}
    <p className="muted">显示 {rows.length} 道 · 固定题包 {source.revision.slice(0,12)}</p>
    <div className="public-source-list">{rows.map(t=>{const installed=state?.tasks.find(x=>x.id==='deepswe-'+t.id);const archived=state?.archivedTasks.find(x=>x.id==='deepswe-'+t.id);return <article key={t.id}><div><h4>{t.title}</h4><p>{categories[t.category]} · {t.language} · {t.repositoryUrl.replace('https://github.com/','')}</p><code title={t.baseCommit}>源码 {t.baseCommit.slice(0,12)}</code><p className="muted">{installed?'源码已下载 · 依赖待验证 · 原生验收待接入':archived?'已归档；请从题库恢复':'源码未下载'}</p></div><div className="source-links">{act&&(installed&&onUse?<button className="btn-primary" onClick={()=>onUse(installed.id)}>查看已下载题目</button>:<button className="btn-secondary" disabled={running||!!archived} onClick={()=>prepare([t.id])}>下载源码与题包</button>)}<a href={t.instructionUrl} target="_blank" rel="noreferrer">题面 ↗</a><a href={t.environmentUrl} target="_blank" rel="noreferrer">环境 ↗</a><a href={t.verifierUrl} target="_blank" rel="noreferrer">验收器 ↗</a></div></article>})}{!rows.length&&<p>没有匹配的公开题目。</p>}</div>
    <Details title="下载了什么，运行还缺什么"><p>下载保存全部题面、Linux 环境定义及隐藏验收器；所选目标仓库固定在题目起始提交。参考解不解包，隐藏测试不进入开发目录。启动网站和下载源码不需要 Docker。</p><p>下载不等于依赖已安装。目前可在桌面工作区准备依赖并开发；原生 Linux 环境与官方验收尚未接通，不能给出 DeepSWE 官方通过率。当前通用 AI 评分另行记录。</p><p>题包采用 Apache-2.0，目标工程沿用各自许可。文件保存在项目 .local/arena，不写入公共源码仓库。</p></Details>
  </section>;
}

import {useState} from 'react';
import source from '../../../catalog/public-task-sources.json';
import {Field} from './ui';

export function PublicTaskSources(){
  const [query,setQuery]=useState('');const [language,setLanguage]=useState('');
  const rows=source.tasks.filter(t=>(!language||t.language===language)&&[t.id,t.title,t.repositoryUrl].some(s=>s.toLowerCase().includes(query.trim().toLowerCase())));
  return <section className="public-sources space-y-4" aria-label="公开题源索引">
    <div className="source-heading"><div><h3>DeepSWE · {source.tasks.length} 道公开任务</h3><p>已核对题目定义，待接入桌面工作区与原生验收器。</p></div><a href={source.repository} target="_blank" rel="noreferrer">官方仓库 ↗</a></div>
    <div className="source-filters"><Field label="搜索公开题目"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="任务名称、编号或仓库"/></Field><Field label="项目语言"><select value={language} onChange={e=>setLanguage(e.target.value)}><option value="">全部语言</option>{[...new Set(source.tasks.map(t=>t.language))].sort().map(l=><option key={l}>{l}</option>)}</select></Field></div>
    <p className="muted">{rows.length} / {source.tasks.length} 道 · 来源版本 {source.revision.slice(0,12)} · 核对日期 {source.checkedAt}</p>
    <div className="public-source-list">{rows.map(t=><article key={t.id}><div><h4>{t.title}</h4><p>{t.language} · {t.repositoryUrl.replace('https://github.com/','')}</p><code title={t.baseCommit}>起点 {t.baseCommit.slice(0,12)}</code></div><div className="source-links"><a href={t.instructionUrl} target="_blank" rel="noreferrer">题面 ↗</a><a href={t.environmentUrl} target="_blank" rel="noreferrer">环境 ↗</a><a href={t.verifierUrl} target="_blank" rel="noreferrer">验收器 ↗</a></div></article>)}{!rows.length&&<p>没有匹配的公开题目。</p>}</div>
    <p className="muted">此索引不计入可运行题数，也不会下载项目、安装依赖或启动任务。题目定义采用 Apache-2.0；目标工程沿用各自许可。</p>
  </section>;
}

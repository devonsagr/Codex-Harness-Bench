import type {BehaviorAcceptance as Report} from './types';
import {useState} from 'react';
import {request} from './api';
import {Details} from './ui';

export function BehaviorAcceptance({report,disabled,run,route}:{report:Report;disabled:boolean;run:()=>void;route:string}){
  const [image,setImage]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const show=async(path:string)=>{setLoading(true);setImage('');setError('');try{const r=await request<{image:string}>(route+'/behavior-image',{attemptId:report.attemptId,path});setImage(r.image);}catch(e){setError((e as Error).message);}finally{setLoading(false);}};
  const words={passed:'通过',failed:'失败',unverified:'待验证'};
  return <section className="behavior-acceptance" aria-label="专项功能验收">
    <div className="behavior-heading"><div><h3>专项功能验收</h3><p>{report.passed} 通过 · {report.failed} 失败 · {report.unverified} 待验证 / {report.total} 项</p></div><button className="btn-secondary" disabled={disabled} onClick={run}>{report.at?'重新检查':'开始检查'} · 不调用 AI</button></div>
    {report.failed>0&&<p role="status" className="score-notice"><strong>已发现功能检查失败。</strong>下方 AI 高分不能抵消这些结果，当前产物不能用于配置成绩对比。</p>}
    <div className="behavior-grid">{report.rows.map(row=><details key={row.id} className={'behavior-row behavior-'+row.status}><summary><strong>{row.label}</strong><span>{words[row.status]}</span></summary><p>{row.detail}</p>{Object.keys(row.evidence).length>0&&<pre className="source">{JSON.stringify(row.evidence,null,2)}</pre>}</details>)}</div>
    <p className="muted">还未覆盖：{report.uncovered} 上述通过数量只针对列出的程序检查，不折算成整题分或审美分。定位或环境异常保留待验证。</p>
    {!!report.images.length&&<Details title={`程序保存的场景截图 · ${report.images.length} 张`}><p className="muted">选择操作前后画面，文件名与上方证据哈希对应。</p><select aria-label="专项验收截图" disabled={loading} defaultValue="" onChange={e=>{if(e.target.value)void show(e.target.value);}}><option value="">选择截图</option>{report.images.map((name,i)=><option key={name} value={name}>{i+1} · {name.slice(0,16)}</option>)}</select>{image&&<img className="review-screenshot" src={image} alt="专项功能检查保存的场景画面"/>}{error&&<p role="alert">{error}</p>}</Details>}
    <Details title="检查版本与证据"><p>{report.version} · 已取得结论 {report.coverage}%（仅限上述检查）</p><p>快照：<code>{report.captureHash}</code></p><p>镜像：<code>{report.imageId||'尚未运行'}</code></p><p>原始 AI 报告、冻结评分权重与历史结果保留。重新检查使用同一快照和固定镜像。</p></Details>
  </section>;
}

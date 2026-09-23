import {useState} from 'react';
import type {Run,Trial,Act} from './types';
import {Dialog,Field,Details,Panel,date,ScoreSlider} from './ui';
import {request} from './api';

type Assessment={id:string;at:string;score:number;coverage:number;method:string;ratings:Record<string,{score:number;reason:string}>};
type Status={files:string[];documents:string[];scripts:Record<string,unknown>;captureHash:string;inspections:{id:string;path:string}[];assessments:Assessment[]};
export function HumanInspection({run,trial,disabled,act}:{run:Run;trial:Trial;disabled:boolean;act:Act}){
  const [open,setOpen]=useState(false),[captureId,setCaptureId]=useState(trial.captures[trial.captures.length-1]!.id);
  const [status,setStatus]=useState<Status|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [file,setFile]=useState<{path:string;text?:string;image?:string;truncated?:boolean}|null>(null);
  const [search,setSearch]=useState('');
  const [method,setMethod]=useState('source'),[previewUrl,setUrl]=useState(''),[reviewed,setReviewed]=useState(false);
  const [ratings,setRatings]=useState<Record<string,{score:string;reason:string}>>({});
  const task=run.tasks.find(t=>t.id===trial.taskId)!;
  const dimensions=Object.entries(run.policy.dimensions).filter(([k,w])=>w>0&&(k!=='ux'||task.hasFrontendUI));
  const route=`/runs/${run.id}/trials/${trial.id}/`;
  async function perform(action:string,data:Record<string,unknown>={},id=captureId){
    setBusy(true);setError('');
    try{const result=await (['inspection-status','inspection-file'].includes(action)?request(route+action,{...data,captureId:id}):act(route+action,{...data,captureId:id}));if(action!=='inspection-file')setStatus(await request<Status>(route+'inspection-status',{captureId:id}));return result;}
    catch(e){setError(e instanceof Error?e.message:String(e));return null;}finally{setBusy(false);}
  }
  const inspection=status?.inspections[status.inspections.length-1];
  // Link only after local validation. This never fetches an arbitrary URL on the server.
  const preview=(()=>{try{const u=new URL(previewUrl);return u.protocol==='http:'&&['localhost','127.0.0.1','[::1]'].includes(u.hostname)&&!!u.port&&!['8765','8877',location.port].includes(u.port)&&!u.username&&!u.password&&!u.search&&!u.hash?u.href:null;}catch{return null;}})();
  return <><Panel title="查看交付 · 人工复核" aside={<button className="btn-secondary" onClick={()=>{setOpen(true);void perform('inspection-status');}}>查看产物与复核</button>}><p className="muted">查看文件、图片或运行独立副本，再按实际观察评分。无需等待 AI 成功；人工参考分单独保存。</p></Panel>
    <Dialog title="人工复核 · 回收版本" open={open} onClose={()=>setOpen(false)}>
      <Field label="复核版本"><select disabled={busy} value={captureId} onChange={e=>{const id=e.target.value;setCaptureId(id);setFile(null);setSearch('');setUrl('');setRatings({});setReviewed(false);setStatus(null);void perform('inspection-status',{},id);}}>{trial.captures.map((c,i)=><option key={c.id} value={c.id}>回收 {i+1} · {c.id}</option>)}</select></Field>
      {error&&<p role="alert" className="alert-error">{error}</p>}
      {status&&<><Field label="搜索产物文件"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="文件名或路径"/></Field><div className="inspection-browser"><Field label={`产物文件 · ${status.files.length}`}><select size={9} aria-label="选择复核文件" disabled={busy} value={file?.path||''} onChange={e=>void perform('inspection-file',{path:e.target.value}).then(r=>{if(r)setFile(r as typeof file);})}>{status.files.filter(p=>p.toLowerCase().includes(search.toLowerCase())).map(p=><option key={p}>{p}</option>)}</select></Field><div className="inspection-preview">{file?.image?<img src={file.image} alt={file.path}/>:file?<><strong>{file.path}</strong><pre className="source">{file.text}</pre>{file.truncated&&<p>内容已截断，请在副本中查看完整文件。</p>}</>:<p className="muted">选择文件查看。HTML 和脚本只显示源码；运行体验请使用下方的独立副本。</p>}</div></div>
      <Details title="运行与界面体验"><p>从此快照创建独立副本，在副本中安装依赖并启动项目。不会改动回收快照或原工作区。</p><p className="muted">运行说明：{status.documents.join('、')||'产物未提供 README / 运行说明'}。以下仅展示项目声明的脚本，不自动执行。</p>{Object.entries(status.scripts).map(([name,command])=><pre className="source" key={name}>{name}: {String(command)}</pre>)}<div className="run-actions"><button className="btn-secondary" disabled={busy||disabled} onClick={()=>void perform('inspection-prepare')}>{inspection?'再建一个副本':'创建审查副本'}</button>{inspection&&<><button className="btn-secondary" disabled={busy||disabled} onClick={()=>void perform('inspection-open',{inspectionId:inspection.id})}>打开副本文件夹</button><button className="btn-secondary" onClick={()=>void navigator.clipboard.writeText(`请在这个人工审查副本中阅读运行说明，安装依赖并启动项目供我体验：\n${inspection.path}\n不要改动原工作区或回收快照。请报告实际启动地址与运行失败原因。`).catch(()=>setError('复制失败，请手动复制路径。'))}>复制启动说明给 Codex</button></>}</div>{inspection&&<p className="muted break-all">{inspection.path}</p>}<Field label="启动后的本机预览地址"><input value={previewUrl} onChange={e=>setUrl(e.target.value)} placeholder="http://127.0.0.1:3000"/></Field>{preview&&<a className="btn-secondary" href={preview} target="_blank" rel="noreferrer">打开项目预览 ↗</a>}<p className="muted">此入口不会自动启动项目。请实际操作界面、键盘及关键流程后再评价；仅阅读代码不能证明交互好坏。</p></Details>
      <Details title="填写独立人工评价"><fieldset disabled={busy||disabled}><Field label="实际复核方式"><select value={method} onChange={e=>setMethod(e.target.value)}><option value="source">阅读文件 / 代码</option><option value="runtime">运行项目与测试</option><option value="visual">实际体验界面与交互</option></select></Field>{dimensions.map(([key])=><div className="inspection-rating" key={key}><ScoreSlider label={run.policy.rubrics?.[key]?.label||key} value={ratings[key]?.score||''} onChange={score=>setRatings({...ratings,[key]:{score,reason:ratings[key]?.reason||''}})}/><textarea aria-label={(run.policy.rubrics?.[key]?.label||key)+'人工依据'} value={ratings[key]?.reason||''} onChange={e=>setRatings({...ratings,[key]:{score:ratings[key]?.score||'',reason:e.target.value}})} placeholder="实际观察、操作步骤、文件或截图依据；没检查的项留空"/></div>)}<label className="check-row"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>我已实际查看所选版本，以上是我的复核记录</label><button className="btn-primary" disabled={!reviewed} onClick={()=>void perform('inspection-save',{reviewed,method,previewUrl,ratings:Object.fromEntries(Object.entries(ratings).filter(([,v])=>v.score!=='').map(([k,v])=>[k,{score:Number(v.score),reason:v.reason}]))}).then(r=>{if(r){setRatings({});setReviewed(false);}})}>保存人工参考分</button></fieldset><p className="muted">分数仅供参考。只按已评分维度计算，并单列覆盖率；不替代原测试、AI 原分或现有人工修正。</p></Details>
      {!!status.assessments.length&&<Details title={`人工复核历史 · ${status.assessments.length}`}>{status.assessments.slice().reverse().map(a=><article key={a.id}><strong>{a.score} 分 · 覆盖 {a.coverage}%</strong><p className="muted">{date(a.at)} · {{source:'文件阅读',runtime:'实际运行',visual:'界面体验'}[a.method]}</p>{Object.entries(a.ratings).map(([k,v])=><p key={k}>{run.policy.rubrics?.[k]?.label||k}：{v.score} · {v.reason}</p>)}</article>)}</Details>}</>}
    </Dialog></>;
}

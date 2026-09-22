import {useState} from 'react';
import type {Task,Trial} from './types';
import {Panel,Details,Field} from './ui';
import {request} from './api';
import {nativeTaskIds} from './PublicCatalog';

export function NativeVerification({task,trial,route,disabled,action}:{task:Task;trial:Trial;route:string;disabled:boolean;action:(name:string,data?:unknown)=>Promise<unknown>}){
  const [suite,setSuite]=useState('1');const [output,setOutput]=useState('');const [error,setError]=useState('');
  if(!nativeTaskIds.includes(task.publicSource?.id||''))return null;
  const suiteNames=task.publicSource?.id==='yaegi-go-embed-directives'?['既有解释器回归','Embed 功能验收']:['解析器','脚本','编译器','编译作用域','编译实例','源码模块','目标功能验收'];
  const capture=trial.captures[trial.captures.length-1];const reports=capture?.nativeVerifications||[];const result=reports[reports.length-1];
  const busy=['checking','judging'].includes(trial.state);const execution=trial.nativeExecution;
  const read=async()=>{setError('');try{const r=await request<{output:string;truncated:boolean}>(route+'/native-log',{suite:Number(suite)});setOutput((r.truncated?'仅显示末尾输出\n':'')+r.output);}catch(e){setError((e as Error).message);}};
  return <Panel title="项目测试验收" aside={<span className="badge">无需 Docker · 不调用模型</span>}>
    <p className="muted">执行上游隐藏测试，分别检查目标功能与既有功能回归。Windows / Go 适配环境，不作为上游 Linux 排行榜成绩。</p>
    {result?<div className="native-results"><div><span>目标测试</span><strong>{result.f2p_passed}<small> / {result.f2p_total}</small></strong><progress aria-label="目标测试通过数" max={result.f2p_total} value={result.f2p_passed}/></div><div><span>原有功能回归</span><strong>{result.p2p_passed}<small> / {result.p2p_total}</small></strong><progress aria-label="回归测试通过数" max={result.p2p_total} value={result.p2p_passed}/></div><div><span>最近完成的验收</span><strong>{result.reward===1?'通过':'未通过'}</strong><span>{result.seconds} 秒 · {result.goVersion}</span></div></div>:<p>回收产物后，运行测试即可获得结果；环境异常不会记成零分。</p>}
    <div className="source-actions"><button className="btn-primary" disabled={disabled||busy||!capture} onClick={()=>void action('native-check',{captureId:capture?.id})}>{result?'重新运行测试':'运行测试验收'}</button>{busy&&execution?.status==='running'&&<button className="btn-secondary" disabled={disabled} onClick={()=>void action('stop')}>停止测试</button>}</div>
    {execution&&trial.lastJobError?.kind!=='native'&&<p className="muted" role="status">{execution.phase}</p>}
    {trial.lastJobError?.kind==='native'&&<p role="alert" className="alert-error">{trial.lastJobError.message}</p>}
    <Details title="查看测试过程与输出"><p className="muted">每次在临时副本运行，禁止联网，写入限于副本。Windows 命令沙箱允许读取宿主文件，并非完整虚拟机隔离。</p><div className="source-actions"><Field label="测试组"><select value={suite} onChange={e=>{setSuite(e.target.value);setOutput('');}}>{suiteNames.map((s,i)=><option key={s} value={i+1}>{i+1}. {s}</option>)}</select></Field><button className="btn-secondary" onClick={()=>void read()}>刷新输出</button></div>{error&&<p className="alert-error">{error}</p>}{output&&<pre className="source">{output}</pre>}{result&&<p className="muted break-all">日志：{result.logDirectory}</p>}</Details>
    {!!result?.notPassed.length&&<Details title={`未通过测试 · ${result.notPassed.length}`}><ul>{result.notPassed.map(n=><li className="muted break-all" key={n}>{n}</li>)}</ul></Details>}
    {reports.length>1&&<Details title={`此快照历次测试 · ${reports.length}`}><ul>{reports.map(r=><li key={r.id}>{r.at} · 修复 {r.f2p_passed}/{r.f2p_total} · 回归 {r.p2p_passed}/{r.p2p_total} · {r.reward?'通过':'未通过'}</li>)}</ul></Details>}
  </Panel>;
}

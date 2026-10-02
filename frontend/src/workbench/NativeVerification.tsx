import {useState} from 'react';
import type {Task,Trial} from './types';
import {Panel,Details,Field,num} from './ui';
import {request} from './api';
import {nativeTaskIds,upstreamDockerTaskIds} from './PublicCatalog';
import {nativeTestProgress} from './scoreExplanation';

export function NativeVerification({task,trial,route,disabled,action}:{task:Task;trial:Trial;route:string;disabled:boolean;action:(name:string,data?:unknown)=>Promise<unknown>}){
  const [suite,setSuite]=useState('1');const [output,setOutput]=useState('');const [error,setError]=useState('');const [copied,setCopied]=useState('');
  const upstream=upstreamDockerTaskIds.includes(task.publicSource?.id||'');
  if(!nativeTaskIds.includes(task.publicSource?.id||'')&&!upstream)return null;
  const setupPrompt=`请为 Codex Harness Bench 的 DeepSWE 题 ${task.publicSource?.id||task.id} 配置本机原题程序验收。先检查 docker info 是否能连接 Docker Desktop Linux 引擎；未安装时按 Docker 官方 Windows 指南准备 Docker Desktop 和 WSL 2。只修复实际检测失败的依赖，保留现有 Docker 镜像、工作区、回收快照、Codex 登录和全局配置；不要重置 Docker 数据或修改评分。引擎可用后回到本题现有回收版本点击“运行测试验收”，保存 F2P/P2P、reward 和日志。环境失败保持未验收，不能填零分或 AI 参考分。请逐项说明检查结果和实际修改。`;
  const suiteNames=upstream?['上游 test.sh 原题验收']:task.publicSource?.id==='yaegi-go-embed-directives'?['既有解释器回归','Embed 功能验收']:['解析器','脚本','编译器','编译作用域','编译实例','源码模块','目标功能验收'];
  const capture=trial.captures[trial.captures.length-1];const reports=capture?.nativeVerifications||[];
  const result=reports.find(report=>report.id===trial.score.nativeVerificationId&&report.captureHash===capture.manifest.sha256);
  const progress=nativeTestProgress(trial);
  const busy=['checking','judging'].includes(trial.state);const execution=trial.nativeExecution;
  const read=async()=>{setError('');try{const r=await request<{output:string;truncated:boolean}>(route+'/native-log',{suite:Number(suite)});setOutput((r.truncated?'仅显示末尾输出\n':'')+r.output);}catch(e){setError((e as Error).message);}};
  return <Panel title="项目测试验收" aside={<span className="badge">{upstream?'上游 Linux / Docker':'Windows Go · 无需 Docker'} · 不调用模型</span>}>
    <p className="muted">执行原题隐藏测试，分别检查目标功能与既有功能回归。{upstream?'固定上游 Linux 镜像；桌面执行条件与官方榜单不同，不作为官方提交成绩。':'Windows / Go 适配环境，不作为上游 Linux 排行榜成绩。'}</p>
    {result?<><div className="native-results"><div><span>目标测试完成比例</span><strong>{num(progress?.target)}%<small> · {result.f2p_passed} / {result.f2p_total}</small></strong><progress aria-label="目标测试通过数" max={result.f2p_total} value={result.f2p_passed}/></div><div><span>旧功能回归通过比例</span><strong>{num(progress?.regression)}%<small> · {result.p2p_passed} / {result.p2p_total}</small></strong><progress aria-label="回归测试通过数" max={result.p2p_total} value={result.p2p_passed}/></div><div><span>上游原题结果 · {result.reward} / 1</span><strong>{result.reward===1?'通过':'未通过'}</strong><span>{result.seconds} 秒 · {result.goVersion||result.imageId?.slice(0,20)||'固定环境'}</span></div></div><p>上述程序结果已成立，不需要AI再打一次分。没通过也有有效结果，并保留在失败统计中；目标测试比例用于观察进展，不替代整题通过。</p></>:<p>回收产物后，运行测试即可获得结果；{upstream?'会自动尝试启动 Docker Desktop Linux 引擎。':''}环境异常不会记成零分，也无需让模型重新做题。</p>}
    <div className="source-actions"><button className="btn-primary" disabled={disabled||busy||!capture} onClick={()=>void action('native-check',{captureId:capture?.id})}>{result?'重新运行测试':'运行测试验收'}</button>{busy&&execution?.status==='running'&&<button className="btn-secondary" disabled={disabled} onClick={()=>void action('stop')}>停止测试</button>}</div>
    {execution&&trial.lastJobError?.kind!=='native'&&<p className="muted" role="status">{execution.phase}</p>}
    {trial.lastJobError?.kind==='native'&&<p role="alert" className="alert-error">{trial.lastJobError.message}</p>}
    {trial.score.taskScorecard&&<Details title="本地连续质量分（独立于原题通过）"><p>{trial.score.taskScorecard.version} · 总权重 100 分，目标语义组70、回归20、工程维护性10。仅后一项需要AI质量取证；缺少它不会抹掉上方的程序结果。</p><div className="native-scorecard-items">{trial.score.taskScorecard.items.map(item=><Details key={item.label} title={<span className="contribution-title"><strong>{item.label}</strong><span>权重 {item.weight} · 得 {item.points==null?'待补证据':item.points.toFixed(1)} 分</span></span>}><p className="break-all">{item.evidence}</p></Details>)}</div></Details>}
    {upstream&&<Details title="Docker 环境配置与复制提示词"><p>点击上方按钮会自动检查并尝试启动 Docker Desktop。若本机引擎损坏，自动启动仍可能失败；当前快照和评分记录会保留。开源使用者可将下面的提示词交给本地技术助手检查环境。</p><button className="btn-secondary" type="button" onClick={()=>void navigator.clipboard.writeText(setupPrompt).then(()=>setCopied('已复制配置提示词')).catch(()=>setCopied('复制失败，请手动选择下方文字'))}>复制环境配置提示词</button>{copied&&<span role="status" className="muted">{copied}</span>}<pre className="source whitespace-pre-wrap">{setupPrompt}</pre><a href="https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/" target="_blank" rel="noreferrer">Docker Desktop 官方排障说明 ↗</a></Details>}
    <Details title="查看测试过程与输出"><p className="muted">{upstream?'在固定 Linux 镜像副本中运行，容器禁网，只挂载本次补丁、固定测试和输出目录。':'每次在临时副本运行，禁止联网，写入限于副本。Windows 命令沙箱允许读取宿主文件，并非完整虚拟机隔离。'}</p><div className="native-log-actions"><Field label="测试组"><select value={suite} onChange={e=>{setSuite(e.target.value);setOutput('');}}>{suiteNames.map((s,i)=><option key={s} value={i+1}>{i+1}. {s}</option>)}</select></Field><button className="btn-secondary" onClick={()=>void read()}>刷新输出</button></div>{error&&<p className="alert-error">{error}</p>}{output&&<pre className="source">{output}</pre>}{result&&<p className="muted break-all">日志：{result.logDirectory}</p>}</Details>
    {!!result?.notPassed.length&&<Details title={`未通过测试 · ${result.notPassed.length}`}><ul>{result.notPassed.map(n=><li className="muted break-all" key={n}>{n}</li>)}</ul></Details>}
    {reports.length>1&&<Details title={`此快照历次测试 · ${reports.length}`}><ul>{reports.map(r=><li key={r.id}>{r.at} · 修复 {r.f2p_passed}/{r.f2p_total} · 回归 {r.p2p_passed}/{r.p2p_total} · {r.reward?'通过':'未通过'}</li>)}</ul></Details>}
  </Panel>;
}

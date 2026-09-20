import {useEffect,useState} from 'react';
import type {Act,Config} from './types';
import {request} from './api';
import {Field,Details,Dialog} from './ui';
type Receipt={id:string;configName:string;status:string;message:string;home:string;configRevision:number;filesMatch?:boolean;canPreserveChanges?:boolean;fileChecks?:{path:string;matches:boolean}[]};
type Host={home:string;instructionsFile:string;connections:Record<string,{id:string;enabled:boolean}[]>;applications:Receipt[]};

export function CodexApply({config,act,save,trialRoute,disabled=false,compact=false}:{config:Config;act:Act;save?:()=>Promise<Config>;trialRoute?:string;disabled?:boolean;compact?:boolean}){
  const [expanded,setExpanded]=useState(false);const [host,setHost]=useState<Host|null>(null);const [error,setError]=useState('');const [result,setResult]=useState('');
  const refresh=()=>request<Host>('/codex/status',{}).then(setHost);
  useEffect(()=>{let live=true;request<Host>('/codex/status',{}).then(h=>{if(live)setHost(h);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[]);
  const active=host?.applications.find(r=>['applying','applied','restore_failed'].includes(r.status));
  const apply=async()=>{setError('');try{const c=save?await save():config;const r=await act<Receipt>(trialRoute||'/codex/switch',{configId:c.id,revision:c.revision});setResult(r.message);await refresh();}catch{await refresh().catch(()=>{});}};
  const undo=async(preserveUnrelated=false)=>{setError('');try{const r=await act<Receipt>('/codex/restore',{applicationId:active?.id,preserveUnrelated});setResult(r.message);await refresh();}catch{await refresh().catch(()=>{});}};
  const content=<section className="codex-apply space-y-3"><h3 className="font-semibold">应用到 Codex</h3>
    <p className="muted">写入本机全局配置并备份；新任务使用，已有任务不保证切换。</p>
    <div className="flex gap-3 flex-wrap items-center"><button type="button" className="btn-primary" disabled={disabled||!host||(!save&&!config.id)} onClick={()=>void apply()}>{save?'保存并应用到 Codex':active?'切换为本题配置':'应用到 Codex'}</button>{active&&<button type="button" className="btn-secondary" disabled={disabled} onClick={()=>void undo()}>撤销上次应用</button>}<button type="button" className="btn-ghost" onClick={()=>{setError('');void refresh().catch(e=>setError(e.message));}}>核对当前文件</button></div>
    {active&&<p role="status" className="text-sm">{active.configName} · v{active.configRevision}：{active.status==='applied'?(active.filesMatch?'写入文件与回执一致':'应用后文件已变化，请展开核对'):'应用尚未完整结束，请核对回执'}</p>}
    {active?.filesMatch===false&&<div className="score-notice space-y-3"><p className="text-sm">发生变化：{active.fileChecks?.filter(f=>!f.matches).map(f=>f.path).join('、')}。这不等于配置全部失效。</p>{active.canPreserveChanges?<><p className="muted">可仅撤销工作台写入的设置，保留后来添加的项目、注释和其他设置；撤销后再应用本题配置。</p><button type="button" className="btn-secondary" disabled={disabled} onClick={()=>void undo(true)}>保留其他修改并撤销</button></>:<p className="muted">规则、技能或本工具写入的设置存在冲突。请在“写入位置与当前状态”核对文件，处理冲突后再点“核对当前文件”；当前文件和原备份均保留。</p>}</div>}
    <Details title="写入位置与当前状态"><p className="muted break-all">{host?.home||'读取中…'}</p><p className="text-sm">规则来源：{host?.instructionsFile||'读取中…'}。使用 AGENTS.override.md 时，Codex 个性化页会提示原 AGENTS.md 被覆盖；这是文件优先级提示。</p><p className="muted">模型与原生设置写入 config.toml；规则写入 AGENTS.override.md；选定技能放入 skills。文件匹配只能确认落盘，项目覆盖、任务选择及桌面重载仍影响实际值。</p>{active?.fileChecks?.map(f=><p className="text-sm break-all" key={f.path}>{f.path} · {f.matches?'与应用回执一致':'已变化或缺失'}</p>)}</Details>
    {error&&<p role="alert" className="alert-error">{error}</p>}{result&&<p role="status" className="muted">{result}</p>}
  </section>;
  return compact?<><div className="config-apply-entry"><button className="btn-secondary" onClick={()=>setExpanded(true)}>Codex 配置</button>{error?<button className="run-status-warning" onClick={()=>setExpanded(true)}>状态读取失败</button>:active&&<button className={active.filesMatch===false||active.status!=='applied'?'run-status-warning':'btn-ghost'} onClick={()=>setExpanded(true)}>{active.status!=='applied'?'应用待核对':active.filesMatch===false?'配置文件已变化':'已应用 · 查看'}</button>}</div><Dialog title="Codex 配置应用" open={expanded} onClose={()=>setExpanded(false)}>{content}{disabled&&<p className="muted">本试次已开始或已归档，不能在这里更换已冻结的配置。</p>}</Dialog></>:content;
}

export function NativeConfigFields({config,change}:{config:Config;change:(patch:Partial<Config>)=>void}){
  const [host,setHost]=useState<Host|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let live=true;request<Host>('/codex/status',{}).then(h=>{if(live)setHost(h);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[]);
  const fields:[string,string,string[]][]=[['web_search','联网搜索',['disabled','cached','live']],['model_verbosity','输出详细程度',['low','medium','high']],['model_reasoning_summary','推理摘要',['auto','concise','detailed','none']]];
  return <section className="space-y-4"><h3 className="font-semibold">Codex 原生配置</h3><div className="grid md:grid-cols-3 gap-4">{fields.map(([key,label,values])=><Field key={key} label={label}><select value={config.nativeSettings?.[key]||''} onChange={e=>{const next={...config.nativeSettings};if(e.target.value)next[key]=e.target.value;else delete next[key];change({nativeSettings:next});}}><option value="">保持宿主设置</option>{values.map(v=><option key={v}>{v}</option>)}</select></Field>)}</div>
    <h3 className="font-semibold">工具与插件</h3><p className="muted">MCP 是工具连接；Superpowers 等是插件包，可能同时包含 Skills、钩子和依赖。这里管理本机已有配置的启用状态；安装与授权在 Codex 插件页完成。</p>
    {error&&<p role="alert" className="alert-error">{error}</p>}{['mcp_servers','plugins'].map(group=><div key={group}><h4 className="text-sm font-medium">{group==='plugins'?'插件（包括 Superpowers）':'MCP 工具连接'}</h4>{host?.connections[group]?.length?host.connections[group].map(item=><Field key={item.id} label={item.id}><select value={config.integrations?.[group]?.[item.id]===undefined?'inherit':String(config.integrations[group][item.id])} onChange={e=>{const next={...config.integrations?.[group]};if(e.target.value==='inherit')delete next[item.id];else next[item.id]=e.target.value==='true';change({integrations:{...config.integrations,[group]:next}});}}><option value="inherit">保持当前（{item.enabled?'启用':'停用'}）</option><option value="true">启用</option><option value="false">停用</option></select></Field>):<p className="muted">config.toml 中未发现此类配置。其他安装来源状态未知，不代表未安装。</p>}</div>)}
    <p className="muted">权限/沙箱、Hooks、记忆、子代理和项目规则同样属于运行条件；本轮保留宿主值，尚不提供迁移。密钥与认证不会导入工作台。</p>
  </section>;
}

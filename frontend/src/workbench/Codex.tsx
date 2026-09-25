import {useEffect,useState} from 'react';
import type {Act,Config} from './types';
import {request} from './api';
import {Field,Details,Dialog} from './ui';
type Receipt={id:string;configId:string;configName:string;status:string;message:string;home:string;configRevision:number;filesMatch?:boolean;settingsMatch?:boolean;canPreserveChanges?:boolean;fileChecks?:{path:string;matches:boolean;managedMatches:boolean}[]};
type Host={model?:string;reasoning?:string;serviceTier?:string;home:string;instructionsFile:string;connections:Record<string,{id:string;enabled:boolean}[]>;applications:Receipt[]};

export function CodexApply({config,act,save,trialRoute,disabled=false,compact=false}:{config:Config;act:Act;save?:()=>Promise<Config>;trialRoute?:string;disabled?:boolean;compact?:boolean}){
  const [expanded,setExpanded]=useState(false);const [host,setHost]=useState<Host|null>(null);const [error,setError]=useState('');const [result,setResult]=useState('');
  const refresh=()=>request<Host>('/codex/status',{}).then(setHost);
  useEffect(()=>{let live=true;request<Host>('/codex/status',{}).then(h=>{if(live)setHost(h);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[]);
  const active=host?.applications.find(r=>['applying','applied','restore_failed'].includes(r.status));
  const speed=config.serviceTier==='fast'?'Fast':config.serviceTier==='standard'?'标准速度':'沿用宿主速度';
  const fileMismatch=!!host&&(host.model!==config.baseModel||(config.reasoning?host.reasoning!==config.reasoning:!!host.reasoning)||(config.serviceTier&&host.serviceTier!==config.serviceTier));
  const apply=async()=>{setError('');try{const c=save?await save():config;const r=await act<Receipt>(trialRoute||'/codex/switch',{configId:c.id,revision:c.revision});setResult(r.message);await refresh();}catch{await refresh().catch(()=>{});}};
  const undo=async(preserveUnrelated=false)=>{setError('');try{const r=await act<Receipt>('/codex/restore',{applicationId:active?.id,preserveUnrelated});setResult(r.message);await refresh();}catch{await refresh().catch(()=>{});}};
  const content=<section className="codex-apply space-y-3"><h3 className="font-semibold">应用到 Codex</h3>
    <p className="muted">点击应用会备份并写入所选模型、思考档位、速度、规则与 Skills，不需要逐项手工切换。已有 Codex 对话不会自动改模型；请在新桌面任务里核对实际选择。</p>
    <dl className="config-facts"><dt>将使用的模型</dt><dd>{config.baseModel}</dd><dt>思考档位</dt><dd>{config.reasoning||'模型默认'}</dd><dt>速度</dt><dd>{speed}</dd><dt>Skills</dt><dd>{config.skills.length} 个已选技能</dd></dl>
    {fileMismatch&&<p role="status" className="score-notice">当前全局文件读回值与本配置不同。应用后请再次核对；工作区的项目设置和桌面当前任务也可能覆盖全局值。</p>}
    <div className="flex gap-3 flex-wrap items-center"><button type="button" className="btn-primary" disabled={disabled||!host||(!save&&!config.id)} onClick={()=>void apply()}>{save?'保存并应用到 Codex':trialRoute&&active?.configId===config.id&&active.configRevision===config.revision&&active.settingsMatch?'确认用于这批题':active?'切换为本题配置':'应用到 Codex'}</button>{active&&<button type="button" className="btn-secondary" disabled={disabled} onClick={()=>void undo(active.filesMatch===false&&active.canPreserveChanges===true)}>撤销上次应用</button>}<button type="button" className="btn-ghost" onClick={()=>{setError('');void refresh().catch(e=>setError(e.message));}}>核对当前文件</button></div>
    {active&&<p role="status" className="text-sm">{active.configName} · v{active.configRevision}：{active.status==='applied'?(active.settingsMatch?(active.filesMatch?'所选设置已应用':'所选设置仍一致；Codex 的其他设置后来有变化'):'所选设置已变化，请核对后再打开新题'):'应用尚未完整结束，请核对回执'}</p>}
    {active?.settingsMatch===false&&<div className="score-notice space-y-3"><p className="text-sm">本配置写入的设置发生变化：{active.fileChecks?.filter(f=>!f.managedMatches).map(f=>f.path).join('、')}。</p><p className="muted">请在“写入位置与当前状态”核对差异；运行中的任务结束前不要切换全局配置。</p></div>}
    <Details title="写入位置与当前状态"><p className="text-sm">当前全局文件：{host?.model||'默认模型'} · {host?.reasoning||'默认档位'} · {host?.serviceTier==='fast'?'Fast':host?.serviceTier==='standard'?'标准速度':'沿用默认速度'}。这是文件读回值，不代表已运行对话的实际值。</p><p className="muted break-all">{host?.home||'读取中…'}</p><p className="text-sm">规则来源：{host?.instructionsFile||'读取中…'}。使用 AGENTS.override.md 时，Codex 个性化页会提示原 AGENTS.md 被覆盖；这是文件优先级提示。</p><p className="muted">模型、速度与原生设置写入 config.toml；规则写入 AGENTS.override.md；选定技能放入 skills。文件匹配只能确认落盘，项目覆盖、任务选择及桌面重载仍影响实际值。</p>{active?.fileChecks?.map(f=><p className="text-sm break-all" key={f.path}>{f.path} · {f.matches?'与应用回执一致':f.managedMatches?'文件有其他变化，本配置写入的设置一致':'本配置写入的设置已变化或缺失'}</p>)}</Details>
    {error&&<p role="alert" className="alert-error">{error}</p>}{result&&<p role="status" className="muted">{result}</p>}
  </section>;
  return compact?<><div className="config-apply-entry"><button className="btn-secondary" onClick={()=>setExpanded(true)}>查看 Codex 配置</button>{error?<button className="run-status-warning" onClick={()=>setExpanded(true)}>状态读取失败</button>:fileMismatch?<button className="run-status-warning" onClick={()=>setExpanded(true)}>模型 / 档位 / 速度待核对</button>:active&&<button className={active.settingsMatch===false||active.status!=='applied'?'run-status-warning':'btn-ghost'} onClick={()=>setExpanded(true)}>{active.status!=='applied'?'应用待核对':active.settingsMatch===false?'所选设置已变化':'所选设置已应用'}</button>}</div><Dialog title="Codex 配置应用" open={expanded} onClose={()=>setExpanded(false)}>{content}{disabled&&<p className="muted">本试次已开始或已归档，不能在这里更换已保存的配置版本。</p>}</Dialog></>:content;
}

export function NativeConfigFields({config,change}:{config:Config;change:(patch:Partial<Config>)=>void}){
  const [host,setHost]=useState<Host|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let live=true;request<Host>('/codex/status',{}).then(h=>{if(live)setHost(h);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[]);
  const fields:[string,string,string[]][]=[['web_search','联网搜索',['disabled','cached','live']],['model_verbosity','输出详细程度',['low','medium','high']],['model_reasoning_summary','推理摘要',['auto','concise','detailed','none']]];
  return <section className="space-y-4"><h3 className="font-semibold">Codex 原生配置</h3><div className="grid md:grid-cols-3 gap-4">{fields.map(([key,label,values])=><Field key={key} label={label}><select value={config.nativeSettings?.[key]||''} onChange={e=>{const next={...config.nativeSettings};if(e.target.value)next[key]=e.target.value;else delete next[key];change({nativeSettings:next});}}><option value="">保持宿主设置</option>{values.map(v=><option key={v}>{v}</option>)}</select></Field>)}</div>
    <h3 className="font-semibold">工具与插件</h3><p className="muted">这里按打开页面时读到的本机 config.toml 列出已配置的 MCP 连接与插件开关；内容随你的配置文件变化，不是固定清单，也不会在后台替你更新插件。安装、授权和插件版本由 Codex 管理。</p><button type="button" className="btn-ghost" onClick={()=>void request<Host>('/codex/status',{}).then(setHost).catch(e=>setError(e.message))}>刷新本机清单</button>
    {error&&<p role="alert" className="alert-error">{error}</p>}{['mcp_servers','plugins'].map(group=><div className="native-group" key={group}><h4 className="text-sm font-medium">{group==='plugins'?'已配置的插件':'MCP 工具连接'}</h4>{host?.connections[group]?.length?host.connections[group].map(item=><Field key={item.id} label={item.id}><select value={config.integrations?.[group]?.[item.id]===undefined?'inherit':String(config.integrations[group][item.id])} onChange={e=>{const next={...config.integrations?.[group]};if(e.target.value==='inherit')delete next[item.id];else next[item.id]=e.target.value==='true';change({integrations:{...config.integrations,[group]:next}});}}><option value="inherit">保持当前（{item.enabled?'启用':'停用'}）</option><option value="true">启用</option><option value="false">停用</option></select></Field>):<p className="muted">config.toml 中未发现此类配置。其他安装来源状态未知，不代表未安装。</p>}</div>)}
    <p className="muted">权限/沙箱、Hooks、记忆、子代理和项目规则同样属于运行条件；本轮保留宿主值，尚不提供迁移。密钥与认证不会导入工作台。</p>
  </section>;
}

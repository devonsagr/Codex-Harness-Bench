import type {Usage} from './types';

const number=(value:number|null|undefined)=>value==null?'—':value.toLocaleString('zh-CN',{maximumFractionDigits:2});
export function ScoreRing({value,label,detail}:{value:number|null|undefined;label:string;detail?:string}){
  return <div className="score-ring"><svg viewBox="0 0 120 120" role="img" aria-label={`${label}：${number(value)}`}><circle className="ring-track" cx="60" cy="60" r="51"/><circle className="ring-value" cx="60" cy="60" r="51" pathLength="100" strokeDasharray={`${value??0} 100`} transform="rotate(-90 60 60)"/><text x="60" y="61" textAnchor="middle" dominantBaseline="middle">{number(value)}</text></svg><div><strong>{label}</strong>{detail&&<p className="muted">{detail}</p>}</div></div>;
}
export function ScoreBar({value}:{value:number|null|undefined}){
  return <span className="score-bar" aria-hidden="true"><span style={{width:`${value??0}%`}}/></span>;
}
export function UsageChart({usage}:{usage:Usage|null}){
  if(!usage)return <p className="muted">等待本题会话用量，自动同步后显示。</p>;
  const input=usage.inputTokens,cache=usage.cacheReadTokens;
  const known=input!=null&&cache!=null;
  const seconds=usage.activeSeconds;
  return <div className="usage-chart"><div className="usage-headline"><div><span className="muted">累计输入 Token</span><strong>{number(input)}</strong></div><div><span className="muted">输出 Token</span><strong>{number(usage.outputTokens)}</strong></div><div><span className="muted">原生记录活动时长</span><strong>{seconds==null?(usage.activity==='running'?'执行中':'—'):`${Math.floor(seconds/60)} 分 ${Math.floor(seconds%60)} 秒`}</strong></div></div>
    <div className="token-composition" role="img" aria-label={known?`输入中缓存 ${number(cache)}，非缓存 ${number(input-cache)}`:'缓存分布未知'}><span style={{width:known&&input>0?`${cache/input*100}%`:'0%'}}/></div>
    <div className="token-legend"><span><i/>缓存输入 {number(cache)}{known&&input>0?` · ${(cache/input*100).toFixed(1)}%`:''}</span><span><i/>非缓存输入 {number(known?input-cache:null)}</span></div>
    <p className="muted">累计值含多次模型调用；缓存包含在输入内，不代表上下文长度或费用。</p>
  </div>;
}

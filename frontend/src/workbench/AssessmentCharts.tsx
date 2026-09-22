import type {Usage} from './types';
import {apiEquivalent} from './presentation';

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
  const estimate=apiEquivalent(usage);
  const dollars=(v:number)=>v.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:3});
  return <div className="usage-chart"><div className="usage-headline"><div><span className="muted">累计输入 Token</span><strong>{number(input)}</strong></div><div><span className="muted">输出 Token</span><strong>{number(usage.outputTokens)}</strong></div><div><span className="muted">原生记录活动时长</span><strong>{seconds==null?(usage.activity==='running'?'执行中':'—'):`${Math.floor(seconds/60)} 分 ${Math.floor(seconds%60)} 秒`}</strong></div></div>
    <div className="token-composition" role="img" aria-label={known?`输入中缓存 ${number(cache)}，非缓存 ${number(input-cache)}`:'缓存分布未知'}><span style={{width:known&&input>0?`${cache/input*100}%`:'0%'}}/></div>
    <div className="token-legend"><span><i/>缓存输入 {number(cache)}{known&&input>0?` · ${(cache/input*100).toFixed(1)}%`:''}</span><span><i/>非缓存输入 {number(known?input-cache:null)}</span></div>
    <div className="usage-equivalent"><div><span>API 等值估算</span><strong>{estimate.low==null?'暂不可估算':`≈ ${dollars(estimate.low)}${estimate.high!==estimate.low?' – '+dollars(estimate.high!):''}`}</strong></div><details><summary>换算依据</summary>{estimate.reason?<p>{estimate.reason}</p>:<><p>{estimate.model} · 每百万 Token：普通输入 ${estimate.rates![0]}，缓存读取 ${estimate.rates![1]}，输出 ${estimate.rates![2]}。</p><p>先从总输入扣除缓存读取，再分别计价。缓存写入按普通输入的 1.25 倍；未记录写入量时，显示从零写入到全部非缓存输入写入的区间。</p></>}<p>按 2026-09-22 的标准短上下文单价换算；长上下文、加速模式、工具及其他附加费用未计入。累计 Token 不能用于判断单次请求的长上下文档位。</p><p>用于比较运行消耗，不是订阅实际账单，也不推算 Plus 周额度。<a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noreferrer">查看官方单价 ↗</a></p></details></div>
    <p className="muted">累计值含多次模型调用；缓存包含在输入内，不代表上下文长度。</p>
  </div>;
}

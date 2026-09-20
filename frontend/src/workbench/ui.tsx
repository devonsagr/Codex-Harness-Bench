import {Children,cloneElement,isValidElement,useId,useEffect,useRef,type ReactNode} from 'react';
export const labels:Record<string,string>={prepared:'待桌面执行',working:'桌面执行中',captured:'已回收',waiting_confirmation:'等待本轮确认',completed:'交付结束',interrupted:'执行中断',checking:'检查运行中',judging:'AI 复审中',passed:'通过',failed:'未通过',timeout:'超时',cancelled:'已停止',error:'环境错误'};
export const num=(v:number|null|undefined,suffix='')=>v==null?'—':v.toLocaleString()+suffix;
export const date=(s:string)=>new Date(s).toLocaleString('zh-CN',{hour12:false});
export function ModelSelect({label='模型',value,onChange,models,disabled=false}:{label?:string;value:string;onChange:(v:string)=>void;models:{id:string;name:string}[];disabled?:boolean}){
  const known=models.some(m=>m.id===value);
  return <select aria-label={label} required disabled={disabled} value={value} onChange={e=>onChange(e.target.value)}>
    {!value&&<option value="">选择模型</option>}{value&&!known&&<option value={value}>{value}（当前配置）</option>}
    {models.map(m=><option key={m.id} value={m.id}>{m.name===m.id?m.id:`${m.name} · ${m.id}`}</option>)}
  </select>;
}
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}){const id=useId();return <div className="field"><label htmlFor={id}>{label}</label>{Children.map(children,child=>isValidElement(child)&&['input','select','textarea'].includes(String(child.type))?cloneElement(child as React.ReactElement<{id:string;'aria-describedby'?:string}>,{id,'aria-describedby':hint?id+'-hint':undefined}):child)}{hint&&<small id={id+'-hint'}>{hint}</small>}</div>;}
export function Panel({title,children,aside}:{title:string;children:ReactNode;aside?:ReactNode}){return <section className="panel p-5 space-y-4"><div className="flex items-center justify-between gap-4"><h2 className="font-semibold">{title}</h2>{aside}</div>{children}</section>;}
export function Empty({children}:{children:ReactNode}){return <div className="panel-subtle p-6 text-sm text-slate-500 dark:text-zinc-400">{children}</div>;}
export function Details({title,children,open=false}:{title:string;children:ReactNode;open?:boolean}){return <details className="panel-subtle p-4" open={open||undefined}><summary className="cursor-pointer font-medium text-sm">{title}</summary><div className="mt-4 space-y-3">{children}</div></details>;}
export function Json({value}:{value:unknown}){return <pre className="source">{JSON.stringify(value,null,2)}</pre>;}

export function ScoreSlider({label,value,onChange,suffix='分',fixed=false}:{label:string;value:string;onChange:(v:string)=>void;suffix?:string;fixed?:boolean}){
  const id=useId();const unknown=value==='';
  return <div className="score-slider"><div className="score-slider-label"><label htmlFor={id}>{label}</label><output htmlFor={id}>{unknown?'未评分':Number(value).toFixed(fixed?2:1)+suffix}</output></div><input id={id} aria-label={label} aria-valuetext={unknown?'未评分':value+suffix} type="range" min="0" max="100" step={fixed?'0.01':'0.1'} value={unknown?0:value} onChange={e=>onChange(e.target.value)} onPointerUp={e=>{if(unknown)onChange(e.currentTarget.value);}} onKeyUp={e=>{if(unknown&&['ArrowLeft','ArrowDown','Home'].includes(e.key))onChange(e.currentTarget.value);}}/>{!fixed&&<div className="score-slider-fine"><input aria-label={label+'：精确分数'} type="number" required min="0" max="100" step="0.1" placeholder="未评分" value={value} onChange={e=>onChange(e.target.value)}/><button type="button" className="btn-ghost" disabled={unknown} onClick={()=>onChange('')}>清除</button></div>}</div>;
}

export function Dialog({title,open,onClose,children}:{title:string;open:boolean;onClose:()=>void;children:ReactNode}){
  const ref=useRef<HTMLDialogElement>(null);const id=useId();
  useEffect(()=>{const d=ref.current;if(open&&!d?.open)d?.showModal();if(!open&&d?.open)d.close();},[open]);
  return <dialog ref={ref} className="work-dialog" aria-labelledby={id} onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}}><header><h2 id={id}>{title}</h2><button type="button" className="btn-secondary" onClick={onClose}>关闭</button></header>{open&&<div className="work-dialog-body">{children}</div>}</dialog>;
}

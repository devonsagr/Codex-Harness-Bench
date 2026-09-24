import {useEffect,useRef,useState} from 'react';
import {ReadingSettings} from '../workbench/ReadingSettings';
import {Activity, BookOpen, Clock3, Database, FlaskConical, Menu, SlidersHorizontal, X} from 'lucide-react';

export type ArenaTab = 'workbench' | 'history' | 'tasks' | 'configs' | 'leaderboard' | 'spec' | 'storage';
export const arenaPages:Record<ArenaTab,{label:string;description:string}>={
  storage:{label:'数据与存储',description:'数据集与工作区'},
  workbench:{label:'评测工作台',description:'让每一次配置改动，都有交付作为依据。'},
  history:{label:'评测历史',description:'查看过往结果'},
  tasks:{label:'任务库',description:'精选真实任务集'},
  configs:{label:'配置库',description:'模型与运行配置'},
  leaderboard:{label:'配置成绩',description:'按配置版本查看题目与历史'},
  spec:{label:'方法说明',description:'评分来源与边界'},
};
const tabs=[{id:'workbench',icon:FlaskConical},{id:'history',icon:Clock3},{id:'leaderboard',icon:Activity},{id:'tasks',icon:BookOpen},{id:'configs',icon:SlidersHorizontal},{id:'storage',icon:Database},{id:'spec',icon:BookOpen}] as const;
export function ArenaHeader({activeTab,onTabChange}:{activeTab:ArenaTab;onTabChange:(tab:ArenaTab)=>void}){
  const [open,setOpen]=useState(false);
  const menuButton=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!open)return;
    const close=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);menuButton.current?.focus();}};
    document.addEventListener('keydown',close);
    return()=>document.removeEventListener('keydown',close);
  },[open]);
  const navigate=(tab:ArenaTab)=>{onTabChange(tab);setOpen(false);};
  return <>
    <header className="mobile-header"><span>Harness <strong>Bench</strong></span><button ref={menuButton} className="icon-button" aria-label={open?'关闭导航':'打开导航'} aria-expanded={open} aria-controls="app-navigation" onClick={()=>setOpen(!open)}>{open?<X size={20}/>:<Menu size={20}/>}</button></header>
    {open&&<button className="nav-backdrop" aria-label="收起导航" onClick={()=>setOpen(false)}/>}
    <aside id="app-navigation" className={'app-sidebar '+(open?'is-open':'')} aria-label="主导航">
      <button className="brand" onClick={()=>navigate('workbench')} aria-label="Harness Bench 工作台"><span className="brand-mark" aria-hidden="true"/><span>Codex Harness<small>用真实任务，检验更好的模型</small></span></button>
      <nav>{tabs.map(({id,icon:Icon})=><button key={id} aria-label={arenaPages[id].label} onClick={()=>navigate(id)} aria-current={activeTab===id?'page':undefined} className={'sidebar-link '+(activeTab===id?'active':'')}><Icon size={22} strokeWidth={1.7}/><span><strong>{arenaPages[id].label}</strong><small>{id==='workbench'?'开始新的评测':arenaPages[id].description}</small></span></button>)}</nav>
      <div className="sidebar-bottom"><div className="editorial-motto" aria-label="Build better with evidence">BUILD<br/>BETTER<br/>WITH EVIDENCE.</div><div className="sidebar-controls"><ReadingSettings/></div></div>
    </aside>
  </>;
}

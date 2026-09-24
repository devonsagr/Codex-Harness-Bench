import {useEffect,useRef,useState} from 'react';
import {ReadingSettings} from '../workbench/ReadingSettings';
import {Activity, ArrowUpRight, BookOpen, Clock3, Database, FlaskConical, Menu, Moon, SlidersHorizontal, Sun, X} from 'lucide-react';

export type ArenaTab = 'workbench' | 'history' | 'tasks' | 'configs' | 'leaderboard' | 'spec' | 'storage';
export const arenaPages:Record<ArenaTab,{label:string;description:string}>={
  storage:{label:'数据与存储',description:'查看源码、产物与复查，按范围清理。'},
  workbench:{label:'开始评测',description:'选题、执行、回收和评分。'},
  history:{label:'评测历史',description:'回到当时的配置、产物与评分。'},
  tasks:{label:'任务库',description:'选择真实任务，确认源码起点和运行条件。'},
  configs:{label:'配置库',description:'把工作方式保存成可比较的版本。'},
  leaderboard:{label:'结果对比',description:'在相同条件下，看清配置之间的差异。'},
  spec:{label:'方法说明',description:'了解评测对象、证据和评分方法。'},
};
const groups=[
  {label:'评测',tabs:[{id:'workbench',icon:FlaskConical},{id:'history',icon:Clock3},{id:'leaderboard',icon:Activity}]},
  {label:'准备',tabs:[{id:'tasks',icon:Database},{id:'configs',icon:SlidersHorizontal}]},
  {label:'参考与管理',tabs:[{id:'storage',icon:Database},{id:'spec',icon:BookOpen}]},
] as const;
export function ArenaHeader({activeTab,onTabChange,theme,onToggleTheme}:{activeTab:ArenaTab;onTabChange:(tab:ArenaTab)=>void;theme:'light'|'dark';onToggleTheme:()=>void}){
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
      <button className="brand" onClick={()=>navigate('workbench')} aria-label="Harness Bench 工作台"><span>Harness<strong>Bench<span className="brand-period">.</span></strong></span></button>
      <p className="sidebar-caption">模型 × 你的 Codex 配置</p>
      <nav>{groups.map(group=><div className="nav-group" key={group.label}><p className="nav-group-title">{group.label}</p>{group.tabs.map(({id,icon:Icon})=><button key={id} aria-label={arenaPages[id].label} onClick={()=>navigate(id)} aria-current={activeTab===id?'page':undefined} className={'sidebar-link '+(activeTab===id?'active':'')}><Icon size={17} strokeWidth={1.7}/><span>{arenaPages[id].label}</span></button>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-local"><span className="status-dot"/>本地工作空间<ArrowUpRight size={14}/></div><p>配置与记录保存在本机</p><div className="sidebar-controls"><ReadingSettings/><button className="icon-button" aria-label={theme==='light'?'切换到暗色模式':'切换到白天模式'} title={theme==='light'?'切换到暗色模式':'切换到白天模式'} onClick={onToggleTheme}>{theme==='light'?<Moon size={18}/>:<Sun size={18}/>}</button></div></div>
    </aside>
  </>;
}

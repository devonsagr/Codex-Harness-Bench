import type {Task} from './types';
import creativeCatalog from '../../../tasks/creative-web-v1/catalog.json';
import coreSet from '../../../catalog/core-task-set.json';

const creativeOrder=new Map<string,number>(creativeCatalog.map((entry,index)=>['original-creative-'+entry.id,index]));
const creativeCategory=new Map<string,string>(creativeCatalog.map(entry=>['original-creative-'+entry.id,entry.category]));
const creativeProfile=new Map<string,string>(creativeCatalog.map(entry=>['original-creative-'+entry.id,entry.profile]));
const coreOrder=new Map<string,number>(coreSet.taskIds.map((id,index)=>[id,index]));
export const isCoreTask=(task:Task)=>coreOrder.has(task.id);
export const creativeTaskCategory=(task:Task)=>creativeCategory.get(task.id)||null;
export const creativeTaskDrawGroup=(task:Task)=>creativeProfile.get(task.id)?.includes('svg')?'svg':creativeTaskCategory(task)||(task.sourceKind==='community-adapted'?task.description||'社区实践':task.sourceKind==='webgen-bench-local'?task.description||'公开网页':taskFamily(task));
const categoryOrder=['矢量插画与空间构图','地标叙事与交互视觉','矢量系统与设计一致性','交互可视化','三维与空间交互','浏览器工具与生产力','可玩游戏与状态系统'];
export function taskLibraryOrder(a:Task,b:Task):number{
  const coreLeft=coreOrder.get(a.id),coreRight=coreOrder.get(b.id);
  if(coreLeft!==undefined||coreRight!==undefined){if(coreLeft===undefined)return 1;if(coreRight===undefined)return -1;return coreLeft-coreRight;}
  const left=creativeOrder.get(a.id),right=creativeOrder.get(b.id);
  if(left===undefined)return right===undefined?0:1;
  if(right===undefined)return -1;
  const leftCategory=categoryOrder.indexOf(creativeCategory.get(a.id)||'');
  const rightCategory=categoryOrder.indexOf(creativeCategory.get(b.id)||'');
  const rank=(value:number)=>value<0?categoryOrder.length:value;
  return rank(leftCategory)-rank(rightCategory)||left-right;
}

export const familyLabels:Record<string,string>={
  'swe-bugfix':'仓库 Bug 修复','swe-feature':'仓库功能扩展','web-interface':'网页交互与前端',
  'fullstack-product':'全栈产品构建','business-workflow':'业务流程与模糊需求','data-analysis':'数据处理与分析',
  'long-horizon':'长期多阶段项目','architecture-engineering':'架构与工程维护',
  'collaboration-planning':'协作、沟通与规划','security-reliability':'安全与可靠性','performance':'性能与效率','other':'其他',
};
export const capabilityLabels:Record<string,string>={
  coding:'工程编程',debugging:'排错修复',frontend:'前端开发',browser:'浏览器交互',api:'接口设计',
  data:'数据处理',reasoning:'逻辑推理',requirements:'需求理解',architecture:'架构设计',
  security:'安全',performance:'性能',reliability:'稳定性',
  'long-context':'长期上下文',collaboration:'协作',communication:'沟通体验',maintainability:'可维护性',
};
export const familyGroups:[string,string,string[]][]=[
  ['core','跨类型精选',[]],
  ['','全部题目',[]],
  ['swe','代码与仓库',['swe-bugfix','swe-feature']],
  ['web','网页与全栈',['web-interface','fullstack-product']],
  ['business','业务与数据',['business-workflow','data-analysis']],
  ['engineering','工程与长期',['long-horizon','architecture-engineering','security-reliability','performance']],
  ['collaboration','协作与规划',['collaboration-planning']],
];
export function taskFamily(task:Task):string{
  if(task.taskFamily)return task.taskFamily;
  if(task.publicSource)return task.publicSource.category==='bugfix'?'swe-bugfix':task.publicSource.category==='enhancement'?'architecture-engineering':'swe-feature';
  if(task.hasFrontendUI)return 'web-interface';
  if(task.taskParadigm==='deterministic-bugfix')return 'swe-bugfix';
  return 'business-workflow';
}
export const inFamilyGroup=(task:Task,group:string)=>!group||(group==='core'?isCoreTask(task):familyGroups.find(([id])=>id===group)?.[2].includes(taskFamily(task))===true);

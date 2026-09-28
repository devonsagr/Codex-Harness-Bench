import type {Policy,Task} from './types';
import {taskFamily} from './TaskTaxonomy';

export const autoScorecardVersion='project-tasktype-v3';
type Group={label:string;weights:Record<string,number>};
const goalV2:Group={label:'用户目标与范围',weights:{intent:50,instruction:10}};
const goalV3:Group={label:'用户目标与范围',weights:{intent:45,instruction:10,reasoning:5}};
const delivery:Group={label:'交付与可维护性',weights:{maintainability:10,handoff:5}};
const use=(weights:Record<string,number>):Group=>({label:'实际使用与可靠性',weights});

const profiles:Record<string,{label:string;groups:Group[]}>= {
  engineering:{label:'工程与程序',groups:[goalV3,use({verification:10,robustness:15}),delivery]},
  web:{label:'网页与产品',groups:[goalV3,use({ux:10,visual:5,verification:5,robustness:5}),delivery]},
  business:{label:'业务与数据',groups:[goalV2,use({reasoning:10,verification:10,robustness:5}),delivery]},
  long:{label:'长期项目',groups:[goalV3,use({'long-context':10,milestones:10,verification:5}),delivery]},
  collaboration:{label:'协作与规划',groups:[goalV2,use({reasoning:10,requirements:10,communication:5}),delivery]},
  security:{label:'安全与可靠性',groups:[goalV3,use({verification:10,robustness:10,security:5}),delivery]},
  performance:{label:'性能与效率',groups:[goalV3,use({verification:10,robustness:10,performance:5}),delivery]},
};

export function autoProfile(task:Task){
  if(task.publicSource)return {id:'public',label:'DeepSWE 原题',groups:[] as Group[]};
  const family=taskFamily(task);
  const id=task.hasFrontendUI&&['web-interface','fullstack-product'].includes(family)?'web':
    ['business-workflow','data-analysis'].includes(family)?'business':
    family==='long-horizon'?'long':family==='collaboration-planning'?'collaboration':
    family==='security-reliability'?'security':family==='performance'?'performance':
    task.hasFrontendUI?'web':'engineering';
  return {id,...profiles[id]};
}

export function scoredDimensions(policy:Policy,task:Task):Record<string,number>{
  if(policy.taskTypeAuto){
    const override=policy.taskOverrides?.[task.id];
    if(override)return Object.fromEntries(Object.entries(override.dimensions).filter(([key,weight])=>weight>0&&(!['ux','visual','originality','responsive','accessibility'].includes(key)||task.hasFrontendUI)));
    const profile=autoProfile(task);
    const groups=policy.autoScorecardVersion==='project-tasktype-v3'?profile.groups:
      profile.groups.map(group=>group===goalV3?goalV2:group);
    return profile.id==='public'?{maintainability:100}:Object.fromEntries(groups.flatMap(group=>Object.entries(group.weights)));
  }
  return Object.fromEntries(Object.entries(policy.dimensions).filter(([key,weight])=>weight>0&&(!['ux','visual','originality','responsive','accessibility'].includes(key)||task.hasFrontendUI)));
}

export const scoreRubrics=(policy:Policy,task:Task)=>policy.taskOverrides?.[task.id]?.rubrics||policy.rubrics||{};

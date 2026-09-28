/** Stable rubric IDs shared by the picker, scoring rules and radar destinations. */
export const uiRubricKeys=new Set(['ux','visual','originality','responsive','accessibility']);

export const rubricGroups=[
  {label:'通用交付',keys:['intent','verification','instruction','handoff']},
  {label:'工程与程序',keys:['robustness','maintainability','security','performance']},
  {label:'网页与产品',keys:['ux','visual','originality','responsive','accessibility']},
  {label:'推理与协作',keys:['reasoning','requirements','long-context','milestones','communication']},
] as const;

export const scoringPresets=[
  {id:'general',label:'通用交付 · 7 项',weights:{intent:35,verification:20,robustness:15,instruction:10,ux:10,handoff:5,maintainability:5}},
  {id:'engineering',label:'工程与程序 · 6 项',weights:{intent:35,verification:20,robustness:15,maintainability:15,instruction:10,handoff:5}},
  {id:'web',label:'网页与产品 · 8 项',weights:{intent:30,ux:15,visual:15,originality:10,responsive:10,accessibility:5,verification:10,handoff:5}},
  {id:'data',label:'业务与数据 · 6 项',weights:{intent:30,verification:20,reasoning:20,robustness:15,maintainability:10,handoff:5}},
  {id:'process',label:'长期协作 · 8 项',weights:{intent:30,instruction:10,reasoning:15,requirements:15,'long-context':10,milestones:10,communication:5,handoff:5}},
] as const;

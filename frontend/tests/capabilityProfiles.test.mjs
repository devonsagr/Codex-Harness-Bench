import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const compile=source=>ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const dataUrl=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const source=readFileSync(new URL('../src/workbench/capabilityProfiles.ts',import.meta.url),'utf8');
const {capabilityProfiles,rubricRadarDestinations}=await import(dataUrl(compile(source)));

const axis=(tasks,id)=>capabilityProfiles(tasks)[0].axes.find(row=>row.id===id);
const publicTask=id=>({id,revision:1,title:id,publicSource:{id,category:'feature'}});
const openTask=(id,hasFrontendUI=false)=>({id,revision:1,title:id,hasFrontendUI,checks:[]});
const entry=(task,score,extra={})=>({task,run:{id:'run-'+task.id,policy:{rubrics:{}}},trial:{
  id:'trial-'+task.id,score:{overall:score,...extra},captures:[{id:'capture-'+task.id,checks:[]}],
  reviews:[{id:'review-'+task.id,captureId:'capture-'+task.id}]},
});
const result=(task,entries)=>({task,entries,mean:entries.reduce((sum,item)=>sum+item.trial.score.overall,0)/entries.length,protocolKey:task.id});
const card=(functionRatio,quality=.8)=>({version:'deepswe-local-v1',items:[
  {label:'目标语义组',ratio:functionRatio,weight:70},
  {label:'旧功能与边界回归',ratio:1,weight:20},
  {label:'工程可维护性',ratio:quality,weight:10},
]});
const reviewed=(task,score,dimensions)=>entry(task,score,{
  machineReviewId:'review-'+task.id,
  effectiveScores:{...dimensions},
  machineRatings:Object.fromEntries(Object.entries(dimensions).map(([key,value])=>[key,{score:value,evidence:[{path:'result.txt',quote:'verified'}]}])),
});

test('six-axis view keeps public pass/fail separate from continuous evidence',()=>{
  const a=publicTask('a'),b=publicTask('b');
  const tasks=[result(a,[entry(a,75,{nativeReward:1,taskScorecard:card(.5)})]),result(b,[entry(b,65,{nativeReward:0,taskScorecard:card(.7,.9)})])];
  assert.equal(capabilityProfiles(tasks).length,1);
  assert.equal(capabilityProfiles(tasks)[0].axes.length,6);
  assert.equal(axis(tasks,'goal').score,60);
  assert.equal(axis(tasks,'engineering').score,85);
  assert.equal(axis(tasks,'reliability').score,100);
  assert.equal(axis(tasks,'web').score,null);
  assert.equal(axis(tasks,'goal').samples[0].runs[0].facets[0].label,'目标语义组');
  tasks[1].entries[0].trial.score.taskScorecard.version='future-card';
  assert.equal(axis(tasks,'goal').score,50);
  assert.equal(axis(tasks,'goal').tasks,1);
});

test('web evidence appears only for a rendered UI, with measured facets named',()=>{
  const web=openTask('web-a',true);
  const tasks=[result(web,[reviewed(web,80,{intent:90,ux:78,verification:85})])];
  assert.equal(axis(tasks,'goal').score,90);
  assert.equal(axis(tasks,'web').score,78);
  assert.match(axis(tasks,'web').samples[0].runs[0].basis,/ux/);
  assert.equal(axis(tasks,'engineering').score,85);
  assert.equal(axis(tasks,'reasoning').score,null);
  assert.equal(axis([result(openTask('code'),[reviewed(openTask('code'),80,{ux:78})])],'web').score,null);
});

test('rubric mapping is contextual and rules are not a separate radar axis',()=>{
  const web=openTask('web-b',true),code=openTask('code-b');
  assert.deepEqual(rubricRadarDestinations('visual',[web]),['网页体验']);
  assert.deepEqual(rubricRadarDestinations('intent',[web,code]),['目标兑现']);
  assert.deepEqual(rubricRadarDestinations('verification',[code]),['工程实现','稳健交付']);
  assert.deepEqual(rubricRadarDestinations('instruction',[web,code]),[]);
  assert.deepEqual(rubricRadarDestinations('visual',[code]),[]);
});

test('automatic card goal and failing configured check use frozen, adjusted evidence',()=>{
  const web={...openTask('web-check',true),checks:[{id:'check'}]};
  const evaluated=reviewed(web,72,{intent:90,instruction:70,verification:85,visual:76});
  evaluated.trial.captures[0].checks=[{status:'failed'}];
  evaluated.trial.score.taskScorecard={version:'project-tasktype-v2',qualityReviewId:'review-web-check',items:[
    {label:'用户目标与范围',ratio:52/60,evidence:'目标 90；规则 70'},
  ]};
  const tasks=[result(web,[evaluated])];
  assert.equal(axis(tasks,'goal').score,86.7);
  assert.equal(axis(tasks,'engineering').score,0);
  assert.equal(axis(tasks,'reliability').score,0);
  assert.equal(axis(tasks,'web').score,76);
  evaluated.trial.captures[0].checks=[{status:'error'}];
  assert.equal(axis(tasks,'engineering').score,null);
});

test('same-task repeats average first and an unknown repeat excludes that task axis',()=>{
  const a=openTask('a'),b=openTask('b');
  const first=reviewed(a,20,{intent:20}),second=reviewed(a,40,{intent:40}),other=reviewed(b,90,{intent:90});
  const tasks=[result(a,[first,second]),result(b,[other])];
  assert.equal(axis(tasks,'goal').score,60);
  second.trial.score.effectiveScores.intent=null;
  assert.equal(axis(tasks,'goal').score,90);
  assert.equal(axis(tasks,'goal').tasks,1);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/workbench/presentation.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {taskFacets,runProgress,apiEquivalent,taskCheckScope,dialogueResult}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));

test('generic page health does not claim task acceptance; task checks keep their scope',()=>{
  assert.equal(taskCheckScope({checks:[]}),'none');
  assert.equal(taskCheckScope({checks:[{image:'chb-verifier:creative-web-v1'}]}),'basic');
  assert.equal(taskCheckScope({checks:[{image:'chb-verifier:creative-web-v1'},{image:'chb-verifier:community-engine-v1'}]}),'task');
  assert.equal(taskCheckScope({checks:[{image:'custom-verifier'}]}),'task');
});

test('communication ratios exclude unknown and inapplicable opportunities, preserve zero',()=>{
  assert.deepEqual(dialogueResult(),{judged:0,rate:null});
  assert.deepEqual(dialogueResult({met:0,missed:0,unknown:2,not_applicable:3}),{judged:0,rate:null});
  assert.deepEqual(dialogueResult({met:0,missed:2,unknown:2,not_applicable:3}),{judged:2,rate:0});
  assert.deepEqual(dialogueResult({met:2,missed:1,unknown:20,not_applicable:30}),{judged:3,rate:66.7});
});
test('facets show only matching real values, including unlabelled difficulty',()=>{
  const tasks=[{channel:'code',difficulty:'Hard'},{channel:'code',difficulty:''},{channel:'ui',difficulty:'Easy'}];
  assert.deepEqual(Object.fromEntries(taskFacets(tasks,'code','').difficulties),{hard:1,'未标注':1});
  assert.deepEqual(taskFacets(tasks,'','easy').channels,[['ui',1]]);
});
const trial=()=>({state:'captured',captures:[{id:'new'}],reviews:[{id:'r',captureId:'new'}],score:{machine:75,machineReviewId:'r'},usage:null});
test('scoring does not imply delivery ended; busy execution wins over old scores',()=>{
  const t=trial(),r={state:'active',trials:[t]};
  assert.equal(runProgress(r),'已评分 · 待结束');
  t.usage={activity:'running'};assert.equal(runProgress(r),'执行中');
  r.state='completed';assert.equal(runProgress(r),'交付结束');
  t.state='judging';assert.equal(runProgress(r),'评分中');
});
test('old capture scores do not claim the latest capture was scored',()=>{
  const t=trial();t.reviews[0].captureId='old';
  assert.equal(runProgress({trials:[t]}),'已回收 · 待评分');
  t.lastJobError={message:'invalid review'};
  assert.equal(runProgress({trials:[t]}),'评分待处理');
});
test('partial batches and zero scores remain visible',()=>{
  const t=trial();t.score.machine=0;
  assert.equal(runProgress({trials:[t,{...trial(),score:{}}]}),'部分已评分 · 1/2');
});
const usage=()=>({models:['gpt-5.6-sol'],inputTokens:1e6,cacheReadTokens:9e5,outputTokens:1e4});
test('cache is included in input; unknown writes produce a bounded standard-rate estimate',()=>{
  const v=apiEquivalent(usage());
  assert.ok(Math.abs(v.low-.96)<1e-10);assert.ok(Math.abs(v.high-1.06)<1e-10);
  const known=apiEquivalent({...usage(),cacheWriteTokens:50000});
  assert.equal(known.low,known.high);assert.ok(Math.abs(known.low-1.01)<1e-10);
});
test('GPT-6 Luna uses its current standard API equivalent rates',()=>{
  const value=apiEquivalent({...usage(),models:['gpt-6-luna']});
  assert.ok(Math.abs(value.low-.024)<1e-10);
  assert.ok(Math.abs(value.high-.0265)<1e-10);
});
test('mixed models, missing tokens and invalid write counts cannot be silently priced',()=>{
  for(const patch of [{models:['gpt-5.6-sol','gpt-5.6-luna']},{models:['unknown']},{cacheReadTokens:null},{cacheReadTokens:2e6},{cacheWriteTokens:2e5},{inputTokens:NaN}]){
    const v=apiEquivalent({...usage(),...patch});assert.ok(v.reason);assert.equal(v.low,undefined);
  }
});

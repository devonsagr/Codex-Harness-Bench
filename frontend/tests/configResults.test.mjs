import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=readFileSync(new URL('../src/workbench/configResults.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {configResults}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const cfg=(revision=1,extra={})=>({id:'config-a',revision,name:'Focused',baseModel:'model-a',reasoning:'low',skills:[],...extra});
const task=(id)=>({id,revision:1,title:id});
const policy=(version='machine')=>({version,objectiveWeight:0,humanWeight:100,dimensions:{quality:100}});
const run=(id,taskId,score,{revision=1,mode='machine',override=false,changed=false,state='completed'}={})=>({
  id,createdAt:`2026-09-${id.padStart(2,'0')}T12:00:00Z`,policy:policy(mode),configs:[cfg(revision,override?{preparationOverride:{}}:{})],tasks:[task(taskId)],
  trials:[{id:`trial-${id}`,configId:'config-a',taskId,state,captures:[{harnessUnchanged:!changed,hostUnchanged:true}],score:{overall:score}}]
});

test('repeat trials average within each task, then distinct tasks get equal weight',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',20),run('02','task-a',40),run('03','task-b',90)],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,60); // task-a mean 30, task-b 90
  assert.equal(result.tasks.length,2);
  assert.equal(result.completed,3);
});

test('archived trials still count, while edited configuration revision stays separate',()=>{
  const state={configs:[cfg(2)],archivedConfigs:[],runs:[run('02','task-a',70,{revision:2})],archivedRuns:[run('01','task-a',30)]};
  const results=configResults(state);
  assert.deepEqual(results.map(g=>[g.config.revision,g.score,g.archivedRuns]),[[2,70,0],[1,30,1]]);
});

test('incomplete and altered conditions remain visible without contaminating the score',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',80),run('02','task-a',95,{changed:true}),run('03','task-a',null,{state:'prepared'}),run('04','task-a',100,{override:true})],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,80);
  assert.equal(result.entries.length,4);
  assert.equal(result.pending,3);
});

test('different scoring policies never produce a combined mean',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',80),run('02','task-b',90,{mode:'other'})],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,null);
  assert.equal(result.policyCount,2);
});

test('untested current and archived configurations still appear as empty scorecards',()=>{
  const state={configs:[cfg()],archivedConfigs:[{...cfg(),id:'archived'}],runs:[],archivedRuns:[]};
  const results=configResults(state);
  assert.deepEqual(results.map(g=>[g.config.id,g.score,g.archivedConfig]),[['config-a',null,false],['archived',null,true]]);
});

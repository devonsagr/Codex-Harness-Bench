import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=readFileSync(new URL('../src/workbench/configResults.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {configResults,matchedComparison}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const cfg=(revision=1,extra={})=>({id:'config-a',revision,name:'Focused',baseModel:'model-a',reasoning:'low',skills:[],...extra});
const task=(id,sourceKind)=>({id,revision:1,title:id,sourceKind});
const policy=(version='machine')=>({version,objectiveWeight:0,humanWeight:100,dimensions:{quality:100}});
const run=(id,taskId,score,{revision=1,mode='machine',override=false,changed=false,state='completed',sourceKind}={})=>({
  id,createdAt:`2026-09-${id.padStart(2,'0')}T12:00:00Z`,policy:policy(mode),configs:[cfg(revision,override?{preparationOverride:{}}:{})],tasks:[task(taskId,sourceKind)],
  trials:[{id:`trial-${id}`,configId:'config-a',taskId,state,captures:[{harnessUnchanged:!changed,hostUnchanged:true}],score:{overall:score}}]
});

test('repeat trials average within a task while different tasks do not create a total grade',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',20),run('02','task-a',40),run('03','task-b',90)],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,null);
  assert.deepEqual(result.tasks.map(t=>t.mean),[30,90]);
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

test('archiving both the configuration and its run keeps the score and makes the archive explicit',()=>{
  const state={configs:[],archivedConfigs:[cfg()],runs:[],archivedRuns:[run('01','task-a',86)]};
  const [result]=configResults(state);
  assert.equal(result.archivedConfig,true);
  assert.equal(result.current,false);
  assert.equal(result.archivedRuns,1);
  assert.equal(result.score,86);
  assert.equal(result.tasks[0].entries[0].archived,true);
});

test('archived count names runs rather than trials in a batch',()=>{
  const batch=run('01','task-a',86);
  batch.tasks.push(task('task-b'));
  batch.trials.push({...batch.trials[0],id:'trial-b',taskId:'task-b',score:{overall:72}});
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[],archivedRuns:[batch]});
  assert.equal(result.archivedRuns,1);
  assert.equal(result.entries.length,2);
});

test('source breakdown is visible without a misleading cross-task score',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[
    run('01','bug-a',20,{sourceKind:'deepswe'}),
    run('02','bug-a',40,{sourceKind:'deepswe'}),
    run('03','bug-b',60,{sourceKind:'deepswe'}),
    run('04','idea-a',90,{sourceKind:'prototype-prompt'})
  ],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,null);
  assert.deepEqual(result.collections.map(c=>[c.label,c.tasks.length,c.trials]),[
    ['DeepSWE',2,3],['开放需求题',1,1]
  ]);
});

test('finished delivery without final grading remains visible and does not claim a score',()=>{
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',null)],archivedRuns:[]});
  assert.equal(result.finished,1);
  assert.equal(result.scored,0);
  assert.equal(result.score,null);
  assert.match(result.reason,/尚无最终评分/);
});

test('removing a run from history removes its score without deleting its frozen record',()=>{
  const hidden={...run('01','task-a',88),historyHidden:true};
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[hidden],archivedRuns:[]});
  assert.equal(result.score,null);
  assert.equal(result.entries.length,0);
  assert.equal(hidden.trials[0].score.overall,88);
});

test('permanently deleted library config disappears from scorecards but historical runs are independent',()=>{
  const state={configs:[],archivedConfigs:[],runs:[run('01','task-a',80)],archivedRuns:[]};
  assert.deepEqual(configResults(state),[]);
  assert.equal(state.runs.length,1);
});

test('different judge versions do not create a misleading combined score',()=>{
  const a=run('01','task-a',80),b=run('02','task-b',90);
  a.trials[0].score.machineReviewId='review-a';b.trials[0].score.machineReviewId='review-b';
  a.trials[0].reviews=[{id:'review-a',model:'gpt-6-luna',reasoningEffort:'max',scoreSchema:'v1'}];
  b.trials[0].reviews=[{id:'review-b',model:'gpt-5.6-luna',reasoningEffort:'max',scoreSchema:'v1'}];
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[a,b],archivedRuns:[]});
  assert.equal(result.score,null);
  assert.equal(result.judgeCount,2);
});

test('matched comparison uses only shared task versions, cancelling coverage differences',()=>{
  const other={...cfg(),id:'config-b',name:'Other'};
  const mapped=(r)=>({...r,configs:[other],trials:r.trials.map(t=>({...t,configId:'config-b'}))});
  const groups=configResults({configs:[cfg(),other],archivedConfigs:[],runs:[run('01','easy',90),run('02','hard',30),mapped(run('03','hard',50)),mapped(run('04','other',100))],archivedRuns:[]});
  const result=matchedComparison(groups.find(g=>g.config.id==='config-a'),groups.find(g=>g.config.id==='config-b'));
  assert.equal(result.tasks.length,1);
  assert.equal(result.baselineScore,30);
  assert.equal(result.candidateScore,50);
  assert.equal(result.delta,20);
});

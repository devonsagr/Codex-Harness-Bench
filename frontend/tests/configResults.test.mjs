import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=readFileSync(new URL('../src/workbench/configResults.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {configResults,entryScore,matchedComparison}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const cfg=(revision=1,extra={})=>({id:'config-a',revision,name:'Focused',baseModel:'model-a',reasoning:'low',skills:[],...extra});
const task=(id,sourceKind)=>({id,revision:1,title:id,sourceKind});
const policy=(version='machine')=>({version,objectiveWeight:0,humanWeight:100,dimensions:{quality:100}});
const run=(id,taskId,score,{revision=1,mode='machine',override=false,changed=false,state='completed',sourceKind}={})=>({
  id,createdAt:`2026-09-${id.padStart(2,'0')}T12:00:00Z`,policy:policy(mode),configs:[cfg(revision,override?{preparationOverride:{}}:{})],tasks:[task(taskId,sourceKind)],
  trials:[{id:`trial-${id}`,configId:'config-a',taskId,state,captures:[{harnessUnchanged:!changed,hostUnchanged:true}],score:{overall:score,assurance:'task-check-pass'}}]
});

test('repeat trials average within a task, then different tasks form a configuration grade',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',20),run('02','task-a',40),run('03','task-b',90)],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,60);
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
  assert.equal(result.score,null);
  assert.equal(result.entries.length,4);
  assert.equal(result.pending,2);
  assert.equal(result.recorded,3);
  assert.match(result.reason,/2 次暂不纳入配置对比/);
  assert.equal(entryScore(result.entries[1]),95);
});

test('fully scored captured trial is visible as provisional but excluded from configuration grade',()=>{
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',91.5,{state:'captured'})],archivedRuns:[]});
  assert.equal(entryScore(result.entries[0]),91.5);
  assert.equal(result.recorded,1);
  assert.equal(result.pending,1);
  assert.equal(result.entries[0].eligible,false);
  assert.equal(result.score,null);
});

test('smoke-only scores remain visible as reference but cannot publish a configuration grade',()=>{
  const weak=run('01','creative-page',94);
  weak.trials[0].score.assurance='ai-reference';
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[weak],archivedRuns:[]});
  assert.equal(result.referenceScore,94);
  assert.equal(result.score,null);
  assert.equal(result.referenceOnly,true);
  assert.equal(result.tasks[0].mean,94);
  assert.match(result.reason,/通用烟检/);
  assert.match(matchedComparison(result,{...result,key:'other'}).reason,/不能把数值差当作配置胜负/);
  weak.trials[0].score.assurance='task-check-fail';
  assert.equal(configResults({configs:[cfg()],archivedConfigs:[],runs:[weak],archivedRuns:[]})[0].score,null);
});

test('different tasks may use task-specific scoring policies in one configuration',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[run('01','task-a',80),run('02','task-b',90,{mode:'other'})],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,85);
  assert.equal(result.policyCount,2);
  assert.deepEqual(result.tasks.map(task=>task.mean),[80,90]);
});

test('another task custom override does not split one task scoring protocol',()=>{
  const first=run('01','task-a',80),second=run('02','task-a',90);
  const auto={version:'arena-machine-v1',taskTypeAuto:true,dimensions:{intent:100},rubrics:{intent:{label:'目标',description:'交付'}}};
  first.policy={...auto,taskOverrides:{'task-b':{dimensions:{intent:100},rubrics:auto.rubrics}}};
  second.policy={...auto,taskOverrides:{'task-c':{dimensions:{intent:100},rubrics:auto.rubrics}}};
  first.trials[0].score.taskScorecard={version:'project-tasktype-v2'};
  second.trials[0].score.taskScorecard={version:'project-tasktype-v2'};
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[first,second],archivedRuns:[]});
  assert.equal(result.tasks.length,1);
  assert.equal(result.tasks[0].mean,85);
});

test('mixed public and open deliveries preserve verified local scores while the batch remains incomplete',()=>{
  const publicRun=run('01','public-a',82,{sourceKind:'deepswe'});
  publicRun.tasks[0].publicSource={id:'public-a',category:'bug-fix',language:'go',environmentStatus:'ready',verifierStatus:'ready'};
  publicRun.trials[0].score={overall:82,scoreSource:'task-scorecard',nativeVerificationId:'native-1',nativeReward:1,taskScorecard:{version:'local-v1',overall:82,nativeVerificationId:'native-1',qualityReviewId:'review-1'}};
  publicRun.trials[0].captures[0]={...publicRun.trials[0].captures[0],manifest:{sha256:'capture-a'},nativeVerifications:[{id:'native-1',captureHash:'capture-a',adapter:'native',reward:1}]};
  const pending=run('03','public-b',null,{sourceKind:'deepswe'});
  pending.tasks[0].publicSource={id:'public-b',category:'bug-fix',language:'go',environmentStatus:'ready',verifierStatus:'ready'};
  pending.trials[0].score={overall:null,scoreSource:'native-verifier'};
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[publicRun,run('02','project-a',92),pending],archivedRuns:[]});
  assert.equal(result.score,null);
  assert.equal(result.completed,2);
  assert.equal(result.recorded,2);
  assert.equal(result.pending,1);
  assert.deepEqual(result.tasks.map(task=>task.mean),[82,92]);
  assert.deepEqual(result.collections.map(source=>source.label),['DeepSWE','其他来源']);
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

test('source breakdown remains visible beside the cross-task score',()=>{
  const state={configs:[cfg()],archivedConfigs:[],runs:[
    run('01','bug-a',20,{sourceKind:'deepswe'}),
    run('02','bug-a',40,{sourceKind:'deepswe'}),
    run('03','bug-b',60,{sourceKind:'deepswe'}),
    run('04','idea-a',90,{sourceKind:'prototype-prompt'})
  ],archivedRuns:[]};
  const [result]=configResults(state);
  assert.equal(result.score,60);
  assert.deepEqual(result.collections.map(c=>[c.label,c.tasks.length,c.trials]),[
    ['DeepSWE',2,3],['开放需求题',1,1]
  ]);
});

test('public task score requires matching local card and native report, never an AI partial score',()=>{
  const verified=run('01','public-a',87,{sourceKind:'deepswe'});
  verified.tasks[0].publicSource={id:'public-a',category:'bug-fix',language:'go',environmentStatus:'ready',verifierStatus:'ready'};
  verified.trials[0].score={overall:87,scoreSource:'task-scorecard',assurance:'native',nativeVerificationId:'native-1',nativeReward:1,partialScore:88,taskScorecard:{version:'local-v1',overall:87,nativeVerificationId:'native-1',qualityReviewId:'review-1'}};
  verified.trials[0].captures[0]={...verified.trials[0].captures[0],manifest:{sha256:'capture-a'},nativeVerifications:[{id:'native-1',captureHash:'capture-a',adapter:'upstream',reward:1}]};
  const state={configs:[cfg()],archivedConfigs:[],runs:[verified],archivedRuns:[]};
  assert.equal(configResults(state)[0].score,87);
  verified.trials[0].captures[0].nativeVerifications[0].captureHash='old-capture';
  assert.equal(configResults(state)[0].score,null);
  assert.equal(entryScore(configResults(state)[0].entries[0]),null);
  verified.trials[0].score.scoreSource='project-rubric';
  assert.equal(configResults(state)[0].score,null);
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

test('different judge versions for different tasks remain labeled within a configuration score',()=>{
  const a=run('01','task-a',80),b=run('02','task-b',90);
  a.trials[0].score.machineReviewId='review-a';b.trials[0].score.machineReviewId='review-b';
  a.trials[0].reviews=[{id:'review-a',model:'gpt-6-luna',reasoningEffort:'max',scoreSchema:'v1'}];
  b.trials[0].reviews=[{id:'review-b',model:'gpt-5.6-luna',reasoningEffort:'max',scoreSchema:'v1'}];
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[a,b],archivedRuns:[]});
  assert.equal(result.score,85);
  assert.equal(result.judgeCount,2);
});

test('the same task with mixed judge protocols does not produce a configuration score',()=>{
  const a=run('01','task-a',80),b=run('02','task-a',90);
  a.trials[0].score.machineReviewId='review-a';b.trials[0].score.machineReviewId='review-b';
  a.trials[0].reviews=[{id:'review-a',model:'judge-a',scoreSchema:'v1'}];
  b.trials[0].reviews=[{id:'review-b',model:'judge-b',scoreSchema:'v1'}];
  const [result]=configResults({configs:[cfg()],archivedConfigs:[],runs:[a,b],archivedRuns:[]});
  assert.equal(result.score,null);
  assert.match(result.reason,/同题混有不同版本或评分协议/);
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

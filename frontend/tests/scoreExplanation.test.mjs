import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const transpile=path=>ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const url=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const capability=url(transpile('../src/workbench/capabilityProfiles.ts'));
const source=transpile('../src/workbench/scoreExplanation.ts').replace("'./capabilityProfiles'",JSON.stringify(capability));
const {currentNativeResult,currentTrialAxes,batchScoreSummary,totalScoreExplanation,programScoreExplanation,nativeTestProgress,missingScoreEvidence}=await import(url(source));

const task=(extra={})=>({id:'task-a',revision:1,title:'A',stages:[{title:'delivery'}],checks:[],...extra});
const trial=(extra={})=>({id:'t1',taskId:'task-a',state:'captured',captures:[{id:'c1',manifest:{sha256:'new'},nativeVerifications:[]}],reviews:[],score:{overall:null,machine:null},...extra});
const run=(t,items=[t])=>({id:'r1',policy:{version:'arena-machine-v1',dimensions:{intent:50,verification:30,handoff:20},rubrics:{}},tasks:[task()],trials:items});

test('no saved grade, reward or report means unknown; no pass is projected into axes',()=>{
  const item=trial(),r=run(item),publicTask=task({publicSource:{id:'some-public-task'}});
  assert.equal(currentNativeResult(item),undefined);
  assert.equal(programScoreExplanation(item,publicTask).value,'待验证');
  assert.ok(currentTrialAxes(r,item,publicTask).every(axis=>axis.score===null));
  assert.match(totalScoreExplanation(r,item,publicTask).status,/先运行原题程序验收/);
});

test('before native verification, absent card does not claim the public task is unsupported',()=>{
  const item=trial(),r=run(item),publicTask=task({publicSource:{id:'not-yet-verified'}});
  const explanation=totalScoreExplanation(r,item,publicTask);
  assert.match(explanation.formula,/原题尚未验收.*再查看是否有对应评分卡/);
  assert.match(explanation.formula,/未验收不表示本题不支持连续评分/);
  assert.doesNotMatch(explanation.formula,/本题没有对应的本地连续评分卡/);
});

test('upstream reward is read only from the selected report bound to current snapshot',()=>{
  const item=trial({score:{overall:null,nativeReward:1,nativeVerificationId:'native-1'}});
  item.captures[0].nativeVerifications=[{id:'native-1',captureHash:'old',reward:1,f2p_passed:2,f2p_total:2,p2p_passed:3,p2p_total:3}];
  const publicTask=task({publicSource:{id:'some-public-task'}}),r={...run(item),tasks:[publicTask]};
  assert.equal(programScoreExplanation(item,publicTask).value,'待验证');
  assert.equal(batchScoreSummary(r).nativeVerified,0);
  item.captures[0].nativeVerifications[0].captureHash='new';
  assert.equal(programScoreExplanation(item,publicTask).value,'通过');
  assert.match(totalScoreExplanation(r,item,publicTask).status,/没有本地连续评分卡/);
  assert.match(totalScoreExplanation(r,item,publicTask).formula,/已取得当前快照的原题结果.*本题没有对应的本地连续评分卡/);
  assert.ok(currentTrialAxes(r,item,publicTask).every(axis=>axis.score===null));
});

test('public radar uses only existing semantic groups, maintenance and regression',()=>{
  const publicTask=task({publicSource:{id:'adaptix-name-mapping-aliases'}});
  const item=trial({score:{overall:78.4,nativeVerificationId:'native-1',taskScorecard:{version:'deepswe-local-v1',overall:78.4,items:[
    {label:'目标行为',weight:70,ratio:1,points:70},
    {label:'旧功能与边界回归',weight:20,ratio:0,points:0},
    {label:'工程可维护性',weight:10,ratio:.84,points:8.4},
  ]}}});
  item.captures[0].nativeVerifications=[{id:'native-1',captureHash:'new',reward:0}];
  const axes=Object.fromEntries(currentTrialAxes(run(item),item,publicTask).map(axis=>[axis.id,axis.score]));
  assert.deepEqual(axes,{goal:100,engineering:84,web:null,reasoning:null,collaboration:null,reliability:0});
  assert.match(totalScoreExplanation(run(item),item,publicTask).formula,/70分.*20分.*10%/);
  assert.match(totalScoreExplanation(run(item),item,publicTask).status,/当前快照的原题验收与本地连续评分卡已有结果/);
});

test('project axes consume evidenced rubric values, preserve zero, and do not borrow overall',()=>{
  const values={intent:92,verification:40,robustness:80,maintainability:60,handoff:90,reasoning:0};
  const ratings=Object.fromEntries(Object.entries(values).map(([key,score])=>[key,{score,evidence:[{path:'app.py',line:1,quote:'real code'}]}]));
  const item=trial({reviews:[{id:'q1',captureId:'c1'}],score:{overall:99,machineReviewId:'q1',effectiveScores:values,machineRatings:ratings}});
  const axes=Object.fromEntries(currentTrialAxes(run(item),item,task()).map(axis=>[axis.id,axis.score]));
  assert.deepEqual(axes,{goal:92,engineering:60,web:null,reasoning:0,collaboration:90,reliability:70});
  item.reviews[0].captureId='old';
  assert.ok(currentTrialAxes(run(item),item,task()).every(axis=>axis.score===null));
});

test('batch mean waits for every saved total and never treats missing score as zero',()=>{
  const a=trial({score:{overall:0}}),b=trial({id:'t2',score:{overall:null}}),r=run(a,[a,b]);
  assert.deepEqual([batchScoreSummary(r).mean,batchScoreSummary(r).scored],[null,1]);
  b.score.overall=100;
  assert.equal(batchScoreSummary(r).mean,50);
});

test('native rate uses known trial outcomes, reports pending denominator separately',()=>{
  const publicTask=task({publicSource:{id:'some-public-task'}});
  const trials=[0,1,2].map(index=>trial({id:'t'+index,score:{overall:null,nativeVerificationId:'n'+index}}));
  trials[0].captures[0].nativeVerifications=[{id:'n0',captureHash:'new',reward:0}];
  trials[1].captures[0].nativeVerifications=[{id:'n1',captureHash:'new',reward:1}];
  const summary=batchScoreSummary({...run(trials[0],trials),tasks:[publicTask]});
  assert.deepEqual([summary.nativeTotal,summary.nativeVerified,summary.nativePassed,summary.nativeRate],[3,2,1,50]);
});

test('fixed test percentage is separate from AI grade and preserves failed zero',()=>{
  const item=trial({score:{overall:95,machine:95,programAcceptance:{version:'evalplus-originfmt-v1',scope:'原始扩展函数测试',score:0,passed:0,failed:1,unverified:0,total:1}}});
  assert.equal(programScoreExplanation(item,task({sourceKind:'evalplus-local'})).value,'0%');
  assert.match(programScoreExplanation(item,task()).detail,/整套扩展输入全部满足/);
  item.score.programAcceptance.score=null;item.score.programAcceptance.unverified=1;
  assert.equal(programScoreExplanation(item,task()).value,'待验证');
});

test('total explanation exposes actual missing groups and respects frozen historical formula',()=>{
  const item=trial({score:{overall:null,taskScorecard:{version:'project-tasktype-v3',items:[{label:'目标与范围',points:60},{label:'交付与维护',points:null}]}}});
  const summary=totalScoreExplanation(run(item),item,task());
  assert.deepEqual(summary.missing,['交付与维护']);
  assert.match(summary.formula,/60分.*25分.*15分/);
  const legacy={...run(item),policy:{version:'arena-review-v2',objectiveWeight:40,humanWeight:60}};
  assert.match(totalScoreExplanation(legacy,trial(),task()).formula,/40%.*60%/);
});

test('historical public task keeps its script/human formula instead of pretending it has a native scorecard',()=>{
  const publicTask=task({publicSource:{id:'historical-public-task'}});
  const item=trial({state:'completed',score:{overall:80,objective:100,human:60}});
  const r={...run(item),policy:{version:'arena-review-v2',objectiveWeight:50,humanWeight:50}};
  const explanation=totalScoreExplanation(r,item,publicTask);
  assert.equal(item.score.overall,(item.score.objective*50+item.score.human*50)/100);
  assert.match(explanation.formula,/脚本检查分 × 50%.*人工分 × 50%/);
  assert.match(explanation.status,/历史综合分.*冻结的脚本检查与人工权重/);
  assert.doesNotMatch(explanation.status,/原题验收与本地连续评分卡已有结果/);
  assert.deepEqual(explanation.missing,[]);
  item.score.overall=null;item.score.human=null;
  assert.deepEqual(totalScoreExplanation(r,item,publicTask).missing,['人工分']);
  assert.match(totalScoreExplanation(r,item,publicTask).status,/历史策略待补证据：人工分/);
});

test('failed native task exposes progress without an AI score or local card',()=>{
  const item=trial({score:{overall:null,nativeVerificationId:'n'}});
  item.captures[0].nativeVerifications=[{id:'n',captureHash:'new',reward:0,f2p_passed:1,f2p_total:4,p2p_passed:99,p2p_total:100}];
  assert.deepEqual([nativeTestProgress(item).target,nativeTestProgress(item).regression,nativeTestProgress(item).result.reward],[25,99,0]);
  item.captures[0].nativeVerifications[0].captureHash='old';
  assert.equal(nativeTestProgress(item),null);
});

test('native completion never rewards invalid or absent denominators',()=>{
  const item=trial({score:{nativeVerificationId:'n'}});
  item.captures[0].nativeVerifications=[{id:'n',captureHash:'new',reward:0,f2p_passed:2,f2p_total:1,p2p_passed:0,p2p_total:0}];
  assert.equal(nativeTestProgress(item).target,null);
  assert.equal(nativeTestProgress(item).regression,null);
});

test('missing observation names the actual counterevidence and its unchanged weight',()=>{
  const item=trial({score:{machineReviewId:'r',scoreProgress:{rows:[{key:'instruction',label:'规则',weight:10,points:null}]},machineRatings:{instruction:{score:null,checks:{coverage:{score:null,reason:'最高等级缺少有效反例证据'}}}}}});
  const [missing]=missingScoreEvidence(item,task());
  assert.equal(missing.section,'quality');assert.equal(missing.weight,10);
  assert.match(missing.reason,/反例证据/);
});

test('configured checks route missing verification to program rather than model',()=>{
  const item=trial({score:{scoreProgress:{rows:[{key:'verification',label:'验证',weight:5,points:null}]}}});
  Object.assign(item.captures[0],{checksConfigured:2,checks:[]});
  const [missing]=missingScoreEvidence(item,task({checks:[{id:'one'},{id:'two'}]}));
  assert.equal(missing.section,'checks');assert.match(missing.reason,/无需调用AI/);
});

test('old capture report is not advertised as the current project having no work',()=>{
  const item=trial({reviews:[{id:'old',kind:'ai',captureId:'old'}],score:{scoreProgress:{rows:[{key:'intent',label:'需求',weight:45,points:null}]}}});
  assert.match(missingScoreEvidence(item,task())[0].reason,/旧评分属于此前产物/);
  assert.equal(programScoreExplanation(item,task()).value,'未配置');
});

test('saved report invalidated by updated evidence is distinguished from absent work',()=>{
  const item=trial({reviews:[{id:'old',kind:'ai',captureId:'c1',scoreSchema:'arena-machine-v1',evidenceKey:'old-checks'}],score:{machineEvidenceKey:'current-checks',scoreProgress:{rows:[{key:'intent',label:'需求',weight:45,points:null}]}}});
  assert.match(missingScoreEvidence(item,task())[0].reason,/已有报告对应此前验收记录.*证据已变化/);
  item.reviews[0].scoreSchema=undefined;
  assert.match(missingScoreEvidence(item,task())[0].reason,/辅助意见/);
});

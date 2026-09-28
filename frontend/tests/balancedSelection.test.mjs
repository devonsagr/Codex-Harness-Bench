import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=readFileSync(new URL('../src/workbench/balancedSelection.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {balancedRandomIds,seededRandom,compactWebGenTask}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));

test('balanced draw alternates sides and spreads origins before repeating',()=>{
  const swe=[{id:'s1',group:'a'},{id:'s2',group:'a'},{id:'s3',group:'b'},{id:'s4',group:'c'}];
  const web=[{id:'w1',group:'svg'},{id:'w2',group:'svg'},{id:'w3',group:'page'},{id:'w4',group:'3d'}];
  const ids=balancedRandomIds(swe,web,3,item=>item.group,item=>item.group,()=>.4);
  assert.equal(ids.length,6);
  assert.equal(new Set(ids).size,6);
  assert.ok(ids.filter((_,index)=>index%2===0).every(id=>id.startsWith('s')));
  assert.ok(ids.filter((_,index)=>index%2===1).every(id=>id.startsWith('w')));
  assert.equal(new Set(ids.filter(id=>id.startsWith('s')).map(id=>swe.find(item=>item.id===id).group)).size,3);
  assert.equal(new Set(ids.filter(id=>id.startsWith('w')).map(id=>web.find(item=>item.id===id).group)).size,3);
});

test('balanced draw rejects oversized or invalid batches',()=>{
  const tasks=[{id:'a',group:'x'}];
  assert.throws(()=>balancedRandomIds(tasks,tasks,2,item=>item.group,item=>item.group),/可选题目不足/);
  assert.throws(()=>balancedRandomIds(tasks,tasks,0,item=>item.group,item=>item.group),/可选题目不足/);
});


test('fixed seed reproduces the draw despite catalog order changes',()=>{
  const a=Array.from({length:15},(_,i)=>({id:'a'+i,group:'g'+(i%3)}));
  const b=Array.from({length:30},(_,i)=>({id:'b'+i,group:'g'+(i%5)}));
  const draw=(left,right,seed)=>balancedRandomIds(left,right,5,t=>t.group,t=>t.group,seededRandom(seed));
  assert.deepEqual(draw(a,b,314),draw([...a].reverse(),[...b].reverse(),314));
  assert.notDeepEqual(draw(a,b,314),draw(a,b,315));
  assert.equal(new Set(draw(a,b,314)).size,10);
});

test('default draw rejects large web products even on older imported records',()=>{
  const task={description:'Productivity Applications',inputPrompt:'Create a local timer.',criteria:[{}]};
  assert.equal(compactWebGenTask(task),true);
  for(const inputPrompt of ['Build an API client.','Create an account system.','Build a multiplayer game.'])assert.equal(compactWebGenTask({...task,inputPrompt}),false);
  assert.equal(compactWebGenTask({...task,description:'Enterprise Resource Planning Systems'}),false);
  assert.equal(compactWebGenTask({...task,criteria:Array(8).fill({})}),false);
});

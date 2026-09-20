import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test,afterEach} from 'node:test';
import ts from 'typescript';

// Run the actual TypeScript helper without adding a browser or test dependency.
const source=readFileSync(process.env.CHB_API_SOURCE || new URL('../src/workbench/api.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ES2020}});
const api=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
const originalFetch=globalThis.fetch;
globalThis.document={querySelector:()=>({content:'test-token'})};
afterEach(()=>{globalThis.fetch=originalFetch;});

test('disconnected GET explains recovery and does not retry',async()=>{
  let calls=0;globalThis.fetch=async()=>{calls++;throw new TypeError('Failed to fetch');};
  await assert.rejects(api.request('/state'),/launch-ui.cmd.*刷新记录.*不会.*删除/);
  assert.equal(calls,1);
});
test('a lost POST response remains uncertain, never automatically resubmitted',async()=>{
  let calls=0;globalThis.fetch=async()=>{calls++;throw new TypeError('Failed to fetch');};
  await assert.rejects(api.request('/capture',{}),/结果尚未确认.*勿重复提交/);
  assert.equal(calls,1);
});
test('expired access token asks for a page reload, not a repeated operation',async()=>{
  globalThis.fetch=async()=>new Response(JSON.stringify({error:'invalid origin'}),{status:403});
  await assert.rejects(api.request('/capture',{}),/访问校验未通过.*保留未提交内容.*重新加载页面/);
});
test('business errors are preserved',async()=>{
  globalThis.fetch=async()=>new Response(JSON.stringify({error:'记录已经更新'}),{status:400});
  await assert.rejects(api.request('/capture',{}),/记录已经更新/);
});
test('an interrupted response body does not claim the operation failed',async()=>{
  globalThis.fetch=async()=>({ok:true,json:async()=>{throw new TypeError('terminated');}});
  await assert.rejects(api.request('/capture',{}),/完整读取.*核对结果.*勿重复提交/);
});
test('confirmed POST succeeds even when the next state read fails',async()=>{
  let calls=0;globalThis.fetch=async(_url,options)=>{
    calls++;assert.equal(options.method,'POST');assert.equal(options.headers['X-CHB-Token'],'test-token');
    return new Response(JSON.stringify({id:'saved-capture'}));
  };
  const result=await api.submitAndRefresh('/capture',{},async()=>{throw new TypeError('Failed to fetch');});
  assert.deepEqual(result,{result:{id:'saved-capture'},refreshed:false});assert.equal(calls,1);
});
test('successful write and refresh retain the server result',async()=>{
  globalThis.fetch=async()=>new Response(JSON.stringify({id:'saved-capture'}));
  let refreshed=false;
  assert.deepEqual(await api.submitAndRefresh('/capture',{},async()=>{refreshed=true;}),{result:{id:'saved-capture'},refreshed:true});
  assert.equal(refreshed,true);
});
test('rejected writes do not invoke refresh or return success',async()=>{
  globalThis.fetch=async()=>new Response(JSON.stringify({error:'版本冲突'}),{status:409});
  let refreshed=false;
  await assert.rejects(api.submitAndRefresh('/capture',{},async()=>{refreshed=true;}),/版本冲突/);
  assert.equal(refreshed,false);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/workbench/applicationStatus.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {applicationStatus,applicationErrorHelp}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const config={id:'a',revision:2};
const receipt={status:'applied',configId:'a',configRevision:2,settingsMatch:true};
test('file readiness requires the selected saved revision and verified managed settings',()=>{
  assert.equal(applicationStatus(receipt,config).ready,true);
  for(const active of [undefined,{...receipt,configId:'b'},{...receipt,configRevision:1},{...receipt,settingsMatch:false},{...receipt,settingsMatch:undefined},{...receipt,status:'applying'},{...receipt,status:'restore_failed'}])assert.equal(applicationStatus(active,config).ready,false);
  assert.equal(applicationStatus(receipt,config,true).ready,false);
  // A value unchanged by the original write can still drift later; receipt
  // matching alone must not override the current model/effort/speed readback.
  assert.equal(applicationStatus(receipt,config,false,true).ready,false);
  assert.match(applicationStatus(receipt,config).detail,/文件状态/);
});
test('restore conflicts give a next step without suggesting forced overwrite',()=>{
  const help=applicationErrorHelp('应用后的文件已被其他操作修改：config.toml；为保留你的修改，未执行撤销。');
  assert.match(help,/未覆盖/);assert.match(help,/核对当前文件/);assert.match(help,/当前任务结束/);
  assert.match(applicationErrorHelp('本工具写入的设置也已改变：model'),/未覆盖/);
  assert.match(applicationErrorHelp('工作台仍有执行或后台检查'),/先结束/);
});

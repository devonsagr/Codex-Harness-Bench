const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');
const [folder, task] = process.argv.slice(2);
const raw = fs.readFileSync(path.join(__dirname, 'cases.json'));
const cases = JSON.parse(raw)[task];
if (!cases) throw new Error('Unknown fixed task');
const context = vm.createContext({console: {log() {}, warn() {}, error() {}}});
let loadError = '';
try { vm.runInContext(fs.readFileSync(path.join(folder, 'model.js'), 'utf8'), context, {timeout: 2000}); }
catch (e) { loadError = String(e); }
function equal(actual, expected) {
  if (typeof expected === 'number') return typeof actual === 'number' && Number.isFinite(actual) && Math.abs(actual-expected) <= 1e-7;
  if (Array.isArray(expected)) return Array.isArray(actual) && actual.length === expected.length && expected.every((v,i)=>equal(actual[i],v));
  if (expected && typeof expected === 'object') return actual && typeof actual === 'object' && Object.keys(actual).length === Object.keys(expected).length && Object.keys(expected).every(k=>equal(actual[k],expected[k]));
  return actual === expected;
}
const rows = cases.map(test => {
  try {
    if (loadError) throw new Error(loadError);
    context.args = structuredClone(test.args);
    const before = JSON.stringify(context.args);
    const actual = vm.runInContext(`globalThis.CHBCore[${JSON.stringify(test.fn)}](...args)`, context, {timeout: 1000});
    if (!equal(actual, test.expected)) throw new Error('计算结果不符合固定输入的预期');
    if (JSON.stringify(context.args) !== before) throw new Error('修改了输入数据');
    return {id:test.id,status:'passed',detail:test.label};
  } catch (e) { return {id:test.id,status:'failed',detail:test.label+'：'+String(e).slice(0,500)}; }
});
console.log(JSON.stringify({version:'community-engine-v1',task,testSha256:crypto.createHash('sha256').update(raw).digest('hex'),rows}));
process.exitCode = rows.every(r=>r.status==='passed') ? 0 : 1;

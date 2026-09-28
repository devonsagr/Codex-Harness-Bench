/* Independent real-browser verifier; no AI call and no candidate network. */
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const {chromium} = require('playwright');

async function verify() {
  const root = process.argv[2] || '/app';
  const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1280,height:800},acceptDownloads:true});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try {
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    await page.getByRole('heading',{name:'业务概览'}).waitFor();
    await assertValue(page,'7 天','¥12,450');
    await assertValue(page,'30 天','¥48,700');
    await assertValue(page,'90 天','¥139,200');
    assert.ok(await page.getByText('/api/login').isVisible(),'Top API must be visible');
    for(const label of ['访问','注册','试用','付费'])assert.ok(await page.getByText(label,{exact:true}).isVisible(),`Missing funnel stage ${label}`);
    const button=page.getByRole('button',{name:'导出 CSV'});
    const [download]=await Promise.all([page.waitForEvent('download'),button.click()]);
    assert.match(download.suggestedFilename(),/\.csv$/i);
    const content=require('node:fs').readFileSync(await download.path(),'utf8');
    assert.match(content,/MRR/);assert.match(content,/139200/);assert.match(content,/\/api\/login/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Horizontal overflow at phone width');
    const range=page.getByRole('button',{name:'7 天'});
    await range.focus();await page.keyboard.press('Enter');
    assert.ok(await page.getByText('¥12,450').isVisible(),'Keyboard range switch failed');
    assert.deepEqual(errors,[],'Browser runtime errors');
    console.log('PASS: range, funnel, API, CSV, keyboard, narrow viewport, runtime');
  } finally { await browser.close(); }
}
async function assertValue(page,label,value){await page.getByRole('button',{name:label}).click();assert.ok(await page.getByText(value).isVisible(),`Missing ${value} after ${label}`);}
verify().catch(error=>{console.error(error);process.exitCode=1;});

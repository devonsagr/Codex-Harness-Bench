const {chromium} = require('playwright');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const [folder, task] = process.argv.slice(2);
(async()=>{
  const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1280,height:800}});
  const rows = [], errors = [];
  page.on('pageerror', e=>errors.push(String(e)));
  await page.route(/^https?:/, route=>route.abort());
  await page.addInitScript(()=>{
    let core = {};
    window.__chbCalls = 0;
    const wrap = value => new Proxy(value, {get(target,key){const fn=target[key];return typeof fn==='function'?function(...args){window.__chbCalls++;return fn.apply(target,args);}:fn;}});
    Object.defineProperty(window,'CHBCore',{configurable:true,get(){return wrap(core);},set(value){core=value;}});
  });
  const record = async(id, fn)=>{try{await fn();rows.push({id,status:'passed',detail:id});}catch(e){rows.push({id,status:'failed',detail:String(e).slice(0,500)});}};
  try {
    await page.goto(pathToFileURL(path.join(folder,'index.html')).href);
    await record('page-content',async()=>{if((await page.locator('body').innerHTML()).length<100)throw Error('页面为空');});
    const state = async expected=>{if((await page.getByRole('status').innerText({timeout:1000})).trim()!==expected)throw Error('实际运行状态没有切换为 '+expected);};
    await record('start-control',async()=>{await page.getByRole('button',{name:/^(开始|运行|自动播放)$/}).first().click({timeout:1500});await state('运行中');});
    await record('pause-control',async()=>{await page.getByRole('button',{name:'暂停',exact:true}).click({timeout:1500});await state('已暂停');});
    await record('reset-control',async()=>{await page.getByRole('button',{name:'重置',exact:true}).click({timeout:1500});await state('待开始');});
    await record('core-connection',async()=>{if(!await page.evaluate(()=>window.__chbCalls>0))throw Error('未观察到页面调用功能核心');});
    for(const width of [390,768,1280]) await record('layout-'+width,async()=>{await page.setViewportSize({width,height:800});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('页面横向溢出');});
    await record('runtime-errors',async()=>{if(errors.length)throw Error(errors.join('\n'));});
  } finally {await browser.close();}
  console.log(JSON.stringify({version:'community-interface-v1',task,rows,scope:'控制入口、核心调用与页面健康；不认证视觉质量或完整流程'}));
  process.exitCode = rows.every(r=>r.status==='passed') ? 0 : 1;
})().catch(e=>{console.error(String(e));process.exitCode=2;});

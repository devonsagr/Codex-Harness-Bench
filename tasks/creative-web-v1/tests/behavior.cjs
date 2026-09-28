// Trusted, black-box probes. Never load candidate JavaScript into Node.
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const crypto=require('node:crypto');
const fs=require('node:fs');
const VERSION='creative-behavior-v3';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const definitions={
  'golden-gate-fog-v1': ['scene-switch','scene-return','scene-keyboard'],
  'mini-exhibit-3d-v1': ['rotate-left','rotate-right','rotate-keyboard'],
  'energy-dashboard-v1': ['weekly-total','weekly-comparison','daily-values'],
  'pixel-postcard-v1': ['draw','undo','clear','export'],
  'meteor-rescue-v1': ['start','pause','resume','restart'],
};
class Unknown extends Error {}
async function run(root,task,artifacts){
  if(!definitions[task])throw Error('Unknown trusted task protocol');
  if(artifacts)fs.mkdirSync(artifacts,{recursive:true});
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1280,height:800},acceptDownloads:true,reducedMotion:'reduce'});
  const page=await context.newPage();page.setDefaultTimeout(1800);
  let errors=[],remote=[];const rows=[];
  page.on('pageerror',e=>errors.push(e.message));
  await context.route(/^https?:/,route=>{remote.push(route.request().url());return route.abort();});
  const result=(id,status,detail,evidence={})=>rows.push({id,status,detail,evidence});
  const probe=async(id,fn)=>{try{const x=await fn();result(id,x.ok?'passed':'failed',x.detail,x.evidence);}
    catch(e){result(id,'unverified',e instanceof Unknown?e.message:'无法可靠执行此项操作：'+String(e.message).slice(0,240));}};
  const settle=async()=>{await page.evaluate(()=>document.activeElement?.blur());await page.mouse.move(0,0);await page.waitForTimeout(400);};
  async function control(pattern){
    const matches=page.getByRole('button',{name:pattern}).or(page.getByRole('radio',{name:pattern})).or(page.getByRole('tab',{name:pattern}));
    const visible=[];for(let i=0;i<await matches.count();i++)if(await matches.nth(i).isVisible())visible.push(matches.nth(i));
    if(visible.length!==1)throw new Unknown('无法唯一识别操作控件；不把定位失败记作功能失败。');
    return visible[0];
  }
  async function surface(threeD=false){
    // Choose a rendered artwork, not the whole page (button text is not evidence).
    const options=await page.locator('canvas,svg,[role="grid"]').evaluateAll(nodes=>nodes.map((n,i)=>({i,area:n.getBoundingClientRect().width*n.getBoundingClientRect().height})).filter(n=>n.area>20000).sort((a,b)=>b.area-a.area));
    if(options.length)return page.locator('canvas,svg,[role="grid"]').nth(options[0].i);
    if(threeD){
      const selector=await page.locator('main *').evaluateAll(nodes=>{
        const n=nodes.find(n=>getComputedStyle(n).perspective!=='none'&&n.getBoundingClientRect().width>100);
        if(!n)return null;
        n.setAttribute('data-chb-observed-surface','true');return '[data-chb-observed-surface="true"]';
      });
      if(selector)return page.locator(selector);
    }
    throw new Unknown('没有识别到独立画布或场景；需要补充适配，不能据此断言作品不合格。');
  }
  async function shot(s){const bytes=await s.screenshot({animations:'disabled'});if(artifacts)fs.writeFileSync(path.join(artifacts,hash(bytes)+'.png'),bytes);return bytes;}
  async function stable(s){const a=await shot(s);await page.waitForTimeout(250);const b=await shot(s);
    if(!a.equals(b))throw new Unknown('场景在无操作时也变化，不能把自然动画误判为交互成功。');return a;}
  async function changed(s,operation){const a=await stable(s);await operation();await settle();const b=await stable(s);
    return {ok:!a.equals(b),detail:'比较操作前后独立场景，排除按钮文字与焦点变化。',evidence:{before:hash(a),after:hash(b)}};}
  try{
    await page.goto(pathToFileURL(path.join(root,'index.html')).href,{waitUntil:'load'});await settle();
    if(task==='golden-gate-fog-v1'){
      let dawn;
      await probe('scene-switch',async()=>{await(await control(/晨|清晨|dawn|morning/i)).click();await settle();const s=await surface();dawn=await stable(s);return changed(s,async()=>{await(await control(/夜|night/i)).click();});});
      await probe('scene-return',async()=>{if(!dawn)throw new Unknown('未建立晨景基线。');const s=await surface();await(await control(/晨|清晨|dawn|morning/i)).click();await settle();const after=await stable(s);return {ok:dawn.equals(after),detail:'切回晨景后，场景应恢复到相同画面。',evidence:{before:hash(dawn),after:hash(after)}};});
      await probe('scene-keyboard',async()=>changed(await surface(),async()=>{const c=await control(/夜|night/i);await c.focus();await c.press('Space');}));
    }else if(task==='mini-exhibit-3d-v1'){
      await probe('rotate-left',async()=>changed(await surface(true),async()=>{await(await control(/左|left/i)).click();}));
      await probe('rotate-right',async()=>changed(await surface(true),async()=>{await(await control(/右|right/i)).click();}));
      await probe('rotate-keyboard',async()=>changed(await surface(true),async()=>{const c=await control(/右|right/i);await c.focus();await c.press('Enter');}));
    }else if(task==='energy-dashboard-v1'){
      const text=await page.locator('body').innerText();
      await probe('weekly-total',async()=>{
        const match=text.match(/(?:本周|this week|weekly total)[^\d]{0,40}(\d+(?:\.\d+)?)/i);
        if(!match)throw new Unknown('没有唯一可读的本周总量标签，不能仅靠页面出现 63 判对。');
        return {ok:Number(match[1])===63,detail:'9+8+11+10+7+12+6 = 63 kWh。',evidence:{observed:match[0],expected:63}};
      });
      await probe('weekly-comparison',async()=>{
        const m=text.replace(/−/g,'-').match(/(?:下降|减少|降低|节省|decrease|less|down)[^\d]{0,20}(\d+(?:\.\d+)?)\s*%|(-\s*\d+(?:\.\d+)?)\s*%/i);
        if(!m)throw new Unknown('未识别到明确方向的环比值；单独出现 10% 不能证明下降。');
        return {ok:Math.abs(Number((m[1]||m[2]).replace(/\s/g,'')))===10,detail:'(63−70)/70 = −10%，必须标明下降方向。',evidence:{observed:m[0],expected:-10}};
      });
      await probe('daily-values',async()=>{
        const names=[/周一|星期一|Monday/i,/周二|星期二|Tuesday/i,/周三|星期三|Wednesday/i,/周四|星期四|Thursday/i,/周五|星期五|Friday/i,/周六|星期六|Saturday/i,/周日|周天|星期日|Sunday/i];
        const marks=await page.locator('svg [aria-label],svg title,[role="img"][aria-label],tr').evaluateAll(nodes=>nodes.map(n=>{
          if(n.tagName==='TR'&&/kWh|千瓦时|度/i.test(n.closest('table')?.textContent||'')){
            const cells=[...n.querySelectorAll('td')].map(c=>c.textContent.trim());
            if(cells.length===2&&/^\d+(?:\.\d+)?$/.test(cells[1]))return cells.join(' ')+' kWh';
          }
          return n.getAttribute('aria-label')||n.textContent;
        }));
        const values=names.map(n=>{const candidates=marks.filter(t=>n.test(t)&&names.filter(day=>day.test(t)).length===1).map(t=>t.match(/(\d+(?:\.\d+)?)\s*(?:kWh|千瓦时|度)/i)).filter(Boolean).map(m=>Number(m[1]));const unique=[...new Set(candidates)];return unique.length===1?unique[0]:null;});
        if(values.some(v=>v===null))throw new Unknown('图表没有足够的逐日可读数值；本项未验证，不据此评价绘制位置是否正确。');
        return {ok:values.every((v,i)=>v===[9,8,11,10,7,12,6][i]),detail:'逐日图表可读数据与给定序列一致；图形比例仍需另审。',evidence:{observed:values}};
      });
    }else if(task==='pixel-postcard-v1'){
      const draw=async(s,fraction)=>{const b=await s.boundingBox();if(!b)throw new Unknown('画布不可见');await page.mouse.click(b.x+b.width*fraction,b.y+b.height*0.4);await settle();};
      let beforeDraw;
      let drew=false;
      await probe('draw',async()=>{const s=await surface();beforeDraw=await stable(s);const r=await changed(s,()=>draw(s,0.35));drew=r.ok;if(!drew)throw new Unknown('本次绘制没有可见变化，可能与原像素同色，不能据此认定画笔失效。');return r;});
      await probe('undo',async()=>{if(!beforeDraw||!drew)throw new Unknown('未建立实际改变画布的绘制基线');const s=await surface();await(await control(/撤销|undo/i)).click();await settle();const b=await stable(s);return {ok:beforeDraw.equals(b),detail:'撤销一次绘制后，画布必须恢复到绘制前。',evidence:{before:hash(beforeDraw),after:hash(b)}};});
      await probe('clear',async()=>{
        // Clear two different drawings. Idempotence alone would allow a no-op.
        page.on('dialog',d=>d.accept());const s=await surface();await draw(s,0.35);const a=await stable(s);
        await(await control(/清空|清除画布|clear/i)).click();await settle();const emptyA=await stable(s);
        await draw(s,0.65);const b=await stable(s);if(b.equals(emptyA))throw new Unknown('第二次绘制未产生可见变化，不能用同一空画布证明清空有效。');await(await control(/清空|清除画布|clear/i)).click();await settle();const emptyB=await stable(s);
        return {ok:!a.equals(emptyA)&&!b.equals(emptyB)&&emptyA.equals(emptyB),detail:'两次不同绘制清空后收敛到同一画布，且确实移除了绘制。',evidence:{paintA:hash(a),paintB:hash(b),clearA:hash(emptyA),clearB:hash(emptyB)}};
      });
      await probe('export',async()=>{
        const s=await surface();if(await s.evaluate(n=>n.tagName.toLowerCase())!=='canvas')throw new Unknown('此实现不是 Canvas，需要适配导出与画布像素对照。');
        await draw(s,0.4);
        const pending=page.waitForEvent('download',{timeout:2500});pending.catch(()=>{});
        let exportControl;
        try{exportControl=await control(/PNG/i);}catch(e){if(!(e instanceof Unknown))throw e;exportControl=await control(/导出|export|下载|download/i);}
        await exportControl.click();const d=await pending;
        const stream=await d.createReadStream();if(!stream)throw new Unknown('导出文件无法读取');const chunks=[];for await(const c of stream)chunks.push(c);const raw=Buffer.concat(chunks);
        const type=raw.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))?'image/png':/^\s*(?:<\?xml[^>]*>\s*)?<svg[\s>]/.test(raw.toString('utf8'))?'image/svg+xml':null;
        if(!type)return {ok:false,detail:'下载结果不是 PNG/SVG。',evidence:{bytes:raw.length}};
        const compare=await s.evaluate(async(canvas,{uri})=>{
          const image=new Image();image.src=uri;await image.decode();
          if(image.naturalWidth*image.naturalHeight>4000000)return null;
          const actual=document.createElement('canvas'),expected=document.createElement('canvas');
          actual.width=expected.width=image.naturalWidth;actual.height=expected.height=image.naturalHeight;
          actual.getContext('2d').drawImage(image,0,0);
          const ctx=expected.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(canvas,0,0,expected.width,expected.height);
          const a=ctx.getImageData(0,0,expected.width,expected.height).data,b=actual.getContext('2d').getImageData(0,0,actual.width,actual.height).data;
          const sx=image.naturalWidth/canvas.width,sy=image.naturalHeight/canvas.height;
          return {equal:a.every((v,i)=>v===b[i]),integerScale:sx===sy&&Number.isInteger(sx)&&sx>=1,opaque:a.every((v,i)=>i%4!==3||v===255),width:image.naturalWidth,height:image.naturalHeight};
        },{uri:'data:'+type+';base64,'+raw.toString('base64')});
        if(!compare)throw new Unknown('无法读取画布像素进行导出对照。');
        if(!compare.equal&&type==='image/png'&&compare.integerScale&&compare.opaque)return {ok:false,detail:'PNG 与按整数倍放大的不透明像素画布内容不一致。',evidence:{fileHash:hash(raw),...compare}};
        if(!compare.equal)throw new Unknown('导出与画布像素不一致，可能是背景/缩放也可能是内容错误，需进一步核对；不自动判失败。');
        return {ok:true,detail:'实际下载文件可解码，并与当前画布逐像素一致。',evidence:{fileHash:hash(raw),...compare}};
      });
    }else if(task==='meteor-rescue-v1'){
      let started=false,pauseControl;
      await probe('start',async()=>{const s=await surface();await(await control(/开始救援|开始游戏|^开始$|^start(?: game)?$/i)).click();await page.waitForTimeout(200);const a=await shot(s);await page.waitForTimeout(350);const b=await shot(s);started=!a.equals(b);return {ok:started,detail:'开始后两个时点实际游戏画面在推进；不能只是切换一张静态海报。',evidence:{before:hash(a),after:hash(b)}};});
      await probe('pause',async()=>{if(!started)throw new Unknown('无法建立游戏进行中的基线');const s=await surface();const c=await control(/暂停|pause/i);pauseControl=await c.elementHandle();await c.click();await settle();const a=await shot(s);await page.waitForTimeout(700);const b=await shot(s);return {ok:a.equals(b),detail:'暂停后两个时点游戏画布保持一致；不包含外部按钮。',evidence:{before:hash(a),after:hash(b)}};});
      await probe('resume',async()=>{if(!started||!pauseControl)throw new Unknown('未建立暂停控件对应关系');const s=await surface();const a=await shot(s);await pauseControl.click();await page.waitForTimeout(700);const b=await shot(s);return {ok:!a.equals(b),detail:'恢复后游戏画布继续变化。',evidence:{before:hash(a),after:hash(b)}};});
      await probe('restart',async()=>{if(!started)throw new Unknown('未开始游戏');const pattern=/(?:得分|分数|已救援|成功次数|score)[^\d]{0,20}(\d+)/i;const before=(await page.locator('body').innerText()).match(pattern);if(!before||Number(before[1])===0)throw new Unknown('尚未观察到非零计分，无法证明重开确实复位。');await(await control(/重新开始|重开|restart/i)).click();await settle();const m=(await page.locator('body').innerText()).match(pattern);if(!m)throw new Unknown('重开后未找到计分读数。');return {ok:Number(m[1])===0,detail:'重新开始后可见计分从非零归零；碰撞和失败规则另行验证。',evidence:{before:before[0],observed:m[0]}};});
    }
    await probe('mobile-layout',async()=>{const samples=[];for(const width of [390,768,1280]){await page.setViewportSize({width,height:800});await page.waitForTimeout(50);samples.push(await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth})));}return {ok:samples.every(s=>s.content<=s.width+1),detail:'三个视口没有页面级横向溢出；不代表所有控件均可用。',evidence:{samples}};});
    result('runtime-errors',errors.length?'failed':'passed','本次操作路径中的未捕获脚本异常。',{errors:errors.slice(0,8)});
    result('offline',remote.length?'failed':'passed','本次路径不依赖 HTTP/HTTPS 网络请求。',{requests:remote.slice(0,8)});
  }catch(e){
    for(const id of [...definitions[task],'mobile-layout','runtime-errors','offline'])if(!rows.some(r=>r.id===id))result(id,'unverified','浏览器或页面启动未完成：'+String(e.message).slice(0,200));
  }finally{await browser.close();}
  return {version:VERSION,task,rows};
}
module.exports={run,definitions,VERSION};
if(require.main===module)run(process.argv[2]||'/app',process.argv[3],process.argv[4]).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e.message);process.exitCode=2;});

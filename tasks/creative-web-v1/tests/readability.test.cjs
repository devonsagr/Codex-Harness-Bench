const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
const {collectReadability}=require('./readability.cjs');

test('readability facts distinguish a usable baseline from visible defects',async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.CHB_CHROMIUM_PATH||undefined});
  try{
    const page=await browser.newPage();
    for(const width of [320,390,768,1280]){
      await page.setViewportSize({width,height:800});
      await page.goto(pathToFileURL(path.join(__dirname,'fixtures/readability-good.html')).href);
      const good=await page.evaluate(collectReadability);
      assert.deepEqual(good.concerns,[],'metadata and hidden text must not become body defects');
      await page.goto(pathToFileURL(path.join(__dirname,'fixtures/readability-defects.html')).href);
      const bad=await page.evaluate(collectReadability);
      assert.equal(bad.smallestBodyFont,8);
      assert.deepEqual(new Set(bad.concerns.map(row=>row.kind)),new Set(['small-text','clipped-text','overlapping-text','small-control']));
      const overlap=bad.concerns.filter(row=>row.kind==='overlapping-text');
      assert.equal(overlap.length,1,'hidden parts of clipped text cannot overlap visible text');
      assert.equal(overlap[0].text,'重叠文字甲');assert.equal(overlap[0].otherText,'重叠文字乙');
      assert.ok(await page.getByRole('heading',{name:'预约时间'}).isVisible());
      await page.getByRole('button',{name:'确认预约'}).click();
      assert.ok(await page.getByText('预约已确认',{exact:true}).isVisible(),'basic interaction can work while text is unreadable');
    }
  }finally{await browser.close();}
});

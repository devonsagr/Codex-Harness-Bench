/* Fixed offline measurements; completion is not a task pass or a design grade. */
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
const {collectReadability}=require('./readability.cjs');

async function measure(){
  const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.CHB_CHROMIUM_PATH||undefined});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:800}});
    await page.route(/^https?:\/\//,route=>route.abort());
    await page.goto(pathToFileURL(path.join(process.argv[2]||'/app','index.html')).href,{waitUntil:'load',timeout:15000});
    for(const width of [320,390,768,1280]){
      await page.setViewportSize({width,height:800});
      await page.waitForTimeout(150);
      console.log('BROWSER_READABILITY '+JSON.stringify(await page.evaluate(collectReadability)));
    }
  }finally{await browser.close();}
}
measure().catch(error=>{console.error('Browser measurement unavailable: '+error.message);process.exitCode=2;});

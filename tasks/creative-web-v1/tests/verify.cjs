/* Shared browser checks. They do not judge aesthetics or task-specific semantics. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

const root = process.argv[2] || '/app';
const profile = process.argv[3] || 'page';
const profiles = new Set(['svg', 'interactive-svg', 'page', 'data', 'interactive', 'form']);

async function verify() {
  assert.ok(profiles.has(profile), 'Unknown trusted creative-web check profile');
  assert.ok(fs.statSync(path.join(root, 'index.html')).isFile(), 'Missing index.html');
  const browser = await chromium.launch({headless:true,args:['--no-sandbox'],
    executablePath:process.env.CHB_CHROMIUM_PATH || undefined});
  const page = await browser.newPage({viewport:{width:1280,height:800}});
  const errors = [];
  const remoteRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {if (/^https?:/i.test(request.url())) remoteRequests.push(request.url());});
  try {
    await page.goto(pathToFileURL(path.join(root, 'index.html')).href, {waitUntil:'load'});
    await page.waitForTimeout(300);
    assert.ok(await page.locator('main').count(), 'Use a main landmark');
    assert.ok(await page.locator('h1').count(), 'The page needs a visible primary heading');
    assert.ok(await page.locator('h1').first().isVisible(), 'Primary heading is hidden');
    assert.ok((await page.locator('body').innerText()).trim().length >= 35, 'The page has too little visible content');
    console.log('PASS: visible main landmark, heading and content');

    let artworkSvg=null;
    if (profile.includes('svg')) {
      const candidates=page.locator('main svg');
      assert.ok(await candidates.count(), 'The artwork or map needs inline SVG');
      let area=0;
      for(let index=0;index<await candidates.count();index++){
        const box=await candidates.nth(index).boundingBox();
        if(box && box.width*box.height>area){area=box.width*box.height;artworkSvg=candidates.nth(index);}
      }
      const svg=artworkSvg;
      assert.ok(svg, 'The SVG artwork must occupy visible space');
      assert.ok(await svg.isVisible(), 'SVG is not visible');
      assert.ok(await svg.locator('path,rect,circle,ellipse,line,polygon,polyline,text,use').count() >= 5,
        'SVG is too sparse for the requested scene');
      assert.ok(await svg.getAttribute('viewBox'), 'SVG needs a responsive viewBox');
      assert.ok(await svg.getAttribute('aria-label') || await svg.locator('title').count(), 'SVG needs an accessible name');
      console.log('PASS: visible, named and responsive SVG structure');
    }
    if (profile === 'data') {
      assert.ok(await page.locator('svg,canvas').count(), 'A data graphic is required');
    }
    if (profile === 'form') {
      assert.ok(await page.locator('input,select,textarea').count(), 'A user input is required');
      assert.ok(await page.getByRole('button').count(), 'A form action is required');
      const named=await page.locator('input,select,textarea').evaluateAll(elements => elements.some(element =>
        element.getClientRects().length>0 && (element.labels?.length || element.getAttribute('aria-label') || element.getAttribute('aria-labelledby'))));
      assert.ok(named, 'At least one visible form input needs an accessible label');
      console.log('PASS: visible form input, accessible name and action');
    }
    if (profile === 'interactive' || profile === 'interactive-svg') {
      const buttons = page.locator('button,[role="button"],[role="radio"],[role="tab"],[role="switch"]');
      assert.ok(await buttons.count(), 'A visible interactive control is required');
      let changed = false;
      for (let i=0; i<Math.min(await buttons.count(), 5); i++) {
        const button = buttons.nth(i);
        if (!await button.isVisible() || !await button.isEnabled()) continue;
        await page.evaluate(() => document.activeElement?.blur());
        const before = await page.locator('main').innerHTML();
        const beforeImage = await (artworkSvg||page.locator('main').first()).screenshot({animations:'disabled'});
        await button.click();
        await page.evaluate(() => document.activeElement?.blur());
        await page.waitForTimeout(100);
        const after = await page.locator('main').innerHTML();
        const afterImage = await (artworkSvg||page.locator('main').first()).screenshot({animations:'disabled'});
        if (profile==='interactive-svg'?!beforeImage.equals(afterImage):before!==after || !beforeImage.equals(afterImage)) { changed=true; break; }
      }
      assert.ok(changed,profile==='interactive-svg'?'A control must visibly change the artwork, not only its own label':'At least one control must persistently update the page');
      console.log('PASS: visible interaction after removing focus-only changes');
      await page.reload({waitUntil:'load'});
      let keyboardAction=false;
      for(let i=0;i<20;i++){
        await page.keyboard.press('Tab');
        const focused=page.locator(':focus');
        if(await focused.count() && await focused.evaluate(element => element.matches('button,[role="button"],[role="radio"],[role="tab"],[role="switch"]'))){
          const before = await page.locator('main').innerHTML();
          const beforeImage = await (artworkSvg||page.locator('main').first()).screenshot({animations:'disabled'});
          const key=await focused.evaluate(element => element.matches('[role="radio"],[role="tab"]')?'ArrowRight':
            element.matches('[role="switch"]')?'Space':'Enter');
          await page.keyboard.press(key);
          await page.evaluate(() => document.activeElement?.blur());
          await page.waitForTimeout(100);
          const after = await page.locator('main').innerHTML();
          const afterImage = await (artworkSvg||page.locator('main').first()).screenshot({animations:'disabled'});
          keyboardAction=profile==='interactive-svg'?!beforeImage.equals(afterImage):before!==after || !beforeImage.equals(afterImage);
          if(keyboardAction)break;
        }
      }
      assert.ok(keyboardAction,'A keyboard-reachable control must persistently change the page');
      console.log('PASS: keyboard interaction visibly changes the page');
    }

    for (const width of [320,390,768,1280]) {
      await page.setViewportSize({width,height:800});
      await page.waitForTimeout(100);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        `Horizontal overflow at ${width}px`);
      const heading=await page.locator('h1').first().boundingBox();
      assert.ok(heading && heading.width>0 && heading.x>=-1 && heading.x+heading.width<=width+1,
        `Primary heading is clipped at ${width}px`);
    }
    console.log('PASS: no horizontal overflow or clipped heading at 320/390/768/1280px');
    assert.deepEqual(errors, [], 'Browser runtime errors');
    console.log('PASS: no browser runtime exception');
    assert.deepEqual(remoteRequests, [], 'Offline task attempted external network resources');
    console.log('PASS: no external network dependency');
    console.log(`PASS: ${profile} browser checks; visual quality and task-specific requirements still need separate evidence`);
  } finally {
    await browser.close();
  }
}
verify().catch(error => {console.error(error);process.exitCode=1;});

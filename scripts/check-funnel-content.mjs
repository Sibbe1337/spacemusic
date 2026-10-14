import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { playwrightModule } from './funnel-support.mjs';
const [origin, stage='2'] = process.argv.slice(2);
const {chromium} = await import(playwrightModule);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
  const routes=[{path:'/guides/music-catalog-valuation-2026/',title:'Music Catalog Valuation Guide 2026: How Much Is Your Catalog Worth?'}];
  if(Number(stage)>=3) routes.push({path:'/blog/music-catalog-sale-documents-checklist/',title:"Music Catalog Sale Documents: A Seller's Checklist"});
  if(Number(stage)>=4) routes.push({path:'/blog/music-catalog-offer-checklist/',title:'Music Catalog Offer Checklist: Questions Before You Sign'});
  const ctx=await browser.newContext();
  await ctx.route('**/*',r=>r.request().method()!=='GET'||new URL(r.request().url()).hostname.includes('plausible.io')?r.abort():r.continue());
  const page=await ctx.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/',{waitUntil:'networkidle'});
  await page.getByRole('link',{name:'Valuation Guide',exact:true}).last().click();
  await page.getByRole('heading',{name:routes[0].title,exact:true}).waitFor();
  await page.waitForFunction(()=>document.title.includes('Method, Example'));
  const text=await page.locator('main').innerText();
  assert(text.includes('$24,000'));
  assert(!/hundreds of deals|hundreds of catalogs|48 hours|3× to 15×|20–40%/.test(text));
  const data=JSON.parse(await readFile('marketing/funnel/valuation-guide.json','utf8'));
  for(const section of data.sections) await page.getByRole('heading',{name:section.heading,exact:true}).waitFor();
  for(const route of routes) {
    for(const width of [390,320,1440]) {
      await page.setViewportSize({width,height:900});
      await page.goto(origin+route.path,{waitUntil:'networkidle'});
      assert.equal(await page.locator('h1').innerText(),route.title);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${route.path} overflow ${width}`);
      assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),'https://spacemusic.io'+route.path);
    }
    for(const target of routes.slice(1)) {
      await page.goto(origin+routes[0].path,{waitUntil:'networkidle'});
      const link=page.locator(`main a[href="${target.path}"]`);
      assert.equal(await link.count(),1);
      await link.press('Enter');
      await page.getByRole('heading',{name:target.title,exact:true}).waitFor();
    }
    const noJs=await browser.newContext({javaScriptEnabled:false});
    const staticPage=await noJs.newPage();
    await staticPage.goto(origin+route.path);
    assert.equal(await staticPage.locator('h1').innerText(),route.title);
    assert.equal(await staticPage.locator('link[rel="canonical"]').getAttribute('href'),'https://spacemusic.io'+route.path);
    const body=await staticPage.locator('main').innerText();
    assert(body.length>5000,`${route.path} missing static article`);
    await noJs.close();
  }
  await page.goto(origin+routes[0].path,{waitUntil:'networkidle'});
  await page.getByRole('link',{name:'Build a Sale Scenario',exact:true}).click();
  await page.getByLabel('Assumed annual-income multiple').waitFor();
  await page.getByRole('link',{name:'Request a free catalog review',exact:true}).first().click();
  await page.getByRole('heading',{name:'We buy your music catalog.',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({origin,stage,routes:routes.map(r=>r.path),mobile:[320,390],desktop:true,keyboard:true,staticContent:true,guideLinks:true,correctCalculatorAndApply:true,errors}));
} finally {await browser.close();}

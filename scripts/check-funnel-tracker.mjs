import assert from 'node:assert/strict';
import path from 'node:path';
import { readFile, stat } from 'node:fs/promises';
import { playwrightModule } from './funnel-support.mjs';
const root=path.resolve(process.argv[2]);
const {chromium}=await import(playwrightModule);
const browser=await chromium.launch({channel:'chrome',headless:true});
const captured=[];
try {
  const context=await browser.newContext();
  // Plausible deliberately ignores webdriver unless its test flag is set.
  // This is only used inside this intercepted context, never in shipped code.
  await context.addInitScript(() => { window.__plausible = true; });
  await context.route('**/*',async route=>{
    const req=route.request(),u=new URL(req.url());
    if(u.hostname==='plausible.io' && req.method()==='POST') {
      captured.push(JSON.parse(req.postData()));
      return route.fulfill({status:202,body:'',headers:{'access-control-allow-origin':'*'}});
    }
    if(u.hostname==='spacemusic.io' && req.method()==='GET') {
      try {
        let file=path.resolve(root,'.'+u.pathname);
        assert(file.startsWith(root+path.sep)||file===root);
        if((await stat(file)).isDirectory()) file=path.join(file,'index.html');
        const contentType={'.html':'text/html','.js':'application/javascript','.css':'text/css','.woff2':'font/woff2','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream';
        return route.fulfill({status:200,body:await readFile(file),contentType});
      }catch{return route.fulfill({status:404,body:'missing'});}
    }
    if(req.method()==='GET' && ['plausible.io','fonts.googleapis.com','fonts.gstatic.com'].includes(u.hostname)) return route.continue();
    return route.abort();
  });
  const page=await context.newPage();
  await page.goto('https://spacemusic.io/calculator/?utm_source=PRIVATE#SECRET',{waitUntil:'networkidle'});
  await page.getByLabel('Monthly net income (USD)',{exact:true}).fill('1000');
  await page.getByLabel('Assumed annual-income multiple').fill('4');
  await page.waitForTimeout(700);
  await page.getByRole('link',{name:'Request a free catalog review',exact:true}).first().click();
  await page.getByLabel('Email',{exact:true}).fill('private@example.invalid');
  await page.waitForTimeout(700);
  assert(captured.some(e=>e.n==='pageview'));
  for(const name of ['calculator_used','apply_clicked','application_started']) assert(captured.some(e=>e.n===name),`Real tracker did not emit ${name}`);
  assert(!captured.some(e=>e.n==='application_submitted'));
  assert(!/PRIVATE|SECRET|private@example|1000/.test(JSON.stringify(captured)));
  for(const e of captured) {
    assert(!e.u.includes('?')&&!e.u.includes('#'));
    for(const key of Object.keys(e.p||{})) assert(['landing_path','apply_source_path'].includes(key));
  }
  const pageviews=captured.filter(e=>e.n==='pageview').map(e=>new URL(e.u).pathname);
  console.log(JSON.stringify({realPlausibleScript:true,networkIntercepted:true,noRequestsSentToAnalytics:true,noReceiverRequests:true,events:captured.map(e=>e.n),pageviews,privacy:'passed',dashboardReporting:'not proven by this mocked test'}));
  if(process.env.EXPECT_DIRECT_APPLY==='1') assert.deepEqual(pageviews,['/calculator/','/apply/'],'One pageview per real page, not an intermediate SPA route');
}finally{await browser.close();}

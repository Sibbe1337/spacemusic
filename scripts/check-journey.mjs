import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { serve,playwrightModule } from './funnel-support.mjs';
const [target]=process.argv.slice(2),server=target.startsWith('http')?null:await serve(target),origin=server?.origin||target.replace(/\/$/,'');
const {chromium}=await import(playwrightModule),browser=await chromium.launch({channel:'chrome',headless:true});
const cta='Request a free catalog review',errors=[];
let page;
const failedRequests=[];
await mkdir('tmp/journey-qa/screenshots',{recursive:true});
try {
  const ctx=await browser.newContext();let submissions=0;
  await ctx.route('**/*',route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.hostname==='formspree.io') { assert.equal(url.pathname,'/f/mpwdnokz');assert.equal(req.method(),'POST');submissions++;return route.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'}); }
    if(req.method()!=='GET'||url.hostname.includes('plausible.io'))return route.abort();
    return route.continue();
  });
  page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('requestfailed',request=>{
    if(new URL(request.url()).origin===origin)failedRequests.push({url:request.url(),error:request.failure()?.errorText});
  });
  for(const route of ['/','/how-it-works/','/sell/','/calculator/','/apply/','/blog/music-catalog-offer-checklist/']) {
    for(const width of [320,390,768,1024,1440]) {
      await page.setViewportSize({width,height:900});await page.goto(origin+route,{waitUntil:'networkidle'});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${route} overflow ${width}`);
      assert.equal(await page.locator('h1').count(),1);
      assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),'https://spacemusic.io'+route);
      if(width===320 || width===1440) await page.screenshot({path:`tmp/journey-qa/screenshots/${route.replaceAll('/','_')}-${width}.png`,fullPage:true});
      if(route==='/') {
        assert((await page.locator('h1').innerText()).includes('Start with a free review.'));
        assert(!(await page.locator('main').innerText()).includes('$2K+'));
        if(width<768) {
          const button=page.getByRole('button',{name:'Open menu',exact:true});
          assert.equal(await button.getAttribute('aria-expanded'),'false');
          assert.equal(await page.locator('#space-mobile-menu').getAttribute('inert'),'');
          await button.press('Enter');
          assert.equal(await page.getByRole('button',{name:'Close menu'}).getAttribute('aria-expanded'),'true');
          await page.locator('#space-mobile-menu').getByRole('link',{name:cta,exact:true}).press('Enter');
          await page.getByRole('button',{name:cta,exact:true}).waitFor();
        }
      }
    }
  }
  await page.goto(origin+'/apply/',{waitUntil:'networkidle'});
  assert.equal(await page.locator('input[required]').count(),2);
  assert.equal(await page.getByLabel('Email',{exact:true}).getAttribute('autocomplete'),'email');
  assert(!(await page.locator('form').innerText()).includes('token'));
  await page.getByLabel('Email',{exact:true}).fill('journey-test@example.invalid');
  await page.getByLabel('Artist or label',{exact:true}).fill('Mock catalog');
  for(const name of ['pricing and offer policy (new tab)','privacy notice (new tab)']) {
    const [popup]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name,exact:true}).click()]);
    await popup.waitForLoadState('domcontentloaded');
    const expected=name.startsWith('pricing')?'SPACE Pricing and Offer Policy':'Information we collect';
    await popup.waitForFunction(text=>document.body.innerText.includes(text),expected);
    assert((await popup.locator('body').innerText()).length>500);await popup.close();
    assert.equal(await page.getByLabel('Email',{exact:true}).inputValue(),'journey-test@example.invalid');
  }
  await page.getByRole('button',{name:cta,exact:true}).press('Enter');
  const confirmation=page.getByRole('status');await confirmation.waitFor();
  assert.equal(await page.locator('form.intake-card').count(),0,'Do not invite a duplicate submission');
  assert(await confirmation.evaluate(node=>node===document.activeElement),'Confirmation receives keyboard focus');
  assert((await confirmation.innerText()).includes('5-7 business days after we receive the relevant information'));
  assert.equal(submissions,1);
  await page.screenshot({path:'tmp/journey-qa/screenshots/confirmation-desktop.png',fullPage:true});
  await page.setViewportSize({width:320,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'tmp/journey-qa/screenshots/confirmation-mobile.png',fullPage:true});
  await confirmation.getByRole('link',{name:'Read the seller document checklist'}).press('Enter');
  await page.getByRole('heading',{name:"Music Catalog Sale Documents: A Seller's Checklist",exact:true}).waitFor();
  await page.goto(origin+'/apply/');await page.getByRole('link',{name:'SPACE home',exact:true}).press('Enter');await page.waitForURL(origin+'/');
  const noJs=await browser.newContext({javaScriptEnabled:false}),staticPage=await noJs.newPage();
  for(const route of ['/','/how-it-works/','/sell/','/apply/']) {
    await staticPage.goto(origin+route);
    assert.equal(await staticPage.locator('h1').count(),1);
    if(route==='/apply/')assert((await staticPage.locator('body').innerText()).includes('The review form needs JavaScript'));
    else assert(await staticPage.getByRole('link',{name:cta,exact:true}).count()>0);
  }
  await noJs.close();assert.deepEqual(errors,[]);
  console.log(JSON.stringify({origin,viewports:[320,390,768,1024,1440],keyboard:true,menuHiddenFromKeyboard:true,correctApply:true,policyLinks:true,confirmation:true,receiverMocks:submissions,noRealLead:true,noJs:true,errors}));
}catch(error){
  console.error(JSON.stringify({url:page?.url(),errors,failedRequests,headings:page?await page.locator('h1').allTextContents():[]}));
  if(page)await page.screenshot({path:'tmp/journey-qa/screenshots/failure.png',fullPage:true}).catch(()=>{});
  throw error;
}finally{await browser.close();server?.close();}

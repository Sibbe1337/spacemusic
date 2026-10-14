import assert from 'node:assert/strict';
import { serve, playwrightModule } from './funnel-support.mjs';
const [directoryOrOrigin] = process.argv.slice(2);
const server = directoryOrOrigin.startsWith('http') ? null : await serve(directoryOrOrigin);
const origin = server?.origin || directoryOrOrigin.replace(/\/$/,'');
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel:'chrome', headless:true });
const errors = [];
try {
  // All requests to the real receiver and all analytics traffic are intercepted.
  const context = await browser.newContext({ viewport:{width:390,height:844} });
  let receiverCalls = 0, payloads = [], outcome = 'success', hold;
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.hostname === 'formspree.io') {
      assert.equal(url.pathname,'/f/mpwdnokz'); assert.equal(request.method(),'POST');
      receiverCalls++; payloads.push(request.postData());
      if (outcome === 'hold') await new Promise(resolve => hold = resolve);
      if (outcome === 'network') return route.abort();
      return route.fulfill({ status:outcome === 'error' ? 422 : 200, contentType:'application/json', body:JSON.stringify(outcome === 'error' ? {errors:[{message:'Rejected'}]} : {ok:true}) });
    }
    if (request.method() !== 'GET' || url.hostname.includes('plausible')) return route.abort();
    return url.origin === origin || ['fonts.googleapis.com','fonts.gstatic.com'].includes(url.hostname) ? route.continue() : route.abort();
  });
  await context.addInitScript(() => {
    window.__events = [];
    window.plausible = (name, options) => window.__events.push({name,options});
    window.plausible.init = () => {};
  });
  const page = await context.newPage();
  const submitButton = () => page.getByRole('button',{name:/^(Start review|Request a free catalog review)$/});
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/calculator/?token=TEST_PRIVATE#secret', {waitUntil:'networkidle'});
  await page.getByLabel('Assumed annual-income multiple').waitFor();
  assert.equal(await page.getByLabel('Assumed annual-income multiple').inputValue(),'');
  assert(!await page.locator('[data-scenario-result]').innerText().then(text => text.includes('$')));
  await page.getByLabel('Monthly net income (USD)',{exact:true}).fill('1000');
  await page.getByLabel('Share of defined rights to sell (%)',{exact:true}).fill('50');
  await page.getByLabel('Assumed annual-income multiple').fill('4');
  await page.waitForFunction(() => document.querySelector('[data-scenario-result]').textContent.includes('$24,000'));
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='calculator_used').length),1);
  await page.getByLabel('Monthly net income (USD)',{exact:true}).fill('0');
  assert((await page.locator('[data-scenario-result]').innerText()).startsWith('$0'));
  await page.getByLabel('Share of defined rights to sell (%)',{exact:true}).fill('101');
  assert((await page.locator('[data-scenario-result]').innerText()).includes('Enter valid'));
  await page.getByLabel('Share of defined rights to sell (%)',{exact:true}).fill('50');
  await page.getByLabel('Assumed annual-income multiple').fill('');
  assert((await page.locator('[data-scenario-result]').innerText()).includes('Enter valid'));
  const eventsBeforeNavigation = await page.evaluate(() => __events);
  assert(!JSON.stringify(eventsBeforeNavigation).includes('1000'));
  await page.getByRole('link',{name:'Request a free catalog review',exact:true}).first().press('Enter');
  await page.waitForURL(origin + '/apply/');
  await submitButton().waitFor();
  assert.equal(await page.locator('input[name="landing_path"]').inputValue(),'/calculator/');
  assert.equal(await page.locator('input[name="apply_source_path"]').inputValue(),'/calculator/');
  await submitButton().click();
  assert.equal(receiverCalls,0,'Invalid fields never submit');
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_submitted').length),0);
  const fill = async () => {
    const another=page.getByRole('button',{name:'Request a review for another catalog',exact:true});
    if (await another.count()) await another.click();
    await page.getByLabel('Email',{exact:true}).fill('mock-only@example.invalid');
    await page.getByLabel('Artist or label',{exact:true}).fill('Private test catalog');
  };
  await fill();
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_started').length),1);
  outcome='hold';
  await submitButton().click();
  await page.waitForFunction(() => document.querySelector('button.primary').disabled);
  // Simulate a second submit event within the pending request, including a keyboard attempt.
  await page.locator('form.intake-card').dispatchEvent('submit');
  assert.equal(receiverCalls,1,'In-flight duplicate is blocked');
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_submitted').length),0,'No success before response');
  hold();
  await page.getByRole('status').filter({hasText:'Review request sent'}).waitFor();
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_submitted').length),1);
  assert(payloads[0].includes('name="landing_path"\r\n\r\n/calculator/'));
  assert(payloads[0].includes('name="apply_source_path"\r\n\r\n/calculator/'));
  assert(!payloads[0].includes('TEST_PRIVATE'));
  for (const failure of ['error','network']) {
    outcome=failure; await fill();
    await submitButton().click();
    await page.getByRole('alert').waitFor();
    assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_submitted').length),1);
    assert.equal(await page.getByLabel('Email',{exact:true}).inputValue(),'mock-only@example.invalid');
  }
  outcome='success';
  await submitButton().click();
  await page.getByRole('status').filter({hasText:'Review request sent'}).waitFor();
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_submitted').length),2,'Retry success counted once');
  assert.equal(await page.evaluate(() => __events.filter(e=>e.name==='application_started').length),1);
  const events = await page.evaluate(() => __events);
  assert(!/mock-only|Private test|TEST_PRIVATE|token|amount|revenue/.test(JSON.stringify(events)));
  await page.evaluate(() => { window.plausible = () => { throw Error('Statistics blocked'); }; });
  await fill(); await submitButton().click();
  await page.getByRole('status').filter({hasText:'Review request sent'}).waitFor();
  assert.equal(receiverCalls,5);
  await page.evaluate(() => { delete window.spaceFunnel; });
  await fill(); await submitButton().click();
  await page.getByRole('status').filter({hasText:'Review request sent'}).waitFor();
  assert.equal(receiverCalls,6);
  for (const route of ['/calculator/','/apply/']) for (const width of [320,390,1440]) {
    await page.setViewportSize({width,height:900});
    await page.goto(origin + route,{waitUntil:'networkidle'});
    assert.equal(await page.locator('h1').count(),1);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflow ${width}`);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),'https://spacemusic.io'+route);
  }
  await context.addInitScript(() => {
    Storage.prototype.getItem = () => { throw Error('Storage blocked'); };
    Storage.prototype.setItem = () => { throw Error('Storage blocked'); };
  });
  await page.goto(origin + '/apply/', { waitUntil:'networkidle' });
  await fill();
  await submitButton().click();
  await page.getByRole('status').filter({hasText:'Review request sent'}).waitFor();
  assert.equal(receiverCalls,7,'Storage failure does not stop the existing Formspree application');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ origin, scenario:true, invalidAndZero:true, sources:true, receiverMocks:receiverCalls, duplicateGuard:true, failureAndRetry:true, blockedAnalytics:true, blockedStorage:true, noPII:true, mobile:[320,390], keyboard:true, errors }));
} finally { await browser.close(); server?.close(); }

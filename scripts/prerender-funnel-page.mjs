import assert from 'node:assert/strict';
import path from 'node:path';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { serve, playwrightModule } from './funnel-support.mjs';
const [directory, route = '/calculator/'] = process.argv.slice(2);
assert(route.startsWith('/') && route.endsWith('/'));
const server = await serve(directory);
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const context = await browser.newContext({ viewport: { width:1440, height:1000 } });
  await context.route('**/*', route => {
    const u = new URL(route.request().url());
    return u.origin === server.origin || ['fonts.googleapis.com','fonts.gstatic.com'].includes(u.hostname) ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(server.origin + route, { waitUntil: 'networkidle' });
  await page.locator('h1').waitFor();
  if (route === '/calculator/') await page.getByLabel('Assumed annual-income multiple').waitFor();
  assert.equal(await page.locator('h1').count(),1);
  assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),'https://spacemusic.io' + route);
  assert.deepEqual(errors, []);
  // Runtime-injected styles must not accumulate when prerendering an existing snapshot.
  await page.evaluate(() => {
    const seen = new Set();
    for (const style of document.querySelectorAll('style')) {
      const signature = style.outerHTML;
      if (seen.has(signature)) style.remove();
      else seen.add(signature);
    }
  });
  let html = (await page.content()).replaceAll(server.origin + '/', '/');
  assert(!html.includes('127.0.0.1'));
  // React's runtime does not preserve disabled attributes in a static no-JS copy.
  if (route === '/calculator/' && !html.includes('JavaScript is needed for the interactive calculation.')) html = html.replace('</body>', '<noscript><p style="padding:24px">JavaScript is needed for the interactive calculation. Use the formula above or <a href="/apply/">request a free catalog review</a>.</p></noscript></body>');
  await writeFile(path.join(directory, route, 'index.html'),html);
  await mkdir('tmp/funnel-qa/screenshots', { recursive:true });
  for (const width of [1440,390,320]) {
    await page.setViewportSize({ width, height:900 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}`);
    await page.screenshot({ path:`tmp/funnel-qa/screenshots/${route.replaceAll('/','_')}-${width}.png`, fullPage:true });
  }
  const noJs = await browser.newContext({ javaScriptEnabled:false });
  await noJs.route('**/*', request => new URL(request.request().url()).origin === server.origin ? request.continue() : request.abort());
  const staticPage = await noJs.newPage();
  await staticPage.goto(server.origin + route, { waitUntil: 'domcontentloaded' });
  assert.equal(await staticPage.locator('h1').innerText(), await page.locator('h1').innerText());
  console.log(JSON.stringify({ route, prerendered:true, mobile:[390,320], noJavaScript:true, errors }));
} finally { await browser.close(); server.close(); }

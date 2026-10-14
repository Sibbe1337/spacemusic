import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { playwrightModule } from './funnel-support.mjs';

const [origin, output, mode, ...extra] = process.argv.slice(2);
const production = mode === '--production';
assert(origin?.startsWith('https://') && output && !extra.length && (!mode || production), 'Usage: ORIGIN OUTPUT [--production]');
assert(production ? origin === 'https://spacemusic.io' : new URL(origin).hostname.endsWith('.spacemusic-a6n.pages.dev'), 'Use explicit production mode only for the public site');
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const errors = [];
await mkdir(output, { recursive: true });
try {
  const ctx = await browser.newContext();
  await ctx.route('**/*', route => {
    const request = route.request();
    if (request.method() !== 'GET' || new URL(request.url()).hostname.includes('plausible.io')) return route.abort();
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on('pageerror', error => errors.push(error.message));
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    const response = await page.goto(origin + '/calculator/', { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200);
    const headerNoindex = /noindex/i.test(response.headers()['x-robots-tag'] || '');
    assert.equal(headerNoindex, !production, production ? 'Production must not inherit preview noindex' : 'Preview must stay out of search');
    if (production) assert(!/noindex/i.test(await page.locator('meta[name="robots"]').getAttribute('content')));
    assert.equal(await page.locator('h1').innerText(), 'How much could your music catalog sell for?');
    assert((await page.locator('#multiple-help').innerText()).includes('no multiple is needed to apply'));
    assert.equal(await page.getByLabel('Assumed annual-income multiple').inputValue(), '');
    assert(!(await page.locator('[data-scenario-result]').innerText()).includes('$'));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow ${width}`);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://spacemusic.io/calculator/');
    if ([390, 1440].includes(width)) {
      await page.screenshot({ path: path.join(output, `calculator-${width}-viewport.png`) });
      await page.screenshot({ path: path.join(output, `calculator-${width}-full.png`), fullPage: true });
    }
  }
  await page.getByRole('link', { name: "seller's document checklist", exact: true }).press('Enter');
  await page.getByRole('heading', { name: "Music Catalog Sale Documents: A Seller's Checklist", exact: true }).waitFor();
  assert.equal(page.url(), origin + '/blog/music-catalog-sale-documents-checklist/');
  await page.goto(origin + '/calculator/', { waitUntil: 'networkidle' });
  await page.locator('summary').filter({ hasText: 'How quickly will I get paid?' }).press('Enter');
  await page.getByRole('link', { name: 'review and payment conditions', exact: true }).press('Enter');
  await page.waitForFunction(() => document.body.innerText.includes('SPACE Pricing and Offer Policy'));
  assert.equal(page.url(), origin + '/pricing.md');
  await page.goto(origin + '/calculator/', { waitUntil: 'networkidle' });
  await page.locator('aside').getByRole('link', { name: 'Request a free catalog review', exact: true }).press('Enter');
  await page.getByRole('heading', { name: 'We buy your music catalog.', exact: true }).waitFor();
  assert.equal(page.url(), origin + '/apply/');
  await page.locator('form.intake-card').waitFor();
  assert.equal(await page.locator('input[required]').count(), 2);
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJs.newPage();
  await staticPage.goto(origin + '/calculator/');
  assert.equal(await staticPage.locator('h1').innerText(), 'How much could your music catalog sell for?');
  assert((await staticPage.locator('#multiple-help').innerText()).includes('no multiple is needed to apply'));
  assert.equal(await staticPage.getByRole('link', { name: "seller's document checklist", exact: true }).count(), 1);
  await staticPage.locator('summary').filter({ hasText: 'How quickly will I get paid?' }).press('Enter');
  assert(await staticPage.getByRole('link', { name: 'review and payment conditions', exact: true }).isVisible());
  assert.equal(await staticPage.locator('noscript').count(), 1);
  await noJs.close();
  assert.deepEqual(errors, []);
  const result = { origin, environment: production ? 'production' : 'preview', checkedAt: new Date().toISOString(), widths: [320,390,768,1024,1440], approvedCopy: true, blankScenario: true, directReviewWithoutMultiple: true, keyboardLinks: ['document checklist', 'offer policy', 'Apply'], noJavaScript: true, indexabilityMatchesEnvironment: true, realSubmissions: 0, errors };
  await writeFile(path.join(output, 'results.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
} finally { await browser.close(); }

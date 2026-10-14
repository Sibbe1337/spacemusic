import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files, playwrightModule} from './funnel-support.mjs';

const [directory, origin = 'https://spacemusic.io'] = process.argv.slice(2);
assert(directory, 'Usage: node scripts/check-serp-live.mjs CANDIDATE [ORIGIN]');
const manifest = JSON.parse(await readFile(directory + '-manifest.json', 'utf8'));
const inventory = await files(directory);
const publicPaths = new Set(inventory.map(f => '/' + f.replace(/(^|\/)index\.html$/, '$1')));
const schemas = d => [...d.querySelectorAll('script[type="application/ld+json"]')]
  .flatMap(n => {const j = JSON.parse(n.textContent); return Array.isArray(j) ? j : [j];})
  .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
const metadata = d => ({title: d.title,
  description: d.querySelector('meta[name="description"]')?.content,
  canonical: d.querySelector('link[rel="canonical"]')?.getAttribute('href'),
  h1: [...d.querySelectorAll('h1')].map(n => n.textContent)});
const expected = new Map();
for (const file of manifest.pages) {
  const d = new JSDOM(await readFile(directory + '/' + file, 'utf8')).window.document;
  expected.set(file, {metadata: metadata(d), schemas: schemas(d)});
}
const {chromium} = await import(playwrightModule);
const browser = await chromium.launch({channel: 'chrome'});
const errors = [], blocked = [], verified = [];
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({viewport: {width, height: 900}, locale: 'en-US', serviceWorkers: 'block'});
    // Only exact public static paths may load; never submit or send analytics.
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() === 'GET' && url.origin === origin && publicPaths.has(url.pathname)) return route.continue();
      blocked.push({method: request.method(), host: url.hostname});
      return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    for (const file of manifest.pages) {
      const url = origin + '/' + file.replace(/index\.html$/, '');
      const response = await page.goto(url, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, url);
      assert(!/noindex/i.test(response.headers()['x-robots-tag'] || ''), url + ' header indexable');
      const d = new JSDOM(await page.content()).window.document;
      assert.deepEqual(metadata(d), expected.get(file).metadata, url + ' metadata parity');
      assert.deepEqual(schemas(d), expected.get(file).schemas, url + ' schema parity');
      assert(![...d.querySelectorAll('meta[name="robots"]')].some(n => /noindex/i.test(n.content)));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), url + ' overflow');
      const faq = page.locator('details').filter({has: page.locator('summary')}).last();
      if (await faq.count()) {
        const open = await faq.evaluate(n => n.open);
        await faq.locator('summary').press('Enter');
        assert.equal(await faq.evaluate(n => n.open), !open, url + ' keyboard FAQ');
      }
      await page.locator('a[href="/apply/"]:visible').last().press('Enter');
      await page.waitForURL(origin + '/apply/');
      assert.equal(await page.locator('h1').textContent(), 'We buy your music catalog.');
      assert.equal(await page.locator('#short-form').count(), 1);
      verified.push({url, width, metadata: true, schema: true, applyNavigation: true});
    }
    await page.goto(origin + '/calculator/', {waitUntil: 'networkidle'});
    await page.getByLabel('Monthly net income (USD)', {exact: true}).fill('1000');
    await page.getByLabel('Assumed annual-income multiple').fill('4');
    await page.getByLabel('Share of defined rights to sell (%)', {exact: true}).fill('50');
    assert((await page.locator('[data-scenario-result]').textContent()).startsWith('$24,000'));
    await context.close();
  }
  assert.deepEqual(errors, [], 'No browser errors');
} finally {await browser.close();}
const result = {verifiedAt: new Date().toISOString(), directory, origin, verified,
  calculatorExample: 24000, errors, blockedRequests: blocked.length, realSubmissions: 0, analyticsSent: 0};
await writeFile('marketing/serp-20261008/qa/live-results.json', JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));

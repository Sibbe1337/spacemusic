import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files, serve, playwrightModule} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {ledger} from '../marketing/motion-20260929/ledger.mjs';

const manifestPath = process.argv[2] || "marketing/motion-20260929/manifest-v3.json";
const m = JSON.parse(await readFile(manifestPath, 'utf8'));
const hash = b => createHash('sha256').update(b).digest('hex');
let checks = 0; const ok = (c, msg) => { assert(c, msg); checks++; };
const reverse = new Map(m.modules.map(([a, b]) => [b, a]));
const unrewrite = t => { for (const [b, a] of reverse) t = t.replaceAll(b, a); return t; };
const src = await files(m.source), out = await files(m.output);

// 1. Inventory: identical plus only the renamed modules.
const added = out.filter(f => !src.includes(f));
assert.deepEqual(added.sort(), m.modules.map(([, b]) => 'assets/' + b).sort()); checks++;
ok(src.every(f => out.includes(f)), 'no file removed');

// 2. Every file is byte-identical, or identical after undoing module renames,
//    except index.html, which may differ only by the decorative figure.
const changedHtml = [];
for (const f of src) {
  const a = await readFile(path.join(m.source, f)), b = await readFile(path.join(m.output, f));
  ok(hash(a) === m.sourceHashes[f], `source unchanged: ${f}`);
  if (a.equals(b)) { checks++; continue; }
  ok(f.endsWith('.html'), `only HTML references may change: ${f}`);
  let t = unrewrite(b.toString());
  if (f === 'index.html') t = t.replace(ledger, '');
  ok(t === a.toString(), `only the intended change in ${f}`);
  changedHtml.push(f);
}
for (const f of ['sitemap.xml', 'robots.txt', '_headers', '_redirects', 'llms.txt', 'pricing.md'])
  ok((await readFile(path.join(m.source, f))).equals(await readFile(path.join(m.output, f))), `${f} identical`);

// 3. Modules: parse, and differ from source only by the figure and renames.
for (const [a, b] of m.modules) {
  const next = await readFile(path.join(m.output, 'assets', b), 'utf8');
  parse(next, {sourceType:'module'}); checks++;
  const old = await readFile(path.join(m.source, 'assets', a), 'utf8');
  let back = unrewrite(next);
  if (b === m.indexModule) {
    const lit = literals(back).filter(n => n.value.includes(ledger));
    ok(lit.length === 1, 'one homepage literal carries the figure');
    back = back.slice(0, lit[0].start) + JSON.stringify(lit[0].value.replace(ledger, '')) + back.slice(lit[0].end);
  }
  ok(back === old, `module only changes intended content: ${a}`);
}

// 4. SEO surface on the homepage.
const pick = h => { const d = new JSDOM(h).window.document; return {
  title: d.title, desc: d.querySelector('meta[name=description]')?.content, canonical: d.querySelector('link[rel=canonical]')?.href,
  robots: d.querySelector('meta[name=robots]')?.content ?? null, h1: [...d.querySelectorAll('h1')].map(x => x.textContent),
  h2: [...d.querySelectorAll('h2')].map(x => x.textContent), ld: [...d.querySelectorAll('script[type="application/ld+json"]')].map(x => x.textContent),
  links: [...d.querySelectorAll('a[href]')].map(x => x.getAttribute('href')), added: d.querySelectorAll('.quiet-comparison>style#motion-comparison').length,
  text: (() => { const c = d.querySelector('.quiet-comparison').cloneNode(true); c.querySelector('style')?.remove(); return c.textContent; })() }; };
const before = pick(await readFile(path.join(m.source, 'index.html'), 'utf8'));
const after = pick(await readFile(path.join(m.output, 'index.html'), 'utf8'));
for (const k of ['title', 'desc', 'canonical', 'robots', 'h1', 'h2', 'ld', 'links', 'text']) { assert.deepEqual(after[k], before[k], k); checks++; }
ok(after.added === 1, 'one style block in the comparison section');

// 5. Browser: desktop and phone, scroll states, client navigation, errors, overflow.
const {chromium} = await import(playwrightModule);
const server = await serve(m.output);
const browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {});
const shots = [];
const errors = [];
for (const [name, viewport] of [['desktop', {width:1280, height:800}], ['mobile', {width:390, height:844}], ['narrow', {width:320, height:640}]]) {
  const page = await browser.newPage({viewport});
  page.on('pageerror', e => errors.push(`${name}: ${e.message}`));
  page.on('console', x => { if (x.type() === 'error') errors.push(`${name}: ${x.text()}`); });
  await page.goto(server.origin + '/', {waitUntil:'networkidle'});
  // Dismiss the existing cookie notice locally so it does not cover the screenshots.
  await page.getByRole('button', {name:'Decline'}).click({timeout:2000}).catch(() => {});
  ok(await page.locator('#motion-comparison').count() === 1, `${name}: style after hydration`);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: no horizontal overflow`);
  ok(await page.evaluate(() => getComputedStyle(document.querySelector('.quiet-comparison .rounded-2xl>.grid:nth-child(2)>:nth-child(2)')).animationName) === 'motion-comparison-fade', `${name}: animation active`);
  const top = await page.evaluate(() => document.querySelector('.quiet-comparison .rounded-2xl').getBoundingClientRect().top + scrollY);
  const tall = await page.evaluate(() => document.querySelector('.quiet-comparison .rounded-2xl').offsetHeight);
  // The figure's top edge at 85%, 55%, 35% and 15% of the viewport height.
  for (const [label, at] of [['1-enter', .85], ['2-collapsing', .55], ['3-late', .35], ['4-settled', .15]]) {
    await page.evaluate(t => scrollTo(0, t), top - viewport.height * at + (at === .85 ? tall * 0 : 0));
    await page.waitForTimeout(300);
    const file = `marketing/motion-20260929/shot-${name}-${label}.png`;
    await page.screenshot({path:file}); shots.push(file);
  }
  const reduced = await browser.newPage({viewport, reducedMotion:'reduce'});
  await reduced.goto(server.origin + '/', {waitUntil:'networkidle'});
  ok(await reduced.evaluate(() => getComputedStyle(document.querySelector('.quiet-comparison .rounded-2xl>.grid:nth-child(2)>:nth-child(2)')).animationName) === 'none', `${name}: reduced motion is still`);
  await reduced.close();
  if (name === 'desktop') {
    await page.goto(server.origin + '/sell/', {waitUntil:'networkidle'});
    await page.locator('a.space-wordmark-link[href="/"]').first().click();
    await page.waitForSelector('#motion-comparison', {state:'attached', timeout:5000}); checks++;
  }
  await page.close();
}
await browser.close(); server.close();
ok(errors.length === 0, 'browser errors: ' + errors.join(' | '));
const report = {manifest:manifestPath, checks, changedHtml:changedHtml.length, modules:m.modules.length, shots};
await writeFile('marketing/motion-20260929/test-results.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));

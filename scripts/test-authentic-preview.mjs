// Verifies an authenticity build: only reviewed edits changed, SEO surface intact,
// server and hydrated text agree, no browser errors.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files, serve, playwrightModule} from './funnel-support.mjs';
import {loadSite, loadEdits, applyToModules, applyToHtml, loadDocs, applyFileEdit} from './authentic-support.mjs';

const manifestPath = process.argv[2];
const m = JSON.parse(await readFile(manifestPath, 'utf8'));
let checks = 0; const ok = (c, msg) => { assert(c, msg); checks++; };
const hash = b => createHash('sha256').update(b).digest('hex');
const mapping = new Map(m.modules);
const rewrite = t => { for (const [a, b] of mapping) t = t.replaceAll(a, b); return t; };
const site = await loadSite(m.source);
const edits = [...new Map((await loadEdits(undefined, m.editFiles)).map(e => [e.find, e])).values()];
const {changed} = applyToModules(site, edits);
const src = await files(m.source), out = await files(m.output);

const docs = await loadDocs(undefined, m.editFiles);
assert.deepEqual(out.filter(f => !src.includes(f)).sort(), [...[...mapping.values()].map(b => 'assets/' + b), ...(m.newFiles ?? []), ...(m.newPages ?? [])].sort()); checks++;
for (const nf of m.newFiles ?? []) ok((await readFile(path.join(m.output, nf), 'utf8')) === rewrite(await readFile(docs.files[nf], 'utf8')), `new file content ${nf}`);
const titleChanges = [], h1Changes = [], rerenderReport = [];
const seo = html => { const d = new JSDOM(html).window.document; return {
  canonical: d.querySelector('link[rel=canonical]')?.href ?? null, robots: d.querySelector('meta[name=robots]')?.content ?? null,
  hrefs: [...d.querySelectorAll('a[href]')].map(a => a.getAttribute('href')), h1: [...d.querySelectorAll('h1')].map(h => h.textContent),
  h2n: d.querySelectorAll('h2').length, title: d.title, ld: [...d.querySelectorAll('script[type="application/ld+json"]')].map(s => JSON.parse(s.textContent)['@type'] ?? 'graph') }; };
for (const f of src) {
  const a = await readFile(path.join(m.source, f)); let b = await readFile(path.join(m.output, f));
  ok(hash(a) === m.sourceHashes[f], `source unchanged ${f}`);
  if (!f.endsWith('.html')) {
    const fes = docs.fileEdits.filter(e => e.file === f);
    if (fes.length) { let t = a.toString(); for (const e of fes) t = applyFileEdit(t, e); ok(t === b.toString(), `only listed file edits in ${f}`); }
    else ok(a.equals(b), `non-HTML identical ${f}`);
    continue;
  }
  const injSel = Object.entries(m.injected ?? {}).filter(([, pages]) => pages.includes(f)).map(([sel]) => sel);
  if (injSel.length) {
    const dom = new JSDOM(b.toString());
    for (const sel of injSel) { const el = dom.window.document.querySelector(sel); ok(!!el, `injected ${sel} present in ${f}`); el.remove(); }
    b = Buffer.from(dom.serialize());
  }
  const rerendered = (m.rerenderPages ?? []).includes(f);
  if (!rerendered) {
    let expected = rewrite(applyToHtml(a.toString(), edits, f).html);
    if (injSel.length) expected = new JSDOM(expected).serialize();
    ok(expected === b.toString(), `only reviewed edits in ${f}`);
  } else {
    // Rerendered page: head must match the edited source head; body is checked in the browser.
    const expected = new JSDOM(rewrite(applyToHtml(a.toString(), edits, f).html)).window.document.head.innerHTML;
    ok(new JSDOM(b.toString()).window.document.head.innerHTML === expected, `head only reviewed edits in ${f}`);
  }
  const s0 = seo(a.toString()), s1 = seo(b.toString());
  const hrefMap = new Map(edits.filter(e => (e.href || (/^https?:\/\//.test(e.find) && !e.code && !e.template && !e.jsonLd)) && (!e.pages || e.pages.some(p => f.startsWith(p)))).map(e => [e.find, e.replace]));
  s0.hrefs = s0.hrefs.map(h => hrefMap.get(h) ?? h);
  const keys = rerendered ? ['canonical', 'robots'] : ['canonical', 'robots', 'hrefs', 'h2n', 'ld'];
  for (const k of keys) { assert.deepEqual(s1[k], s0[k], `${k} ${f}`); checks++; }
  if (rerendered) {
    const internal = h => h.filter(x => x.startsWith('/'));
    const lost = [...new Set(internal(s0.hrefs))].filter(h => !s1.hrefs.includes(h));
    ok(lost.length === 0, `internal links lost on ${f}: ${lost.join(', ')}`);
    rerenderReport.push({page: f, h2Before: s0.h2n, h2After: s1.h2n, newLinks: [...new Set(s1.hrefs)].filter(h => !s0.hrefs.includes(h))});
  }
  ok(s1.h1.length === s0.h1.length, `h1 count ${f}`);
  if (s1.title !== s0.title) titleChanges.push([f, s0.title, s1.title]);
  if (s1.h1.join() !== s0.h1.join()) h1Changes.push([f, s0.h1.join(' | '), s1.h1.join(' | ')]);
}
for (const [a, b] of mapping) {
  const code = await readFile(path.join(m.output, 'assets', b), 'utf8');
  parse(code, {sourceType: 'module'}); checks++;
  ok(code === rewrite(changed.get(a) ?? site.codes.get(a)), `module content ${a}`);
}
for (const np of m.newPages ?? []) {
  const d = new JSDOM(await readFile(path.join(m.output, np), 'utf8')).window.document;
  const url = 'https://spacemusic.io/' + np.replace(/index\.html$/, '');
  ok(d.querySelector('link[rel=canonical]')?.href === url, `canonical ${np}`);
  ok(d.querySelectorAll('h1').length === 1 && d.querySelector('main')?.textContent.length > 500, `content ${np}`);
  ok((await readFile(path.join(m.output, 'sitemap.xml'), 'utf8')).includes(`<loc>${url}</loc>`), `sitemap ${np}`);
  ok(!/noindex/.test(d.querySelector('meta[name=robots]')?.content ?? ''), `indexable ${np}`);
}
// No old text left in active modules or HTML.
const outSite = await loadSite(m.output);
const leftovers = [];
for (const e of edits) {
  if (e.replace.includes(e.find) || e.href || e.jsonLd || e.code) continue;
  for (const n of outSite.active) if ((!e.modules || e.modules.some(x => n.startsWith(x))) && !e.template && !e.htmlOnly && outSite.codes.get(n).includes(JSON.stringify(e.find).slice(1, -1))) leftovers.push(`${e.file}#${e.index} in ${n}`);
}
ok(leftovers.length === 0, 'old text remains: ' + leftovers.slice(0, 5).join(', '));

// Browser: server text equals hydrated text on sampled changed pages.
const pages = process.env.ALL_PAGES ? [...m.changedPages, ...(m.newPages ?? [])] : m.changedPages.filter((_, i) => i % Math.max(1, Math.floor(m.changedPages.length / 24)) === 0).slice(0, 24);
const {chromium} = await import(playwrightModule);
const server = await serve(m.output);
const browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? {channel: process.env.PLAYWRIGHT_CHANNEL} : {});
const errors = [], mismatches = [];
const norm = s => s.replace(/\s+/g, ' ').trim();
for (const f of pages) {
  const url = server.origin + '/' + f.replace(/index\.html$/, '');
  const noJs = await browser.newContext({javaScriptEnabled: false, locale: 'en-US'}); const p0 = await noJs.newPage();
  await p0.goto(url); const before = norm(await p0.locator('main').first().innerText().catch(() => ''));
  await noJs.close();
  const p = await browser.newPage({locale: 'en-US'}); p.on('pageerror', e => errors.push(`${f}: ${e.message}`));
  await p.goto(url, {waitUntil: 'networkidle'});
  const after = norm(await p.locator('main').first().innerText().catch(() => ''));
  for (const [sel, list] of Object.entries(m.injected ?? {})) if (list.includes(f)) {
    const server = new JSDOM(await readFile(path.join(m.output, f), 'utf8')).window.document.querySelector(sel)?.outerHTML;
    const live = await p.evaluate(x => document.querySelector(x)?.outerHTML ?? null, sel);
    ok(server === live, `${sel} identical server/hydrated on ${f}`);
  }
  if (before !== after) mismatches.push(f);
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `no overflow ${f}`);
  await p.close();
}
await browser.close(); server.close();
ok(errors.length === 0, 'browser errors: ' + errors.join(' | '));
ok(mismatches.length === 0, 'server/hydrated text differs: ' + mismatches.join(', '));
const report = {manifest: manifestPath, checks, rerenderReport, pagesChanged: m.changedPages.length, browserPages: pages.length, titleChanges, h1Changes};
await writeFile(path.join(path.dirname(manifestPath), 'test-results.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({checks, pagesChanged: m.changedPages.length, browserPages: pages.length, titleChanges: titleChanges.length, h1Changes: h1Changes.length}, null, 2));

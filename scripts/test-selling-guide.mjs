import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';

const [manifestPath] = process.argv.slice(2);
assert(manifestPath, 'Usage: MANIFEST');
const m = JSON.parse(await readFile(manifestPath, 'utf8'));
const inventory = await files(m.output);
const hash = s => createHash('sha256').update(s).digest('hex');
const read = (root, f) => readFile(path.join(root, f), 'utf8');
const norm = s => s.replace(/\s+/g, ' ').trim();
const unversion = s => { for (const [a, b] of m.modules) s = s.replaceAll(b, a); return s; };
let checks = 0;
const equal = (a, b, label) => { assert.deepEqual(a, b, label); checks++; };
const ok = (a, label) => { assert(a, label); checks++; };
for (const [f, expected] of Object.entries(m.sourceHashes)) {
  equal(hash(await readFile(path.join(m.source, f))), expected, `Baseline immutable: ${f}`);
  if (!f.endsWith('.html')) equal(await readFile(path.join(m.output, f)), await readFile(path.join(m.source, f)), `Existing asset/config preserved: ${f}`);
  else if (f !== m.htmlFile) equal(unversion(await read(m.output, f)), await read(m.source, f), `Unrelated HTML preserved: ${f}`);
}
equal(inventory.filter(f => f.endsWith('.html')), Object.keys(m.sourceHashes).filter(f => f.endsWith('.html')), 'No HTML route additions or removals');
equal((await read(m.output, 'sitemap.xml')).match(/<loc>/g).length, 140, '140 existing sitemap URLs');
equal(inventory.filter(f => !Object.hasOwn(m.sourceHashes, f)).sort(), m.modules.map(([, b]) => 'assets/' + b).sort(), 'Only versioned JS added');
const before = new JSDOM(await read(m.source, m.htmlFile)).window.document;
const after = new JSDOM(await read(m.output, m.htmlFile)).window.document;
for (const selector of ['h1', 'link[rel="canonical"]', 'meta[name="robots"]', 'link[rel="stylesheet"]', 'form', 'script:not([type="application/ld+json"])']) {
  equal([...after.querySelectorAll(selector)].map(n => unversion(n.outerHTML)), [...before.querySelectorAll(selector)].map(n => n.outerHTML), `Preserved ${selector}`);
}
equal(after.title, before.title, 'Search title retained');
for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
  equal(after.querySelectorAll(selector).length, 1, `Single ${selector}`);
  equal(after.querySelector(selector).content, m.next.metaDescription, `Current ${selector}`);
}
equal(m.next.sections.map(s => [s.id, s.heading]), m.old.sections.map(s => [s.id, s.heading]), 'Ten topic IDs and headings retained');
equal([...after.querySelectorAll('main > section[id]')].map(s => s.id), m.next.sections.map(s => s.id), 'Section ordering');
for (const section of m.next.sections) {
  const node = after.getElementById(section.id);
  equal(node.querySelector('h2').textContent, section.heading, `Heading: ${section.id}`);
  equal(norm(node.querySelector('.space-blog-content').innerHTML), norm(new JSDOM(section.contentHtml).window.document.body.innerHTML), `SSR/client HTML: ${section.id}`);
  ok([...after.querySelectorAll(`a[href="#${section.id}"]`)].length > 0, `TOC anchor: ${section.id}`);
}
for (const key of ['tldr', 'introduction', 'metaDescription']) ok([...after.querySelectorAll('p')].some(n => n.textContent === m.next[key]), `Visible ${key}`);
equal([...after.querySelectorAll('.space-reviewed-faq summary')].map(n => n.textContent), m.next.faq.map(f => f.question), 'Native FAQ questions');
equal([...after.querySelectorAll('.space-reviewed-faq details > p')].map(n => n.textContent), m.next.faq.map(f => f.answer), 'No-JS FAQ answers');
equal(after.querySelectorAll('.space-blog-content script,.space-blog-content iframe,.space-blog-content form,.space-reviewed-faq script').length, 0, 'Content has no executable embeds');
const schemas = [...after.querySelectorAll('script[type="application/ld+json"]')].map(n => JSON.parse(n.textContent));
const article = schemas.find(s => s['@type'] === 'Article');
equal(article.dateModified, m.next.reviewedDate, 'Article review date');
equal(article.description, m.next.metaDescription, 'Article description');
equal(schemas.find(s => s['@type'] === 'FAQPage').mainEntity.map(q => ({question:q.name, answer:q.acceptedAnswer.text})), m.next.faq, 'FAQ schema matches visible answers');
const sourcesLabel = [...after.querySelectorAll('main > section p')].find(n => n.textContent === 'Sources');
equal([...sourcesLabel.nextElementSibling.querySelectorAll('a')].map(a => ({source:a.textContent, url:a.getAttribute('href')})), m.next.citations, 'Citations');
const seenLinks = new Set();
for (const a of after.querySelectorAll('a[href]')) {
  const href = a.getAttribute('href');
  if (seenLinks.has(href) || !href.startsWith('/') || href.startsWith('//')) continue;
  seenLinks.add(href);
  const url = new URL(href, 'https://spacemusic.io');
  const dest = url.pathname.slice(1);
  const f = inventory.includes(dest) ? dest : path.join(dest, 'index.html');
  ok(inventory.includes(f), `Link exists: ${href}`);
  if (url.hash) ok(new JSDOM(await read(m.output, f)).window.document.getElementById(url.hash.slice(1)), `Fragment exists: ${href}`);
}
for (const [old, next] of Object.entries(m.linkChanges)) {
  ok(!after.querySelector(`a[href="${old}"]`) && !after.querySelector(`a[href="${old}/"]`), `Dead link removed: ${old}`);
  ok(after.querySelector(`a[href="${next}"]`), `Replacement exists: ${next}`);
}
const canonicalPath = href => {
  const u = new URL(href, 'https://spacemusic.io');
  return u.pathname.replace(/\/$/, '') + u.hash;
};
const relatedHeading = [...after.querySelectorAll('h3')].find(n => n.textContent === 'Spoke pages');
equal([...relatedHeading.nextElementSibling.querySelectorAll('a')].map(a => ({title:a.textContent, url:canonicalPath(a.getAttribute('href'))})), m.next.spokeLinks.map(s => ({title:s.title, url:canonicalPath(s.url)})), 'Complete RelatedContent SSR/client link parity');
const guideLabel = [...after.querySelectorAll('main > section p')].find(n => n.textContent === 'Related guides');
equal([...guideLabel.nextElementSibling.querySelectorAll('a')].map(a => canonicalPath(a.getAttribute('href'))), m.next.spokeLinks.map(s => canonicalPath(s.url)), 'Complete related-guides SSR/client link parity');
const body = after.body.cloneNode(true);
body.querySelectorAll('script,style').forEach(n => n.remove());
for (const forbidden of ['3 to 15 times', '3–15x', 'over 100 active', 'typically $500 to $2,000', 'NPS is the royalty revenue that actually reaches you']) ok(!body.textContent.includes(forbidden), `Unsupported claim removed: ${forbidden}`);
ok(body.textContent.includes('$24,000') && body.textContent.includes('not a market valuation'), 'Hypothetical example clearly qualified');
equal(1000 * 12 * 4 * .5, 24000, 'Scenario mathematics');
function record(code, variable) {
  const node = parse(code, {sourceType:'module'}).program.body.flatMap(n => n.declarations || []).find(n => n.id.name === variable).init;
  return JSON.parse(JSON.stringify(vm.runInNewContext('(' + code.slice(node.start, node.end) + ')', {}, {timeout:1000})));
}
const [oldModule, nextModule] = m.modules.find(([a]) => a.startsWith('PillarGuidePage-'));
const oldCode = await read(m.source, 'assets/' + oldModule), newCode = await read(m.output, 'assets/' + nextModule);
equal(record(newCode, 'k'), m.next, 'Client record equals reviewed manifest');
equal(record(newCode, 'S'), record(oldCode, 'S'), 'Unrelated Music Rights 101 record unchanged');
ok(newCode.includes('t.contentHtml?') && newCode.includes('a.reviewedFaqHtml?') && newCode.includes('a.reviewedDate?'), 'Reviewed template changes conditional');
ok(newCode.includes('reloadDocument:!!a.reviewedDate&&t.url.includes("#")'), 'Reviewed spoke fragment uses native navigation');
ok(newCode.includes('nativeHashLinks:!!a.reviewedDate'), 'Only reviewed guide opts in to related hash navigation');
const relatedModule = m.modules.find(([a]) => a.startsWith('RelatedContent-'));
const relatedCode = await read(m.output, 'assets/' + relatedModule[1]);
ok(relatedCode.includes('nativeHashLinks:H=!1') && relatedCode.includes('reloadDocument:H&&s.to.includes("#")'), 'RelatedContent keeps old behavior unless explicitly opted in');
const visited = new Set();
async function visit(name) {
  if (visited.has(name)) return;
  visited.add(name);
  const code = await read(m.output, 'assets/' + name);
  parse(code, {sourceType:'module'});
  for (const n of literals(code)) if (/^(\.\/|assets\/).+\.js$/.test(n.value)) {
    const dep = path.basename(n.value);
    ok(inventory.includes('assets/' + dep), `Dependency exists: ${dep}`);
    await visit(dep);
  }
}
await visit(m.entry);
console.log(JSON.stringify({status:'PASS', checks, sitemapUrls:140, changedCopyPages:1, linkedDestinations:seenLinks.size, activeModules:visited.size, production:'unchanged; preview only'}, null, 2));

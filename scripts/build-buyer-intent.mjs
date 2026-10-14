import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {corrections, sharedCopy} from '../marketing/buyer-intent-20260916/content.mjs';

const [source, output, manifestPath] = process.argv.slice(2);
assert(source && output && manifestPath, 'Usage: APPROVED_SOURCE FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Output must be separate');
const hash = value => createHash('sha256').update(value).digest('hex');
const inventory = await files(source);
const codes = new Map();
for (const f of inventory.filter(f => /^assets\/.*\.js$/.test(f))) codes.set(path.basename(f), await readFile(path.join(source, f), 'utf8'));
const home = await readFile(path.join(source, 'index.html'), 'utf8');
const entry = home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry, 'index-article-360c41838159-quietseo-fd17485db4c3.js', 'Start from the approved whole-site preview');
const dependencies = name => literals(codes.get(name)).map(n => path.basename(n.value)).filter(n => codes.has(n));
const reachable = new Set();
function visit(name) { if (reachable.has(name)) return; reachable.add(name); dependencies(name).forEach(visit); }
visit(entry);
function moduleFor(prefix) {
  const found = [...reachable].filter(n => n.startsWith(prefix));
  assert.equal(found.length, 1, prefix);
  return found[0];
}
function walk(node, fn) {
  if (!node || typeof node !== 'object') return;
  fn(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(n => walk(n, fn));
    else if (value && typeof value === 'object') walk(value, fn);
  }
}
function recordNode(code, slug) {
  const found = [];
  walk(parse(code, {sourceType:'module'}), n => {
    if (n.type === 'ObjectExpression' && n.properties.some(p => p.type === 'ObjectProperty' && (p.key.name || p.key.value) === 'slug' && p.value.value === slug)) found.push(n);
  });
  assert.equal(found.length, 1, slug);
  return found[0];
}
function merge(before, patch) {
  const result = {...before};
  for (const [key, value] of Object.entries(patch)) {
    assert(Object.hasOwn(before, key), `Unexpected field ${key}`);
    result[key] = value && typeof value === 'object' && !Array.isArray(value) ? merge(before[key], value) : value;
  }
  return result;
}
function differences(a, b, result = [], key = '') {
  assert.equal(typeof a, typeof b, key);
  if (typeof a === 'string') { if (a !== b) result.push({key, before:a, after:b}); return result; }
  assert.deepEqual(Object.keys(a), Object.keys(b), key);
  for (const k of Object.keys(a)) differences(a[k], b[k], result, `${key}.${k}`);
  return result;
}
const {marked} = await import(process.env.MARKED_MODULE);
const escape = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const changed = new Set(), records = [], globalPairs = new Map(sharedCopy);
for (const change of corrections) {
  const name = moduleFor(`${change.family}-`);
  const exported = await import(path.resolve(source, 'assets', name));
  const old = exported[change.family === 'comparisons' ? 'c' : 'p'].find(x => x.slug === change.slug);
  assert(old, change.slug);
  const next = merge(old, change.patch), edits = differences(old, next);
  if (old.title !== next.title) globalPairs.set(old.title, next.title);
  // Listing cards consume the same record descriptions as the detail routes.
  for (const key of ['description', 'metaDescription']) {
    if (typeof old[key] === 'string' && old[key] !== next[key]) globalPairs.set(old[key], next[key]);
  }
  const markdown = await readFile(`marketing/buyer-intent-20260916/${change.slug}.md`, 'utf8');
  const guidance = marked.parse(markdown);
  // Native details keep the same FAQ available without JS and keyboard operable.
  const faq = `<section aria-labelledby="buyer-faq"><h2 id="buyer-faq">FAQ</h2>${next.faq.map(x => `<details class="border-b border-black/10 py-4"><summary class="cursor-pointer font-medium">${escape(x.question)}</summary><p>${escape(x.answer)}</p></details>`).join('')}</section>`;
  next.buyerGuidanceHtml = guidance + faq;
  const code = codes.get(name), node = recordNode(code, change.slug);
  codes.set(name, code.slice(0, node.start) + JSON.stringify(next) + code.slice(node.end));
  changed.add(name);
  records.push({...change, edits, old, next});
}
for (const [prefix, variable] of [['ComparisonPage-', 't'], ['PersonaPage-', 'a']]) {
  const name = moduleFor(prefix), code = codes.get(name), marker = `${variable}.faq.length>0&&e.jsxs("div"`;
  assert.equal(code.split(marker).length, 2, `One FAQ render in ${prefix}`);
  const guidance = `${variable}.buyerGuidanceHtml&&e.jsx("div",{className:"space-blog-content space-buyer-guidance mb-14",dangerouslySetInnerHTML:{__html:${variable}.buyerGuidanceHtml}}),!${variable}.buyerGuidanceHtml&&`;
  codes.set(name, code.replace(marker, guidance + marker));
  changed.add(name);
}
for (const name of reachable) {
  const before = codes.get(name);
  let after = before;
  for (const [a, b] of globalPairs) after = after.replaceAll(a, b);
  if (after !== before) { codes.set(name, after); changed.add(name); }
}
let growing = true;
while (growing) {
  growing = false;
  for (const name of reachable) if (!changed.has(name) && dependencies(name).some(n => changed.has(n))) { changed.add(name); growing = true; }
}
const revision = hash([...changed].sort().map(n => n + codes.get(n)).join('\n')).slice(0, 12);
const mapping = new Map([...changed].map(n => [n, n.replace(/\.js$/, `-intent-${revision}.js`)]));
await mkdir(output);
await cp(source, output, {recursive:true});
for (const name of changed) {
  let text = codes.get(name);
  for (const [a, b] of mapping) text = text.replaceAll(a, b);
  parse(text, {sourceType:'module'});
  await writeFile(path.join(output, 'assets', mapping.get(name)), text);
}
const copyPages = [], pageEdits = {};
for (const f of inventory.filter(f => f.endsWith('.html'))) {
  const before = await readFile(path.join(source, f), 'utf8');
  const record = records.find(r => f === r.route.slice(1) + 'index.html');
  const pairs = new Map(globalPairs);
  if (record) for (const edit of record.edits) {
    assert(!pairs.has(edit.before) || pairs.get(edit.before) === edit.after, `Ambiguous ${f}: ${edit.before}`);
    pairs.set(edit.before, edit.after);
  }
  const dom = new JSDOM(before), d = dom.window.document;
  let touched = false;
  const applied = new Set();
  const swap = value => {
    if (!pairs.has(value)) return value;
    touched = true; applied.add(value); return pairs.get(value);
  };
  const walker = d.createTreeWalker(d, 4);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.tagName === 'SCRIPT') {
      if (node.parentElement.type === 'application/ld+json') node.textContent = JSON.stringify(JSON.parse(node.textContent), (key, value) => typeof value === 'string' ? swap(value) : value);
    } else node.textContent = swap(node.textContent);
  }
  for (const el of d.querySelectorAll('[content]')) el.setAttribute('content', swap(el.getAttribute('content')));
  // Page title adds the site suffix, unlike the shared record title.
  if (record && record.old.title !== record.next.title) d.title = d.title.replace(record.old.title, record.next.title);
  if (record) {
    const faqHeading = [...d.querySelectorAll('h2')].find(el => el.textContent === 'FAQ');
    assert(faqHeading, `FAQ in ${f}`);
    const section = d.createElement('div');
    section.className = 'space-blog-content space-buyer-guidance mb-14';
    section.innerHTML = record.next.buyerGuidanceHtml;
    faqHeading.parentElement.replaceWith(section);
    touched = true;
  }
  if (touched) {
    copyPages.push(f);
    pageEdits[f] = [...applied].map(before => ({before, after:pairs.get(before)}));
  }
  let after = touched ? dom.serialize() : before;
  for (const [a, b] of mapping) after = after.replaceAll(a, b);
  await writeFile(path.join(output, f), after);
}
// A curated directory is useful, but it is not a ranking/citation mechanism.
const llms = await readFile(path.join(source, 'llms.txt'), 'utf8');
assert(!llms.includes('## Catalog Sale Decisions'));
const directory = `## Catalog Sale Decisions\n\nSPACE offers direct catalog review, not a loan, line of credit or royalty advance. These educational resources distinguish products and contractual scope.\n\n- [Independent label funding options](https://spacemusic.io/blog/independent-record-label-funding-options/): Compare selling existing catalog interests with advances, loans or retaining the catalog; prepare the label's own rights and cash-flow evidence.\n- [Catalog sale versus loan](https://spacemusic.io/compare/catalog-sale-vs-catalog-loan/): Rights, repayment, retained income and questions about advances.\n- [Partial versus full sale](https://spacemusic.io/compare/partial-sale-vs-full-sale/): Define the sold share, exclusions, control and future releases.\n- [Independent catalog owners](https://spacemusic.io/for/independent-artist-catalog-owner/): Prepare a catalog for individual review across genres.\n\n`;
await writeFile(path.join(output, 'llms.txt'), llms.replace('## Tools\n', directory + '## Tools\n'));
const sourceHashes = {};
for (const f of inventory) sourceHashes[f] = hash(await readFile(path.join(source, f)));
const manifest = {source, output, revision, entry:mapping.get(entry), sitemapUrls:140, copyPages, pageEdits, modules:[...mapping], records:records.map(({route, slug, family, edits, next}) => ({route, slug, family, edits, next})), sourceHashes, status:'PREVIEW ONLY; not a production release'};
await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
console.log(JSON.stringify({output, revision, copyPages, modules:changed.size, sitemapUrls:140}, null, 2));

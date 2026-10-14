import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { files } from './funnel-support.mjs';
import { literals, replaceLiterals } from './journey-support.mjs';

const [manifestFile] = process.argv.slice(2);
const map = JSON.parse(await readFile(manifestFile, 'utf8'));
const { source, output } = map;
const inventory = await files(source), candidateFiles = await files(output);
const read = (root, file) => readFile(path.join(root, file), 'utf8');
const reverse = new Map(map.changed.map(([oldName, newName]) => [newName, oldName]));
const undoHtmlVersions = html => {
  for (const [newName, oldName] of reverse) html = html.replaceAll(`/assets/${newName}`, `/assets/${oldName}`);
  return html;
};
for (const file of inventory) {
  assert(candidateFiles.includes(file), `Deleted ${file}`);
  const original = await readFile(path.join(source, file));
  assert.equal(createHash('sha256').update(original).digest('hex').slice(0, 12), map.sourceHashes[file], `Baseline changed: ${file}`);
  if (!file.endsWith('.html') || file.startsWith('apply/')) assert(original.equals(await readFile(path.join(output, file))), `Changed protected file: ${file}`);
  else if (file !== 'calculator/index.html') assert.equal(undoHtmlVersions(await read(output, file)), original.toString(), `Unrelated HTML change: ${file}`);
}
for (const [oldName, newName] of map.changed) {
  if (oldName === map.oldCalculator) continue;
  const code = await read(output, 'assets/' + newName);
  const revert = literals(code).filter(node => reverse.has(path.basename(node.value))).map(node => [node.value, node.value.slice(0, -path.basename(node.value).length) + reverse.get(path.basename(node.value))]);
  const restored = replaceLiterals(code, revert);
  // Literal quote normalization is immaterial; compare parsed string replacements on both sides.
  const original = await read(source, 'assets/' + oldName);
  const oldNames = new Set(map.changed.map(([old]) => old));
  const normalized = literals(original).filter(node => oldNames.has(path.basename(node.value))).map(node => [node.value, node.value]);
  assert.equal(restored, replaceLiterals(original, normalized), `Behavior changed in importer: ${oldName}`);
}
let seoPages = 0;
const sitemap = await read(output, 'sitemap.xml');
const urls = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => match[1]);
assert.equal(urls.length, 139);
assert.equal(new Set(urls).size, 139);
for (const url of urls) {
  const route = new URL(url).pathname;
  if (!route.endsWith('/')) continue;
  const file = route.slice(1) + 'index.html';
  const before = new JSDOM(await read(source, file)).window.document;
  const after = new JSDOM(undoHtmlVersions(await read(output, file))).window.document;
  const metadata = document => ({ title: document.title, meta: [...document.querySelectorAll('meta')].map(node => node.outerHTML).sort(), canonical: [...document.querySelectorAll('link[rel="canonical"]')].map(node => node.outerHTML), schema: [...document.querySelectorAll('script[type="application/ld+json"]')].map(node => JSON.parse(node.textContent)) });
  assert.deepEqual(metadata(after), metadata(before), `SEO metadata changed: ${file}`);
  assert.equal(after.querySelectorAll('h1').length, 1, `${file} H1 count`);
  assert.equal(after.querySelector('link[rel="canonical"]').href, url);
  assert(!/noindex/i.test(after.querySelector('meta[name="robots"]')?.content || ''));
  seoPages++;
}
const baseline = new JSDOM(await read(source, 'calculator/index.html')).window.document;
const doc = new JSDOM(await read(output, 'calculator/index.html')).window.document;
assert.equal(doc.querySelector('h1').textContent, 'How much could your music catalog sell for?');
assert(doc.getElementById('multiple-help').textContent.includes('no multiple is needed to apply'));
assert.equal(doc.querySelectorAll('noscript').length, baseline.querySelectorAll('noscript').length, 'Do not duplicate the no-JS fallback');
assert.equal(doc.querySelectorAll('section').length, baseline.querySelectorAll('section').length, 'Existing sections retained');
assert.deepEqual([...doc.querySelectorAll('summary')].map(node => node.textContent), [...baseline.querySelectorAll('summary')].map(node => node.textContent), 'FAQ topics retained');
const replaced = new Set([
  'Explore a hypothetical sale using your monthly net income and an assumed multiple you choose. This is not a market valuation or a SPACE offer.',
  'Choose your own positive assumption. No market multiple is supplied. A multiple is not a number of years to multiply again, nor the legal term of a sale.',
  'Monthly net income x 12 x assumed multiple x share sold. There is no extra years multiplier and no predicted price range.',
]);
const paragraphs = [...doc.querySelectorAll('p')].map(node => node.textContent);
for (const node of baseline.querySelectorAll('p')) if (!replaced.has(node.textContent)) assert(paragraphs.includes(node.textContent), `Unapproved paragraph removal: ${node.textContent}`);
for (const href of ['/blog/music-catalog-sale-documents-checklist/', '/pricing.md']) assert.equal(doc.querySelectorAll(`a[href="${href}"]`).length, 1);
assert.equal(doc.querySelectorAll('a[href="/apply/"]').length, baseline.querySelectorAll('a[href="/apply/"]').length, 'No duplicate Apply actions');
for (const node of doc.querySelectorAll('a[href^="/"]')) {
  const route = new URL(node.getAttribute('href'), 'https://spacemusic.io').pathname;
  assert(candidateFiles.includes(route.slice(1) + 'index.html') || candidateFiles.includes(route.slice(1)), `Broken destination ${route}`);
}
const report = { output, onlyContentChanged: '/calculator/', sitemapUrls: urls.length, seoPages, seoMetadata: 'unchanged', existingAssets: 'byte-identical', apply: 'byte-identical', importerChanges: 'version references only', sectionsAndFaqTopics: 'retained', newContextLinks: 2, duplicateLinks: false, checkedAt: new Date().toISOString() };
await writeFile(path.join(path.dirname(manifestFile), 'static-checks.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));

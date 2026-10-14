import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {ledger} from '../marketing/motion-20260929/ledger.mjs';

// Adds only the decorative comparison motion (idea 2) to the homepage of the
// current production artifact. Everything else is copied byte for byte.
const [output, manifestPath] = process.argv.slice(2);
assert(output && manifestPath, 'Usage: FRESH_OUTPUT MANIFEST');
const source = 'tmp/editorial-preview-v5-20260916';
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Keep production immutable');
const release = await readFile('marketing/RELEASE.md', 'utf8');
assert(release.startsWith('# Current Marketing Release\n\nProduction: https://55284dbb.'), 'Rebase if production changed');
const hash = s => createHash('sha256').update(s).digest('hex');
const inventory = await files(source);
const read = f => readFile(path.join(source, f), 'utf8');
const home = new JSDOM(await read('index.html'));
const entry = path.basename(home.window.document.querySelector('script[type="module"][src]').src);
assert(entry.endsWith('-editorial-466b8cbb93ba.js'), 'Build from the published blog release');
const codes = new Map();
for (const f of inventory.filter(f => /^assets\/.*\.js$/.test(f))) codes.set(path.basename(f), await read(f));
const dependencies = n => literals(codes.get(n)).map(x => path.basename(x.value)).filter(x => codes.has(x));
const active = new Set();
function visit(n) { if (active.has(n)) return; active.add(n); dependencies(n).forEach(visit); }
visit(entry);
const found = [...active].filter(n => n.startsWith('Index-og-'));
assert.equal(found.length, 1, 'homepage module');
const indexModule = found[0];

const d = home.window.document;
const main = d.querySelector('main');
const oldHome = main.innerHTML;
const section = main.querySelector('section.quiet-comparison');
assert.equal(section.querySelector('h2').textContent, 'Stream it. Or sell it.');
const intro = section.querySelector('h2 + p');
assert(intro && intro.nextElementSibling.classList.contains('rounded-2xl'), 'comparison table position');
section.insertAdjacentHTML('afterbegin', ledger);
const newHome = main.innerHTML;

// Server HTML and the client-rendered homepage share one literal; update both.
const candidates = literals(codes.get(indexModule)).filter(n => n.value === oldHome);
assert.equal(candidates.length, 1, 'shared server/client homepage markup');
const c = candidates[0];
const code = codes.get(indexModule);
codes.set(indexModule, code.slice(0, c.start) + JSON.stringify(newHome) + code.slice(c.end));
parse(codes.get(indexModule), {sourceType:'module'});

const changed = new Set([indexModule]);
let growing = true;
while (growing) {
  growing = false;
  for (const n of active) if (!changed.has(n) && dependencies(n).some(x => changed.has(x))) { changed.add(n); growing = true; }
}
const revision = hash([...changed].sort().map(n => n + codes.get(n)).join('\n')).slice(0, 12);
const mapping = new Map([...changed].map(n => [n, `${n.split('-').slice(0,2).join('-')}-motion-${hash(n + revision).slice(0,12)}.js`]));
const rewrite = text => { for (const [a, b] of mapping) text = text.replaceAll(a, b); return text; };
await mkdir(output); await cp(source, output, {recursive:true});
for (const n of changed) { const next = rewrite(codes.get(n)); parse(next, {sourceType:'module'}); await writeFile(path.join(output, 'assets', mapping.get(n)), next); }
for (const f of inventory.filter(f => f.endsWith('.html'))) {
  const html = f === 'index.html' ? home.serialize() : await read(f);
  const next = rewrite(html);
  if (next !== html || f === 'index.html') await writeFile(path.join(output, f), next);
}
const sourceHashes = {};
for (const f of inventory) sourceHashes[f] = hash(await readFile(path.join(source, f)));
await mkdir(path.dirname(manifestPath), {recursive:true});
await writeFile(manifestPath, JSON.stringify({source, output, revision, entry:mapping.get(entry), indexModule:mapping.get(indexModule), modules:[...mapping], sourceHashes, sitemapUrls:141, status:'PREVIEW ONLY; no production promotion authorized'}, null, 2) + '\n');
console.log(JSON.stringify({output, revision, modules:changed.size}, null, 2));

import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {audienceHeading, audienceLinks, sellerPaths, calculatorChoice, calculatorNext} from '../marketing/conversion-20260917/content.mjs';

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
function moduleFor(prefix) {
  const found = [...active].filter(n => n.startsWith(prefix));
  assert.equal(found.length, 1, prefix);
  return found[0];
}
function walk(n, fn) {
  if (!n || typeof n !== 'object') return;
  if (n.type) fn(n);
  for (const [k, v] of Object.entries(n)) if (!['loc', 'extra'].includes(k)) {
    if (Array.isArray(v)) v.forEach(c => walk(c, fn));
    else if (v && typeof v === 'object') walk(v, fn);
  }
}
function edit(code, edits) {
  let limit = code.length;
  for (const x of edits.sort((a, b) => b.start - a.start)) {
    assert(x.end <= limit, 'Edits must not overlap');
    code = code.slice(0, x.start) + x.text + code.slice(x.end);
    limit = x.start;
  }
  return code;
}
const changed = new Set();
function replaceHTML(name, before, after) {
  const code = codes.get(name);
  const candidates = literals(code).filter(n => n.value === before);
  assert.equal(candidates.length, 1, `Shared server/client markup in ${name}`);
  codes.set(name, edit(code, [{...candidates[0], text:JSON.stringify(after)}]));
  changed.add(name);
}

const d = home.window.document;
const main = d.querySelector('main');
const oldHome = main.innerHTML;
const breadth = d.querySelector('.growth-breadth');
assert.equal(breadth.children.length, 2);
for (const [i, block] of [...breadth.children].entries()) {
  const a = d.createElement('a');
  a.href = audienceLinks[i][0]; a.textContent = audienceLinks[i][1]; a.className = 'conversion-text-link';
  block.querySelector('p').after(a);
}
const audience = d.createElement('section');
audience.className = 'conversion-audience'; audience.setAttribute('aria-labelledby', 'conversion-audience-title');
audience.innerHTML = `<div class="conversion-wrap"><h2 id="conversion-audience-title">${audienceHeading}</h2></div>`;
audience.firstElementChild.append(breadth);
main.querySelector('.quiet-bento').after(audience);
replaceHTML(moduleFor('Index-og-'), oldHome, main.innerHTML);

const sell = new JSDOM(await read('sell/index.html'));
const sellMain = sell.window.document.querySelector('main');
const oldSell = sellMain.innerHTML;
sellMain.querySelector('.sell-hero').insertAdjacentHTML('afterend', sellerPaths);
replaceHTML(moduleFor('GenreIndex-'), oldSell, sellMain.innerHTML);

const calculator = new JSDOM(await read('calculator/index.html'));
const cd = calculator.window.document;
const root = cd.querySelector('#root>div.min-h-screen'); assert(root);
root.id = 'space-conversion-calculator';
const sections = [...root.querySelectorAll(':scope>section')]; assert.equal(sections.length, 5);
sections[0].firstElementChild.insertAdjacentHTML('beforeend', `<div class="conversion-choice">${calculatorChoice}</div>`);
const inputs = sections[1].firstElementChild.firstElementChild;
inputs.id = 'calculator-inputs'; inputs.tabIndex = -1;
const aside = sections[1].querySelector('aside');
const method = aside.lastElementChild;
assert.equal(method.querySelector('h3').textContent, 'From an assumption to a useful next step');
method.className = 'conversion-method-content';
const methodSection = cd.createElement('section'); methodSection.className = 'conversion-method';
const methodWrap = cd.createElement('div'); methodWrap.className = 'conversion-wrap';
methodWrap.append(method); methodSection.append(methodWrap); sections[1].after(methodSection);
aside.insertAdjacentHTML('beforeend', `<div class="conversion-next">${calculatorNext}</div>`);

// Patch only presentation calls in the published calculator. Its compiled math,
// state, event tracking and imports remain intact until dependency versioning.
const calculatorName = moduleFor('Calculator-');
let code = codes.get(calculatorName);
const calls = [];
walk(parse(code, {sourceType:'module'}), n => {
  if (n.type === 'CallExpression' && n.callee.property?.name === 'createElement') calls.push(n);
});
const cls = n => n.arguments[1]?.properties?.find(p => p.key?.name === 'className')?.value?.value;
const one = (fn, label) => {const found = calls.filter(fn); assert.equal(found.length, 1, label); return found[0];};
const callRoot = one(n => cls(n) === 'min-h-screen flex flex-col bg-cream', 'calculator root');
const hero = one(n => cls(n) === sections[0].className, 'calculator hero');
const heroBody = hero.arguments[2];
const inputsCall = one(n => cls(n) === inputs.className, 'calculator inputs');
const asideCall = one(n => n.arguments[0].value === 'aside', 'calculator result');
const methodCall = asideCall.arguments.at(-1);
assert(code.slice(methodCall.start, methodCall.end).includes('From an assumption to a useful next step'));
const gridSection = one(n => cls(n) === sections[1].className && n.arguments[0].value === 'section', 'calculator grid');
const react = callRoot.callee.object.name;
const staticBlock = (cl, html) => `${react}.createElement("div",{className:${JSON.stringify(cl)},dangerouslySetInnerHTML:{__html:${JSON.stringify(html)}}})`;
const oldMethod = code.slice(methodCall.start, methodCall.end);
const methodClass = methodCall.arguments[1].properties.find(p => p.key?.name === 'className').value;
const newMethod = oldMethod.slice(0, methodClass.start - methodCall.start) + '"conversion-method-content"' + oldMethod.slice(methodClass.end - methodCall.start);
code = edit(code, [
  {start:callRoot.arguments[1].start+1, end:callRoot.arguments[1].start+1, text:'id:"space-conversion-calculator",'},
  {start:heroBody.end-1, end:heroBody.end-1, text:','+staticBlock('conversion-choice', calculatorChoice)},
  {start:inputsCall.arguments[1].start+1, end:inputsCall.arguments[1].start+1, text:'id:"calculator-inputs",tabIndex:-1,'},
  {...methodCall, text:staticBlock('conversion-next', calculatorNext)},
  {start:gridSection.end, end:gridSection.end, text:`,${react}.createElement("section",{className:"conversion-method"},${react}.createElement("div",{className:"conversion-wrap"},${newMethod}))`},
]);
parse(code, {sourceType:'module'}); codes.set(calculatorName, code); changed.add(calculatorName);

let growing = true;
while (growing) {
  growing = false;
  for (const n of active) if (!changed.has(n) && dependencies(n).some(d => changed.has(d))) { changed.add(n); growing = true; }
}
const css = await readFile('marketing/conversion-20260917/conversion.css', 'utf8');
const revision = hash(css + [...changed].sort().map(n => n + codes.get(n)).join('\n')).slice(0,12);
const cssName = `conversion-${revision}.css`;
const mapping = new Map([...changed].map(n => [n, `${n.split('-').slice(0,2).join('-')}-cro-${hash(n+revision).slice(0,12)}.js`]));
const rewrite = text => {for (const [a,b] of mapping) text = text.replaceAll(a,b); return text;};
await mkdir(output); await cp(source, output, {recursive:true});
await writeFile(path.join(output, 'assets', cssName), css);
for (const n of changed) {const next = rewrite(codes.get(n)); parse(next, {sourceType:'module'}); await writeFile(path.join(output,'assets',mapping.get(n)),next);}
const docs = new Map([['index.html', home], ['sell/index.html', sell], ['calculator/index.html', calculator]]);
for (const f of inventory.filter(f => f.endsWith('.html') && !f.startsWith('apply/'))) {
  let html = docs.has(f) ? docs.get(f).serialize() : await read(f);
  // Scoped CSS must be available after client navigation from any marketing page.
  html = html.replace('</head>', `<link rel="stylesheet" href="/assets/${cssName}"></head>`);
  await writeFile(path.join(output, f), rewrite(html));
}
const sourceHashes = {};
for (const f of inventory) sourceHashes[f] = hash(await readFile(path.join(source,f)));
await mkdir(path.dirname(manifestPath), {recursive:true});
await writeFile(manifestPath, JSON.stringify({source, output, revision, cssName, entry:mapping.get(entry), modules:[...mapping], pages:[...docs.keys()], sourceHashes, sitemapUrls:141, status:'PREVIEW ONLY; no production promotion authorized', calculatorModule:mapping.get(calculatorName)},null,2)+'\n');
console.log(JSON.stringify({output,revision,modules:changed.size,pages:[...docs.keys()],sitemapUrls:141},null,2));

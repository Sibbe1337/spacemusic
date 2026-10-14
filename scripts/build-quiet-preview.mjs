import assert from 'node:assert/strict';
import { readFile,writeFile,mkdir,cp } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { parse } from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import { files } from './funnel-support.mjs';
import { literals,replaceLiterals } from './journey-support.mjs';
import { quietHomeLayout } from '../marketing/quiet-preview-20260916/layout.mjs';

const [sourceManifest,output,manifestPath] = process.argv.slice(2);
assert(sourceManifest && output && manifestPath,'Usage: GROWTH_V5_MANIFEST FRESH_OUTPUT MANIFEST');
const baseline = JSON.parse(await readFile(sourceManifest,'utf8'));
assert.equal(baseline.revision,'52842f5a03ff','Use the verified v5 preview as the design baseline');
const source = baseline.output;
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Preserve the baseline');
const hash = value => createHash('sha256').update(value).digest('hex');
const inventory = await files(source);
const sourceHashes = Object.fromEntries(await Promise.all(inventory.map(async f=>[f,hash(await readFile(path.join(source,f)))])));
const home = new JSDOM(await readFile(path.join(source,'index.html'),'utf8'));
const oldHTML = home.window.document.querySelector('main').innerHTML;
const main = quietHomeLayout(home.window.document);
const codes = new Map();
for (const file of inventory.filter(f=>/^assets\/.*\.js$/.test(f))) codes.set(path.basename(file),await readFile(path.join(source,file),'utf8'));
const entry = home.window.document.querySelector('script[type="module"][src]').getAttribute('src').split('/').pop();
const dependencies = name => literals(codes.get(name)).map(n=>path.basename(n.value)).filter(n=>codes.has(n));
const reachable = new Set();
function visit(name) { if(reachable.has(name))return; reachable.add(name); dependencies(name).forEach(visit); }
visit(entry);
assert(reachable.has(baseline.homeModule),'Current homepage must be reachable');
const homeCode = codes.get(baseline.homeModule);
const candidates = [];
const walk = node => {
  if (!node || typeof node!=='object') return;
  if (node.type==='StringLiteral' && node.value===oldHTML || node.type==='TemplateLiteral' && !node.expressions.length && node.quasis[0].value.cooked===oldHTML) candidates.push(node);
  for (const value of Object.values(node)) if(Array.isArray(value))value.forEach(walk);else if(value && typeof value==='object')walk(value);
};
walk(parse(homeCode,{sourceType:'module'}));
assert.equal(candidates.length,1,'Replace only the trusted shared homepage HTML constant');
const node = candidates[0];
codes.set(baseline.homeModule,homeCode.slice(0,node.start)+JSON.stringify(main.innerHTML)+homeCode.slice(node.end));
const changed = new Set([baseline.homeModule]);
let growing = true;
while(growing) { growing=false; for(const name of reachable) if(!changed.has(name)&&dependencies(name).some(n=>changed.has(n))) { changed.add(name); growing=true; } }
const stylesheet = await readFile('marketing/quiet-preview-20260916/quiet.css','utf8');
const styleName = `quiet-${hash(stylesheet).slice(0,12)}.css`;
const revision = hash([...changed].sort().map(n=>n+codes.get(n)).join('\n')+stylesheet).slice(0,12);
const renamed = new Map([...changed].map(n=>[n,`${n.slice(0,-3)}-quiet-${revision}.js`]));
await mkdir(output);
await cp(source,output,{recursive:true});
await writeFile(path.join(output,'assets',styleName),stylesheet);
for(const name of changed) {
  const pairs = literals(codes.get(name)).filter(n=>renamed.has(path.basename(n.value))).map(n=>[n.value,n.value.slice(0,-path.basename(n.value).length)+renamed.get(path.basename(n.value))]);
  await writeFile(path.join(output,'assets',renamed.get(name)),replaceLiterals(codes.get(name),pairs));
}
for(const file of inventory.filter(f=>f.endsWith('.html')&&!f.startsWith('apply/'))) {
  let html = file==='index.html'?home.serialize():await readFile(path.join(source,file),'utf8');
  for(const [from,to]of renamed) html=html.replaceAll(`/assets/${from}`,`/assets/${to}`);
  html=html.replace('</head>',`<link rel="stylesheet" href="/assets/${styleName}"></head>`);
  await writeFile(path.join(output,file),html);
}
await mkdir(path.dirname(manifestPath),{recursive:true});
await writeFile(manifestPath,JSON.stringify({sourceManifest,source,output,revision,homeModule:renamed.get(baseline.homeModule),stylesheet:styleName,changedModules:[...renamed],sourceHashes,scope:'Homepage layout only; preview only',production:'unchanged'},null,2)+'\n');
console.log(JSON.stringify({output,revision,changedModules:changed.size,stylesheet:styleName,status:'preview only'}));

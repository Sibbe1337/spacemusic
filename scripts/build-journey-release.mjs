import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { files } from './funnel-support.mjs';
import { copy, literals, replaceLiterals, directApplicationLinks, sourceModules, updateSharedDocument } from './journey-support.mjs';

const [source,output,applyBuild] = process.argv.slice(2);
assert(source && output && applyBuild && path.resolve(source)!==path.resolve(output));
const hash = text => createHash('sha256').update(text).digest('hex').slice(0,12);
const inventory = await files(source), originals = new Map(), codes = new Map();
const home = await readFile(path.join(source,'index.html'),'utf8');
const entry = home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry,'index-guide-e66c64405e6c.js','Start from the verified funnel release');
assert(!home.includes('data-space-design'));
for (const file of inventory.filter(file=>file.startsWith('assets/') && file.endsWith('.js'))) {
  const name = path.basename(file), original = await readFile(path.join(source,file),'utf8');
  originals.set(name,original);
  let code = original;
  if (sourceModules[name]) code=replaceLiterals(code,sourceModules[name],true);
  code=replaceLiterals(code,copy.ctaAliases.map(old=>[old,copy.cta]));
  if (name==='Footer-CiCbq8u0.js') {
    code=replaceLiterals(code,[copy.footer],true);
    const link='e.jsx(i,{to:s,className:"type-small text-white/80';
    assert.equal(code.split(link).length,3);
    code=code.replaceAll(link,'e.jsx(s==="/apply"?"a":i,{...(s==="/apply"?{href:"/apply/"}:{to:s}),className:"type-small text-white/80');
  }
  if (name==='Navbar-DK5bZPep.js') {
    code=code.replaceAll('Calculator-LQUD5H9x.js','Calculator-scenario-a3cd3270b5bd.js').replaceAll('ApplicationForm-DRjdd2L1.js','CanonicalApplication-3b3108140369.js');
    const menu='e.jsx("div",{className:`md:hidden overflow-hidden';
    assert(code.includes(menu));
    code=code.replace(menu,'e.jsx("div",{id:"space-mobile-menu","aria-hidden":!r,inert:r?void 0:"",className:`md:hidden overflow-hidden');
    const toggle='"aria-label":r?"Close menu":"Open menu"';
    assert(code.includes(toggle));
    code=code.replace(toggle,'"aria-expanded":r,"aria-controls":"space-mobile-menu",'+toggle);
  }
  if (name==='GenreIndex-nzzjt_go.js') {
    const pattern=/[\w$]+\.typicalMultiples\.split\(","\)\[0\]/g;
    assert.equal([...code.matchAll(pattern)].length,3);
    code=code.replace(pattern,JSON.stringify('Individually reviewed'));
    // Keep both existing actions, but give the review action primary emphasis.
    const primary='inline-flex items-center gap-2 bg-brand text-white font-medium px-7 py-3.5 text-base rounded-full hover:bg-brand-hover transition-colors';
    const secondary='inline-flex items-center gap-2 text-ink-muted font-medium px-7 py-3.5 text-base rounded-full hover:text-white transition-colors';
    code=code.replace(JSON.stringify(primary),'"__CTA_SWAP__"').replace(JSON.stringify(secondary),JSON.stringify(primary)).replace('"__CTA_SWAP__"',JSON.stringify(secondary));
  }
  codes.set(name,directApplicationLinks(code));
}
const dependencies = name => new Set(literals(codes.get(name)).map(n=>path.basename(n.value)).filter(n=>codes.has(n)));
const reachable = new Set();
function visit(name) { if(reachable.has(name))return; reachable.add(name); for(const child of dependencies(name))visit(child); }
visit(entry);
assert(reachable.has('CanonicalApplication-3b3108140369.js'));
assert(!reachable.has('ApplicationForm-DRjdd2L1.js'),'Do not warm the retired application');
const changed = new Set([...reachable].filter(name=>codes.get(name)!==originals.get(name)));
let growing=true;
while(growing) {
  growing=false;
  for(const name of reachable) if(!changed.has(name) && [...dependencies(name)].some(dep=>changed.has(dep))) { changed.add(name);growing=true; }
}
const css = await readFile('marketing/journey/cta.css','utf8');
// A release fingerprint avoids recursive content hashes for cyclic ESM imports.
const revision=hash([...changed].sort().map(name=>name+codes.get(name)).join('\n')+css);
const renamed=new Map([...changed].map(name=>[name,`${name.slice(0,-3)}-journey-${revision}.js`]));
await mkdir(output);await cp(source,output,{recursive:true});
for(const name of changed) {
  const replacements=literals(codes.get(name)).filter(node=>renamed.has(path.basename(node.value))).map(node=>[node.value,node.value.slice(0,-path.basename(node.value).length)+renamed.get(path.basename(node.value))]);
  await writeFile(path.join(output,'assets',renamed.get(name)),replaceLiterals(codes.get(name),replacements));
}
const cssPath=`assets/journey-cta-${hash(css)}.css`;
await writeFile(path.join(output,cssPath),css);
let updatedPages=0;
for(const file of inventory.filter(file=>file.endsWith('.html') && file!=='apply/index.html')) {
  const dom=new JSDOM(await readFile(path.join(source,file),'utf8')), doc=dom.window.document;
  updateSharedDocument(doc);
  for(const node of doc.querySelectorAll('[src],[href]')) for(const attribute of ['src','href']) {
    const value=node.getAttribute(attribute);
    if(value?.startsWith('/assets/') && renamed.has(path.basename(value))) node.setAttribute(attribute,'/assets/'+renamed.get(path.basename(value)));
  }
  const style=doc.createElement('link');style.rel='stylesheet';style.href='/'+cssPath;doc.head.append(style);
  await writeFile(path.join(output,file),dom.serialize());updatedPages++;
}
const built=new JSDOM(await readFile(path.join(applyBuild,'index.html'),'utf8')).window.document;
const app=new JSDOM(await readFile(path.join(source,'apply/index.html'),'utf8'));
const appDoc=app.window.document;
for(const selector of ['script[type="module"][src]','link[rel="stylesheet"]']) {
  const node=built.querySelector(selector), attribute=node.tagName==='SCRIPT'?'src':'href';
  const asset=node.getAttribute(attribute);
  assert(asset.startsWith('/apply/assets/'));
  await cp(path.join(applyBuild,asset.slice('/apply/'.length)),path.join(output,asset.slice(1)));
  appDoc.querySelector(selector).setAttribute(attribute,asset);
}
for(const name of ['description','og:description','twitter:description']) {
  const selector=name.includes(':')?`meta[property="${name}"],meta[name="${name}"]`:`meta[name="${name}"]`;
  appDoc.querySelector(selector).setAttribute('content',built.querySelector(selector).content);
}
appDoc.getElementById('root').innerHTML=built.getElementById('root').innerHTML;
assert((await readFile(path.join(output,appDoc.querySelector('script[type="module"][src]').getAttribute('src').slice(1)),'utf8')).includes('https://formspree.io/f/mpwdnokz'));
await writeFile(path.join(output,'apply/index.html'),app.serialize());
for(const file of inventory.filter(file=>!file.endsWith('.html'))) assert((await readFile(path.join(source,file))).equals(await readFile(path.join(output,file))),`Existing asset changed: ${file}`);
await mkdir('tmp/journey-qa',{recursive:true});
await writeFile('tmp/journey-qa/module-map.json',JSON.stringify({source,output,revision,entry:renamed.get(entry),changed:[...renamed],htmlPages:updatedPages+1},null,2));
console.log(JSON.stringify({output,entry:renamed.get(entry),newModules:changed.size,htmlPages:updatedPages+1,oldAssets:'preserved',sitemap:'unchanged'}));

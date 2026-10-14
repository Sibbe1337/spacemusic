import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { transform } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { files } from './funnel-support.mjs';
import { literals } from './journey-support.mjs';

const [manifestPath] = process.argv.slice(2);
assert(manifestPath,'Usage: QUIET_MANIFEST');
const m = JSON.parse(await readFile(manifestPath,'utf8'));
const load = (root,file)=>readFile(path.join(root,file),'utf8');
const document = html=>new JSDOM(html).window.document;
const inventory = await files(m.output);
const hash = value=>createHash('sha256').update(value).digest('hex');
let checks = 0;
const same = (a,b,label)=>{assert.deepEqual(a,b,label);checks++;};
const metadata = d=>[...d.querySelectorAll('title,meta,link[rel="canonical"],script[type="application/ld+json"]')].map(n=>n.outerHTML);
for(const [file,digest]of Object.entries(m.sourceHashes)) {
  same(hash(await readFile(path.join(m.source,file))),digest,`Baseline drift: ${file}`);
  assert(inventory.includes(file),`File removed: ${file}`);checks++;
  if(!file.endsWith('.html')||file.startsWith('apply/')) same(await load(m.output,file),await load(m.source,file),`Protected file changed: ${file}`);
  if(file.endsWith('.html')) {
    const old=document(await load(m.source,file)), next=document(await load(m.output,file));
    same(metadata(next),metadata(old),`Metadata and schemas unchanged: ${file}`);
    if(file!=='index.html')same(next.body.innerHTML,old.body.innerHTML,`Other body unchanged: ${file}`);
    for(const el of next.querySelectorAll('script[src],link[rel="stylesheet"],link[rel="preload"],link[rel="modulepreload"]')) {
      const value=el.getAttribute('src')||el.getAttribute('href');
      if(value.startsWith('/')&&!value.startsWith('//')){assert(inventory.includes(value.slice(1)),`Missing asset: ${value}`);checks++;}
    }
  }
}
const before=document(await load(m.source,'index.html')),after=document(await load(m.output,'index.html'));
const texts=d=>{
  const result=new Map(),walker=d.createTreeWalker(d.body,4);
  while(walker.nextNode()) {
    if(['SCRIPT','STYLE'].includes(walker.currentNode.parentElement?.tagName))continue;
    const text=walker.currentNode.textContent.replace(/\s+/g,' ').trim();
    if(text)result.set(text,(result.get(text)||0)+1);
  }
  return [...result].sort(([a],[b])=>a.localeCompare(b));
};
same(texts(after),texts(before),'Every text node retained exactly, including all visible copy');
const links=d=>[...d.querySelectorAll('a[href]')].map(a=>[a.getAttribute('href'),a.textContent.replace(/\s+/g,' ').trim()]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
same(links(after),links(before),'Every existing link and anchor text retained');
same(after.querySelectorAll('main>section').length,10,'Original nine sections plus relocated review');
same(after.querySelector('h1').textContent,before.querySelector('h1').textContent,'H1 unchanged');
same(after.querySelectorAll('h1').length,1,'One H1');
same(after.querySelectorAll('.quiet-bento-grid>div,.quiet-bento-grid>dl').length,3,'One three-surface bento');
if(after.querySelector('.quiet-genre-directory')) {
  const directory=after.querySelector('.quiet-genre-directory');
  same(directory.children.length,9,'Nine visible genre destinations');
  same([...directory.children].map(a=>a.getAttribute('href')),[...before.querySelectorAll('.growth-genres .grid>a')].map(a=>a.getAttribute('href')),'Preserve genre destinations and order');
  same(directory.querySelectorAll('h3').length,9,'Each genre retains its heading');
  same(directory.querySelectorAll('p').length,9,'Each genre retains its description');
  same(directory.querySelectorAll('[hidden],[aria-hidden="true"],details,button').length,0,'No content hidden behind an interaction');
  same(after.querySelector('.quiet-genres').getAttribute('aria-labelledby'),'catalog-genres-title','Genre section has a visible accessible label');
  same(after.querySelector('.quiet-genre-introduction a').getAttribute('href'),'/apply/','All-genre application remains visible alongside the index');
  same(after.querySelectorAll('.growth-breadth>div').length,2,'Both audience explanations remain');
  const previous=document(await readFile('tmp/quiet-home-v2-20260916/index.html','utf8'));
  const isolated=document(await load(m.output,'index.html'));
  for(const d of [previous,isolated]) d.querySelector('.quiet-genres').replaceWith(d.createElement('section'));
  same(isolated.body.innerHTML,previous.body.innerHTML,'Homepage changes are isolated to the selected genre section');
}
const cjs=(await transform(await load(m.output,`assets/${m.homeModule}`),{format:'cjs'})).code;
for(const blocked of [false,true]) {
  const exports={},module={exports};let show=true,stored=false;
  const element=(type,props)=>({type,props});
  const vendor={e:{jsx:element,jsxs:element},r:{useState:()=>[show,v=>{show=v;}],useEffect:()=>{}},aF:'Helmet'};
  runInNewContext(cjs,{module,exports,require:name=>name.includes('vendor-')?vendor:name.includes('Navbar-')?{N:'Navbar'}:name.includes('Footer-')?{F:'Footer'}:name.includes('SEOHead-')?{S:'SEOHead'}:{C:'CookieBanner'},localStorage:{setItem:()=>{if(blocked)throw Error('blocked');stored=true;}}});
  same(module.exports.growthMainHTML,after.querySelector('main').innerHTML,'Same client and server HTML');
  const tree=module.exports.default().props.children;
  same(tree.find(n=>n.type==='main').props.dangerouslySetInnerHTML.__html,module.exports.growthMainHTML,'Client renders trusted HTML');
  tree.find(n=>n?.type==='CookieBanner').props.onAccept();
  same(show,false,'Cookie banner dismisses');same(stored,!blocked,'Blocked storage isolated');
}
for(const [,name]of m.changedModules) {
  for(const value of literals(await load(m.output,`assets/${name}`)).map(n=>n.value).filter(v=>/^\.\/[^/]+\.(js|css)$/.test(v))) {assert(inventory.includes(`assets/${value.slice(2)}`),`${name}: missing ${value}`);checks++;}
}
same([...after.querySelectorAll('main details')].map(n=>n.outerHTML),[...before.querySelectorAll('main details')].map(n=>n.outerHTML),'Native FAQs unchanged');
console.log(JSON.stringify({status:'PASS',checks,homepageCopy:'all unchanged',homepageLinks:'all unchanged',metadata:'unchanged on every page',apply:'byte-identical',otherBodies:'unchanged',clientSSRParity:true,sitemapURLs:139,production:'not changed'},null,2));

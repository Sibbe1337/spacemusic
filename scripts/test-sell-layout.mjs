import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { runInNewContext } from 'node:vm';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { transform } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { files } from './funnel-support.mjs';

const [beforeManifest, afterManifest] = process.argv.slice(2);
assert(beforeManifest && afterManifest, 'Usage: PREVIOUS_PREVIEW_MANIFEST NEW_PREVIEW_MANIFEST');
const previous = JSON.parse(await readFile(beforeManifest,'utf8'));
const current = JSON.parse(await readFile(afterManifest,'utf8'));
const read = (root,file) => readFile(path.join(root,file),'utf8');
const dom = html => new JSDOM(html).window.document;
let checks = 0;
const same = (actual,expected,label) => { assert.deepEqual(actual,expected,label); checks++; };
const before = dom(await read(previous.output,'sell/index.html'));
const after = dom(await read(current.output,'sell/index.html'));
const metadata = d => [...d.querySelectorAll('title,meta,link[rel="canonical"],script[type="application/ld+json"]')].map(n=>n.outerHTML);
same(metadata(after),metadata(before),'Sell metadata and structured data are unchanged from the reviewed preview');
same(after.querySelector('h1').textContent,before.querySelector('h1').textContent,'Sell H1 text unchanged');
same(after.querySelectorAll('main h1').length,1,'H1 is inside the main landmark');
const textCounts = d => {
  const counts = new Map(), walker = d.createTreeWalker(d.body,4);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (['SCRIPT','STYLE'].includes(node.parentElement?.tagName)) continue;
    const text = node.textContent.replace(/\s+/g,' ').trim();
    if (text) counts.set(text,(counts.get(text)||0)+1);
  }
  return counts;
};
const retainedText = textCounts(after);
for (const [text,count] of textCounts(before)) {
  assert((retainedText.get(text)||0)>=count,`Existing text lost: ${text}`); checks++;
}
const linkCounts = d => {
  const counts = new Map();
  for (const a of d.querySelectorAll('a[href]')) {
    const key = `${a.getAttribute('href')}|${a.textContent.replace(/\s+/g,' ').trim()}`;
    counts.set(key,(counts.get(key)||0)+1);
  }
  return counts;
};
const retainedLinks = linkCounts(after);
for (const [key,count] of linkCounts(before)) {
  assert((retainedLinks.get(key)||0)>=count,`Link or anchor text lost: ${key}`); checks++;
}
same(after.querySelectorAll('.sell-guide').length,38,'38 complete guide links retained');
same([...after.querySelectorAll('.sell-guide-list')].map(n=>n.children.length),[3,10,25],'Original genre groups retained');
same(after.querySelectorAll('.sell-cluster').length,4,'All four existing subgenre overviews retained');
for (const a of after.querySelectorAll('main a[href^="#"],a.space-skip')) {
  assert(after.getElementById(a.hash.slice(1)),`Missing jump destination: ${a.hash}`); checks++;
}
const IDs = [...after.querySelectorAll('[id]')].map(n=>n.id);
same(new Set(IDs).size,IDs.length,'No duplicate IDs');
const code = await read(current.output,`assets/${current.sellModule}`);
const cjs = (await transform(code,{format:'cjs'})).code;
const exports = {}, module = {exports};
const elements = (type,props) => ({type,props});
runInNewContext(cjs,{module,exports,require:name=>name.includes('vendor-')?{e:{jsx:elements,jsxs:elements}}:name.includes('Navbar-')?{N:'Navbar'}:name.includes('Footer-')?{F:'Footer'}:{S:'SEOHead'}});
same(module.exports.growthSellHTML,after.querySelector('main').innerHTML,'Client and server Sell content are identical');
const tree = module.exports.default().props.children;
const seo = tree.find(n=>n.type==='SEOHead').props;
same(seo.title,after.querySelector('meta[property="og:title"]').content,'Client title');
same(seo.description,after.querySelector('meta[name="description"]').content,'Client description');
same(seo.canonical,'/sell/','Client canonical');
same(JSON.stringify(seo.schema),JSON.stringify([...after.querySelectorAll('script[type="application/ld+json"]')].sort((a,b)=>a.id.localeCompare(b.id)).map(n=>JSON.parse(n.textContent))),'Client schema');
same(tree.find(n=>n.type==='main').props.dangerouslySetInnerHTML.__html,module.exports.growthSellHTML,'Client renders the same trusted content');
for (const file of (await files(previous.output)).filter(f=>f.endsWith('.html') && f!=='sell/index.html')) {
  const old = dom(await read(previous.output,file)), next = dom(await read(current.output,file));
  same(next.body.innerHTML,old.body.innerHTML,`No other page body changed: ${file}`);
  same(metadata(next),metadata(old),`No other page metadata changed: ${file}`);
}
for (const file of ['apply/index.html','sitemap.xml','robots.txt','_headers','_redirects']) {
  same(await read(current.output,file),await read(previous.output,file),`Protected preview file unchanged: ${file}`);
}
const oldCSS = await read(previous.output,`assets/${previous.stylesheet}`);
const newCSS = await read(current.output,`assets/${current.stylesheet}`);
assert(newCSS.startsWith(oldCSS),'Existing preview styles must not change'); checks++;
console.log(JSON.stringify({status:'PASS',checks,existingSellText:'all retained',existingSellLinks:'all retained',genreGuides:38,clientSSRParity:true,otherPageBodies:'unchanged',metadata:'unchanged',apply:'byte-identical',scope:'Sell layout only relative to previous preview'},null,2));

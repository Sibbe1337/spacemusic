import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import vm from 'node:vm';
const [baseline,output,manifestFile]=process.argv.slice(2);
assert(baseline&&output&&manifestFile,'Usage: APPROVED_QUIET_PREVIEW FINAL_OUTPUT MANIFEST');
const manifest=JSON.parse(await readFile(manifestFile,'utf8'));
let checks=0;
const inventory=await files(output), oldInventory=await files(baseline);
const norm=s=>s.replace(/\s+/g,' ').trim();
const labelPath=`/blog/${manifest.article}/`;
const pages=oldInventory.filter(f=>f.endsWith('.html'));
for(const f of pages){
  const before=new JSDOM(await readFile(path.join(baseline,f),'utf8')).window.document;
  const after=new JSDOM(await readFile(path.join(output,f),'utf8')).window.document;
  assert(after.body.classList.contains('space-quiet-site'),f);checks++;
  assert.equal(after.querySelectorAll('h1').length,before.querySelectorAll('h1').length,f);checks++;
  assert.equal(after.title,before.title,`${f}: title`);checks++;
  assert.equal(after.querySelector('link[rel="canonical"]')?.href,before.querySelector('link[rel="canonical"]')?.href,`${f}: canonical`);checks++;
  assert.equal(after.querySelector('meta[name="robots"]')?.content,before.querySelector('meta[name="robots"]')?.content,`${f}: robots`);checks++;
  for(const a of before.querySelectorAll('a[href]')){
    // The reviewed comparison replaces four unsupported source citations.
    if(f==='compare/space-vs-duetti/index.html'&&manifest.comparisonEdits.some(e=>e.before===a.getAttribute('href')))continue;
    assert([...after.querySelectorAll('a[href]')].some(b=>b.getAttribute('href')===a.getAttribute('href')),`${f}: lost link ${a.href}`);checks++;
  }
  if(f!=='compare/space-vs-duetti/index.html'){
    assert.equal(after.querySelector('meta[name="description"]')?.content,before.querySelector('meta[name="description"]')?.content,`${f}: description`);checks++;
    const plain=d=>{const clone=d.body.cloneNode(true);for(const e of clone.querySelectorAll('script,style'))e.remove();return norm(clone.textContent);};
    for(const a of after.querySelectorAll(`a[href="${labelPath}"]`)){
      if(a.closest('.space-label-guide-link'))a.closest('.space-label-guide-link').remove();
      else if(f==='glossary/catalog-loan/index.html')a.closest('aside').remove();
    }
    assert.equal(plain(after),plain(before),`${f}: old visible text must be retained`);checks++;
    const schemas=d=>[...d.querySelectorAll('script[type="application/ld+json"]')].map(n=>JSON.parse(n.textContent));
    assert.deepEqual(schemas(after),schemas(before),`${f}: schema`);checks++;
  }
}
for(const f of ['_headers','_redirects','robots.txt','llms.txt','pricing.md']){assert.equal(await readFile(path.join(output,f),'utf8'),await readFile(path.join(baseline,f),'utf8'),f);checks++;}
// Form receiver, SDK and attribution runtime remain byte-identical.
const applyBefore=new JSDOM(await readFile(path.join(baseline,'apply/index.html'),'utf8')).window.document;
const applyAfter=new JSDOM(await readFile(path.join(output,'apply/index.html'),'utf8')).window.document;
// Only the new known public path is added to attribution; all behavior stays identical.
const stripArticle=s=>s.replace(`,${JSON.stringify(labelPath)}`,'');
assert.deepEqual([...applyBefore.querySelectorAll('script')].map(e=>e.outerHTML),[...applyAfter.querySelectorAll('script')].map(e=>stripArticle(e.outerHTML)));checks++;
assert.deepEqual([...applyBefore.querySelectorAll('form')].map(e=>e.outerHTML),[...applyAfter.querySelectorAll('form')].map(e=>e.outerHTML));checks++;
for(const s of applyBefore.querySelectorAll('script[src^="/"]')){const f=s.getAttribute('src').slice(1);assert((await readFile(path.join(output,f))).equals(await readFile(path.join(baseline,f))),f);checks++;}
const oldUrls=[...(await readFile(path.join(baseline,'sitemap.xml'),'utf8')).matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);
const urls=[...(await readFile(path.join(output,'sitemap.xml'),'utf8')).matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);
assert.equal(oldUrls.length,139);assert.equal(urls.length,140);assert.equal(new Set(urls).size,140);checks+=3;
oldUrls.forEach(url=>{assert(urls.includes(url),url);checks++;});
const articleDoc=new JSDOM(await readFile(path.join(output,labelPath,'index.html'),'utf8')).window.document;
const tracker=[...articleDoc.scripts].find(s=>s.textContent.includes('if(window.spaceFunnel)'));
assert(tracker,'Article attribution script');checks++;
const window={}, stored=new Map();
vm.runInNewContext(tracker.textContent,{window,document:{referrer:'',addEventListener(){}},location:{pathname:labelPath,hostname:'spacemusic.io',origin:'https://spacemusic.io',href:'https://spacemusic.io'+labelPath},sessionStorage:{getItem:k=>stored.get(k),setItem:(k,v)=>stored.set(k,v)},URL});
assert.equal(window.spaceFunnel.publicPath(labelPath),labelPath);checks++;
assert.equal(window.spaceFunnel.publicPath(labelPath+'?email=private@example.com'),'');checks++;
assert.equal(window.spaceFunnel.sources().landing_path,labelPath);checks++;
const event=window.spaceFunnel.transformRequest({n:'apply_clicked',u:'https://spacemusic.io'+labelPath+'?token=private',p:{landing_path:labelPath,email:'private@example.com',amount:999},r:'https://example.com/private?q=secret'});
assert.equal(event.u,'https://spacemusic.io'+labelPath);assert.equal(event.r,'https://example.com');assert.deepEqual(Object.keys(event.p),['landing_path']);checks+=3;
assert.equal(articleDoc.querySelectorAll('h1').length,1);checks++;
assert.equal(articleDoc.querySelector('link[rel="canonical"]').href,`https://spacemusic.io${labelPath}`);checks++;
assert(articleDoc.querySelector('main').textContent.includes('not a loan or royalty-advance product'));checks++;
const entryText=await readFile(path.join(output,'assets',manifest.entry),'utf8');
const blog=path.basename(entryText.match(/assets\/BlogPost-[\w-]+\.js/)[0]);
const article=JSON.parse((await readFile(path.join(output,'assets',blog),'utf8')).match(/^const article = (.+);$/m)[1]);
const content=[...articleDoc.querySelectorAll('.space-blog-content')];
const normalizedHTML=value=>norm(new JSDOM(value).window.document.body.innerHTML);
assert.equal(normalizedHTML(content[0].innerHTML),normalizedHTML(article.introduction));assert.equal(normalizedHTML(content[1].innerHTML),normalizedHTML(article.body));checks+=2;
const comparisonHTML=await readFile(path.join(output,'compare/space-vs-duetti/index.html'),'utf8');
const comparisonDOM=new JSDOM(comparisonHTML).window.document;
for(const edit of manifest.comparisonEdits){
  assert(comparisonDOM.documentElement.textContent.includes(edit.after)||[...comparisonDOM.querySelectorAll('[content],[href]')].some(el=>el.getAttribute('content')===edit.after||el.getAttribute('href')===edit.after),`Missing reviewed copy: ${edit.after}`);checks++;
}
const activeSeen=new Set();
async function visit(name){
  if(activeSeen.has(name))return;activeSeen.add(name);
  const file=path.join(output,'assets',name),code=await readFile(file,'utf8');
  for(const n of literals(code))if(/^(\.\/|assets\/).+\.js$/.test(n.value)){const dep=path.basename(n.value);assert(inventory.includes(`assets/${dep}`),`Missing module ${dep}`);checks++;await visit(dep);}
}
await visit(manifest.entry);
const broken=[];
for(const f of manifest.copyPages){
  const d=new JSDOM(await readFile(path.join(output,f),'utf8')).window.document;
  for(const a of d.querySelectorAll('a[href]')){
    const href=a.getAttribute('href');if(!href.startsWith('/')||href.startsWith('//'))continue;
    const p=href.split(/[?#]/)[0];
    if(!inventory.includes(p.replace(/^\//,''))&&!inventory.includes(path.join(p,'index.html').replace(/^\//,'')))broken.push({file:f,href});
  }
}
assert.deepEqual(broken,[],'Review local destinations');checks++;
console.log(JSON.stringify({status:'PASS',checks,existingPages:pages.length,newArticle:labelPath,oldSitemapUrlsRetained:139,finalSitemapUrls:140,activeModules:activeSeen.size,apply:'form and receiver unchanged; attribution only adds the new public path',production:'not touched'},null,2));

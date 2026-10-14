import assert from 'node:assert/strict';
import {cp,mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';

const [source,output,manifestFile]=process.argv.slice(2);
assert(source&&output&&manifestFile,'Usage: ARTICLE_BUILD FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Separate output required');
const hash=v=>createHash('sha256').update(v).digest('hex');
const inventory=await files(source), codes=new Map();
for(const f of inventory.filter(f=>/^assets\/.*\.js$/.test(f))) codes.set(path.basename(f),await readFile(path.join(source,f),'utf8'));
const html=await readFile(path.join(source,'index.html'),'utf8');
const entry=html.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
const deps=name=>literals(codes.get(name)).map(n=>path.basename(n.value)).filter(n=>codes.has(n));
const reachable=new Set();
function visit(name){if(reachable.has(name))return;reachable.add(name);deps(name).forEach(visit);}
visit(entry);
function moduleFor(prefix){const n=[...reachable].filter(n=>n.startsWith(prefix));assert.equal(n.length,1,prefix);return n[0];}
const changed=new Set(), documents=new Map();
async function document(file){if(!documents.has(file))documents.set(file,new JSDOM(await readFile(path.join(source,file),'utf8')));return documents.get(file).window.document;}

// One reviewed comparison refresh. Other competitor records remain untouched.
const dataName=moduleFor('competitorComparisonsExpanded-');
const code=codes.get(dataName), tree=parse(code,{sourceType:'module'}), matches=[];
function findRecord(n){
  if(!n||typeof n!=='object')return;
  if(n.type==='ObjectExpression'&&n.properties.some(p=>p.type==='ObjectProperty'&&(p.key.name||p.key.value)==='slug'&&p.value.value==='space-vs-duetti'))matches.push(n);
  for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(findRecord);else if(v&&typeof v==='object')findRecord(v);}
}
findRecord(tree);assert.equal(matches.length,1);
const target=matches[0];
const old=(await import(path.resolve(source,'assets',dataName))).c.find(x=>x.slug==='space-vs-duetti');
const next=JSON.parse(await readFile('marketing/quiet-site-20260916/duetti.json','utf8'));
const pairs=new Map();
function diff(a,b,key=''){
  assert.equal(typeof a,typeof b,key);
  if(typeof a==='string'){
    if(a!==b){assert(!pairs.has(a)||pairs.get(a)===b,`Ambiguous replacement: ${a}`);pairs.set(a,b);}
    return;
  }
  if(Array.isArray(a)){assert.equal(a.length,b.length,key);a.forEach((v,i)=>diff(v,b[i],`${key}.${i}`));return;}
  assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),key);
  for(const k of Object.keys(a))diff(a[k],b[k],`${key}.${k}`);
}
diff(old,next);
codes.set(dataName,code.slice(0,target.start)+JSON.stringify(next)+code.slice(target.end));changed.add(dataName);
const comparison=await document('compare/space-vs-duetti/index.html');
const walker=comparison.createTreeWalker(comparison,4);
while(walker.nextNode()){
  const n=walker.currentNode;
  if(n.parentElement?.tagName==='SCRIPT'){
    if(n.parentElement.type==='application/ld+json')n.textContent=JSON.stringify(JSON.parse(n.textContent),(k,v)=>pairs.get(v)??v);
  } else if(pairs.has(n.textContent))n.textContent=pairs.get(n.textContent);
}
for(const el of comparison.querySelectorAll('[content],[href]'))for(const key of ['content','href'])if(pairs.has(el.getAttribute(key)))el.setAttribute(key,pairs.get(el.getAttribute(key)));

const guidePath='/blog/independent-record-label-funding-options/';
function allowArticleAttribution(text){
  return text.replace(/(<script[^>]*>)([\s\S]*?)(<\/script>)/g,(all,open,body,close)=>{
    if(!body.includes('if(window.spaceFunnel)'))return all;
    const match=body.match(/new Set\((\[[^\]]+\])\)/);assert(match,'Expected public-path allowlist');
    const paths=JSON.parse(match[1]);assert(paths.includes('/apply/'));
    assert(!paths.includes(guidePath),'New public route must be added exactly once');
    return open+body.replace(match[1],JSON.stringify([...paths,guidePath]))+close;
  });
}
function addLabelLink(d,type){
  let target;
  if(type==='home')target=[...d.querySelectorAll('.growth-breadth>div')].find(el=>el.querySelector('h3')?.textContent==='Independent labels & catalog owners');
  else target=d.querySelector('.sell-review');
  assert(target,`Missing ${type} audience section`);
  assert(!target.querySelector(`a[href="${guidePath}"]`),'Avoid duplicate link');
  const p=d.createElement('p');p.className='space-label-guide-link';
  const a=d.createElement('a');a.href=guidePath;a.className='text-brand underline underline-offset-4';a.textContent='Planning the next release? Compare label funding options';
  p.append(a);target.append(p);
}
for(const [file,prefix,type,marker] of [['index.html','Index-og-','home','growth-hero-layout'],['sell/index.html','GenreIndex-','sell','sell-hero-layout']]){
  addLabelLink(await document(file),type);
  const name=moduleFor(prefix);
  const pageCode=codes.get(name), nodes=literals(pageCode);
  function templates(n){
    if(!n||typeof n!=='object')return;
    if(n.type==='TemplateLiteral'&&n.expressions.length===0)nodes.push({...n,value:n.quasis[0].value.cooked});
    for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(templates);else if(v&&typeof v==='object')templates(v);}
  }
  templates(parse(pageCode,{sourceType:'module'}));
  const values=nodes.filter(n=>n.value.includes(marker)&&n.value.length>1000);
  assert.equal(values.length,1,`Trusted ${type} HTML export`);
  const fragment=new JSDOM(`<main>${values[0].value}</main>`).window.document;
  addLabelLink(fragment,type);
  codes.set(name,pageCode.slice(0,values[0].start)+JSON.stringify(fragment.querySelector('main').innerHTML)+pageCode.slice(values[0].end));changed.add(name);
}

// Re-version every affected importer; immutable prior assets stay available.
let growing=true;
while(growing){growing=false;for(const name of reachable)if(!changed.has(name)&&deps(name).some(n=>changed.has(n))){changed.add(name);growing=true;}}
const revision=hash([...changed].sort().map(n=>n+codes.get(n)).join('\n')).slice(0,12);
const mapping=new Map([...changed].map(n=>[n,n.replace(/\.js$/,`-quietseo-${revision}.js`)]));
await mkdir(output);await cp(source,output,{recursive:true});
for(const name of changed){let text=codes.get(name);for(const [a,b] of mapping)text=text.replaceAll(a,b);await writeFile(path.join(output,'assets',mapping.get(name)),text);}
for(const f of inventory.filter(f=>f.endsWith('.html'))){
  let text=documents.has(f)?documents.get(f).serialize():await readFile(path.join(source,f),'utf8');
  for(const [a,b] of mapping)text=text.replaceAll(a,b);
  text=allowArticleAttribution(text);
  await writeFile(path.join(output,f),text);
}

// Render the authored article from the same data consumed by the client route.
// No browser-dependent post-build mutation or empty client-only article shell.
const blogName=path.basename(codes.get(entry).match(/assets\/BlogPost-[\w-]+\.js/)[0]);
const article=JSON.parse(codes.get(blogName).match(/^const article = (.+);$/m)[1]);
const articleDOM=new JSDOM(await readFile(path.join(output,'blog/music-catalog-offer-checklist/index.html'),'utf8'));
const d=articleDOM.window.document;
const esc=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
d.title=article.seoTitle;
for(const [selector,value] of [
  ['meta[name="description"]',article.description],['meta[property="og:title"]',article.seoTitle],['meta[property="og:description"]',article.description],['meta[property="og:url"]',article.url],['meta[name="twitter:title"]',article.seoTitle],['meta[name="twitter:description"]',article.description],['meta[property="article:published_time"]',article.datePublished],['meta[property="article:modified_time"]',article.dateModified]
]){const el=d.querySelector(selector);assert(el,selector);el.content=value;}
d.querySelector('link[rel="canonical"]').href=article.url;
const schemas=[...d.querySelectorAll('script[type="application/ld+json"]')];assert.equal(schemas.length,article.schema.length);
schemas.forEach((el,i)=>{el.textContent=JSON.stringify(article.schema[i]);});
const main=d.querySelector('.space-blog-article');assert(main);
main.innerHTML=`<article><header class="space-blog-header"><nav aria-label="Breadcrumb"><a href="/">SPACE</a><span aria-hidden="true">/</span><span>${esc(article.category)}</span></nav><h1>${esc(article.title)}</h1><p class="space-blog-meta">By <a href="/about/">${esc(article.author)}</a> | <time datetime="${article.datePublished}">${esc(article.displayDate)}</time> | ${article.readingTime} min read</p></header><div class="space-blog-content">${article.introduction}</div><nav class="space-blog-toc" aria-label="In this article"><p>In this article</p><ol>${article.headings.map(h=>`<li><a href="#${h.id}">${esc(h.text)}</a></li>`).join('')}</ol></nav><div class="space-blog-content">${article.body}</div></article>`;
await writeFile(path.join(output,'blog',article.slug,'index.html'),articleDOM.serialize());
const sourceHashes={};for(const file of inventory)sourceHashes[file]=hash(await readFile(path.join(source,file)));
const manifest={source,output,revision,entry:mapping.get(entry),article:article.slug,copyPages:['index.html','sell/index.html','compare/space-vs-duetti/index.html','glossary/catalog-loan/index.html',`blog/${article.slug}/index.html`],comparisonEdits:[...pairs].map(([before,after])=>({before,after})),modules:[...mapping],sourceHashes,status:'preview only; production not changed'};
await writeFile(manifestFile,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({output,revision,copyEdits:pairs.size,articleWords:article.wordCount,sitemapUrls:140,status:manifest.status},null,2));

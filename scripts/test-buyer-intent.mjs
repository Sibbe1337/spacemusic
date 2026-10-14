import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';

const [manifestFile] = process.argv.slice(2);
assert(manifestFile, 'Usage: MANIFEST');
const m = JSON.parse(await readFile(manifestFile, 'utf8'));
const inventory = await files(m.output);
const read = (root, f) => readFile(path.join(root, f), 'utf8');
const hash = v => createHash('sha256').update(v).digest('hex');
const norm = v => v.replace(/\s+/g, ' ').trim();
const checks = {count:0};
const equal = (a,b,label) => {assert.deepEqual(a,b,label);checks.count++;};
const ok = (a,label) => {assert(a,label);checks.count++;};
const unversion = text => {for(const [a,b] of m.modules)text=text.replaceAll(b,a);return text;};
const text = d => {const c=d.body.cloneNode(true);c.querySelectorAll('script,style').forEach(e=>e.remove());return norm(c.textContent);};
for(const [f, expected] of Object.entries(m.sourceHashes)) {
  equal(hash(await readFile(path.join(m.source,f))), expected, `Baseline modified: ${f}`);
  if(!f.endsWith('.html') && f !== 'llms.txt') equal(await readFile(path.join(m.output,f)),await readFile(path.join(m.source,f)),`Preserve ${f}`);
}
const oldPages=Object.keys(m.sourceHashes).filter(f=>f.endsWith('.html'));
equal(inventory.filter(f=>f.endsWith('.html')),oldPages,'No routes added/removed');
for(const f of oldPages){
  const old=await read(m.source,f), fresh=await read(m.output,f);
  const before=new JSDOM(old).window.document, after=new JSDOM(fresh).window.document;
  equal([...after.querySelectorAll('link[rel="stylesheet"]')].map(n=>n.outerHTML),[...before.querySelectorAll('link[rel="stylesheet"]')].map(n=>n.outerHTML),`${f}: approved styles`);
  equal(after.querySelectorAll('h1').length,before.querySelectorAll('h1').length,`${f}: H1 count`);
  for(const selector of ['link[rel="canonical"]','meta[name="robots"]'])equal(after.querySelector(selector)?.outerHTML,before.querySelector(selector)?.outerHTML,`${f}: ${selector}`);
  equal([...after.querySelectorAll('script:not([type="application/ld+json"])')].map(n=>unversion(n.outerHTML)),[...before.querySelectorAll('script:not([type="application/ld+json"])')].map(n=>n.outerHTML),`${f}: scripts/analytics unchanged except imports`);
  equal([...after.querySelectorAll('form')].map(n=>n.outerHTML),[...before.querySelectorAll('form')].map(n=>n.outerHTML),`${f}: forms`);
  if(!m.copyPages.includes(f)){equal(unversion(fresh),old,`${f}: unrelated HTML byte-identical`);continue;}
  const pairs=new Map(m.pageEdits[f].map(e=>[e.before,e.after]));
  const walker=before.createTreeWalker(before,4);
  while(walker.nextNode()){
    const n=walker.currentNode;
    if(n.parentElement?.tagName==='SCRIPT'&&n.parentElement.type==='application/ld+json')n.textContent=JSON.stringify(JSON.parse(n.textContent),(k,v)=>pairs.get(v)??v);
    else if(pairs.has(n.textContent))n.textContent=pairs.get(n.textContent);
  }
  for(const el of before.querySelectorAll('[content]'))if(pairs.has(el.getAttribute('content')))el.setAttribute('content',pairs.get(el.getAttribute('content')));
  const record=m.records.find(r=>f===r.route.slice(1)+'index.html');
  if(record){
    const faq=[...before.querySelectorAll('h2')].find(n=>n.textContent==='FAQ');faq.parentElement.remove();
    const guidance=after.querySelector('.space-buyer-guidance');ok(guidance,`${f}: guidance`);
    equal(norm(guidance.innerHTML),norm(new JSDOM(record.next.buyerGuidanceHtml).window.document.body.innerHTML),`${f}: SSR/client guidance parity`);
    equal([...guidance.querySelectorAll('summary')].map(n=>n.textContent),record.next.faq.map(x=>x.question),`${f}: native FAQ`);
    equal([...guidance.querySelectorAll('details>p')].map(n=>n.textContent),record.next.faq.map(x=>x.answer),`${f}: no-JS FAQ answers`);
    equal(guidance.querySelectorAll('script,iframe,form').length,0,`${f}: trusted content only`);
    equal(after.querySelector('h1').textContent,record.next.title,`${f}: heading`);
    equal(after.title,record.next.title+' — SPACE',`${f}: search title`);
    equal(after.querySelector('meta[name="description"]').content,record.next.metaDescription,`${f}: description`);
    const schemas=[...after.querySelectorAll('script[type="application/ld+json"]')].map(n=>JSON.parse(n.textContent));
    const faqSchema=schemas.find(s=>s['@type']==='FAQPage');
    equal(faqSchema.mainEntity.map(s=>({question:s.name,answer:s.acceptedAnswer.text})),record.next.faq,`${f}: visible/schema answers`);
    for(const edit of record.edits) if(!edit.key.startsWith('.faq')){
      ok(after.documentElement.textContent.includes(edit.after)||[...after.querySelectorAll('[content]')].some(n=>n.content===edit.after),`${f}: reviewed copy ${edit.key}`);
    }
    guidance.remove();
  }
  equal(text(after),text(before),`${f}: only reviewed copy changed`);
  const links=d=>[...d.querySelectorAll('a[href]')].map(n=>n.getAttribute('href'));
  equal(links(after),links(before),`${f}: original links retained`);
}
for(const record of m.records){
  const mapped=m.modules.find(([a])=>a.startsWith(record.family+'-'));
  ok(mapped,`${record.slug}: versioned data`);
  const exportKey=record.family==='comparisons'?'c':'p';
  const next=(await import(path.resolve(m.output,'assets',mapped[1])))[exportKey];
  const old=(await import(path.resolve(m.source,'assets',mapped[0])))[exportKey];
  equal(next.find(x=>x.slug===record.slug),record.next,`${record.slug}: runtime data`);
  for(const item of old.filter(x=>!m.records.some(r=>r.slug===x.slug)))equal(next.find(x=>x.slug===item.slug),item,`${item.slug}: unrelated data unchanged`);
  const index=record.family==='comparisons'?'compare/index.html':'for/index.html';
  const listing=new JSDOM(await read(m.output,index)).window.document;
  const card=listing.querySelector(`main a[href="${record.route}"]`);
  ok(card,`${index}: card ${record.slug}`);
  equal(card.querySelector('p').textContent,record.family==='comparisons'?record.next.metaDescription:record.next.description,`${index}: SSR/client card description`);
  equal(card.querySelector('h2').textContent,record.family==='comparisons'?record.next.title:record.next.personaName,`${index}: SSR/client card title`);
}
const visited=new Set();
async function visit(name){
  if(visited.has(name))return;visited.add(name);
  const code=await read(m.output,'assets/'+name);parse(code,{sourceType:'module'});
  for(const n of literals(code))if(/^(\.\/|assets\/).+\.js$/.test(n.value)){
    const dep=path.basename(n.value);ok(inventory.includes('assets/'+dep),`Missing module: ${dep}`);await visit(dep);
  }
}
await visit(m.entry);
for(const f of m.copyPages){
  const d=new JSDOM(await read(m.output,f)).window.document;
  for(const el of d.querySelectorAll('a[href]')){
    const href=el.getAttribute('href');
    if(!href.startsWith('/')||href.startsWith('//'))continue;
    const dest=href.split(/[?#]/)[0].slice(1);
    ok(inventory.includes(dest)||inventory.includes(path.join(dest,'index.html')),`${f}: destination ${href}`);
  }
}
const sitemap=await read(m.output,'sitemap.xml');
equal((sitemap.match(/<loc>/g)||[]).length,140,'All 140 sitemap URLs preserved');
const llms=await read(m.output,'llms.txt'), previousLlms=await read(m.source,'llms.txt');
equal(llms.replace(/## Catalog Sale Decisions\n[\s\S]*?(?=## Tools\n)/,''),previousLlms,'llms only appends curated decisions');
for(const match of llms.matchAll(/\]\(https:\/\/spacemusic.io([^)]*)\)/g)){
  const dest=match[1].slice(1);ok(inventory.includes(dest)||inventory.includes(path.join(dest,'index.html')),`llms link ${match[1]}`);
}
console.log(JSON.stringify({status:'PASS',checks:checks.count,htmlPages:oldPages.length,sitemapUrls:140,reviewedPages:3,referenceOrCtaUpdates:m.copyPages.length-3,activeModules:visited.size,apply:'all forms, inline tracking, receiver and external runtime preserved',production:'unchanged; preview only'},null,2));

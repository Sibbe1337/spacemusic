import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { files } from './funnel-support.mjs';
import { copy, updateSharedDocument } from './journey-support.mjs';
const [baseline,release]=process.argv.slice(2);
const read=(root,file)=>readFile(path.join(root,file));
const inventory=await files(baseline), after=await files(release);
const map=JSON.parse(await readFile('tmp/journey-qa/module-map.json','utf8'));
assert.equal(map.output,release);
const reverse=new Map(map.changed.map(([old,next])=>[next,old]));
const changedContent=new Set(['index.html','how-it-works/index.html','sell/index.html','apply/index.html']);
for(const file of inventory) {
  assert(after.includes(file),`Deleted ${file}`);
  if(!file.endsWith('.html')) assert((await read(baseline,file)).equals(await read(release,file)),`Existing asset changed ${file}`);
}
let count=0;
for(const file of inventory.filter(name=>name.endsWith('.html'))) {
  const before=new JSDOM(await read(baseline,file)), next=new JSDOM(await read(release,file));
  const a=before.window.document,b=next.window.document;
  assert.equal(b.querySelectorAll('h1').length,1,file+' H1');
  if(file!=='index.html') assert.equal(b.querySelector('h1').textContent,a.querySelector('h1').textContent,file+' H1 unchanged');
  for(const selector of ['link[rel="canonical"]','meta[name="robots"]']) {
    assert.equal(b.querySelectorAll(selector).length,1,file+' '+selector);
    assert.equal(b.querySelector(selector).getAttribute(selector.startsWith('link')?'href':'content'),a.querySelector(selector).getAttribute(selector.startsWith('link')?'href':'content'),file+' '+selector);
  }
  assert.equal(b.querySelectorAll('meta[name="description"]').length,1);
  for(const json of b.querySelectorAll('script[type="application/ld+json"]')) JSON.parse(json.textContent);
  for(const node of b.querySelectorAll('[src],[href]')) for(const attr of ['src','href']) {
    const value=node.getAttribute(attr);
    if(value?.startsWith('/assets/') && reverse.has(path.basename(value))) node.setAttribute(attr,'/assets/'+reverse.get(path.basename(value)));
  }
  b.querySelectorAll('link[href^="/assets/journey-cta-"]').forEach(node=>node.remove());
  if(!changedContent.has(file)) {
    updateSharedDocument(a);
    assert.equal(b.head.innerHTML,a.head.innerHTML,file+' metadata unchanged');
    assert.equal(b.body.innerHTML,a.body.innerHTML,file+' only shared CTA/footer changed');
  } else {
    assert(b.querySelectorAll('section').length>=a.querySelectorAll('section').length,file+' sections preserved');
    if(file==='index.html') {
      assert(b.querySelector('h1').textContent.startsWith('Sell part of your catalog.'));
      const schema=[...b.querySelectorAll('script[type="application/ld+json"]')].map(n=>JSON.parse(n.textContent)).find(n=>n['@type']==='FAQPage');
      assert.equal(schema.mainEntity.length,8,'All existing FAQ subjects preserved');
      assert(!/\$2,000|\$2K|paid today|Get cash in days|3-10x|\$117,600|Fixed, guaranteed/.test(b.body.textContent+JSON.stringify(schema)));
    }
  }
  for(const node of b.querySelectorAll('a[href="/apply/"],a[href="/apply"]')) assert(!copy.ctaAliases.includes(node.textContent.trim()),file+' old primary CTA');
  count++;
}
const sitemap=(await read(release,'sitemap.xml')).toString();
assert.equal([...sitemap.matchAll(/<loc>/g)].length,139);
console.log(JSON.stringify({release,htmlPages:count,sitemap:139,allExistingUrls:'unchanged',existingAssets:'byte-identical',unrelatedContentAndMetadata:'unchanged except reviewed CTA/footer',homeFaqTopics:8}));

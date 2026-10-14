import assert from 'node:assert/strict';
import {cp,mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {loadSite,applyToModules} from './authentic-support.mjs';
import {serve,playwrightModule} from './funnel-support.mjs';
import {source,pages,makeEdits} from '../marketing/serp-20261008/content.mjs';

const output=process.argv[2];
assert(output,'Usage: node scripts/build-serp-preview.mjs FRESH_OUTPUT');
assert(path.resolve(output)!==path.resolve(source),'Never overwrite production');
const release=await readFile('marketing/RELEASE.md','utf8');
assert(release.startsWith('# Current Marketing Release\n\nProduction: https://29e7801c.'),'Rebase on the current release');
const hash=s=>createHash('sha256').update(s).digest('hex');
const site=await loadSite(source),edits=makeEdits(site);
const {stats,changed}=applyToModules(site,edits);
stats.forEach((s,i)=>assert(s.js>0,`Unapplied edit ${i}`));
const modules=new Map(changed);
let growing=true;
while(growing){growing=false;for(const n of site.active)if(!modules.has(n)&&site.deps(n).some(d=>modules.has(d))){modules.set(n,site.codes.get(n));growing=true;}}
const revision=hash(JSON.stringify(edits)).slice(0,12);
const mapping=new Map([...modules.keys()].map(n=>[n,`${n.split('-')[0]}-serp-${hash(n+revision).slice(0,12)}.js`]));
const rewrite=s=>{for(const [a,b]of mapping)s=s.replaceAll(a,b);return s;};
await mkdir(output); // Fails on an existing directory; never mixes releases.
await cp(source,output,{recursive:true});
for(const[n,c]of modules)await writeFile(path.join(output,'assets',mapping.get(n)),rewrite(c));
for(const f of site.htmlFiles){const old=await readFile(path.join(source,f),'utf8'),next=rewrite(old);if(next!==old)await writeFile(path.join(output,f),next);}

const {chromium}=await import(playwrightModule),server=await serve(output);
const browser=await chromium.launch({channel:'chrome'});
try{
  const context=await browser.newContext({locale:'en-US',serviceWorkers:'block'});
  // No lead submissions, third-party scripts or analytics leave this build.
  await context.route('**/*',r=>new URL(r.request().url()).origin===server.origin&&r.request().method()==='GET'?r.continue():r.abort());
  for(const f of pages){
    const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(server.origin+'/'+f.replace(/index\.html$/,''),{waitUntil:'networkidle'});
    assert.equal(errors.length,0,`${f}: ${errors.join('; ')}`);
    const rendered=await page.evaluate(()=>({root:document.getElementById('root').innerHTML,title:document.title,tags:[...document.head.querySelectorAll('[data-rh]')].map(n=>n.outerHTML)}));
    const dest=path.join(output,f),dom=new JSDOM(await readFile(dest,'utf8')),d=dom.window.document;
    d.getElementById('root').innerHTML=rendered.root;
    d.title=rendered.title;
    // Helmet can emit several schema scripts. Remove the previous set once,
    // not on each append (which would silently retain only the last script).
    if(rendered.tags.some(t=>t.includes('application/ld+json')))
      d.head.querySelectorAll('script[data-rh][type="application/ld+json"]').forEach(n=>n.remove());
    for(const html of rendered.tags){
      const el=JSDOM.fragment(html).firstElementChild;
      if(el.tagName==='TITLE')continue;
      // Replace by semantic key, including older static copies without data-rh.
      let selector;
      if(el.tagName==='META')selector=el.hasAttribute('name')?`meta[name="${el.getAttribute('name')}"]`:`meta[property="${el.getAttribute('property')}"]`;
      if(el.tagName==='LINK'&&el.rel==='canonical')selector='link[rel="canonical"]';
      if(selector)d.head.querySelectorAll(selector).forEach(n=>n.remove());
      else if(el.id)d.getElementById(el.id)?.remove();
      d.head.appendChild(d.importNode(el,true));
    }
    await writeFile(dest,dom.serialize());
    await page.close();
  }
}finally{await browser.close();server.close();}
const sourceHashes={};for(const f of site.inventory)sourceHashes[f]=hash(await readFile(path.join(source,f)));
const manifest={source,output,revision,pages,modules:[...mapping],changedModules:[...changed.keys()],sourceHashes,status:'PREVIEW ONLY; not deployed'};
await writeFile(output+'-manifest.json',JSON.stringify(manifest,null,2)+'\n');
await writeFile('marketing/serp-20261008/edits.json',JSON.stringify(edits,null,2)+'\n');
console.log(JSON.stringify({output,revision,pages:pages.length,changedModules:changed.size,versionedModules:modules.size}));

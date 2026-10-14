import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,access} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files,serve,playwrightModule} from './funnel-support.mjs';
import {loadSite,applyToModules,stringNodes} from './authentic-support.mjs';
import {makeEdits} from '../marketing/serp-20261008/content.mjs';

const output=process.argv[2];assert(output,'Usage: CANDIDATE');
const m=JSON.parse(await readFile(output+'-manifest.json','utf8')),mapping=new Map(m.modules);
const hash=b=>createHash('sha256').update(b).digest('hex');
const rewrite=s=>{for(const[a,b]of mapping)s=s.replaceAll(a,b);return s;};
let checks=0;const eq=(a,b,label)=>{assert.deepEqual(a,b,label);checks++;};
const ok=(a,label)=>{assert(a,label);checks++;};
const read=(dir,f)=>readFile(path.join(dir,f),'utf8');
const dom=s=>new JSDOM(s).window.document;
const normalized=s=>s.replace(/\s+/g,' ').trim();
const schemas=d=>[...d.querySelectorAll('script[type="application/ld+json"]')].flatMap(s=>{const j=JSON.parse(s.textContent);return Array.isArray(j)?j:[j];});
const signature=d=>({title:d.title,description:d.querySelector('meta[name="description"]')?.content,canonical:d.querySelector('link[rel="canonical"]')?.getAttribute('href'),h1:[...d.querySelectorAll('h1')].map(n=>n.textContent)});
const inventory=await files(output);
for(const[f,h]of Object.entries(m.sourceHashes)){
  eq(hash(await readFile(path.join(m.source,f))),h,'Source immutable: '+f);
  ok(inventory.includes(f),'No removed file: '+f);
  if(!m.pages.includes(f)){
    if(f.endsWith('.html'))eq(await read(output,f),rewrite(await read(m.source,f)),'Unrelated HTML unchanged: '+f);
    else eq(hash(await readFile(path.join(output,f))),h,'Existing non-HTML unchanged: '+f);
  }
}
const site=await loadSite(m.source),edits=makeEdits(site),changes=applyToModules(site,edits).changed;
for(const[a,b]of mapping)eq(await read(output,'assets/'+b),rewrite(changes.get(a)||site.codes.get(a)),'Exact reviewed module: '+b);
for(const name of inventory.filter(f=>f.endsWith('.js')&&f.includes('-serp-')))stringNodes(await read(output,name));
const urls=[...(await read(output,'sitemap.xml')).matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);eq(urls.length,144,'Sitemap URL count');
for(const url of urls){
  const route=new URL(url).pathname,f=route.slice(1)+(route.endsWith('/')?'index.html':'');
  if(!f.endsWith('.html')){eq(await read(output,f),await read(m.source,f),url+' non-HTML resource unchanged');continue;}
  const d=dom(await read(output,f));
  eq(d.querySelectorAll('link[rel="canonical"]').length,1,url+' canonical count');
  eq(d.querySelector('link[rel="canonical"]').href,url,url+' canonical');
  ok(![...d.querySelectorAll('meta[name="robots"]')].some(n=>/noindex/i.test(n.content)),url+' indexable');
  eq(d.querySelectorAll('h1').length,1,url+' H1');schemas(d);
}
const staticSignatures=new Map();
const staticSchema=new Map();
const schemaKey=s=>JSON.stringify(s,Object.keys(s).sort());
for(const f of m.pages){
  const old=dom(await read(m.source,f)),d=dom(await read(output,f));
  staticSignatures.set(f,signature(d));
  staticSchema.set(f,schemas(d));
  if(f!=='calculator/index.html')ok(schemas(d).some(s=>['Article','BlogPosting'].includes(s['@type'])),f+' article schema present');
  if(f.startsWith('guides/')||f.startsWith('compare/'))ok(schemas(d).some(s=>s['@type']==='FAQPage'),f+' FAQ schema present');
  eq(signature(d).h1,signature(old).h1,f+' H1 preserved');
  for(const selector of ['meta[name="description"]','meta[property="og:title"]','meta[property="og:description"]','meta[name="twitter:title"]','meta[name="twitter:description"]'])eq(d.querySelectorAll(selector).length,1,f+' unique '+selector);
  const oldLinks=[...old.querySelectorAll('#root a[href]')].map(a=>a.getAttribute('href')).filter(h=>h.startsWith('/'));
  const links=[...d.querySelectorAll('#root a[href]')].map(a=>a.getAttribute('href'));
  for(const href of new Set(oldLinks))ok(links.includes(href),f+' retains internal destination '+href);
  for(const href of new Set(links.filter(h=>h.startsWith('/')))){
    const pathname=new URL(href,'https://spacemusic.io').pathname;
    const file=pathname.slice(1)+(pathname.endsWith('/')?'index.html':'');
    // Known static destinations; no unrelated GSC query/page inference.
    try{await access(path.join(output,file));checks++;}catch{await access(path.join(output,file,'index.html'));checks++;}
  }
  for(const faq of schemas(d).filter(s=>s['@type']==='FAQPage'))for(const item of faq.mainEntity){
    const match=[...d.querySelectorAll('details')].find(n=>normalized(n.querySelector('summary')?.textContent||'')===normalized(item.name));
    ok(match,f+' FAQ exists in server HTML: '+item.name);
    ok(normalized(match.textContent).includes(normalized(item.acceptedAnswer.text)),f+' visible answer matches schema');
  }
}
eq(await read(output,'apply/index.html'),await read(m.source,'apply/index.html'),'Apply byte-identical');
const qa='marketing/serp-20261008/qa';await mkdir(qa,{recursive:true});
const server=await serve(output),{chromium}=await import(playwrightModule),browser=await chromium.launch({channel:'chrome'});
const errors=[],blocked=[];
async function context(options={}){
  const c=await browser.newContext({locale:'en-US',serviceWorkers:'block',...options});
  await c.route('**/*',r=>{const req=r.request();if(new URL(req.url()).origin===server.origin&&req.method()==='GET')return r.continue();blocked.push({method:req.method(),host:new URL(req.url()).hostname});return r.abort();});
  return c;
}
try{
  for(const js of [true,false]){
    const c=await context({javaScriptEnabled:js});const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));
    for(const width of [320,390,768,1440]){
      await p.setViewportSize({width,height:900});
      for(const f of m.pages){
        const response=await p.goto(server.origin+'/'+f.replace(/index\.html$/,''),{waitUntil:'networkidle'});
        eq(response.status(),200,f+' HTTP');
        const s=await p.evaluate(()=>({title:document.title,description:document.querySelector('meta[name="description"]')?.content,canonical:document.querySelector('link[rel="canonical"]')?.getAttribute('href'),h1:[...document.querySelectorAll('h1')].map(n=>n.textContent)}));
        eq(s,staticSignatures.get(f),f+' metadata/H1 parity JS='+js);
        const liveSchemas=await p.evaluate(()=>[...document.querySelectorAll('script[type="application/ld+json"]')].flatMap(n=>{const j=JSON.parse(n.textContent);return Array.isArray(j)?j:[j];}));
        const order=xs=>xs.sort((a,b)=>schemaKey(a).localeCompare(schemaKey(b)));
        eq(order(liveSchemas),order(structuredClone(staticSchema.get(f))),f+' complete schema parity JS='+js);
        ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),f+' no overflow '+width);
        const faq=p.locator('details').filter({has:p.locator('summary')}).last();
        if(await faq.count()){
          const wasOpen=await faq.evaluate(n=>n.open);
          await faq.locator('summary').press('Enter');
          eq(await faq.evaluate(n=>n.open),!wasOpen,f+' keyboard disclosure JS='+js);
        }
        if(js){await p.evaluate(()=>scrollTo(0,0));await p.screenshot({path:qa+'/'+f.split('/').filter(Boolean).slice(-2,-1)[0]+'-'+width+'.png'});}
        const apply=p.locator('a[href="/apply/"]:visible').last();
        ok(await apply.count()>0,f+' review next step');await apply.press('Enter');
        await p.waitForURL(server.origin+'/apply/');
        eq(await p.locator('h1').textContent(),'We buy your music catalog.',f+' correct Apply');
        eq(await p.locator('#short-form').count(),1,f+' existing fallback present');
      }
    }
    await c.close();
  }
  const c=await context(),p=await c.newPage();
  await p.goto(server.origin+'/calculator/',{waitUntil:'networkidle'});
  const income=p.getByLabel('Monthly net income (USD)',{exact:true}),multiple=p.getByLabel('Assumed annual-income multiple'),share=p.getByLabel('Share of defined rights to sell (%)',{exact:true}),result=p.locator('[data-scenario-result]');
  eq(await multiple.inputValue(),'','No preset multiple');ok(!(await result.textContent()).includes('$'),'Blank result');
  for(const test of [['1000','4','50','$24,000'],['0','4','50','$0'],['1000','4','0','$0'],['1000','4','100','$48,000'],['-1','4','50',null],['1000','0','50',null],['1000','4','101',null],['1000','4','-1',null],['','4','50',null],['1000','','50',null]]){
    await income.fill(test[0]);await multiple.fill(test[1]);await share.fill(test[2]);
    const text=await result.textContent();ok(test[3]===null?text.includes('Enter valid'):text.startsWith(test[3]),'Math '+JSON.stringify(test));
  }
  await p.getByRole('button',{name:'Calculate net income from receipts',exact:true}).click();
  await p.getByLabel('Monthly receipts before payouts and costs (USD)',{exact:true}).fill('4000');
  await p.getByLabel('Artist royalty payout (%)',{exact:true}).fill('40');
  await p.getByLabel('Operating costs (%)',{exact:true}).fill('10');
  await multiple.fill('4');await share.fill('50');ok((await result.textContent()).startsWith('$48,000'),'Derived net scenario');
  await p.getByLabel('Operating costs (%)',{exact:true}).fill('61');ok((await result.textContent()).includes('Enter valid'),'Excess deductions invalid');
  await c.close();
  eq(errors,[],'No browser errors');
}finally{await browser.close();server.close();}
const results={checks,source:m.source,output,sitemapUrls:144,changedPages:m.pages,jsAndNoJs:true,widths:[320,390,768,1440],applyUnchanged:true,realSubmissions:0,analyticsSent:0,blockedRequests:blocked.length,errors};
await writeFile(qa+'/results.json',JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results,null,2));

import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {build} from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {auditLinks} from './audit-internal-links.mjs';
import {primary,explore,learn,aliases,operational,createLinkResolver,resourceTitle,resourceDescription} from '../marketing/internal-links-20260916/navigation.mjs';

const [manifestPath]=process.argv.slice(2);
const m=JSON.parse(await readFile(manifestPath,'utf8'));
const inventory=await files(m.output);
const read=(root,f)=>readFile(path.join(root,f),'utf8');
const hash=s=>createHash('sha256').update(s).digest('hex');
const resolve=createLinkResolver(m.publicPaths);
const norm=s=>s.replace(/\s+/g,' ').trim();
const unversion=s=>{for(const [a,b]of m.modules)s=s.replaceAll(b,a);return s;};
let checks=0;
let marketingHeaders=0;
function equal(a,b,message){assert.deepEqual(a,b,message);checks++;}
function ok(a,message){assert(a,message);checks++;}
for(const [f,digest]of Object.entries(m.sourceHashes)){
  equal(hash(await readFile(path.join(m.source,f))),digest,`Baseline immutable: ${f}`);
  if(!f.endsWith('.html')&&!['sitemap.xml','_redirects'].includes(f))equal(await readFile(path.join(m.output,f)),await readFile(path.join(m.source,f)),`Existing asset and hosting policy unchanged: ${f}`);
}
const beforeSitemap=[...(await read(m.source,'sitemap.xml')).matchAll(/<loc>(.*?)<\/loc>/g)].map(x=>x[1]);
const afterSitemap=[...(await read(m.output,'sitemap.xml')).matchAll(/<loc>(.*?)<\/loc>/g)].map(x=>x[1]);
equal(afterSitemap,[...beforeSitemap,'https://spacemusic.io/blog/'],'140 existing URLs retained in order; Resources added');
equal(new Set(afterSitemap).size,141,'No duplicate sitemap URLs');
equal(inventory.filter(f=>f.endsWith('.html')).sort(),[...Object.keys(m.sourceHashes).filter(f=>f.endsWith('.html')),'blog/index.html'].sort(),'Only Resources is a new HTML route');
for(const f of Object.keys(m.sourceHashes).filter(f=>f.endsWith('.html'))){
  const bd=new JSDOM(await read(m.source,f)),ad=new JSDOM(await read(m.output,f));
  const before=bd.window.document,after=ad.window.document;
  equal(after.title,before.title,`Search title: ${f}`);
  for(const sel of ['h1','h2','meta','link[rel="canonical"]','script[type="application/ld+json"]','form'])equal([...after.querySelectorAll(sel)].map(n=>n.outerHTML),[...before.querySelectorAll(sel)].map(n=>n.outerHTML),`Preserve ${sel}: ${f}`);
  equal([...after.querySelectorAll('p')].map(n=>norm(n.textContent)),[...before.querySelectorAll('p')].map(n=>norm(n.textContent)),`Preserve every paragraph: ${f}`);
  const html=after.documentElement.outerHTML;
  for(const n of before.querySelectorAll('main a[href]')){
    const href=n.getAttribute('href');
    const expected=n.textContent.trim()==='Back to all articles'?'/blog/#articles':resolve(href);
    ok([...after.querySelectorAll('main a[href]')].some(a=>a.getAttribute('href')===expected&&norm(a.textContent)===norm(n.textContent)),`Content link retained with resolved destination: ${f} ${href}`);
  }
  for(const n of after.querySelectorAll('script:not([type="application/ld+json"])')){
    const restored=unversion(n.outerHTML).replace('const f=new Set(["/blog/",','const f=new Set([');
    ok([...before.querySelectorAll('script:not([type="application/ld+json"])')].some(b=>b.outerHTML===restored),`Existing scripts only, aside from versioned imports and public path allowlist: ${f}`);
  }
  const mobile=after.getElementById('space-mobile-menu');
  if(!['apply/index.html','data/conversion-intelligence/index.html','data/space-market-index/index.html'].includes(f))ok(mobile,`Every public marketing page has shared server navigation: ${f}`);
  if(mobile){
    marketingHeaders++;
    const nav=mobile.closest('nav');
    equal([...nav.querySelector('.hidden.md\\:flex').querySelectorAll('a')].map(a=>[a.getAttribute('href'),a.textContent]),[...primary.map(i=>[i.to,i.label]),['/apply/','Request a free catalog review']],`Primary links: ${f}`);
    equal([...mobile.querySelectorAll('a')].map(a=>a.getAttribute('href')),[...primary.map(i=>i.to),'/apply/'],`Mobile menu: ${f}`);
    ok(nav.classList.contains('space-site-nav'),`Tablet navigation scope: ${f}`);
  }
  const foot=after.querySelector('footer');
  if(foot)for(const [label,items]of [['Explore',explore],['Learn',learn]])equal([...foot.querySelector(`nav[aria-label="${label}"]`).querySelectorAll('a')].map(a=>[a.getAttribute('href'),a.textContent]),items.map(i=>[i.to,i.label]),`Footer ${label}: ${f}`);
  ok(!html.includes('href="#"'),'No placeholder anchors');
  bd.window.close();ad.window.close();
}
equal(marketingHeaders,135,'Complete existing marketing-header coverage, not a conditional sample');
const cases=[
 ['/sell','/sell/'],['https://www.spacemusic.io/calculator?utm_source=test#example','/calculator/?utm_source=test#example'],
 ['/guides/music-catalog-tax-guide?x=1','/guides/how-to-sell-music-rights/?x=1#tax-implications'],
 ['/streaming-rates/spotify/','/streaming-rates/spotify-2026/'],
 ['/blog?tag=rights','/guides/music-rights-101/'],['/?category=Streaming','/streaming-rates/'],
 ['#section','#section'],['https://example.com/sell','https://example.com/sell'],
 ['https://analyzer.spacemusic.io/','https://analyzer.spacemusic.io/'],['mailto:hello@spacemusic.io','mailto:hello@spacemusic.io'],
 ['/not-a-real-page','/not-a-real-page'],['/pricing.md','/pricing.md'],['/apply','/apply/'],
 ['//example.com/sell','//example.com/sell'],[undefined,undefined]
];
for(const [value,expected]of cases)equal(resolve(value),expected,`Resolver: ${value}`);
const linkCode=await read(m.output,'assets/'+m.newModules.find(n=>n.startsWith('InternalLinks-')));
const fakeJsx={jsx:(component,props)=>({component,props})};
const wrapper=linkCode.replace(/^import[^\n]+\n/,'').replaceAll('export const ','const ');
const context={URL,React:{forwardRef:f=>f},e:fakeJsx,RouterLink:'router'};
vm.createContext(context);
vm.runInContext(wrapper+';globalThis.testLink=Link;globalThis.resolve=resolveLink;',context);
for(const [value,expected]of cases)equal(context.resolve(value),expected,`Client resolver: ${value}`);
for(const to of ['/apply','/llms.txt','/pricing.md','/guides/music-catalog-tax-guide','#section'])equal(context.testLink({to},null).props.reloadDocument,true,`Native destination: ${to}`);
equal(context.testLink({to:'/sell'},null).props.reloadDocument,false,'Standard links retain SPA navigation');
equal(context.testLink({to:{pathname:'/calculator',search:'?a=1',hash:'#example'}},null).props.to.pathname,'/calculator/','Object route normalized');
const redirects=await read(m.output,'_redirects');
ok(redirects.startsWith((await read(m.source,'_redirects')).trimEnd()),'Existing redirects preserved');
for(const [from,to]of Object.entries(aliases))for(const suffix of ['','/'])ok(redirects.includes(`${from}${suffix} ${to} 301`),`Historical alias: ${from}${suffix}`);
const library=new JSDOM(await read(m.output,'blog/index.html')).window.document;
equal(library.querySelector('h1').textContent,resourceTitle,'Directory heading');
equal(library.querySelector('meta[name="description"]').content,resourceDescription,'Directory description');
equal(library.querySelector('link[rel="canonical"]').href,'https://spacemusic.io/blog/','Directory canonical');
equal(library.querySelector('meta[property="og:type"]').content,'website','Directory SSR/client Open Graph type');
equal([...library.querySelectorAll('script[type="application/ld+json"]')].map((n)=>[n.id,n.getAttribute('data-rh')]),[['seo-schema-0','true'],['seo-schema-1','true']],'Directory schemas managed by Helmet without duplicates or navigation leaks');
ok(library.querySelector('.space-site-nav a[href="/blog/"]'),'Resources also has shared SSR navigation');
const resourceCode=await read(m.output,'assets/'+m.newModules.find(n=>n.startsWith('Resources-')));
ok(resourceCode.includes('schema:')&&!resourceCode.includes('structuredData:'),'SEOHead schema API used');
const embedded=literals(resourceCode).find(n=>n.value.startsWith('<header class="space-library-intro"'));
equal(new JSDOM(embedded.value).window.document.body.innerHTML,library.querySelector('main').innerHTML,'Resources SSR/client content identical');
const pillarModule=m.modules.find(([name])=>name.startsWith('PillarGuidePage-'))[1];
const pillarCode=await read(m.output,'assets/'+pillarModule);
const pillarRecord=parse(pillarCode,{sourceType:'module'}).program.body.flatMap(n=>n.declarations||[]).find(n=>n.id.name==='k').init;
const pillar=vm.runInNewContext('('+pillarCode.slice(pillarRecord.start,pillarRecord.end)+')',{}, {timeout:1000});
const guide=new JSDOM(await read(m.output,'guides/how-to-sell-music-rights/index.html')).window.document;
const relatedHeading=[...guide.querySelectorAll('h3')].find(n=>n.textContent==='Spoke pages');
equal([...relatedHeading.nextElementSibling.querySelectorAll('a')].map(a=>[a.textContent,a.getAttribute('href')]),JSON.parse(JSON.stringify(pillar.spokeLinks.map(s=>[s.title,resolve(s.url)]))),'Complete related-spoke server/client destinations and labels');
const visited=new Set();
async function visit(name){
  if(visited.has(name))return;visited.add(name);
  const code=await read(m.output,'assets/'+name);parse(code,{sourceType:'module'});
  for(const n of literals(code))if(/^(\.\/|assets\/).+\.js$/.test(n.value)){const dep=path.basename(n.value);ok(inventory.includes('assets/'+dep),`Dependency: ${dep}`);await visit(dep);}
}
await visit(m.entry);
await build({entryPoints:[path.join(m.output,'assets',m.entry)],bundle:true,format:'esm',platform:'browser',write:false,logLevel:'silent'});
checks++;
const audit=await auditLinks(m.output);
equal(audit.issues,[],'Every static internal link and fragment resolves, no placeholders');
equal(audit.summary.unreachable.sort(),[...operational].sort(),'Only two preserved operational dashboards are excluded from public navigation');
ok(audit.summary.maxDepth<=3,'Public pages at most three links from home');
await writeFile(manifestPath.replace('manifest','test-results'),JSON.stringify({status:'PASS',checks,activeModules:visited.size,summary:audit.summary,production:'unchanged; preview only'},null,2)+'\n');
console.log(JSON.stringify({status:'PASS',checks,activeModules:visited.size,summary:audit.summary},null,2));

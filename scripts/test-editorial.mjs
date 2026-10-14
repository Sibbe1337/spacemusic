import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {build} from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {auditLinks} from './audit-internal-links.mjs';
import {literals} from './journey-support.mjs';

const [manifestPath='marketing/editorial-20260916/manifest-v5.json']=process.argv.slice(2);
const m=JSON.parse(await readFile(manifestPath,'utf8')),hash=s=>createHash('sha256').update(s).digest('hex');
let checks=0,articles=0,legacy=0;
const eq=(a,b,label)=>{assert.deepEqual(a,b,label);checks++;};
const norm=s=>s.replace(/\s+/g,' ').trim();
const unversion=s=>{for(const[a,b]of m.modules)s=s.replaceAll(b,a);return s;};
for(const f of await files(m.source)){
  const before=await readFile(path.join(m.source,f)),after=await readFile(path.join(m.output,f));
  eq(hash(before),m.sourceHashes[f],`immutable ${f}`);
  if(!f.endsWith('.html')){eq(hash(before),hash(after),`preserve existing asset/hosting file ${f}`);continue;}
  const aDOM=new JSDOM(before.toString()),bDOM=new JSDOM(unversion(after.toString())),a=aDOM.window.document,b=bDOM.window.document;
  const style=b.querySelector(`link[href="/assets/${m.cssName}"]`);assert(style);style.remove();checks++;
  eq(b.head.outerHTML,a.head.outerHTML,`metadata/scripts/styles preserved ${f}`);
  if(!f.startsWith('blog/'))eq(b.documentElement.outerHTML,a.documentElement.outerHTML,`non-blog page preserved ${f}`);
  else{
    const am=a.querySelector('main'),bm=b.querySelector('main');
    eq(b.querySelector('.space-site-nav')?.outerHTML,a.querySelector('.space-site-nav')?.outerHTML,`shared header untouched ${f}`);
    eq(b.querySelector('footer')?.outerHTML,a.querySelector('footer')?.outerHTML,`footer untouched ${f}`);
    eq(bm.querySelector('h1').textContent,am.querySelector('h1').textContent,`H1 ${f}`);
    eq([...bm.querySelectorAll('h2')].map(n=>n.textContent),[...am.querySelectorAll('h2')].map(n=>n.textContent),`H2 ${f}`);
    const afterParagraphs=[...bm.querySelectorAll('p')].map(n=>norm(n.textContent));
    for(const p of am.querySelectorAll('p'))if(p.textContent!=='In this article')assert(afterParagraphs.includes(norm(p.textContent)),`paragraph retained ${f}: ${p.textContent.slice(0,60)}`);checks++;
    const afterLinks=[...bm.querySelectorAll('a[href]')].map(n=>[n.getAttribute('href'),norm(n.textContent),n.getAttribute('aria-label')]);
    for(const link of am.querySelectorAll('a[href]')){
      if(!norm(link.textContent)&&link.querySelector('img'))continue;
      assert(afterLinks.some(x=>JSON.stringify(x)===JSON.stringify([link.getAttribute('href'),norm(link.textContent),link.getAttribute('aria-label')])),`link retained ${f}: ${link.outerHTML}`);checks++;
    }
    eq(bm.querySelectorAll('img').length,0,`no stock images ${f}`);
    eq([...bm.querySelectorAll('[id]')].map(n=>n.id).sort(),[...am.querySelectorAll('[id]')].map(n=>n.id).sort(),`fragment IDs ${f}`);
    if(f!=='blog/index.html'){
      articles++;
      const selector=am.classList.contains('space-blog-article')?'.space-blog-content':'.editorial-prose>div';
      const originals=am.querySelectorAll(selector==='.editorial-prose>div'?'.prose>div':selector);
      const bodies=[...bm.querySelectorAll(selector)].map(n=>{
        for(const table of n.querySelectorAll('.space-blog-table')){
          eq(table.getAttribute('tabindex'),'0',`keyboard table ${f}`);
          eq(table.getAttribute('role'),'region',`table region ${f}`);
          assert(table.getAttribute('aria-label'),`table label ${f}`);checks++;
        }
        return n.innerHTML;
      });
      eq(bodies,[...originals].map(n=>n.innerHTML),`exact article body preserved ${f}`);
      const toc=bm.querySelector('details.space-blog-toc, .editorial-toc details');assert(toc?.open&&toc.querySelector('summary'),'Native accessible TOC');checks++;
      if(!am.classList.contains('space-blog-article')){
        legacy++;
        eq(bm.querySelector('.editorial-note').textContent,m.notes.note,`unverified author note ${f}`);
        eq(bm.querySelectorAll('form').length,0,`no inert submission ${f}`);
        assert(bm.querySelector('fieldset[disabled]'));checks++;
        assert(bm.querySelector('.editorial-author summary').textContent.includes('unverified'));checks++;
      }
    }
  }
  aDOM.window.close();bDOM.window.close();
}
eq(articles,14,'14 articles');eq(legacy,6,'6 legacy articles');
for(const[from,to]of m.modules){
  const a=await readFile(path.join(m.source,'assets',from),'utf8'),b=await readFile(path.join(m.output,'assets',to),'utf8');parse(b,{sourceType:'module'});checks++;
  // Authored article datasets (including dates, sources and schema) are unchanged.
  if(a.includes('const article = '))eq(b.match(/^const article = (.+);$/m)?.[1],a.match(/^const article = (.+);$/m)?.[1],`authored payload ${to}`);
}
const resources=m.modules.find(([a])=>a.startsWith('Resources-'))[1];
const resourceCode=await readFile(path.join(m.output,'assets',resources),'utf8');
const resourceHTML=literals(resourceCode).find(n=>n.value.startsWith('<header class="space-library-intro"')).value;
eq(new JSDOM(resourceHTML).window.document.body.innerHTML,new JSDOM(await readFile(path.join(m.output,'blog/index.html'),'utf8')).window.document.querySelector('main').innerHTML,'Resources SSR/runtime parity');
await build({entryPoints:[path.join(m.output,'assets',m.entry)],bundle:true,write:false,format:'esm',logLevel:'silent'});checks++;
const audit=await auditLinks(m.output);eq(audit.issues,[],'Internal graph clean');eq(audit.summary.sitemap,141,'Sitemap retained');
eq(audit.summary.unreachable.sort(),['/data/conversion-intelligence/','/data/space-market-index/'],'unchanged operational exceptions');
const result={status:'PASS',checks,articles,legacy,removedImages:m.removedImages,links:audit.summary};
await writeFile(path.join(path.dirname(manifestPath),'test-results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));

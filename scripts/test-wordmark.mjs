import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {build} from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import {files} from './funnel-support.mjs';
import {auditLinks} from './audit-internal-links.mjs';

const [manifestPath='marketing/identity-20260916/manifest-v1.json']=process.argv.slice(2);
const m=JSON.parse(await readFile(manifestPath,'utf8'));
const hash=x=>createHash('sha256').update(x).digest('hex');
let checks=0,htmlPages=0,brands=0;
function equal(a,b,label){assert.deepEqual(a,b,label);checks++;}
const sourceFiles=await files(m.source),outputFiles=await files(m.output);
function undoVersions(text){for(const [from,to] of m.modules)text=text.replaceAll(to,from);return text;}
function brandAnchors(d){return [...d.querySelectorAll('.space-site-nav a[aria-label][href="/"],footer a[href="/"],.masthead a.wordmark[href="/"]')].filter(a=>a.textContent.trim()==='SPACE');}
for(const f of sourceFiles){
  const before=await readFile(path.join(m.source,f));
  equal(hash(before),m.sourceHashes[f],`immutable source ${f}`);
  const after=await readFile(path.join(m.output,f));
  if(!f.endsWith('.html')){equal(hash(after),hash(before),`retained ${f}`);continue;}
  htmlPages++;
  const oldDom=new JSDOM(before.toString()),newDom=new JSDOM(undoVersions(after.toString()));
  const old=oldDom.window.document,next=newDom.window.document;
  const a=brandAnchors(old),b=brandAnchors(next);
  equal(b.length,a.length,`brand count ${f}`);
  for(let i=0;i<a.length;i++){
    brands++;
    equal(b[i].getAttribute('href'),a[i].getAttribute('href'),`home link ${f}`);
    equal(b[i].getAttribute('aria-label'),a[i].getAttribute('aria-label'),`accessible name ${f}`);
    equal(b[i].querySelector('svg')?.getAttribute('aria-hidden'),'true',`decorative mark ${f}`);
    equal([...b[i].querySelectorAll('path')].map(p=>p.getAttribute('d')),m.paths.map(p=>p.d),`vector ${f}`);
    equal(b[i].querySelectorAll('rect').length,0,`old pixel icon removed ${f}`);
    equal(b[i].querySelector('.space-wordmark-text')?.textContent,'SPACE',`fallback brand text ${f}`);
    b[i].replaceWith(next.importNode(a[i],true));
  }
  const styles=[...next.querySelectorAll(`link[href="/assets/${m.cssName}"]`)];
  equal(styles.length,1,`single stylesheet ${f}`);styles[0].remove();
  // Reverse only the declared branding edits; everything else must match exactly.
  equal(next.documentElement.outerHTML,old.documentElement.outerHTML,`all non-brand DOM preserved ${f}`);
  oldDom.window.close();newDom.window.close();
}
equal(brands,275,'136 headers + 138 footers + standalone Apply');
equal(htmlPages,139,'all HTML pages');
await build({entryPoints:[path.join(m.output,'assets',m.entry)],bundle:true,write:false,format:'esm',logLevel:'silent'});checks++;
const audit=await auditLinks(m.output);
equal(audit.issues,[],'no broken/placeholder/noncanonical/fragment links');
equal(audit.summary.internalLinks,6660,'same internal-link graph');
equal(audit.summary.sitemap,141,'all sitemap URLs');
equal(audit.summary.unreachable.sort(),['/data/conversion-intelligence/','/data/space-market-index/'],'unchanged operational exceptions');
const result={checks,htmlPages,brands,publicFiles:outputFiles.filter(f=>!['_headers','_redirects'].includes(f)).length,links:audit.summary,status:'PASS'};
await writeFile('marketing/identity-20260916/test-results.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));

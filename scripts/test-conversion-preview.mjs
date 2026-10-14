import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {build} from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {auditLinks} from './audit-internal-links.mjs';
import {calculatorChoice, calculatorNext} from '../marketing/conversion-20260917/content.mjs';

const [manifestPath, ...extra] = process.argv.slice(2);
assert(manifestPath && !extra.length, 'Usage: node scripts/test-conversion-preview.mjs MANIFEST');
const m = JSON.parse(await readFile(manifestPath, 'utf8'));
const hash = x => createHash('sha256').update(x).digest('hex');
const read = (root, f) => readFile(path.join(root, f), 'utf8');
let checks = 0, htmlPages = 0;
const equal = (a,b,label) => {assert.deepEqual(a,b,label); checks++;};
const undo = html => {for (const [old,next] of m.modules) html = html.replaceAll(next,old); return html;};
function textCounts(d) {
  const counts = new Map(), walker = d.createTreeWalker(d.body, 4);
  while (walker.nextNode()) {
    if (walker.currentNode.parentElement?.closest('script,style')) continue;
    const text = walker.currentNode.textContent.replace(/\s+/g,' ').trim();
    if (text) counts.set(text, (counts.get(text)||0)+1);
  }
  return counts;
}
function linkCounts(d) {
  const counts = new Map();
  for (const a of d.querySelectorAll('a[href]')) {
    const key = JSON.stringify([a.getAttribute('href'), a.textContent.trim(), a.getAttribute('aria-label')]);
    counts.set(key, (counts.get(key)||0)+1);
  }
  return counts;
}
for (const f of await files(m.source)) {
  const before = await readFile(path.join(m.source,f));
  const after = await readFile(path.join(m.output,f));
  equal(hash(before), m.sourceHashes[f], `source immutable: ${f}`);
  if (!f.endsWith('.html') || f.startsWith('apply/')) {
    equal(hash(after), hash(before), `retained file: ${f}`);
    if (f.endsWith('.html')) htmlPages++;
    continue;
  }
  htmlPages++;
  const oldDom = new JSDOM(before.toString()), nextDom = new JSDOM(undo(after.toString()));
  const old = oldDom.window.document, next = nextDom.window.document;
  const styles = next.querySelectorAll(`link[href="/assets/${m.cssName}"]`);
  equal(styles.length,1, `one scoped stylesheet: ${f}`); styles[0].remove();
  equal(next.head.outerHTML,old.head.outerHTML,`all SEO metadata and tracking preserved: ${f}`);
  equal([...next.querySelectorAll('h1')].map(n=>n.textContent), [...old.querySelectorAll('h1')].map(n=>n.textContent), `H1 preserved: ${f}`);
  if (!m.pages.includes(f)) equal(next.documentElement.outerHTML,old.documentElement.outerHTML,`non-target page unchanged: ${f}`);
  else {
    for (const [text,count] of textCounts(old)) equal((textCounts(next).get(text)||0)>=count,true,`retained copy ${f}: ${text.slice(0,80)}`);
    for (const [link,count] of linkCounts(old)) equal((linkCounts(next).get(link)||0)>=count,true,`retained link ${f}: ${link}`);
    const ids = [...next.querySelectorAll('[id]')].map(n=>n.id);
    equal(new Set(ids).size,ids.length,`unique IDs: ${f}`);
  }
  oldDom.window.close(); nextDom.window.close();
}
equal(htmlPages,139,'all HTML retained');
equal(await read(m.output,'sitemap.xml'), await read(m.source,'sitemap.xml'),'141 URLs and lastmods byte-preserved');
for (const [old, next] of m.modules) {
  const before = await read(m.source,'assets/'+old), after = undo(await read(m.output,'assets/'+next));
  if (!/^(Index-og-|GenreIndex-|Calculator-)/.test(old)) equal(after,before,`dependency-only change: ${old}`);
  if (/^(Index-og-|GenreIndex-)/.test(old)) {
    const file = old.startsWith('Index-og-') ? 'index.html' : 'sell/index.html';
    const a = new JSDOM(await read(m.source,file)), b = new JSDOM(await read(m.output,file));
    const oldHTML = a.window.document.querySelector('main').innerHTML;
    const newHTML = b.window.document.querySelector('main').innerHTML;
    const newLiteral = literals(after).filter(n=>n.value===newHTML);
    const oldLiteral = literals(before).filter(n=>n.value===oldHTML);
    equal(newLiteral.length,1,`server/client parity ${file}`); equal(oldLiteral.length,1,`old parity ${file}`);
    equal(after.slice(0,newLiteral[0].start),before.slice(0,oldLiteral[0].start),`only main content changed: ${file}`);
    equal(after.slice(newLiteral[0].end),before.slice(oldLiteral[0].end),`component unchanged: ${file}`);
    a.window.close();b.window.close();
  }
  if (old.startsWith('Calculator-')) {
    const a = parse(before,{sourceType:'module'}), b = parse(after,{sourceType:'module'});
    const oldFunctions = a.program.body.filter(n=>n.type==='FunctionDeclaration');
    const newFunctions = b.program.body.filter(n=>n.type==='FunctionDeclaration');
    equal(newFunctions.map(n=>n.id.name),oldFunctions.map(n=>n.id.name),'calculator functions preserved');
    for (const fn of oldFunctions) {
      const nextFn = newFunctions.find(n=>n.id.name===fn.id.name);
      if (!before.slice(fn.start,fn.end).includes('Hypothetical sale scenario')) equal(after.slice(nextFn.start,nextFn.end),before.slice(fn.start,fn.end),'compiled math helper unchanged: '+fn.id.name);
      else {
        const oldSetup=fn.body.body.filter(n=>n.type!=='ReturnStatement').map(n=>before.slice(n.start,n.end));
        const newSetup=nextFn.body.body.filter(n=>n.type!=='ReturnStatement').map(n=>after.slice(n.start,n.end));
        equal(newSetup,oldSetup,'calculator state, inputs and analytics unchanged');
      }
    }
    equal(literals(after).filter(n=>n.value===calculatorChoice).length,1,'client chooser matches server copy');
    equal(literals(after).filter(n=>n.value===calculatorNext).length,1,'client next steps match server copy');
  }
}
const calc = new JSDOM(await read(m.output,'calculator/index.html')).window.document;
equal(calc.querySelector('aside').querySelectorAll('.conversion-method-content').length,0,'explanation removed only from sidebar');
equal(calc.querySelectorAll('.conversion-method-content').length,1,'full explanation retained once');
const normalizeHTML = html => {const dom = new JSDOM(html); const result = dom.window.document.body.innerHTML; dom.window.close(); return result;};
equal(calc.querySelector('.conversion-choice').innerHTML,normalizeHTML(calculatorChoice),'static chooser copy');
equal(calc.querySelector('.conversion-next').innerHTML,normalizeHTML(calculatorNext),'static next-step copy');
equal(calc.querySelectorAll('noscript').length>0,true,'no-JS explanation retained');
const css = await read(m.output,'assets/'+m.cssName);
const gzipBytes = gzipSync(css).length;
equal(gzipBytes<3500,true,'small scoped CSS budget');
equal(/@import|url\(/.test(css),false,'no new font/image/network dependencies');
await build({entryPoints:[path.join(m.output,'assets',m.entry)],bundle:true,write:false,format:'esm',logLevel:'silent'}); checks++;
const audit = await auditLinks(m.output);
equal(audit.issues,[],'no broken, noncanonical, placeholder or fragment links');
equal(audit.summary.sitemap,141,'all sitemap URLs retained');
equal(audit.summary.unreachable.sort(),['/data/conversion-intelligence/','/data/space-market-index/'],'no new orphan routes');
const result = {status:'PASS',checks,htmlPages,cssGzipBytes:gzipBytes,links:audit.summary,scope:m.pages,production:'unchanged'};
await writeFile(path.join(path.dirname(manifestPath),'test-results.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));

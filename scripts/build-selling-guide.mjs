import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {guide} from '../marketing/selling-guide-20260916/content.mjs';

const [source, output, manifestPath] = process.argv.slice(2);
assert(source && output && manifestPath, 'Usage: VERIFIED_SOURCE FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Separate output required');
const {marked} = await import(process.env.MARKED_MODULE);
const hash = s => createHash('sha256').update(s).digest('hex');
const inventory = await files(source);
const codes = new Map();
for (const f of inventory.filter(f => /^assets\/.*\.js$/.test(f))) codes.set(path.basename(f), await readFile(path.join(source, f), 'utf8'));
const home = await readFile(path.join(source, 'index.html'), 'utf8');
const entry = home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry, 'index-article-360c41838159-quietseo-fd17485db4c3-intent-50f4feb4050e.js', 'Use the verified 02276b90 production release');
const dependencies = name => literals(codes.get(name)).map(n => path.basename(n.value)).filter(n => codes.has(n));
const reachable = new Set();
function visit(name) { if (reachable.has(name)) return; reachable.add(name); dependencies(name).forEach(visit); }
visit(entry);
const names = [...reachable].filter(n => n.startsWith('PillarGuidePage-'));
assert.equal(names.length, 1);
const name = names[0];
let code = codes.get(name);
const declarations = parse(code, {sourceType:'module'}).program.body.flatMap(n => n.declarations || []);
const node = declarations.find(n => n.id.name === 'k').init;
const old = JSON.parse(JSON.stringify(vm.runInNewContext('(' + code.slice(node.start, node.end) + ')', {}, {timeout:1000})));
assert.equal(old.slug, 'how-to-sell-music-rights');
assert.deepEqual(Object.keys(guide.sections), old.sections.map(s => s.id));
assert.equal(guide.answers.length, old.faq.length);
const route = '/guides/how-to-sell-music-rights/';
const htmlFile = route.slice(1) + 'index.html';
const escape = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
function sectionHtml(markdown) {
  const d = new JSDOM(marked.parse(markdown)).window.document;
  for (const p of d.querySelectorAll('p')) p.className = 'mb-6';
  for (const list of d.querySelectorAll('ul,ol')) list.className = `mb-6 list-inside ${list.tagName === 'OL' ? 'list-decimal' : 'list-disc'}`;
  for (const li of d.querySelectorAll('li')) li.className = 'mb-3';
  for (const a of d.querySelectorAll('a')) a.className = 'underline underline-offset-2';
  return d.body.innerHTML;
}
const next = {...old, metaDescription:guide.metaDescription, tldr:guide.tldr, introduction:guide.introduction,
  reviewedDate:'2026-09-16', citations:guide.citations,
  sections:old.sections.map(s => ({...s, content:guide.sections[s.id], contentHtml:sectionHtml(guide.sections[s.id])})),
  faq:old.faq.map((f, i) => ({...f, answer:guide.answers[i]}))};
const linkChanges = {
  '/guides/partial-rights-explained':'/compare/partial-sale-vs-full-sale/',
  '/guides/music-catalog-tax-guide':route + '#tax-implications'
};
next.spokeLinks = old.spokeLinks.map(s => ({...s, url:linkChanges[s.url] || s.url}));
next.reviewedFaqHtml = next.faq.map(f => `<details class="border-b border-black/10"><summary class="cursor-pointer text-base font-medium py-5">${escape(f.question)}</summary><p class="text-muted-foreground pb-5 leading-relaxed">${escape(f.answer)}</p></details>`).join('');
code = code.slice(0, node.start) + JSON.stringify(next) + code.slice(node.end);
function replaceOnce(before, after) {
  assert.equal(code.split(before).length, 2, `Unique render guard: ${before.slice(0, 90)}`);
  code = code.replace(before, after);
}
const bodyClass = 'space-blog-content text-muted-foreground leading-relaxed max-w-3xl ml-9';
const paragraph = 'e.jsx("p",{className:"text-muted-foreground leading-relaxed whitespace-pre-line max-w-3xl ml-9",children:t.content})';
replaceOnce(paragraph, `t.contentHtml?e.jsx("div",{className:${JSON.stringify(bodyClass)},dangerouslySetInnerHTML:{__html:t.contentHtml}}):${paragraph}`);
const faq = 'e.jsx(f,{type:"single",collapsible:!0,className:"w-full",children:a.faq.map((t,i)=>e.jsxs(w,{value:`faq-${i}`,className:"border-b border-black/10",children:[e.jsx(b,{className:"text-base font-medium py-5 hover:no-underline text-left",children:t.question}),e.jsx(v,{className:"text-muted-foreground pb-5 leading-relaxed",children:t.answer})]},i))})';
replaceOnce(faq, `a.reviewedFaqHtml?e.jsx("div",{className:"space-reviewed-faq",dangerouslySetInnerHTML:{__html:a.reviewedFaqHtml}}):${faq}`);
replaceOnce('headline:a.title,description:a.metaDescription,', 'headline:a.title,description:a.metaDescription,...(a.reviewedDate?{dateModified:a.reviewedDate}:{}),');
replaceOnce('children:"Free valuation. No obligation."', 'children:a.reviewedDate?"Free initial review. No obligation to sell.":"Free valuation. No obligation."');
replaceOnce('to:t.url,className:', 'to:t.url,reloadDocument:!!a.reviewedDate&&t.url.includes("#"),className:');
replaceOnce('e.jsx(y,{title:"Related content",groups:c,trackTemplate:"pillar_guide"})', 'e.jsx(y,{title:"Related content",groups:c,trackTemplate:"pillar_guide",nativeHashLinks:!!a.reviewedDate})');
codes.set(name, code);
const changed = new Set([name]);
// Opt in only on the reviewed guide; native hash navigation needs no new JS.
const relatedName = [...reachable].find(n => n.startsWith('RelatedContent-'));
let relatedCode = codes.get(relatedName);
const relatedSignature = 'trackTemplate:r="unknown"})';
const relatedLink = 'to:s.to,onClick:';
assert.equal(relatedCode.split(relatedSignature).length, 2);
assert.equal(relatedCode.split(relatedLink).length, 2);
relatedCode = relatedCode.replace(relatedSignature, 'trackTemplate:r="unknown",nativeHashLinks:H=!1})').replace(relatedLink, 'to:s.to,reloadDocument:H&&s.to.includes("#"),onClick:');
codes.set(relatedName, relatedCode);
changed.add(relatedName);
let growing = true;
while (growing) {
  growing = false;
  for (const n of reachable) if (!changed.has(n) && dependencies(n).some(d => changed.has(d))) { changed.add(n); growing = true; }
}
const revision = hash([...changed].sort().map(n => n + codes.get(n)).join('\n')).slice(0, 12);
const mapping = new Map([...changed].map(n => [n, n.replace(/\.js$/, `-selling-${revision}.js`)]));
await mkdir(output);
await cp(source, output, {recursive:true});
for (const n of changed) {
  let text = codes.get(n);
  for (const [a, b] of mapping) text = text.replaceAll(a, b);
  parse(text, {sourceType:'module'});
  await writeFile(path.join(output, 'assets', mapping.get(n)), text);
}
for (const f of inventory.filter(f => f.endsWith('.html'))) {
  let text = await readFile(path.join(source, f), 'utf8');
  if (f === htmlFile) {
    const dom = new JSDOM(text), d = dom.window.document;
    const replaceText = (before, after) => {
      const matches = [...d.querySelectorAll('p')].filter(n => n.textContent === before);
      assert.equal(matches.length, 1, `SSR text: ${before.slice(0, 60)}`);
      matches[0].textContent = after;
    };
    replaceText(old.tldr, next.tldr);
    replaceText(old.introduction, next.introduction);
    replaceText(old.metaDescription, next.metaDescription);
    replaceText('Free valuation. No obligation.', 'Free initial review. No obligation to sell.');
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) d.querySelector(selector).content = next.metaDescription;
    for (const section of next.sections) {
      const container = d.getElementById(section.id);
      assert(container && container.querySelector('h2').textContent === section.heading);
      const before = container.querySelector('p');
      assert(before);
      const after = d.createElement('div');
      after.className = bodyClass;
      after.innerHTML = section.contentHtml;
      before.replaceWith(after);
    }
    const faqLabel = [...d.querySelectorAll('main > section p')].find(n => n.textContent === 'FAQ');
    assert(faqLabel && faqLabel.nextElementSibling);
    const faqDiv = d.createElement('div');
    faqDiv.className = 'space-reviewed-faq';
    faqDiv.innerHTML = next.reviewedFaqHtml;
    faqLabel.nextElementSibling.replaceWith(faqDiv);
    const sourcesLabel = [...d.querySelectorAll('main > section p')].find(n => n.textContent === 'Sources');
    assert.equal(sourcesLabel.nextElementSibling.tagName, 'OL');
    sourcesLabel.nextElementSibling.innerHTML = next.citations.map(c => `<li class="text-sm text-muted-foreground"><a href="${escape(c.url)}" target="_blank" rel="noopener noreferrer" class="hover:underline underline-offset-2">${escape(c.source)}</a></li>`).join('');
    for (const a of d.querySelectorAll('a[href]')) {
      const key = a.getAttribute('href').replace(/\/$/, '');
      if (linkChanges[key]) a.setAttribute('href', linkChanges[key]);
    }
    const relatedHeading = [...d.querySelectorAll('h3')].find(n => n.textContent === 'Spoke pages');
    assert(relatedHeading);
    const linkList = relatedHeading.nextElementSibling;
    const linkTemplate = linkList.querySelector('a');
    // The old client filter excluded the two nonexistent routes from this SSR list.
    for (const item of next.spokeLinks) {
      if ([...linkList.querySelectorAll('a')].some(a => a.textContent === item.title)) continue;
      const a = linkTemplate.cloneNode(false);
      a.textContent = item.title;
      a.setAttribute('href', item.url);
      linkList.append(a);
    }
    for (const script of d.querySelectorAll('script[type="application/ld+json"]')) {
      const schema = JSON.parse(script.textContent);
      if (schema['@type'] === 'Article') { schema.description = next.metaDescription; schema.dateModified = next.reviewedDate; }
      if (schema['@type'] === 'FAQPage') schema.mainEntity = next.faq.map(f => ({'@type':'Question', name:f.question, acceptedAnswer:{'@type':'Answer', text:f.answer}}));
      script.textContent = JSON.stringify(schema);
    }
    text = dom.serialize();
  }
  for (const [a, b] of mapping) text = text.replaceAll(a, b);
  await writeFile(path.join(output, f), text);
}
const sourceHashes = {};
for (const f of inventory) sourceHashes[f] = hash(await readFile(path.join(source, f)));
const manifest = {source, output, revision, route, htmlFile, old, next, linkChanges, entry:mapping.get(entry), modules:[...mapping], sourceHashes, status:'PREVIEW ONLY; production unchanged'};
await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
console.log(JSON.stringify({output, revision, modules:changed.size, copyPages:[htmlFile], sitemapUrls:140}, null, 2));

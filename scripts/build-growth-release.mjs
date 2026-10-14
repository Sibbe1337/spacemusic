import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { transform } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { files } from './funnel-support.mjs';
import { literals, replaceLiterals } from './journey-support.mjs';
import { positioning, replacements } from '../marketing/growth-20260916/copy.mjs';
import { layoutSellPage } from '../marketing/growth-20260916/sell-layout.mjs';

function applyPageCopy(d, pairs) {
  const walker = d.createTreeWalker(d,4);
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (n.parentElement?.tagName === 'SCRIPT') {
      if (n.parentElement.type === 'application/ld+json') {
        const json = JSON.parse(n.textContent);
        n.textContent = JSON.stringify(json, (key,value) => pairs.find(([a]) => a === value)?.[1] ?? value);
      }
    } else for (const [a,b] of pairs) if (n.textContent === a) n.textContent = b;
  }
  for (const meta of d.querySelectorAll('meta[content]')) for (const [a,b] of pairs) if (meta.content === a) meta.content = b;
}

const [source, output, manifestFile] = process.argv.slice(2);
assert(source && output && manifestFile, 'Usage: BASELINE FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Output must be separate from baseline');
const hash = value => createHash('sha256').update(value).digest('hex');
const inventory = await files(source);
const originalHTML = await readFile(path.join(source, 'index.html'), 'utf8');
const entry = originalHTML.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry, 'index-typeform-45ce7e3ed34b.js', 'Start from verified Typeform release, not a design preview');
assert.equal(inventory.length, 340);
const sitemap = await readFile(path.join(source, 'sitemap.xml'), 'utf8');
assert.equal([...sitemap.matchAll(/<loc>/g)].length, 139);
const codes = new Map();
for (const file of inventory.filter(file => /^assets\/.*\.js$/.test(file))) codes.set(path.basename(file), await readFile(path.join(source, file), 'utf8'));
const dependencies = name => literals(codes.get(name)).map(n => path.basename(n.value)).filter(n => codes.has(n));
const reachable = new Set();
function visit(name) { if (reachable.has(name)) return; reachable.add(name); dependencies(name).forEach(visit); }
visit(entry);
function moduleFor(prefix) {
  const found = [...reachable].filter(n => n.startsWith(prefix));
  assert.equal(found.length, 1, prefix);
  return found[0];
}
const changed = new Set();
for (const [page, prefix] of [['about', 'AboutPage-'], ['brand-facts', 'BrandFacts-'], ['sell', 'GenreIndex-']]) {
  const name = moduleFor(prefix);
  codes.set(name, replaceLiterals(codes.get(name), replacements[page], true));
  if (page === 'about') codes.set(name, replaceLiterals(codes.get(name), [['Apply Now ', 'Request a free catalog review ']], true));
  changed.add(name);
}

const homeDOM = new JSDOM(originalHTML);
const doc = homeDOM.window.document;
const main = doc.querySelector('main');
main.id = 'space-growth-home';
main.tabIndex = -1;
const sections = [...main.querySelectorAll(':scope>section')];
assert.equal(sections.length, 9);
const schemaNodes = [...doc.querySelectorAll('script[type="application/ld+json"]')];
const schemas = schemaNodes.map(node => JSON.parse(node.textContent));
schemas.find(s => s['@type'] === 'Organization').description = positioning;
const faq = schemas.find(s => s['@type'] === 'FAQPage');
faq.mainEntity[0].acceptedAnswer.text = 'We consider revenue-generating catalogs across all genres, including hip-hop, R&B, pop, rock, ambient, meditation, lo-fi, focus, wellness, nature soundscapes, electronic, house, techno, trance and drum & bass. Artists, producers and labels can apply. Documented income and transferable rights require individual review; no genre guarantees an offer.';
faq.mainEntity[1].acceptedAnswer.text = 'Start with the guided catalog review on our Apply page. We review the information you submit and follow up privately for any additional evidence. An offer depends on catalog fit, documented income and rights. Payment requires a completed agreement and satisfied transfer conditions.';
schemas.forEach((s, i) => { schemaNodes[i].textContent = JSON.stringify(s); schemaNodes[i].id = `seo-schema-${i}`; });
sections[0].className = 'growth-hero';
sections[0].innerHTML = `<div class="growth-hero-layout">
  <div class="growth-hero-copy">
    <p class="growth-kicker">Direct music rights buyer / All genres considered</p>
    <h1 class="growth-title">Sell your music catalog.<span>On terms you understand.</span></h1>
    <p class="growth-intro">Your music has earned its place. Explore what comes next. SPACE buys revenue-generating catalogs directly from artists, producers and labels, across all genres.</p>
    <div class="growth-actions"><a href="/apply/" class="bg-brand text-white inline-flex">Request a free catalog review <span aria-hidden="true">&nbsp; &#8594;</span></a><a href="/calculator/" class="growth-secondary">Explore a scenario first &#8594;</a></div>
    <p class="growth-reassurance">Free initial review. No obligation to sell. No auction or listing. Every catalog is reviewed individually.</p>
  </div>
  <aside class="growth-review" aria-label="What a catalog review covers">
    <div class="growth-review-top"><span>Your catalog, your next chapter</span><span>SPACE</span></div>
    <h2>Sell part of your catalog.<br>Or explore a full sale.</h2>
    <p>Start with a free review. Define what you want to sell before deciding on an offer.</p>
    <dl><div><dt>Your music</dt><dd>Hip-hop, R&amp;B, pop, rock, electronic, ambient and beyond.</dd></div><div><dt>Your rights</dt><dd>Selected recordings or a defined share. Ownership and contract terms matter.</dd></div><div><dt>Your decision</dt><dd>Review any offer and agreement with an independent adviser. No obligation to accept.</dd></div></dl>
    <a href="/how-it-works/">What happens after you apply? &#8594;</a>
  </aside>
</div>`;
sections[1].classList.add('growth-facts');
const oldDirect = 'SPACE is a direct music-rights buyer for independent catalog owners. It buys revenue-generating catalogs in ambient, lo-fi, meditation, electronic, house, wellness, and soundscape genres without using an auction marketplace.';
function setExactText(root, before, after) {
  const walker = doc.createTreeWalker(root, 4);
  let found = 0;
  while (walker.nextNode()) if (walker.currentNode.textContent === before) { walker.currentNode.textContent = after; found++; }
  assert(found, `Missing homepage text: ${before}`);
}
setExactText(main, oldDirect, positioning + ' We do not use an auction marketplace.');
setExactText(main, 'Start with your email and artist or label name. We follow up by email to request the relevant streaming links, royalty statements and rights documents privately.', 'Start with the guided review on our Apply page. Share the information requested about your catalog and rights. We follow up privately if more streaming links, royalty statements or rights documents are needed.');
setExactText(main, 'Genres we acquire.', 'Your genre belongs in the conversation.');
setExactText(main, 'From mood catalogs to commercial electronic rights, we evaluate catalogs with real demand across streaming, creator channels, wellness apps, and licensing.', 'All genres are considered. Hip-hop, R&B, pop and rock sit alongside our existing ambient, lo-fi, meditation, electronic, house, wellness and soundscape topics. The guides below are a starting point, not an eligibility list.');
sections[5].classList.add('growth-genres');
const genreGrid = sections[5].querySelector('.grid');
const genrePaths = ['sell-ambient-music-catalog','sell-lo-fi-beats-catalog','sell-meditation-music-rights','sell-electronic-music-catalog','sell-house-music-catalog','sell-tropical-house-catalog','sell-focus-music-catalog','sell-nature-soundscape-catalog','sell-wellness-music-catalog'];
const genreLinks = [...genreGrid.querySelectorAll('a')];
assert.equal(genreLinks.length,genrePaths.length);
genreLinks.forEach((a,i) => {
  const url = `/sell/${genrePaths[i]}/`;
  assert(sitemap.includes(`https://spacemusic.io${url}</loc>`),`Existing genre destination required: ${url}`);
  a.href = url;
});
genreGrid.insertAdjacentHTML('beforebegin', `<div class="growth-breadth"><div><h3>Artists &amp; producers</h3><p>A single release, selected tracks or a larger catalog: explain the rights you own and the income they generate.</p></div><div><h3>Independent labels &amp; catalog owners</h3><p>Bring your release list, artist agreements and royalty records. We review the specific rights you can offer.</p></div><a href="/apply/">Genre not listed? Request an individual review &#8594;</a></div>`);
const faqContainer = sections[7].querySelector('[data-orientation="vertical"]');
faqContainer.replaceChildren();
faq.mainEntity.forEach(question => {
  const details = doc.createElement('details');
  details.className = 'growth-faq-item';
  const summary = doc.createElement('summary');
  summary.textContent = question.name;
  const answer = doc.createElement('p');
  answer.textContent = question.acceptedAnswer.text;
  details.append(summary, answer);
  faqContainer.append(details);
});
const skip = doc.createElement('a');
skip.className = 'space-skip'; skip.href = '#space-growth-home'; skip.textContent = 'Skip to main content';
doc.querySelector('#root').prepend(skip);

// The exact same trusted build-time main content is used for SSR and client navigation.
// There is no user-supplied HTML, hydration-time text patching or new runtime dependency.
const homepageModule = moduleFor('Index-og-');
const homeSource = `import {e as jsx,r as React,aF as Helmet} from './vendor-DhPEFgb5.js';
import {N as Navbar} from './${moduleFor('Navbar-')}';
import {F as Footer} from './${moduleFor('Footer-')}';
import {S as SEOHead} from './${moduleFor('SEOHead-')}';
import {C as CookieBanner} from './${moduleFor('CookieBanner-')}';
export const growthMainHTML=${JSON.stringify(main.innerHTML)};
export default function Home(){
 const [showConsent,setShowConsent]=React.useState(false);
 React.useEffect(()=>{try{setShowConsent(!localStorage.getItem('cookiesAccepted'));}catch{setShowConsent(true);}},[]);
 return jsx.jsxs('div',{className:'min-h-screen flex flex-col w-full',children:[
 jsx.jsx('a',{href:'#space-growth-home',className:'space-skip',children:'Skip to main content'}),
 jsx.jsx(SEOHead,{title:${JSON.stringify(doc.title)},description:${JSON.stringify(doc.querySelector('meta[name="description"]').content)},canonical:'/',type:'website',image:'https://spacemusic.io/social/space-catalog-v1.png',schema:${JSON.stringify(schemas)}}),
 jsx.jsxs(Helmet,{children:[jsx.jsx('meta',{property:'og:image:type',content:'image/png'}),jsx.jsx('meta',{property:'og:image:width',content:'1730'}),jsx.jsx('meta',{property:'og:image:height',content:'909'}),jsx.jsx('meta',{property:'og:image:alt',content:'SPACE: Sell your music catalog. One direct buyer. One clear offer. Free evaluation. No obligation.'}),jsx.jsx('meta',{name:'twitter:image:alt',content:${JSON.stringify(doc.querySelector('meta[name="twitter:image:alt"]').content)}})]}),
 jsx.jsx(Navbar,{}),jsx.jsx('main',{id:'space-growth-home',tabIndex:-1,dangerouslySetInnerHTML:{__html:growthMainHTML}}),jsx.jsx(Footer,{}),showConsent?jsx.jsx(CookieBanner,{onAccept:()=>{try{localStorage.setItem('cookiesAccepted','true');}catch{}setShowConsent(false);}}):null]});}`;
codes.set(homepageModule, (await transform(homeSource, { format:'esm', minify:true })).code);
changed.add(homepageModule);
const sellDOM = new JSDOM(await readFile(path.join(source,'sell/index.html'),'utf8'));
const sellDoc = sellDOM.window.document;
applyPageCopy(sellDoc, replacements.sell);
const sellMain = layoutSellPage(sellDoc);
const sellModule = moduleFor('GenreIndex-');
const sellSchemas = [...sellDoc.querySelectorAll('script[type="application/ld+json"]')]
  .sort((a,b) => a.id.localeCompare(b.id)).map(node => JSON.parse(node.textContent));
const sellSource = `import {e as jsx} from './vendor-DhPEFgb5.js';
import {N as Navbar} from './${moduleFor('Navbar-')}';
import {F as Footer} from './${moduleFor('Footer-')}';
import {S as SEOHead} from './${moduleFor('SEOHead-')}';
export const growthSellHTML=${JSON.stringify(sellMain.innerHTML)};
export default function Sell(){return jsx.jsxs('div',{className:'min-h-screen flex flex-col',children:[
jsx.jsx('a',{href:'#space-growth-sell',className:'space-skip',children:'Skip to main content'}),
jsx.jsx(SEOHead,{title:${JSON.stringify(sellDoc.querySelector('meta[property="og:title"]').content)},description:${JSON.stringify(sellDoc.querySelector('meta[name="description"]').content)},canonical:'/sell/',schema:${JSON.stringify(sellSchemas)}}),
jsx.jsx(Navbar,{}),jsx.jsx('main',{id:'space-growth-sell',className:'flex-grow',tabIndex:-1,dangerouslySetInnerHTML:{__html:growthSellHTML}}),jsx.jsx(Footer,{})]});}`;
codes.set(sellModule, (await transform(sellSource,{format:'esm',minify:true})).code);
let growing = true;
while (growing) {
  growing = false;
  for (const name of reachable) if (!changed.has(name) && dependencies(name).some(n => changed.has(n))) { changed.add(name); growing = true; }
}
const fontCSS = await readFile('marketing/design/fonts/fonts.css', 'utf8');
const stylesheet = fontCSS + '\n' + await readFile('marketing/growth-20260916/growth.css', 'utf8') + '\n' + await readFile('marketing/growth-20260916/sell.css', 'utf8');
const styleName = `growth-${hash(stylesheet).slice(0,12)}.css`;
const revision = hash([...changed].sort().map(n => n + codes.get(n)).join('\n')).slice(0,12);
const renamed = new Map([...changed].map(n => [n, `${n.slice(0,-3)}-growth-${revision}.js`]));
await mkdir(output);
await cp(source, output, { recursive:true });
await writeFile(path.join(output,'assets',styleName), stylesheet);
for (const name of (await files('marketing/design/fonts')).filter(n => n !== 'fonts.css')) await cp(path.join('marketing/design/fonts',name), path.join(output,'fonts',name));
for (const name of changed) {
  const pairs = literals(codes.get(name)).filter(n => renamed.has(path.basename(n.value))).map(n => [n.value, n.value.slice(0,-path.basename(n.value).length) + renamed.get(path.basename(n.value))]);
  await writeFile(path.join(output,'assets',renamed.get(name)), replaceLiterals(codes.get(name),pairs));
}
const copyPages = Object.keys(replacements).map(p => `${p}/index.html`);
for (const file of inventory.filter(f => f.endsWith('.html') && !f.startsWith('apply/'))) {
  let html = file === 'index.html' ? homeDOM.serialize() : file === 'sell/index.html' ? sellDOM.serialize() : await readFile(path.join(source,file),'utf8');
  if (copyPages.includes(file) && file !== 'sell/index.html') {
    const dom = new JSDOM(html);
    const d = dom.window.document;
    const pairs = replacements[file.split('/')[0]];
    applyPageCopy(d, pairs);
    html = dom.serialize();
  }
  for (const [oldName,newName] of renamed) html = html.replaceAll(`/assets/${oldName}`, `/assets/${newName}`);
  html = html.replace(/<link\b(?=[^>]*rel="preload")(?=[^>]*as="font")[^>]*>/g, '');
  html = html.replace('</head>', `<link rel="preload" href="/fonts/inter-latin-c940764593d0.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="/assets/${styleName}"></head>`);
  await writeFile(path.join(output,file), html);
}
const brand = JSON.parse(await readFile(path.join(source,'.well-known/brand-facts.json'),'utf8'));
brand.description = positioning;
brand.catalogTypes.push('Hip-hop and rap','R&B and soul','Pop','Rock','Other genres considered individually');
brand.service.initialOfferTimeline = 'Typically 5-7 business days after relevant information is received, if the catalog is a fit';
brand.lastUpdated = '2026-09-16';
await writeFile(path.join(output,'.well-known/brand-facts.json'), JSON.stringify(brand,null,2)+'\n');
let llms = await readFile(path.join(source,'llms.txt'),'utf8');
for (const [a,b] of [
  ['Last updated: 2026-09-07','Last updated: 2026-09-16'],
  ["SPACE's published genre coverage includes ambient, lo-fi, meditation, electronic, house, wellness, and soundscape music.", 'All genres are considered, including hip-hop, R&B, pop and rock alongside ambient, lo-fi, meditation, electronic, house, wellness and soundscape catalogs.'],
  ['Published reference multiples and calculator outputs are indicative, not guaranteed offers.', 'The calculator models assumptions chosen by the visitor, not market value or a SPACE offer. There is no fixed genre multiple.'],
  ['Valuation factors and illustrative reference multiples, not guaranteed purchase offers.', 'Documented income, rights and valuation factors, with a hypothetical calculation rather than a guaranteed purchase offer.'],
  ['Estimate a reference value from revenue, costs, years, and the share sold; not a purchase offer.', 'Model monthly net income x 12 x a visitor-supplied assumed multiple x the share sold. A hypothetical scenario, not market value or a purchase offer.'],
  ["SPACE's published company reference; stated valuation ranges are indicative.", "SPACE's published company reference, all-genre eligibility, review criteria and conditional offer policy."],
]) { assert(llms.includes(a), a); llms = llms.replace(a,b); }
await writeFile(path.join(output,'llms.txt'),llms);
const immutable = inventory.filter(f => !f.endsWith('.html') && !['llms.txt','.well-known/brand-facts.json'].includes(f) || f.startsWith('apply/'));
for (const file of immutable) assert((await readFile(path.join(source,file))).equals(await readFile(path.join(output,file))), `Protected file changed: ${file}`);
await mkdir(path.dirname(manifestFile),{recursive:true});
await writeFile(manifestFile,JSON.stringify({source,output,revision,stylesheet:styleName,homeModule:renamed.get(homepageModule),sellModule:renamed.get(sellModule),changedModules:[...renamed],intentionalContentPages:['index.html',...copyPages],sitemapURLs:139,apply:'byte-identical',production:'not changed',sourceHashes:Object.fromEntries(await Promise.all(inventory.map(async f => [f,hash(await readFile(path.join(source,f)))])))},null,2));
console.log(JSON.stringify({output,revision,newModules:changed.size,stylesheet:styleName,apply:'byte-identical',sitemap:'139 unchanged',status:'draft preview build'}));

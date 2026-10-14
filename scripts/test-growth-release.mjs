import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { files } from './funnel-support.mjs';
import { literals } from './journey-support.mjs';
import { parse } from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import { transform } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { runInNewContext } from 'node:vm';
import { replacements } from '../marketing/growth-20260916/copy.mjs';

const [manifestPath] = process.argv.slice(2);
assert(manifestPath, 'Usage: BUILD_MANIFEST');
const manifest = JSON.parse(await readFile(manifestPath,'utf8'));
const {source,output,changedModules,intentionalContentPages} = manifest;
const hash = value => createHash('sha256').update(value).digest('hex');
const inventory = await files(output);
const load = (root,file) => readFile(path.join(root,file),'utf8');
const dom = html => new JSDOM(html).window.document;
let checks = 0;
function same(actual,expected,label) { assert.deepEqual(actual,expected,label); checks++; }
for (const [file,digest] of Object.entries(manifest.sourceHashes)) {
  same(hash(await readFile(path.join(source,file))),digest,`Baseline drift: ${file}`);
  assert(inventory.includes(file),`File removed: ${file}`); checks++;
  if (!file.endsWith('.html') && !['llms.txt','.well-known/brand-facts.json'].includes(file) || file.startsWith('apply/')) {
    same(await load(output,file),await load(source,file),`Protected file: ${file}`);
  }
}
const urls = [...(await load(output,'sitemap.xml')).matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);
same(urls.length,139,'Sitemap count');
for (const url of urls) {
  const pathname = new URL(url).pathname.slice(1);
  if (/\.(md|txt)$/.test(pathname)) {
    const before = await load(source,pathname), after = await load(output,pathname);
    if (pathname === 'llms.txt') {
      same(after.match(/^## .+$/gm),before.match(/^## .+$/gm),'llms sections retained');
      same([...after.matchAll(/\]\((https[^)]+)\)/g)].map(m=>m[1]),[...before.matchAll(/\]\((https[^)]+)\)/g)].map(m=>m[1]),'llms destinations retained');
      assert(!/<head|<meta|<html/i.test(after),'llms remains plain text'); checks++;
    } else same(after,before,`Plain-text sitemap entry: ${url}`);
    continue;
  }
  const file = path.join(pathname,'index.html');
  const before = dom(await load(source,file));
  const after = dom(await load(output,file));
  const meta = (d,selector) => [...d.querySelectorAll(selector)].map(n=>n.outerHTML);
  same(after.title,before.title,`Title preserved: ${url}`);
  same(meta(after,'link[rel="canonical"]'),meta(before,'link[rel="canonical"]'),`Canonical: ${url}`);
  same(meta(after,'meta[name="robots"]'),meta(before,'meta[name="robots"]'),`Robots: ${url}`);
  same(after.querySelectorAll('h1').length,before.querySelectorAll('h1').length,`H1 count: ${url}`);
  if (!intentionalContentPages.includes(file)) {
    same(after.body.innerHTML,before.body.innerHTML,`Untouched body: ${url}`);
    same(meta(after,'meta'),meta(before,'meta'),`Untouched metadata: ${url}`);
    same(meta(after,'script[type="application/ld+json"]'),meta(before,'script[type="application/ld+json"]'),`Untouched schema: ${url}`);
  }
  for (const el of after.querySelectorAll('script[src],link[rel="stylesheet"],link[rel="modulepreload"],link[rel="preload"]')) {
    const asset = el.getAttribute('src') || el.getAttribute('href');
    if (asset.startsWith('/') && !asset.startsWith('//')) { assert(inventory.includes(asset.slice(1)),`${url}: missing ${asset}`); checks++; }
  }
}
for (const [,name] of changedModules) {
  const code = await load(output,`assets/${name}`);
  for (const value of literals(code).map(n=>n.value).filter(v=>/^\.\/[^/]+\.(js|css)$/.test(v))) {
    assert(inventory.includes(`assets/${value.slice(2)}`),`${name}: missing ${value}`); checks++;
  }
}
for (const [page,pairs] of Object.entries(replacements)) {
  const d = dom(await load(output,`${page}/index.html`));
  for (const [before,after] of pairs) {
    assert(!d.documentElement.textContent.includes(before) && !d.documentElement.outerHTML.includes(before), `${page}: obsolete copy ${before}`);
    assert(d.documentElement.textContent.includes(after) || [...d.querySelectorAll('meta')].some(n=>n.content===after),`${page}: missing replacement ${after}`);
    checks+=2;
  }
}
const home = dom(await load(output,'index.html'));
const oldHome = dom(await load(source,'index.html'));
same(home.querySelectorAll('main>section').length,oldHome.querySelectorAll('main>section').length,'All homepage sections retained');
const destinations = new Set([...home.querySelectorAll('a[href]')].map(n=>n.getAttribute('href')));
for (const link of oldHome.querySelectorAll('a[href]')) { assert(destinations.has(link.getAttribute('href')),`Homepage lost destination: ${link.href}`); checks++; }
const faq = [...home.querySelectorAll('script[type="application/ld+json"]')].map(n=>JSON.parse(n.textContent)).find(s=>s['@type']==='FAQPage');
same([...home.querySelectorAll('details')].map(n=>({question:n.querySelector('summary').textContent,answer:n.querySelector('p').textContent})),faq.mainEntity.map(q=>({question:q.name,answer:q.acceptedAnswer.text})),'Visible HTML FAQ equals schema');
const main = home.querySelector('main').innerHTML;
const homeCode = await load(output,`assets/${manifest.homeModule}`);
const constants = literals(homeCode).map(n=>n.value);
for (const node of parse(homeCode,{sourceType:'module'}).program.body) {
  for (const declaration of node.declarations || []) {
    if (declaration.init?.type==='TemplateLiteral' && !declaration.init.expressions.length) constants.push(declaration.init.quasis[0].value.cooked);
  }
}
assert(constants.includes(main),'Client and server homepage content must be identical'); checks++;
same(home.querySelectorAll('meta[name="description"]').length,1,'One description');
same(home.querySelectorAll('meta[property="og:image"]').length,1,'One OG image');
// Exercise the generated component's consent callback without any network or real leads.
const cjs = (await transform(homeCode,{format:'cjs'})).code;
for (const blockedStorage of [false,true]) {
  let visible = true, stored = false;
  const exports = {};
  const module = {exports};
  const component = name => name;
  const elements = (type,props) => ({type,props});
  const vendor = {e:{jsx:elements,jsxs:elements},r:{useState:()=>[visible,v=>{visible=v;}],useEffect:()=>{}},aF:component('Helmet')};
  runInNewContext(cjs,{module,exports,require:name=>name.includes('vendor-')?vendor:name.includes('Navbar-')?{N:'Navbar'}:name.includes('Footer-')?{F:'Footer'}:name.includes('SEOHead-')?{S:'SEOHead'}:{C:'CookieBanner'},localStorage:{setItem:()=>{if(blockedStorage)throw Error('blocked');stored=true;}}});
  const tree = module.exports.default();
  const children = tree.props.children;
  const banner = children.find(n=>n?.type==='CookieBanner');
  assert.equal(typeof banner.props.onAccept,'function','Consent callback supplied'); checks++;
  banner.props.onAccept();
  same(visible,false,`Consent dismisses with storage blocked=${blockedStorage}`);
  same(stored,!blockedStorage,'Storage failure isolated');
  const extras = children.find(n=>n?.type==='Helmet').props.children;
  same(extras.find(n=>n.props.name==='twitter:image:alt').props.content,home.querySelector('meta[name="twitter:image:alt"]').content,'Twitter image-alt retained');
}
same(await load(output,'_headers'),await load(source,'_headers'),'Hosting headers');
same(await load(output,'_redirects'),await load(source,'_redirects'),'Routing');
console.log(JSON.stringify({status:'PASS',checks,sitemap:139,apply:'byte-identical',contentPages:intentionalContentPages,unchangedOtherPageBodies:true,homepageClientSSRParity:true,faqWithoutJavaScript:true,notTested:'real browser performance, analytics reports, lead delivery and production indexing'},null,2));

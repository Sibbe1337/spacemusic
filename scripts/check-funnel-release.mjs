import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import { files } from './funnel-support.mjs';
const [baseline, release, expected = '137'] = process.argv.slice(2);
const baseFiles = await files(baseline), releaseFiles = await files(release);
const read = (root,file) => readFile(path.join(root,file),'utf8');
const urls = xml => [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => match[1]);
const before = urls(await read(baseline,'sitemap.xml')), after = urls(await read(release,'sitemap.xml'));
assert.equal(before.length,137); assert.equal(after.length,Number(expected)); assert.equal(new Set(after).size,after.length);
for (const url of before) assert(after.includes(url),`Removed sitemap URL ${url}`);
for (const file of baseFiles) assert(releaseFiles.includes(file),`Deleted asset ${file}`);
for (const file of ['robots.txt','_headers','_redirects','llms.txt','pricing.md']) assert.equal(await read(baseline,file),await read(release,file),`${file} changed`);
const allowed = new Set(['calculator/index.html','guides/music-catalog-valuation-2026/index.html','glossary/metadata/index.html','glossary/buyout-deal/index.html']);
const strip = html => html.replace(/<script data-space-funnel="v1">[\s\S]*?<\/script>\s*/g,'').replace(/<script>\s*window\.plausible=[\s\S]*?plausible\.init\(\)\s*<\/script>\s*/g,'').replace(/\/assets\/index-[\w-]+\.js/g,'/assets/ENTRY.js').replace(/\/apply\/assets\/index-[\w-]+\.js/g,'/apply/assets/APPLY.js').replace(/\s*<script async(?:="")? src="https:\/\/plausible\.io[^\"]+"><\/script>\s*/g,'');
const normalized = html => strip(html).replace(/>\s+</g,'><');
for (const file of baseFiles.filter(file=>file.endsWith('.html') && !allowed.has(file))) assert.equal(normalized(await read(baseline,file)),normalized(await read(release,file)),`Unrelated content or metadata changed: ${file}`);
let pages=0;
for (const url of after) {
  const pathname = new URL(url).pathname;
  if (!pathname.endsWith('/')) continue;
  const file = pathname.slice(1)+'index.html';
  const html = await read(release,file), doc = new JSDOM(html).window.document;
  assert.equal(doc.querySelectorAll('h1').length,1,`${url} H1`);
  assert.equal(doc.querySelectorAll('link[rel="canonical"]').length,1,`${url} canonical count`);
  assert.equal(doc.querySelector('link[rel="canonical"]').getAttribute('href'),url,`${url} canonical`);
  assert.equal(doc.querySelectorAll('meta[name="description"]').length,1,`${url} description count`);
  assert(doc.title.trim());
  assert(!/noindex/.test(doc.querySelector('meta[name="robots"]')?.content || ''),`${url} indexability`);
  for (const schema of doc.querySelectorAll('script[type="application/ld+json"]')) JSON.parse(schema.textContent);
  if (allowed.has(file) || !baseFiles.includes(file)) for (const a of doc.querySelectorAll('a[href^="/"]')) {
    const dest = new URL(a.getAttribute('href'),'https://spacemusic.io');
    if (dest.pathname === '/' || dest.pathname.endsWith('/')) assert(releaseFiles.includes(dest.pathname.slice(1)+'index.html'),`${url}: broken link ${dest.pathname}`);
    else assert(releaseFiles.includes(dest.pathname.slice(1)) || releaseFiles.includes(dest.pathname.slice(1)+'/index.html'),`${url}: broken link ${dest.pathname}`);
  }
  pages++;
}
console.log(JSON.stringify({release,sitemap:after.length,preserved:before.length,htmlPagesChecked:pages,unrelatedContentAndSEO:'unchanged',existingAssets:'all preserved',robotsAndTextResources:'unchanged',newContentLinks:'valid'}));

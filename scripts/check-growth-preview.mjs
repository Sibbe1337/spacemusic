import assert from 'node:assert/strict';
import { JSDOM } from '../services/seller_ui/node_modules/jsdom/lib/api.js';

const origin = process.argv[2];
const expectedUrls = Number(process.argv[3] || 139);
assert(Number.isSafeInteger(expectedUrls) && expectedUrls > 0, 'Expected sitemap size');
assert(origin && /^https:\/\/[^/]+\.pages\.dev$/.test(origin),'Expected a Pages preview origin, never production');
const sitemapResponse = await fetch(`${origin}/sitemap.xml`);
assert.equal(sitemapResponse.status,200);
const urls = [...(await sitemapResponse.text()).matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);
assert.equal(urls.length,expectedUrls);
let htmlPages = 0;
for (let i=0;i<urls.length;i+=6) {
  await Promise.all(urls.slice(i,i+6).map(async canonical => {
    const pathname = new URL(canonical).pathname;
    const response = await fetch(origin+pathname,{redirect:'manual'});
    assert.equal(response.status,200,pathname);
    assert.match(response.headers.get('x-robots-tag')||'',/noindex/i,`Preview must not be indexed: ${pathname}`);
    if (!response.headers.get('content-type')?.includes('text/html')) return;
    htmlPages++;
    const doc = new JSDOM(await response.text()).window.document;
    const tags = doc.querySelectorAll('link[rel="canonical"]');
    assert.equal(tags.length,1,pathname);
    assert.equal(tags[0].href,canonical,pathname);
    assert(doc.querySelector('h1'),pathname);
    assert(![...doc.querySelectorAll('meta[name="robots"]')].some(m=>/noindex/i.test(m.content)),`Do not bake preview noindex into production HTML: ${pathname}`);
  }));
}
for (const [pathname,type] of [['/llms.txt','text/plain'],['/pricing.md','text/']]) {
  const r = await fetch(origin+pathname);
  assert(r.headers.get('content-type')?.includes(type));
  assert.equal(r.headers.get('link'),`<https://spacemusic.io${pathname}>; rel="canonical"`);
}
console.log(JSON.stringify({origin,sitemapURLs:urls.length,htmlPages,status:'PASS',status200:true,previewNoindex:true,productionCanonicalsPreserved:true,plainTextCanonicalHeaders:true}));

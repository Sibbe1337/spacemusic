import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';

const [originArg, manifestPath, ...extra] = process.argv.slice(2);
assert(originArg && manifestPath && !extra.length, 'Usage: PREVIEW_ORIGIN MANIFEST');
const origin = new URL(originArg).origin;
assert(/^https:\/\/[a-z0-9-]+\.spacemusic-a6n\.pages\.dev$/.test(origin), 'Only this project preview is supported');
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const xml = await readFile(`${manifest.output}/sitemap.xml`, 'utf8');
const urls = [...xml.matchAll(/<loc>\s*([^<]+)\s*<\/loc>/g)].map(m => m[1]);
assert.equal(urls.length, 141);
const results = [];
for (const canonical of urls) {
  const url = new URL(canonical);
  assert.equal(url.origin, 'https://spacemusic.io');
  const response = await fetch(origin + url.pathname, {redirect:'manual', signal:AbortSignal.timeout(20000)});
  assert.equal(response.status, 200, `${url.pathname} HTTP status`);
  assert.match(response.headers.get('x-robots-tag') || '', /\bnoindex\b/i, `${url.pathname} preview must not be indexed`);
  if ((response.headers.get('content-type') || '').includes('text/html')) {
    const doc = new JSDOM(await response.text()).window.document;
    const links = [...doc.querySelectorAll('link[rel="canonical"]')].map(n => n.getAttribute('href'));
    assert.deepEqual(links, [canonical], `${url.pathname} production canonical`);
    assert(doc.querySelector('h1'), `${url.pathname} server-rendered H1`);
    for (const meta of doc.querySelectorAll('meta[name="robots"]')) {
      assert(!/noindex|\bnone\b/i.test(meta.content), 'Do not bake preview noindex into a production candidate');
    }
  } else await response.arrayBuffer();
  results.push({path:url.pathname, status:200, previewNoindex:true, canonical});
}
// The deployed preview must not change the three production pages or Apply.
for (const file of ['index.html', 'sell/index.html', 'calculator/index.html', 'apply/index.html', 'sitemap.xml', 'robots.txt']) {
  const pathname = '/' + file.replace(/(^|\/)index\.html$/, '$1');
  const response = await fetch('https://spacemusic.io' + pathname, {redirect:'manual', signal:AbortSignal.timeout(20000)});
  assert.equal(response.status, 200, `production ${pathname}`);
  assert(!/noindex|\bnone\b/i.test(response.headers.get('x-robots-tag') || ''), `production ${pathname} must remain indexable`);
  assert((await readFile(`${manifest.source}/${file}`)).equals(Buffer.from(await response.arrayBuffer())), `production ${pathname} must remain unchanged`);
}
const report = {checkedAt:new Date().toISOString(), origin, manifest:manifestPath, revision:manifest.revision, urls:results.length, productionSpotChecks:6, status:'PASS', results};
await writeFile('marketing/conversion-20260917/live-checks.json', JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({origin,urls:results.length,productionSpotChecks:6,status:'PASS'},null,2));

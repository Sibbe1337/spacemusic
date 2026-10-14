const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM } = require('../../../services/admin_ui/node_modules/jsdom');

const root = __dirname;
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const baseline = JSON.parse(read('gsc-baseline.json'));
const days = (Date.parse(baseline.end) - Date.parse(baseline.start)) / 86400000 + 1;
assert.equal(days, 90);
assert.equal(1000 * 12 * 4 * 0.5, 24000);
assert.equal(600 * 12 * 4 * 0.5, 14400);
assert.equal(800 * 12 * 4 * 0.5, 19200);
assert.equal(30000 - 5000 - 2000, 23000);
assert.equal(30000 - 2000, 28000);

const files = ['REVIEW.md', 'WORKFLOW-DRAFTS.md', 'DISTRIBUTION-DRAFTS.md', 'APPROVAL-AND-MEASUREMENT.md'];
const publicUrls = new Set();
const missingLocal = [];
for (const file of files) {
  for (const match of read(file).matchAll(/\]\(([^)]+)\)/g)) {
    const href = match[1];
    if (href.startsWith('https://spacemusic.io/')) publicUrls.add(href.split('#')[0]);
    else if (!/^(https?:|mailto:|#)/.test(href) && !fs.existsSync(path.resolve(root, href))) missingLocal.push({ file, href });
  }
}
assert.deepEqual(missingLocal, []);

const evidence = name => JSON.parse(read(`evidence/${name}.json`));
const newLinks = [
  ['calculator', '/blog/music-catalog-sale-documents-checklist/'],
  ['calculator', '/compare/partial-sale-vs-full-sale/'],
  ['calculator', '/pricing.md'],
  ['guides__music-catalog-valuation-2026', '/compare/selling-masters-vs-selling-publishing/'],
  ['blog__music-catalog-sale-documents-checklist', '/blog/music-catalog-offer-checklist/'],
  ['blog__music-catalog-offer-checklist', '/compare/catalog-sale-vs-catalog-loan/'],
];
for (const [source, destination] of newLinks) {
  const page = evidence(source);
  const existing = page.links.map(link => new URL(link.href, page.url).pathname);
  assert(!existing.includes(destination), `Proposed link duplicates existing destination on ${source}: ${destination}`);
  publicUrls.add(`https://spacemusic.io${destination}`);
}

async function main() {
  const checks = [];
  for (const url of [...publicUrls].sort()) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(20000) });
      const body = await response.text();
      const contentType = response.headers.get('content-type') || '';
      const doc = contentType.includes('html') ? new JSDOM(body).window.document : null;
      const canonical = doc?.querySelector('link[rel="canonical"]')?.href || null;
      checks.push({ requested: url, final_url: response.url, status: response.status, content_type: contentType, canonical, title: doc?.title || null, checked_at: new Date().toISOString(), expected_current_content: response.ok && (!doc || canonical === url) });
    } catch (error) {
      checks.push({ requested: url, error: error.message, checked_at: new Date().toISOString(), expected_current_content: false });
    }
  }
  const sitemapResponse = await fetch('https://spacemusic.io/sitemap.xml', { signal: AbortSignal.timeout(20000) });
  const sitemap = await sitemapResponse.text();
  const sitemapUrls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
  assert.equal(sitemapResponse.status, 200);
  assert.equal(sitemapUrls.length, 139);
  assert.equal(new Set(sitemapUrls).size, 139);
  const result = { status: 'Draft-pack checks only; no deployment or application submission', checked_at: new Date().toISOString(), inclusive_gsc_days: days, arithmetic_examples: 'passed', local_artifact_links: 'passed', six_proposed_links_absent_from_existing_sources: 'passed', current_sitemap_count: sitemapUrls.length, checks };
  fs.writeFileSync(path.join(root, 'validation.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ ...result, checks: undefined, public_urls_checked: checks.length, exceptions: checks.filter(row => !row.expected_current_content) }, null, 2));
  if (checks.some(row => !row.expected_current_content)) process.exitCode = 1;
}
main().catch(error => { console.error(error); process.exitCode = 1; });

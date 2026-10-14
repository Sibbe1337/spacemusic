const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('../../../services/admin_ui/node_modules/jsdom');
const out = path.join(__dirname, 'evidence');
fs.mkdirSync(out, { recursive: true });
const paths = ['/', '/pricing.md', '/apply/', '/how-it-works/', '/calculator/', '/guides/music-catalog-valuation-2026/', '/guides/what-are-your-streams-worth-2026/', '/guides/best-music-rights-buyers-2026/', '/compare/space-vs-royalty-exchange/', '/compare/partial-sale-vs-full-sale/', '/compare/selling-masters-vs-selling-publishing/', '/compare/catalog-sale-vs-catalog-loan/', '/blog/', '/blog/music-catalog-sale-documents-checklist/', '/blog/music-catalog-offer-checklist/', '/blog/royalty-exchange-alternatives/', '/blog/beatbread-vs-catalog-buyers/', '/glossary/master-rights/', '/glossary/publishing-rights/', '/glossary/revenue-multiple/', '/glossary/metadata/', '/brand-facts/', '/sitemap.xml'];
(async () => {
  const sitemap = await (await fetch('https://spacemusic.io/sitemap.xml')).text();
  const extras = [...sitemap.matchAll(/<loc>(https:\/\/spacemusic\.io\/blog\/[^<]+)<\/loc>/g)].map(m => new URL(m[1]).pathname);
  for (const p of [...extras, '/sell/', '/about/', '/guides/music-rights-101/', '/guides/how-to-sell-music-rights/', '/glossary/catalog-valuation/', '/glossary/buyout-deal/']) if (!paths.includes(p)) paths.push(p);
  const results = [];
  for (const p of paths) {
    const response = await fetch('https://spacemusic.io' + p);
    const html = await response.text();
    const id = p === '/' ? 'homepage' : p.replace(/^\/|\/$/g, '').replaceAll('/', '__');
    fs.writeFileSync(path.join(out, id + '.source'), html);
    const doc = new JSDOM(html).window.document;
    const content = doc.querySelector('main') || doc.body;
    content.querySelectorAll('script, style, noscript').forEach(e => e.remove());
    const record = { requested: p, url: response.url, status: response.status, fetched: new Date().toISOString(), contentType: response.headers.get('content-type'), title: doc.title, description: doc.querySelector('meta[name="description"]')?.content, canonical: doc.querySelector('link[rel="canonical"]')?.href, headings: Array.from(content.querySelectorAll('h1,h2,h3'), e => e.textContent.trim()), paragraphs: Array.from(content.querySelectorAll('p'), e => e.textContent.trim()), links: Array.from(content.querySelectorAll('a'), e => ({text:e.textContent.trim(), href:e.getAttribute('href')})), text: /text\/(plain|markdown)|xml/.test(response.headers.get('content-type') || '') ? html : content.textContent.replace(/\s+/g, ' ').trim() };
    fs.writeFileSync(path.join(out, id + '.json'), JSON.stringify(record, null, 2));
    results.push({path:p,status:record.status,title:record.title,canonical:record.canonical});
  }
  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(results,null,2));
  console.log(JSON.stringify(results,null,2));
})();

// Generates the sourced data pages (deal tracker, platform catalog sizes, Deezer
// prices) as one lazy page module plus the edit file that routes them, adds them to
// the sitemap and llms.txt, and prerenders them. Data: marketing/growth-20260930/data.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {SOURCE} from './authentic-support.mjs';

const D = 'marketing/growth-20260930/data/';
const deals = JSON.parse(await readFile(D + 'deals.json', 'utf8'));
const multiples = JSON.parse(await readFile(D + 'multiples.json', 'utf8'));
const platforms = JSON.parse(await readFile(D + 'platform-catalogs.json', 'utf8'));
const prices = JSON.parse(await readFile(D + 'deezer-prices.json', 'utf8'));
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const ext = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">${esc(label)}</a>`;
const monthName = d => { const [y, m] = d.split('-'); return m ? new Date(Date.UTC(+y, +m - 1, 1)).toLocaleString('en-US', {month: 'short', timeZone: 'UTC'}) + ' ' + y : y; };
const H1 = 'text-3xl md:text-5xl font-semibold tracking-tight mb-6 leading-[1.1]';
const H2 = 'text-2xl md:text-3xl font-semibold tracking-tight mb-4 mt-12';
const P = 'text-muted-foreground leading-relaxed mb-4';
const TABLE = 'w-full text-sm border-collapse';
const TH = 'text-left py-3 pr-4 font-medium whitespace-nowrap';
const TD = 'py-3 pr-4';
const table = (heads, rows) => `<div class="overflow-x-auto"><table class="${TABLE}" style="min-width:760px"><thead><tr class="border-b border-black/10">${heads.map(h => `<th class="${TH}">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr class="border-b border-black/[0.06]">${r.map((c, i) => `<td class="${TD}" style="vertical-align:top${i === 0 ? ';white-space:nowrap' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const crumbs = (label) => `<p class="text-sm text-muted-foreground mb-6"><a href="/data/music-catalog-market-2026/" class="hover:underline">Data</a> / ${esc(label)}</p>`;
const updated = d => `<p class="text-sm text-muted-foreground mb-8">By SPACE Editorial Team. Updated ${new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'})}.</p>`;
const org = {'@type': 'Organization', name: 'SPACE', url: 'https://spacemusic.io/'};

// Deal tracker
const list = [...deals.deals].sort((a, b) => b.date.localeCompare(a.date));
const years = list.map(d => +d.date.slice(0, 4));
const stat = s => list.filter(d => d.priceStatus === s).length;
const priceCell = d => d.price ? `${esc(d.price)}${d.priceStatus === 'reported' ? '' : ''}` : '<span class="text-muted-foreground">Undisclosed</span>';
const dealHtml = crumbs('Music Catalog Deal Tracker') +
  `<h1 class="${H1}">Music Catalog Deal Tracker: Public Deals ${Math.min(...years)}–${Math.max(...years)}</h1>` + updated(deals.updated) +
  `<p class="${P}">This tracker lists ${list.length} publicly reported music catalog acquisitions from ${Math.min(...years)} to ${Math.max(...years)}. Every row links to the report it comes from. A price is shown only when the parties or a filing disclosed it (${stat('disclosed')} deals) or a named publication reported it (${stat('reported')} deals). The other ${stat('undisclosed')} prices were not disclosed. SPACE does not estimate prices.</p>` +
  `<p class="${P}">Found an error or a missing deal? Email hello@spacemusic.io with a source.</p>` +
  `<h2 class="${H2}">Deals by date</h2>` +
  table(['Date', 'Buyer', 'Seller', 'What was sold', 'Price', 'Source'], list.map(d => [esc(monthName(d.date)), esc(d.buyer), esc(d.seller), esc(d.assets) + (d.notes ? `<br><span class="text-xs text-muted-foreground">${esc(d.notes)}</span>` : ''), priceCell(d), ext(d.url, d.source)])) +
  `<h2 class="${H2}">Publicly stated valuation multiples</h2>` +
  `<p class="${P}">These multiples were stated by the companies or valuers named below. They use different bases (net publisher share, net label share, net revenue) and periods, so they are not directly comparable with each other or with any single catalog. SPACE does not use a fixed multiple; every catalog is reviewed individually.</p>` +
  table(['Multiple', 'What was said', 'Date', 'Source'], multiples.items.map(m => [`<strong>${esc(m.value)}</strong>`, esc(m.statement) + (m.context ? `<br><span class="text-xs text-muted-foreground">${esc(m.context)}</span>` : ''), esc(monthName(m.date)), ext(m.url, m.source)])) +
  `<h2 class="${H2}">How to use this data</h2>` +
  `<p class="${P}">Large headline deals involve famous songs and decades of income, so they say little about a smaller catalog. For your own catalog, start from documented net income and the rights being sold. <a href="/guides/music-catalog-valuation-2026/" class="underline underline-offset-2">Read how catalog value is set</a>, <a href="/calculator/" class="underline underline-offset-2">model a scenario</a>, or <a href="/apply/" class="underline underline-offset-2">request a free catalog review</a>.</p>`;

// Platform catalog sizes
const pl = platforms.platforms;
const catHtml = crumbs('Streaming Platform Catalog Sizes') +
  `<h1 class="${H1}">How Many Songs Are on Spotify, Apple Music and Other Platforms? (2026)</h1>` + updated(platforms.updated) +
  `<p class="${P}">Spotify, Apple Music, Amazon Music, Deezer and Qobuz each say on their own pages that they offer 100 million tracks or more. The table below shows what each platform states about its catalog and its users, with a link to the page where it says so. Where a platform does not publish a number, the table says so.</p>` +
  table(['Platform', 'Catalog, as stated', 'Users or subscribers', 'Sources'], pl.map(p => [
    `<strong>${esc(p.name)}</strong>`,
    (p.catalog ? esc(p.catalog) : '<span class="text-muted-foreground">Not published</span>') + (p.notes ? `<br><span class="text-xs text-muted-foreground">${esc(p.notes)}</span>` : ''),
    p.users ? esc(p.users) : '<span class="text-muted-foreground">Not published</span>',
    [p.catalogUrl && ext(p.catalogUrl, p.catalogSource || 'Catalog'), p.usersUrl && ext(p.usersUrl, p.usersSource || 'Users')].filter(Boolean).join('<br>')])) +
  `<h2 class="${H2}">Why these numbers are hard to compare</h2>` +
  `<p class="${P}">Platforms count differently. Some figures include videos, live recordings or user uploads, and none of them say how many tracks are ever played. A bigger catalog also means more competition for listening time, which is one reason income from older tracks varies so much.</p>` +
  `<p class="${P}">If you own recordings on these platforms, <a href="/tools/streaming-calculator/" class="underline underline-offset-2">estimate your streaming income</a> from your own statements, or <a href="/guides/what-are-your-streams-worth-2026/" class="underline underline-offset-2">read how platforms pay</a>.</p>`;

// Deezer prices
const pr = prices.countries;
const priceHtml = `<p class="text-sm text-muted-foreground mb-6"><a href="/streaming-rates/" class="hover:underline">Streaming Rates</a> / Deezer Prices</p>` +
  `<h1 class="${H1}">Deezer Prices 2026 by Country: Premium, Duo, Family and Student</h1>` + updated(prices.checked) +
  `<p class="${P}">Deezer sets its prices by country. We checked Deezer's own offers pages for ${pr.length} countries in September 2026. Prices are monthly unless noted, and Deezer can change them at any time, so confirm on Deezer's site before you subscribe.</p>` +
  table(['Country', 'Premium', 'Duo', 'Family', 'Student', 'Source'], pr.map(c => [`<strong>${esc(c.country)}</strong>`, esc(c.premium), esc(c.duo), esc(c.family), esc(c.student), ext(c.url, 'Deezer offers page')])) +
  (pr.some(c => c.annual) ? `<p class="text-xs text-muted-foreground mt-3">Annual plans as listed on Deezer's offers pages: ${pr.filter(c => c.annual).map(c => `${esc(c.country)}: ${esc(c.annual)}`).join('; ')}.</p>` : '') +
  `<h2 class="${H2}">What Deezer pays artists</h2>` +
  `<p class="${P}">Subscription prices are not what artists earn per stream. Deezer pays rights holders from a revenue pool under its artist-centric model. <a href="/streaming-rates/deezer-2026/" class="underline underline-offset-2">See how Deezer calculates payouts</a>, or <a href="/tools/streaming-calculator/" class="underline underline-offset-2">estimate your own streaming income</a>.</p>`;

const PAGES = {
  '/data/music-catalog-deals/': {title: 'Music Catalog Deal Tracker 2019–2026: Public Deals and Prices', description: `${list.length} publicly reported music catalog acquisitions with buyer, seller, rights sold, reported price and source, plus multiples stated by catalog buyers.`, html: dealHtml,
    schema: {'@context': 'https://schema.org', '@type': 'Dataset', name: 'Music Catalog Deal Tracker', description: 'Publicly reported music catalog acquisitions with sources.', url: 'https://spacemusic.io/data/music-catalog-deals/', creator: org, dateModified: deals.updated, temporalCoverage: `${Math.min(...years)}/${Math.max(...years)}`}},
  '/data/streaming-platform-catalog-sizes/': {title: 'Streaming Platform Catalog Sizes 2026: Spotify, Apple Music, Deezer and More', description: 'How many songs are on Spotify, Apple Music, Amazon Music, YouTube Music, Deezer, TIDAL, SoundCloud, Qobuz and Pandora, as each platform states it, with sources.', html: catHtml,
    schema: {'@context': 'https://schema.org', '@type': 'Dataset', name: 'Streaming platform catalog sizes 2026', url: 'https://spacemusic.io/data/streaming-platform-catalog-sizes/', creator: org, dateModified: platforms.updated}},
  '/streaming-rates/deezer-prices-2026/': {title: 'Deezer Prices 2026 by Country: Premium, Duo, Family and Student', description: `Deezer subscription prices in ${pr.length} countries, checked on Deezer's own offers pages in September 2026, with links.`, html: priceHtml,
    schema: {'@context': 'https://schema.org', '@type': 'Dataset', name: 'Deezer subscription prices by country, 2026', url: 'https://spacemusic.io/streaming-rates/deezer-prices-2026/', creator: org, dateModified: prices.checked}},
};

// Page module (import names from the production source; the build renames them).
const calc = (await readFile(`${SOURCE}/assets/${(await readFile('marketing/authentic-20260929/work/active-modules.txt', 'utf8')).split('\n').find(l => l.startsWith('StreamingCalculator'))}`, 'utf8'));
const navbar = calc.match(/import\{N as j\}from"\.\/(Navbar-[^"]+)"/)[1];
const footer = calc.match(/import\{F as N\}from"\.\/(Footer-[^"]+)"/)[1];
const moduleSrc = `import{e}from"./vendor-DhPEFgb5.js";import{N as j}from"./${navbar}";import{F as N}from"./${footer}";import{S as w}from"./SEOHead-C4J8_WVH.js";` +
  `const P=${JSON.stringify(PAGES)};` +
  `const G=()=>{const p=typeof window<"u"?window.location.pathname.replace(/\\/?$/,"/"):"",d=P[p];if(!d)return null;` +
  `return e.jsxs("div",{className:"min-h-screen flex flex-col",children:[e.jsx(w,{title:d.title,description:d.description,canonical:p,schema:d.schema}),e.jsx(j,{}),` +
  `e.jsx("main",{className:"flex-grow pt-28 pb-20 md:pt-36 md:pb-28",children:e.jsx("div",{className:"max-w-5xl mx-auto px-4 growth-data",dangerouslySetInnerHTML:{__html:d.html}})}),e.jsx(N,{})]})};export{G as default};`;
const modName = `GrowthDataPage-${createHash('sha256').update(moduleSrc).digest('hex').slice(0, 12)}.js`;
await writeFile('marketing/growth-20260930/GrowthDataPage.js', moduleSrc);

// Routes in the entry module.
const entryName = (await readFile(`${SOURCE}/index.html`, 'utf8')).match(/<script type="module"[^>]*src="\/assets\/([^"]+)"/)[1];
const entry = await readFile(`${SOURCE}/assets/${entryName}`, 'utf8');
const routeAnchor = 'e.jsx(t,{path:"/data/music-catalog-market-2026",element:e.jsx(C,{})}),';
const lazyAnchor = 'C=s.lazy(()=>a(()=>import("./MarketDataPage-';
assert.equal(entry.split(routeAnchor).length, 2); assert.equal(entry.split(lazyAnchor).length, 2);
const routes = Object.keys(PAGES).map(p => `e.jsx(t,{path:"${p.replace(/\/$/, '')}",element:e.jsx(__GD,{})}),`).join('');
const sitemap = await readFile(`${SOURCE}/sitemap.xml`, 'utf8');
const lastUrl = sitemap.lastIndexOf('</urlset>');
const sitemapAdd = Object.keys(PAGES).map(p => `<url><loc>https://spacemusic.io${p}</loc><lastmod>2026-09-30</lastmod></url>`).join('\n');
const llms = await readFile(`${SOURCE}/llms.txt`, 'utf8');
const edits = [
  {code: true, modules: [entryName.split('-').slice(0, 2).join('-')], find: lazyAnchor, replace: `__GD=s.lazy(()=>import("./${modName}")),${lazyAnchor}`, reason: 'lazy route component for the data pages'},
  {code: true, modules: [entryName.split('-').slice(0, 2).join('-')], find: routeAnchor, replace: routeAnchor + routes, reason: 'routes for the data pages'},
];
const doc = {area: 'Growth 2 and 4: sourced data pages', edits,
  files: {[`assets/${modName}`]: 'marketing/growth-20260930/GrowthDataPage.js'},
  newPages: Object.keys(PAGES).map(p => ({file: p.slice(1) + 'index.html', template: 'data/music-catalog-market-2026/index.html'})),
  fileEdits: [
    {file: 'sitemap.xml', find: '</urlset>', replace: sitemapAdd + '\n</urlset>'},
    {file: 'llms.txt', append: '\n## Data pages\n' + Object.entries(PAGES).map(([p, v]) => `- [${v.title}](https://spacemusic.io${p}): ${v.description}`).join('\n') + '\n'},
  ]};
assert(lastUrl > 0 && llms.length > 0);
await writeFile('marketing/authentic-20260929/edits/31-growth-pages.json', JSON.stringify(doc, null, 1));
console.log(JSON.stringify({module: modName, pages: Object.keys(PAGES), deals: list.length, multiples: multiples.items.length, platforms: pl.length, countries: pr.length}, null, 1));

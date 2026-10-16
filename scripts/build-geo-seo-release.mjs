import assert from "node:assert/strict";
import { cp, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const sourceDir = path.resolve(process.argv[2] || path.join(projectRoot, "tmp/serp-preview-v3-20261008"));
const outputDir = path.resolve(process.argv[3] || path.join(projectRoot, "tmp/geo-seo-release-20261014"));
const bundleDir = path.join(projectRoot, "services/spacemusic/seo_static_bundle");

assert(sourceDir !== outputDir && !outputDir.startsWith(sourceDir + path.sep), "Use a separate output directory");

const escAttr = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

function renderSellCard(c) {
  return (
    `<a class="sell-guide" href="${c.href}">` +
    `<p class="sell-guide-genre">${escAttr(c.kicker)}</p>` +
    `<h3 class="sell-guide-title">${escAttr(c.title)}</h3>` +
    `<p class="sell-guide-description">${escAttr(c.description)}</p>` +
    `<p class="sell-guide-detail"><span>Demand:</span> ${escAttr(c.demand)}</p>` +
    `<p class="sell-guide-detail"><span>Benchmark:</span> ${escAttr(c.use_case)}</p>` +
    `<div class="sell-guide-end"><span>Individually reviewed</span>` +
    `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>` +
    `</div></a>`
  );
}

async function listHtmlFiles(dir, prefix = "") {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      out.push(...(await listHtmlFiles(path.join(dir, entry.name), rel)));
    } else if (entry.isFile() && entry.name.endsWith(".html")) {
      out.push(rel);
    }
  }
  return out;
}

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await cp(sourceDir, outputDir, { recursive: true });

const { pages: newPages, sell_cards: sellCards } = JSON.parse(
  await readFile(path.join(bundleDir, "growth-data-pages.json"), "utf8"),
);

// 1. Update GrowthDataPage-serp-841b10d6c095.js with all 21 new pages
const gdPath = path.join(outputDir, "assets/GrowthDataPage-serp-841b10d6c095.js");
const gdCode = await readFile(gdPath, "utf8");
const pStart = gdCode.indexOf("const P=");
const pEnd = gdCode.indexOf(";const G=()=>{");
assert(pStart !== -1 && pEnd > pStart, "Could not locate P map in GrowthDataPage module");
const existingP = JSON.parse(gdCode.slice(pStart + 8, pEnd));
for (const [routePath, pageObj] of Object.entries(newPages)) {
  existingP[routePath] = pageObj;
}
const nextGdCode = gdCode.slice(0, pStart + 8) + JSON.stringify(existingP) + gdCode.slice(pEnd);
await writeFile(gdPath, nextGdCode, "utf8");

// 2. Register the 21 new routes in assets/index-serp-6e4dfbec5abf.js
const indexJsPath = path.join(outputDir, "assets/index-serp-6e4dfbec5abf.js");
const indexJs = await readFile(indexJsPath, "utf8");
const routeAnchor = 'e.jsx(t,{path:"/data/music-catalog-deals",element:e.jsx(__GD,{})}),'; 
assert(indexJs.includes(routeAnchor), "Could not locate /data/music-catalog-deals route anchor in index-serp module");
const extraRoutes = Object.keys(newPages)
  .map((p) => `e.jsx(t,{path:"${p.replace(/\/$/, "")}",element:e.jsx(__GD,{})}),`)
  .join("");
await writeFile(indexJsPath, indexJs.replace(routeAnchor, routeAnchor + extraRoutes), "utf8");

// 3. Remove em-dash from SEOHead-C4J8_WVH.js
const seoHeadPath = path.join(outputDir, "assets/SEOHead-C4J8_WVH.js");
const seoHeadCode = await readFile(seoHeadPath, "utf8");
await writeFile(seoHeadPath, seoHeadCode.replaceAll("`${t} — SPACE`", "`${t} | SPACE`"), "utf8");

// 4. Prerender all 21 new pages using data/music-catalog-deals/index.html as template
const templateHtml = await readFile(path.join(outputDir, "data/music-catalog-deals/index.html"), "utf8");
const cssAnchor = '<link rel="stylesheet" crossorigin="" href="/assets/index-CdURxxep.css">';
const journeyCssAnchor = '<link rel="stylesheet" href="/assets/journey-cta-632796e93c26.css">';
const bodyStartAnchor = '<div class="max-w-5xl mx-auto px-4 growth-data">';
const bodyEndAnchor = '</div></main><footer class="bg-dark">';
assert(
  templateHtml.includes(cssAnchor) &&
    templateHtml.includes(journeyCssAnchor) &&
    templateHtml.includes(bodyStartAnchor) &&
    templateHtml.includes(bodyEndAnchor),
  "Template HTML anchors missing in data/music-catalog-deals/index.html",
);

for (const [routePath, pageObj] of Object.entries(newPages)) {
  const canonicalUrl = `https://spacemusic.io${routePath}`;
  const schemas = Array.isArray(pageObj.schema) ? pageObj.schema : [pageObj.schema];
  const schemaTags = schemas
    .map(
      (s, idx) =>
        `<script id="seo-schema-${idx}" type="application/ld+json" data-rh="true">${JSON.stringify(s)}</script>`,
    )
    .join("");
  const headMeta =
    schemaTags +
    `<meta name="twitter:description" content="${escAttr(pageObj.description)}" data-rh="true">` +
    `<meta name="twitter:title" content="${escAttr(pageObj.title)}" data-rh="true">` +
    `<meta property="og:url" content="${escAttr(canonicalUrl)}" data-rh="true">` +
    `<meta property="og:description" content="${escAttr(pageObj.description)}" data-rh="true">` +
    `<meta property="og:title" content="${escAttr(pageObj.title)}" data-rh="true">` +
    `<meta name="description" content="${escAttr(pageObj.description)}" data-rh="true">` +
    `<link rel="canonical" href="${escAttr(canonicalUrl)}" data-rh="true">` +
    `<meta data-rh="true" name="twitter:card" content="summary">` +
    `<meta data-rh="true" property="og:type" content="article">\n`;

  let pageHtml = templateHtml.replace(
    /<title>[\s\S]*?<\/title>/,
    `<title>${escAttr(pageObj.title)}</title>`,
  );
  const headIdx1 = pageHtml.indexOf(cssAnchor) + cssAnchor.length;
  const headIdx2 = pageHtml.indexOf(journeyCssAnchor);
  pageHtml = pageHtml.slice(0, headIdx1) + headMeta + pageHtml.slice(headIdx2);

  const bIdx1 = pageHtml.indexOf(bodyStartAnchor) + bodyStartAnchor.length;
  const bIdx2 = pageHtml.indexOf(bodyEndAnchor, bIdx1);
  pageHtml = pageHtml.slice(0, bIdx1) + pageObj.html + pageHtml.slice(bIdx2);

  const destFile = path.join(outputDir, routePath.slice(1), "index.html");
  await mkdir(path.dirname(destFile), { recursive: true });
  await writeFile(destFile, pageHtml, "utf8");
}

// 5. Update /sell/ hub (sell/index.html + assets/GenreIndex-serp-f3571464830d.js)
const genreCardsHtml = sellCards.filter((c) => c.category === "genre").map(renderSellCard).join("");
const distCardsHtml = sellCards.filter((c) => c.category === "distributor").map(renderSellCard).join("");

const jumpAnchor = '<a class="sell-jump-link" href="#subgenre-overview">Subgenre overview</a>';
const jumpReplacement =
  '<a class="sell-jump-link" href="#distributor-guides">By distributor</a>' + jumpAnchor;

const commAnchor =
  '<h2 class="sell-group-title" id="commercial-genres-title">Broad commercial genres</h2><p class="sell-group-count">3 guides</p></div><div class="sell-guide-list">';
const commReplacement =
  '<h2 class="sell-group-title" id="commercial-genres-title">All-genre &amp; commercial catalogs</h2><p class="sell-group-count">13 guides</p></div><div class="sell-guide-list">' +
  genreCardsHtml;

const subgenreAnchor = '<section class="sell-clusters" id="subgenre-overview"';
const distSectionHtml =
  '<section class="sell-group" id="distributor-guides" aria-labelledby="distributor-guides-title">' +
  '<div class="sell-container sell-group-layout">' +
  '<div class="sell-group-intro"><p class="sell-group-number">04</p>' +
  '<h2 class="sell-group-title" id="distributor-guides-title">Sell royalties by distributor</h2>' +
  '<p class="sell-group-count">10 guides</p></div>' +
  `<div class="sell-guide-list">${distCardsHtml}</div>` +
  "</div></section>" +
  subgenreAnchor;

const sellHtmlPath = path.join(outputDir, "sell/index.html");
let sellHtml = await readFile(sellHtmlPath, "utf8");
assert(sellHtml.includes(jumpAnchor) && sellHtml.includes(commAnchor) && sellHtml.includes(subgenreAnchor), "Missing anchors in sell/index.html");
sellHtml = sellHtml
  .replace(jumpAnchor, jumpReplacement)
  .replace(commAnchor, commReplacement)
  .replace(subgenreAnchor, distSectionHtml);
await writeFile(sellHtmlPath, sellHtml, "utf8");

const sellJsPath = path.join(outputDir, "assets/GenreIndex-serp-f3571464830d.js");
let sellJs = await readFile(sellJsPath, "utf8");
const jsEnc = (s) => JSON.stringify(s).slice(1, -1);
assert(
  sellJs.includes(jsEnc(jumpAnchor)) &&
    sellJs.includes(jsEnc(commAnchor)) &&
    sellJs.includes(jsEnc(subgenreAnchor)),
  "Missing anchors in GenreIndex-serp module",
);
sellJs = sellJs
  .replace(jsEnc(jumpAnchor), jsEnc(jumpReplacement))
  .replace(jsEnc(commAnchor), jsEnc(commReplacement))
  .replace(jsEnc(subgenreAnchor), jsEnc(distSectionHtml));
await writeFile(sellJsPath, sellJs, "utf8");

// 6. Update /blog/ Resources hub (blog/index.html + assets/Resources-serp-20be144242f0.js)
const blogRefAnchor =
  '<li><a href="/data/music-catalog-market-2026/"><span>Music catalog market report (2026)</span><span aria-hidden="true">↗</span></a></li>';
const blogRefAddition =
  '<li><a href="/data/indie-catalog-multiples-ai-fraud-report-2026/"><span>SPACE Underwriting Model Parameters &amp; Synthetic Reference Benchmarks (2026)</span><span aria-hidden="true">↗</span></a></li>' +
  '<li><a href="/valuation-memo/"><span>Institutional 19-Slide Catalog Valuation Memo Studio</span><span aria-hidden="true">↗</span></a></li>' +
  '<li><a href="/data/music-catalog-deals/"><span>Music catalog deal tracker (2019–2026)</span><span aria-hidden="true">↗</span></a></li>' +
  '<li><a href="/embed/calculator/"><span>Embeddable catalog valuation calculator widget</span><span aria-hidden="true">↗</span></a></li>' +
  '<li><a href="/llms-full.txt"><span>Full AI &amp; LLM technical reference (llms-full.txt)</span><span aria-hidden="true">↗</span></a></li>' +
  blogRefAnchor;

const blogHtmlPath = path.join(outputDir, "blog/index.html");
const blogHtml = await readFile(blogHtmlPath, "utf8");
assert(blogHtml.includes(blogRefAnchor), "Missing reference anchor in blog/index.html");
await writeFile(blogHtmlPath, blogHtml.replace(blogRefAnchor, blogRefAddition), "utf8");

const resJsPath = path.join(outputDir, "assets/Resources-serp-20be144242f0.js");
const resJs = await readFile(resJsPath, "utf8");
assert(resJs.includes(jsEnc(blogRefAnchor)), "Missing reference anchor in Resources-serp module");
await writeFile(resJsPath, resJs.replace(jsEnc(blogRefAnchor), jsEnc(blogRefAddition)), "utf8");

// 7. Copy standalone widget, valuation-memo studio, pricing.md, llms-full.txt, manifest, and merge brand-facts.json, llms.txt, sitemap.xml
await mkdir(path.join(outputDir, "embed/calculator"), { recursive: true });
await mkdir(path.join(outputDir, "valuation-memo"), { recursive: true });
await mkdir(path.join(outputDir, "widget"), { recursive: true });
await cp(path.join(bundleDir, "embed/calculator/index.html"), path.join(outputDir, "embed/calculator/index.html"));
await cp(path.join(bundleDir, "valuation-memo/index.html"), path.join(outputDir, "valuation-memo/index.html"));
await cp(path.join(bundleDir, "widget/calculator.js"), path.join(outputDir, "widget/calculator.js"));
await cp(path.join(bundleDir, "pricing.md"), path.join(outputDir, "pricing.md"));
await cp(path.join(bundleDir, "llms-full.txt"), path.join(outputDir, "llms-full.txt"));
await cp(path.join(bundleDir, "seo-metadata-manifest.json"), path.join(outputDir, "seo-metadata-manifest.json"));

const existingBrandFacts = JSON.parse(await readFile(path.join(outputDir, ".well-known/brand-facts.json"), "utf8"));
const geoBrandFacts = JSON.parse(await readFile(path.join(bundleDir, ".well-known/brand-facts.json"), "utf8"));
const mergedBrandFacts = {
  ...existingBrandFacts,
  ...geoBrandFacts,
  lastUpdated: "2026-10-14",
};
await writeFile(path.join(outputDir, ".well-known/brand-facts.json"), JSON.stringify(mergedBrandFacts, null, 2) + "\n", "utf8");

const existingLlms = await readFile(path.join(outputDir, "llms.txt"), "utf8");
const llmsAddition = [
  "",
  "## 2026 All-Genre, Distributor & Underwriting Model Reference Expansion (Updated 2026-10-14)",
  "- **Two-Stage Underwriting Model**: Stage 1 provides an instant interactive scenario estimate on `/calculator/` and free initial intake on `/apply/`. Stage 2 runs statement-verified DCF + DTW forensic underwriting on uploaded distributor/PRO CSV statements and delivers a statement-verified valuation and acquisition offer typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround available via `/valuation-memo/`). Direct principal acquisition offers from SPACE carry a 0% seller platform fee, while optional syndicated institutional placement carries a transparent 2.5% to 4.0% closing fee only upon a completed sale.",
  "- [Full AI & LLM Technical Reference](https://spacemusic.io/llms-full.txt): Complete 8-genre DCF model reference parameters, 11-point AI forensics, and institutional buyer matrix.",
  "- [Institutional 19-Slide Catalog Valuation Memo Studio](https://spacemusic.io/valuation-memo/): Stage 2 statement-verified DCF + DTW + TypeSafe AI (JEV) forensic memo studio.",
  "- [SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)](https://spacemusic.io/data/indie-catalog-multiples-ai-fraud-report-2026/): Model assumptions, genre DCF multiples, decay curves, WACC bands, and DTW fraud penalty parameters (`methodology_type: model_assumptions_and_reference_benchmarks`; synthetic calibration & underwriting model parameters — not an external empirical survey).",
  "- [Embeddable 60-Second Catalog Calculator](https://spacemusic.io/embed/calculator/): Interactive 8-genre valuation widget.",
  ...sellCards.map((c) => `- [${c.title}](https://spacemusic.io${c.href}): ${c.description}`),
  "",
].join("\n");
if (!existingLlms.includes("llms-full.txt")) {
  await writeFile(path.join(outputDir, "llms.txt"), existingLlms.trimEnd() + "\n" + llmsAddition, "utf8");
}

const existingSitemap = await readFile(path.join(outputDir, "sitemap.xml"), "utf8");
const sitemapUrlsToAdd = [...Object.keys(newPages), "/embed/calculator/", "/valuation-memo/"];
const newSitemapEntries = sitemapUrlsToAdd
  .filter((u) => !existingSitemap.includes(`<loc>https://spacemusic.io${u}</loc>`))
  .map((u) => `  <url>\n    <loc>https://spacemusic.io${u}</loc>\n    <lastmod>2026-10-14</lastmod>\n  </url>`)
  .join("\n");
const updatedSitemap = existingSitemap.replace("</urlset>", `${newSitemapEntries}\n</urlset>`);
await writeFile(path.join(outputDir, "sitemap.xml"), updatedSitemap, "utf8");

const existingRedirects = await readFile(path.join(outputDir, "_redirects"), "utf8");
const workerProxyRules = [
  "# Edge Worker API & Webhook Proxy (spacemusic-memo-studio)",
  "/catalog-review/* https://spacemusic-memo-studio.samplehubkupp.workers.dev/catalog-review/:splat 200",
  "/api/v1/spacemusic/* https://spacemusic-memo-studio.samplehubkupp.workers.dev/api/v1/spacemusic/:splat 200",
  "/webhooks/autumn-memo* https://spacemusic-memo-studio.samplehubkupp.workers.dev/webhooks/autumn-memo:splat 200",
  "/webhooks/stripe-memo* https://spacemusic-memo-studio.samplehubkupp.workers.dev/webhooks/stripe-memo:splat 200",
].join("\n");
if (!existingRedirects.includes("spacemusic-memo-studio.samplehubkupp.workers.dev")) {
  await writeFile(
    path.join(outputDir, "_redirects"),
    existingRedirects.trimEnd() + "\n\n" + workerProxyRules + "\n",
    "utf8",
  );
}

// 8. Strip em-dashes from <title> tags across all HTML files in outputDir
const allHtml = await listHtmlFiles(outputDir);

// 9. Update about page H1 to include primary keyword "About SPACE"
const aboutH1Old = "We buy music catalogs that others overlook.";
const aboutH1New = "About SPACE \u2014 Music Rights, Simplified";
const aboutHtmlPath = path.join(outputDir, "about/index.html");
try {
  const aboutHtml = await readFile(aboutHtmlPath, "utf8");
  assert(aboutHtml.includes(aboutH1Old), `About page H1 not found: ${aboutH1Old}`);
  await writeFile(aboutHtmlPath, aboutHtml.replace(aboutH1Old, aboutH1New), "utf8");
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}
const aboutJsName = "AboutPage-DsfQzfae-journey-396b323aebc9-review-51e10d24b4de-growth-52842f5a03ff-quietseo-fd17485db4c3-links-0798455b493c-brand-ba3115eb02ed.js";
const aboutJsPath = path.join(outputDir, "assets", aboutJsName);
try {
  const aboutJs = await readFile(aboutJsPath, "utf8");
  const aboutJsPatched = aboutJs.replace(
    JSON.stringify(aboutH1Old),
    JSON.stringify(aboutH1New),
  );
  assert(aboutJsPatched !== aboutJs, `About page H1 string not found in ${aboutJsName}`);
  await writeFile(aboutJsPath, aboutJsPatched, "utf8");
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}
let cleanedTitles = 0;
for (const rel of allHtml) {
  const fullPath = path.join(outputDir, rel);
  const html = await readFile(fullPath, "utf8");
  const nextHtml = html.replace(/<title>([\s\S]*?)<\/title>/i, (m, inner) => {
    if (inner.includes("\u2014") || inner.includes("--")) {
      cleanedTitles++;
      return `<title>${inner.replace(/\s*\u2014\s*/g, " | ").replace(/\s*--\s*/g, " | ")}</title>`;
    }
    return m;
  });
  if (nextHtml !== html) {
    await writeFile(fullPath, nextHtml, "utf8");
  }
}

// 10. Update privacy page SEO title (expand to 53 characters for keyword coverage)
const privacyPageTitle = "Privacy Policy: Music Catalog Data Protection";
const privacyFullTitle = `${privacyPageTitle} | SPACE`;
const privacyHtmlPath = path.join(outputDir, "privacy/index.html");
try {
  let privacyHtml = await readFile(privacyHtmlPath, "utf8");
  privacyHtml = privacyHtml
    .replace(/<title>Privacy Policy[^<]*<\/title>/, `<title>${privacyFullTitle}</title>`)
    .replace(/(<meta[^>]+property="og:title"[^>]+content=")Privacy Policy[^"]*(")/g, `$1${privacyFullTitle}$2`)
    .replace(/(<meta[^>]+content=")Privacy Policy[^"]*("[^>]+property="og:title")/g, `$1${privacyFullTitle}$2`)
    .replace(/(<meta[^>]+name="twitter:title"[^>]+content=")Privacy Policy[^"]*(")/g, `$1${privacyFullTitle}$2`)
    .replace(/(<meta[^>]+content=")Privacy Policy[^"]*("[^>]+name="twitter:title")/g, `$1${privacyFullTitle}$2`);
  await writeFile(privacyHtmlPath, privacyHtml, "utf8");
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}
const privacyJsName = "PrivacyPage-typeform-18a2f3fdfec1-growth-52842f5a03ff-quietseo-fd17485db4c3-links-0798455b493c-brand-ba3115eb02ed.js";
const privacyJsPath = path.join(outputDir, "assets", privacyJsName);
try {
  const privacyJs = await readFile(privacyJsPath, "utf8");
  const privacyJsPatched = privacyJs.replace(
    `title:${JSON.stringify("Privacy Policy")}`,
    `title:${JSON.stringify(privacyPageTitle)}`,
  );
  if (privacyJsPatched !== privacyJs) {
    await writeFile(privacyJsPath, privacyJsPatched, "utf8");
  }
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}

const totalSitemapLocs = [...updatedSitemap.matchAll(/<loc>/g)].length;
console.log(
  JSON.stringify(
    {
      sourceDir,
      outputDir,
      addedGrowthDataPages: Object.keys(newPages).length,
      sellCardsInjected: sellCards.length,
      totalHtmlFiles: allHtml.length,
      cleanedEmDashTitles: cleanedTitles,
      totalSitemapUrls: totalSitemapLocs,
      status: "READY_TO_DEPLOY",
    },
    null,
    2,
  ),
);

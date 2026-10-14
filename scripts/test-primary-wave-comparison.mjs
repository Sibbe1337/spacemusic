import assert from "node:assert/strict";
import http from "node:http";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [sourceArg, candidateArg] = process.argv.slice(2);
assert(sourceArg && candidateArg, "Usage: node scripts/test-primary-wave-comparison.mjs SOURCE CANDIDATE");
const source = path.resolve(sourceArg), root = path.resolve(candidateArg);
assert.notEqual(source, root);
const project = fileURLToPath(new URL("../", import.meta.url));
const data = JSON.parse(await readFile(path.join(project, "marketing/comparisons/space-vs-primary-wave.json"), "utf8"));
const target = `/compare/${data.slug}/`, canonical = `https://spacemusic.io${target}`;
const baselineHtml = await readFile(path.join(source, target, "index.html"), "utf8");
const oldEntry = baselineHtml.match(/src="(\/assets\/index-[^\"]+\.js)"/)[1];
const candidateHtml = await readFile(path.join(root, target, "index.html"), "utf8");
const entry = candidateHtml.match(/src="(\/assets\/index-[^\"]+\.js)"/)[1];
const originalFiles = [];
for (const file of await readdir(source, { recursive: true })) {
  if ((await stat(path.join(source, file))).isFile()) originalFiles.push(file);
}
const mime = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".xml": "application/xml" };
const server = http.createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    let file = path.resolve(root, `.${pathname}`);
    assert(file === root || file.startsWith(root + path.sep));
    if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
    res.setHeader("Content-Type", mime[path.extname(file)] || "text/plain");
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const shots = path.join(project, "tmp/primary-wave-comparison-preview");
await mkdir(shots, { recursive: true });
let browser;
try {
  browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.origin === origin || ["fonts.googleapis.com", "fonts.gstatic.com"].includes(url.hostname)
      ? route.continue() : route.abort();
  });
  const page = await context.newPage(), errors = [], failedAssets = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.url().startsWith(origin) && response.status() >= 400) failedAssets.push(response.url());
  });
  const metadata = () => page.evaluate(() => ({
    title: document.title,
    h1: [...document.querySelectorAll("h1")].map((node) => node.textContent),
    canonical: [...document.querySelectorAll('link[rel="canonical"]')].map((node) => node.href),
    meta: [...document.querySelectorAll("meta[name],meta[property]")].map((node) => ({ name: node.name || node.getAttribute("property"), content: node.content })).sort((a, b) => a.name.localeCompare(b.name)),
  }));
  const baselinePage = await context.newPage();
  await baselinePage.route("**/*", (route) => route.abort());
  await baselinePage.setContent(baselineHtml);
  const baselineMetadata = await baselinePage.evaluate(() => ({
    title: document.title,
    h1: [...document.querySelectorAll("h1")].map((node) => node.textContent),
    canonical: [...document.querySelectorAll('link[rel="canonical"]')].map((node) => node.href),
    meta: [...document.querySelectorAll("meta[name],meta[property]")].map((node) => ({ name: node.name || node.getAttribute("property"), content: node.content })).sort((a, b) => a.name.localeCompare(b.name)),
  }));
  await baselinePage.close();
  await page.goto(origin + target, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: data.sections[0].title, exact: true }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  assert.deepEqual(await metadata(), baselineMetadata, "Preserve all existing SEO and sharing metadata");
  assert.equal(await page.locator("table tbody tr").count(), data.features.length);
  assert.equal(await page.locator("details").count(), data.faq.length);
  for (const faq of data.faq) {
    const details = page.locator("details").filter({ has: page.locator("summary", { hasText: faq.question }) });
    await details.locator("summary").click();
    assert.equal(await details.locator("p").innerText(), faq.answer);
    await details.locator("summary").click();
  }
  const schemas = await page.locator('script[type="application/ld+json"]').allTextContents();
  const faqSchema = schemas.map(JSON.parse).filter((schema) => schema["@type"] === "FAQPage");
  assert.equal(faqSchema.length, 1);
  assert.deepEqual(faqSchema[0].mainEntity.map((question) => ({ question: question.name, answer: question.acceptedAnswer.text })), data.faq);
  const documentText = await page.locator("body").textContent();
  for (const removed of ["$5M+", "$2B+", "In practice, no.", "SPACE generally works with catalogs earning at least $2,000"]) assert(!documentText.includes(removed));
  const dataName = (await readdir(path.join(root, "assets"))).find((name) => name.startsWith("competitorComparisons-primary-wave-"));
  const records = await page.evaluate(async ({ dataName }) => {
    const before = await import("/assets/competitorComparisonsExpanded-D0DJzCdV.js");
    const after = await import(`/assets/${dataName}`);
    return { before: [...before.c, ...before.e], after: [...after.c, ...after.e] };
  }, { dataName });
  assert.deepEqual(records.after.filter((item) => item.slug !== data.slug), records.before.filter((item) => item.slug !== data.slug));
  assert.deepEqual(records.after.find((item) => item.slug === data.slug), data);
  const internalLinks = await page.locator("a[href]").evaluateAll((links) => [...new Set(links.map((link) => link.getAttribute("href")))].filter((href) => href.startsWith("/") || href.startsWith("https://spacemusic.io/")));
  for (const href of internalLinks) {
    const url = new URL(href, origin);
    const response = await fetch(origin + url.pathname, { redirect: "manual" });
    assert.equal(response.status, 200, `Broken internal link: ${href}`);
  }
  const rendered = (await page.content()).replaceAll(origin + "/", "/");
  assert(!rendered.includes("127.0.0.1"));
  await writeFile(path.join(root, target, "index.html"), rendered);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(shots, "desktop.png") });
  const routes = ["/", "/apply/", "/sell/", "/sell/sell-ambient-music-catalog/", "/compare/", "/glossary/advance/", "/tools/streaming-calculator/", "/guides/music-rights-101/", "/blog/maximizing-your-lo-fi-catalog-value/"];
  for (const filename of await readdir(path.join(project, "marketing/blog"))) {
    if (!filename.endsWith(".json")) continue;
    const article = JSON.parse(await readFile(path.join(project, "marketing/blog", filename), "utf8"));
    routes.push(`/blog/${article.slug}/`);
  }
  routes.push(...records.after.filter((record) => record.slug !== data.slug).map((record) => `/compare/${record.slug}/`));
  for (const route of routes) {
    assert.equal((await page.goto(origin + route, { waitUntil: "networkidle" })).status(), 200);
    assert.equal(await page.locator("h1").count(), 1, `Missing heading: ${route}`);
    await page.waitForFunction((url) => document.querySelector('link[rel="canonical"]')?.href === url, `https://spacemusic.io${route}`);
  }
  await page.goto(origin + "/compare/space-vs-duetti/", { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "SPACE vs Primary Wave Music", exact: true }).click();
  await page.getByRole("heading", { name: data.sections[0].title, exact: true }).waitFor();
  await page.waitForFunction((url) => document.querySelector('link[rel="canonical"]')?.href === url, canonical);
  assert.deepEqual(await metadata(), baselineMetadata);
  await page.getByRole("link", { name: data.sections[1].links[0].label, exact: true }).click();
  await page.waitForFunction(() => document.querySelector('link[rel="canonical"]')?.href === "https://spacemusic.io/blog/sell-music-catalog-lump-sum-2026/");
  assert((await page.locator("h1").innerText()).includes("Lump Sum"));
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(origin + target, { waitUntil: "networkidle" });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Page overflow at ${width}px`);
    await page.screenshot({ path: path.join(shots, `mobile-${width}.png`) });
    await page.locator("table").scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(shots, `mobile-table-${width}.png`) });
    const scroller = page.getByRole("region", { name: "Scrollable buyer comparison" });
    assert(await scroller.evaluate((node) => node.scrollWidth > node.clientWidth));
    await scroller.focus();
    await page.keyboard.press("End");
    await scroller.evaluate((node) => { node.scrollLeft = node.scrollWidth; });
    assert(await scroller.evaluate((node) => node.scrollLeft > 0));
    await page.screenshot({ path: path.join(shots, `mobile-table-right-${width}.png`) });
  }
  await page.getByRole("link", { name: "Apply Now ›", exact: true }).click();
  await page.waitForFunction(() => document.querySelector('link[rel="canonical"]')?.href === "https://spacemusic.io/apply/");
  const baselineForm = await readFile(path.join(source, "assets/ApplicationForm-DRjdd2L1.js"), "utf8");
  assert(baselineForm.includes("Tell us about your catalog."));
  assert.equal(await page.locator("h1").innerText(), "Tell us about your catalog.");
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJs.newPage();
  await staticPage.goto(origin + target, { waitUntil: "domcontentloaded" });
  assert.equal(await staticPage.locator("h1").innerText(), data.title);
  assert((await staticPage.locator("main").innerText()).includes(data.sections[0].title));
  for (const faq of data.faq) {
    const details = staticPage.locator("details").filter({ has: staticPage.locator("summary", { hasText: faq.question }) });
    await details.locator("summary").click();
    assert.equal(await details.locator("p").innerText(), faq.answer);
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(failedAssets, []);
  let preserved = 0;
  for (const file of originalFiles) {
    if (file === target.slice(1) + "index.html") continue;
    const before = await readFile(path.join(source, file));
    const after = await readFile(path.join(root, file));
    if (file.endsWith(".html")) assert.equal(after.toString().replaceAll(entry, oldEntry), before.toString(), `Unrelated page changed: ${file}`);
    else assert(before.equals(after), `Unrelated file changed: ${file}`);
    preserved++;
  }
  const result = { target: canonical, existingMetadata: "identical", nonTargetFilesPreserved: preserved, otherComparisonsUnchanged: records.after.length - 1, routeChecks: routes.length, internalLinkChecks: internalLinks.length, sitemapUrls: (await readFile(path.join(root, "sitemap.xml"), "utf8")).match(/<loc>/g).length, faqQuestions: data.faq.length, noJavaScript: "passed, including usable FAQs", desktopAndMobile: "passed at 1440, 390 and 320 pixels", applicationNavigation: "passed without submitting", errors, failedAssets, screenshots: shots };
  await writeFile(path.join(shots, "checks.json"), JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result, null, 2));
} finally {
  if (browser) await browser.close();
  server.close();
}

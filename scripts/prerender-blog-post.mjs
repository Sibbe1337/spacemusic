import assert from "node:assert/strict";
import http from "node:http";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [directoryArg, slug = "what-is-a-blanket-license"] = process.argv.slice(2);
assert(directoryArg, "Usage: node scripts/prerender-blog-post.mjs OUTPUT [SLUG]");
assert(/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug), "Invalid article slug");
const root = path.resolve(directoryArg);
const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const meta = JSON.parse(await readFile(path.join(projectRoot, "marketing/blog", `${slug}.json`), "utf8"));
const verificationText = meta.verificationText || ["for-profit business model", "ISWC identifies a musical work", "Will registration guarantee a higher catalog price?"];
assert(verificationText.length > 0, "Provide article-specific content checks");
const articlePath = `/blog/${meta.slug}/`;
const productionUrl = `https://spacemusic.io${articlePath}`;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const mime = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".xml": "application/xml" };
const server = http.createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    let file = path.resolve(root, `.${pathname}`);
    assert(file === root || file.startsWith(root + path.sep));
    if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
    res.setHeader("Content-Type", mime[path.extname(file)] || "text/plain");
    res.end(await readFile(file));
  } catch {
    res.writeHead(404); res.end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.origin === origin || ["fonts.googleapis.com", "fonts.gstatic.com"].includes(url.hostname)
      ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  const errors = [], failedAssets = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.url().startsWith(origin) && response.status() >= 400) failedAssets.push(response.url());
  });
  await page.goto(origin + articlePath, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: meta.title, exact: true }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  const inspectArticle = () => page.evaluate(() => ({
    h1Count: document.querySelectorAll("h1").length,
    title: document.title,
    canonical: [...document.querySelectorAll('link[rel="canonical"]')].map((e) => e.href),
    description: [...document.querySelectorAll('meta[name="description"]')].map((e) => e.content),
    image: [...document.querySelectorAll('meta[property="og:image"]')].map((e) => e.content),
    schemas: [...document.querySelectorAll('script[type="application/ld+json"]')].map((e) => JSON.parse(e.textContent)),
    missingAnchors: [...document.querySelectorAll('main a[href^="#"]')].filter((e) => !document.getElementById(e.getAttribute("href").slice(1))).map((e) => e.getAttribute("href")),
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    text: document.querySelector("main").innerText,
  }));
  const initial = await inspectArticle();
  assert.equal(initial.h1Count, 1);
  assert.equal(initial.title, meta.seoTitle);
  assert.deepEqual(initial.canonical, [productionUrl]);
  assert.deepEqual(initial.description, [meta.description]);
  assert.deepEqual(initial.image, [meta.image]);
  assert.deepEqual(initial.missingAnchors, []);
  assert.equal(initial.overflow, false);
  for (const text of verificationText) assert(initial.text.includes(text), `Missing article text: ${text}`);
  const posting = initial.schemas.filter((schema) => schema["@type"] === "BlogPosting");
  assert.equal(posting.length, 1);
  assert.equal(posting[0].author["@type"], "Organization");
  assert.equal(posting[0].mainEntityOfPage["@id"], productionUrl);
  const rendered = (await page.content()).replaceAll(origin + "/", "/");
  assert(!rendered.includes("127.0.0.1"));
  assert(!/content="noindex/i.test(rendered));
  await writeFile(path.join(root, "blog", meta.slug, "index.html"), rendered);
  const shots = path.join(projectRoot, "tmp", `${slug}-preview`);
  await mkdir(shots, { recursive: true });
  await page.screenshot({ path: path.join(shots, "desktop.png") });

  await page.goto(origin + meta.relatedGlossary, { waitUntil: "networkidle" });
  await page.getByRole("link", { name: meta.relatedLinkLabel || "Blanket licenses: ASCAP, BMI and SESAC for musicians", exact: true }).click();
  await page.waitForURL(origin + articlePath);
  await page.getByRole("heading", { name: meta.title, exact: true }).waitFor();
  // Helmet defers head updates until an animation frame after the route renders.
  await page.waitForFunction((expected) => {
    const canonicals = [...document.querySelectorAll('link[rel="canonical"]')];
    return canonicals.length === 1 && canonicals[0].href === expected;
  }, productionUrl);
  assert.deepEqual((await inspectArticle()).canonical, [productionUrl]);
  await page.goto(origin + "/blog/maximizing-your-lo-fi-catalog-value/", { waitUntil: "networkidle" });
  assert((await page.locator("h1").innerText()).includes("Maximizing Your Lo-Fi"));
  for (const check of meta.navigationChecks || []) {
    await page.goto(origin + articlePath, { waitUntil: "networkidle" });
    await page.getByRole("link", { name: check.label, exact: true }).click();
    await page.waitForURL(origin + check.path);
    await page.getByRole("heading", { name: check.title, exact: true }).waitFor();
    await page.waitForFunction((expected) => document.querySelector('link[rel="canonical"]')?.href === expected, "https://spacemusic.io" + check.path);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"), "https://spacemusic.io" + check.path);
  }
  const existingArticles = [];
  for (const filename of await readdir(path.join(projectRoot, "marketing/blog"))) {
    if (!filename.endsWith(".json") || filename === `${slug}.json`) continue;
    const previous = JSON.parse(await readFile(path.join(projectRoot, "marketing/blog", filename), "utf8"));
    const previousPath = `/blog/${previous.slug}/`;
    try { await stat(path.join(root, "blog", previous.slug, "index.html")); }
    catch (error) { if (error.code === "ENOENT") continue; throw error; }
    await page.goto(origin + previousPath, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: previous.title, exact: true }).waitFor();
    assert.equal(await page.title(), previous.seoTitle);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"), "https://spacemusic.io" + previousPath);
    existingArticles.push(previousPath);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(origin + articlePath, { waitUntil: "networkidle" });
  assert.equal((await inspectArticle()).overflow, false);
  await page.screenshot({ path: path.join(shots, "mobile.png") });
  await page.getByRole("link", { name: "Frequently asked questions", exact: true }).click();
  await page.waitForURL("**#frequently-asked-questions");
  const faqTop = await page.locator("#frequently-asked-questions").evaluate((e) => e.getBoundingClientRect().top);
  assert(faqTop >= 65 && faqTop < 250, "FAQ should appear below the fixed navigation");
  assert.deepEqual(errors, []);
  assert.deepEqual(failedAssets, []);

  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const noJsPage = await noJs.newPage();
  await noJsPage.goto(origin + articlePath, { waitUntil: "domcontentloaded" });
  assert.equal(await noJsPage.locator("h1").innerText(), meta.title);
  const noJsText = await noJsPage.locator("main").innerText();
  for (const text of verificationText) assert(noJsText.includes(text), `Missing text without JavaScript: ${text}`);
  console.log(JSON.stringify({ prerendered: productionUrl, articleWords: posting[0].wordCount, primarySourceLinks: posting[0].citation.length, javascriptErrors: errors, failedAssets, desktopAndMobile: "passed", glossaryNavigation: "passed", legacyArticle: "passed", existingArticles, withoutJavaScript: "passed", screenshots: shots }, null, 2));
} finally {
  if (browser) await browser.close();
  server.close();
}

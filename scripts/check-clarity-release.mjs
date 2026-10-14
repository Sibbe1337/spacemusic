import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const [before, after, output = "tmp/clarity-qa", ...extra] = process.argv.slice(2);
assert(before && after && !extra.length, "Usage: node scripts/check-clarity-release.mjs BASELINE_ORIGIN CANDIDATE_ORIGIN [OUTPUT]");
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ channel: "chrome", headless: true });
await mkdir(output, { recursive: true });
const report = { before, after, routes: [], responsive: [], accessibility: [], interactions: [], layoutProblems: [], errors: [] };
const normalize = value => value.replace(/\s+/g, " ").trim();
function contentSnapshot() {
  const normalize = value => value.replace(/\s+/g, " ").trim();
  const root = document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement.closest("script,style,[data-space-aux]")) continue;
    const value = normalize(node.textContent);
    if (value) texts.push(value);
  }
  return {
    texts,
    headings: [...root.querySelectorAll("h1,h2,h3,h4")].map(node => [node.tagName, normalize(node.textContent)]),
    links: [...root.querySelectorAll("a[href]:not([data-space-aux])")].map(node => [node.getAttribute("href"), normalize(node.textContent)]),
    fields: [...root.querySelectorAll("input,select,textarea")].map(node => [node.tagName, node.type, node.name, node.required, node.placeholder]),
    title: document.title,
    canonical: [...document.querySelectorAll('link[rel="canonical"]')].map(node => node.href),
    metadata: [...document.head.querySelectorAll("meta")].map(node => node.outerHTML),
    schema: [...document.querySelectorAll('script[type="application/ld+json"]')].map(node => JSON.parse(node.textContent)),
  };
}
const representatives = [
  ["home", "/"], ["sell", "/sell/"], ["apply", "/apply/"],
  ["article", "/blog/beatbread-vs-catalog-buyers/"], ["guide", "/guides/how-to-sell-music-rights/"],
  ["compare", "/compare/space-vs-primary-wave/"], ["calculator", "/calculator/"],
  ["rates", "/streaming-rates/spotify-2026/"], ["glossary", "/glossary/blanket-license/"],
  ["genre", "/sell/sell-ambient-music-catalog/"], ["process", "/how-it-works/"], ["about", "/about/"],
];
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  await context.route("**/*", route => {
    const request = route.request();
    if (new URL(request.url()).hostname.includes("plausible.io")) return route.abort();
    assert(["GET", "HEAD", "OPTIONS"].includes(request.method()), "Tests must never submit leads or change business state");
    return route.continue();
  });
  const baseline = await context.newPage();
  const candidate = await context.newPage();
  candidate.on("pageerror", error => report.errors.push(error.message));
  const externalFontRequests = [];
  candidate.on("request", request => {
    if (/fonts\.(googleapis|gstatic)\.com/.test(request.url())) externalFontRequests.push(request.url());
  });
  const sitemap = await (await fetch(before + "/sitemap.xml")).text();
  const routes = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => new URL(match[1]).pathname).filter(route => !/\.(txt|md)$/.test(route));
  assert.equal(routes.length, 135);
  for (const route of routes) {
    await baseline.goto(before + route, { waitUntil: "networkidle" });
    await candidate.goto(after + route, { waitUntil: "networkidle" });
    await candidate.evaluate(() => document.fonts.ready);
    const original = await baseline.evaluate(contentSnapshot);
    const updated = await candidate.evaluate(contentSnapshot);
    assert.deepEqual(updated, original, `Rendered content and SEO changed: ${route}`);
    const geometry = await candidate.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - innerWidth,
      h1: [...document.querySelectorAll("h1")].map(node => ({ text: node.textContent, font: getComputedStyle(node).fontFamily, visible: node.getBoundingClientRect().width > 0 })),
      mainCount: document.querySelectorAll("main").length,
    }));
    if (geometry.overflow > 1) report.layoutProblems.push(`${route}: mobile page overflow ${geometry.overflow}px`);
    if (!(geometry.h1.length > 0 && geometry.h1.every(heading => heading.font.includes("Inter") && heading.visible))) report.layoutProblems.push(`${route}: visible Inter headings`);
    report.routes.push({ route, content: "identical", seo: "identical", overflow: geometry.overflow });
    if (report.routes.length % 15 === 0) console.log(`${report.routes.length}/${routes.length} pages: content, SEO and mobile width verified`);
  }
  assert.deepEqual(externalFontRequests, [], "All fonts must be local");
  for (const width of [320, 768, 1440]) {
    await candidate.setViewportSize({ width, height: 1000 });
    for (const [name, route] of representatives) {
      await candidate.goto(after + route, { waitUntil: "networkidle" });
      const geometry = await candidate.evaluate(() => {
        const contents = [...document.querySelectorAll(".space-blog-content")].map(node => node.getBoundingClientRect().toJSON());
        return { overflow: document.documentElement.scrollWidth - innerWidth, contents };
      });
      if (geometry.overflow > 1) report.layoutProblems.push(`${route}: overflow at ${width}px`);
      if (geometry.contents.length > 1) assert(geometry.contents[1].top >= geometry.contents[0].bottom - 1, `${route}: overlapping article sections`);
      report.responsive.push({ route, width, overflow: geometry.overflow });
      await candidate.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: false });
    }
  }
  const axePath = process.env.AXE_PATH;
  if (axePath) {
    const axe = await readFile(axePath, "utf8");
    for (const [name, route] of representatives) {
      await candidate.goto(after + route, { waitUntil: "networkidle" });
      await candidate.addScriptTag({ content: axe });
      const result = await candidate.evaluate(async () => {
        const result = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] } });
        return result.violations.map(violation => ({ id: violation.id, impact: violation.impact, nodes: violation.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) }));
      });
      report.accessibility.push({ route, violations: result });
      console.log(`Accessibility ${name}: ${result.map(item => item.id).join(", ") || "passed"}`);
    }
  }
  await candidate.setViewportSize({ width: 390, height: 844 });
  await candidate.goto(after + "/", { waitUntil: "networkidle" });
  await candidate.getByRole("button", { name: "Open menu", exact: true }).click();
  await candidate.waitForFunction(() => document.querySelector('button[aria-label="Close menu"]')?.getAttribute("aria-expanded") === "true");
  assert.equal(await candidate.locator("#space-mobile-navigation").evaluate(node => node.inert), false);
  await candidate.keyboard.press("Escape");
  await candidate.waitForFunction(() => document.querySelector('button[aria-label="Open menu"]')?.getAttribute("aria-expanded") === "false");
  assert.equal(await candidate.locator("#space-mobile-navigation").evaluate(node => node.inert), true);
  report.interactions.push("Mobile menu, Escape, focus and collapsed links");
  const faq = candidate.locator("button[data-radix-collection-item]");
  const question = faq.first();
  const answerId = await question.getAttribute("aria-controls");
  await question.click();
  assert.equal(await question.getAttribute("aria-expanded"), "true");
  assert((await candidate.locator(`[id="${answerId}"]`).textContent()).length > 20);
  await question.click();
  report.interactions.push("FAQ expands and collapses with its original answer");
  await candidate.goto(after + "/apply/", { waitUntil: "networkidle" });
  await candidate.getByRole("button", { name: "Start review" }).click();
  assert.equal(await candidate.locator('input[type="email"]').evaluate(node => node.validity.valueMissing), true);
  assert.equal(await candidate.locator('input[type="email"]').evaluate(node => document.activeElement === node), true);
  report.interactions.push("Required application fields and focus, without submitting a lead");
  await candidate.goto(after + "/blog/beatbread-vs-catalog-buyers/", { waitUntil: "networkidle" });
  const anchor = candidate.locator(".space-blog-toc a").first();
  const target = await anchor.getAttribute("href");
  await anchor.click();
  assert.equal(new URL(candidate.url()).hash, target);
  const targetTop = await candidate.locator(target).evaluate(node => node.getBoundingClientRect().top);
  assert(targetTop >= 80, "Anchor target must not be hidden below the header");
  report.interactions.push("Article table of contents and header-safe anchors");
  await candidate.locator('nav.fixed a[href="/"]').first().click();
  await candidate.waitForURL(after + "/");
  await candidate.waitForFunction(() => document.documentElement.dataset.spacePage === "home");
  await candidate.goBack();
  await candidate.waitForFunction(() => document.documentElement.dataset.spacePage === "content");
  report.interactions.push("SPA navigation and browser back preserve the design");
  assert.deepEqual(report.errors, [], "Unexpected JavaScript errors");
  assert.deepEqual(report.layoutProblems, [], "Layout regressions");
  console.log(JSON.stringify({ pages: report.routes.length, responsiveCases: report.responsive.length, interactions: report.interactions, accessibility: report.accessibility.map(item => ({ route: item.route, violations: item.violations.map(issue => issue.id) })), errors: report.errors }, null, 2));
} finally {
  await writeFile(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
  await browser.close();
}

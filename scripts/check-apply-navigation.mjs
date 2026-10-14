import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const [originArg = "https://spacemusic.io", output = "tmp/apply-navigation-check", ...extra] = process.argv.slice(2);
assert(!extra.length, "Usage: node scripts/check-apply-navigation.mjs [ORIGIN] [OUTPUT]");
const origin = new URL(originArg).origin;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ channel: "chrome", headless: true });
const results = [];
await mkdir(output, { recursive: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    new MutationObserver(() => {
      if (document.querySelector("h1")?.textContent === "Tell us about your catalog.") sessionStorage.setItem("qa-legacy-apply-mounted", "true");
    }).observe(document, { childList: true, subtree: true });
  });
  const errors = [];
  const legacyRequests = [];
  await context.route("**/*", route => {
    const request = route.request();
    if (new URL(request.url()).hostname.includes("plausible.io")) return route.abort();
    assert(["GET", "HEAD", "OPTIONS"].includes(request.method()), "Do not submit any applications during navigation tests");
    if (request.url().includes("ApplicationForm-DRjdd2L1.js")) legacyRequests.push(request.url());
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(30000);
  page.on("pageerror", error => errors.push(error.message));
  const documents = [];
  page.on("request", request => {
    if (request.resourceType() === "document") documents.push(new URL(request.url()).pathname);
  });
  async function verifyApplication(label, suffix = "") {
    await page.waitForURL(origin + "/apply/" + suffix, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => /Tell us about your catalog|We buy your music catalog/.test(document.querySelector("h1")?.textContent || ""));
    assert.equal(await page.locator("h1").textContent(), "We buy your music catalog.", `${label}: must use the standalone application, not the retired form`);
    assert.equal(page.url(), origin + "/apply/" + suffix, `${label}: canonical application URL`);
    await page.locator("form.intake-card").waitFor();
    assert.equal(await page.locator("form.intake-card").count(), 1);
    assert.equal(await page.getByRole("button", { name: /^(Start review|Request a free catalog review)$/ }).count(), 1);
    assert.equal(await page.getByRole("button", { name: "Start the application", exact: true }).count(), 0);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"), "https://spacemusic.io/apply/");
    assert.equal(await page.locator('input[type="email"]').getAttribute("required"), "");
    results.push(label);
  }
  await page.goto(origin + "/", { waitUntil: "networkidle" });
  const initialDocuments = documents.length;
  await page.locator('nav.fixed a[href="/apply/"]').first().click({ noWaitAfter: true });
  await verifyApplication("Homepage navigation");
  assert(documents.length > initialDocuments && documents.at(-1) === "/apply/", "Cross the application boundary with a document navigation");
  if (process.env.QUICK_CHECK === "1") process.exitCode = 0;
  else {
    await page.goBack({ waitUntil: "networkidle" });
    assert.equal(new URL(page.url()).pathname, "/", "Back should return directly to the homepage, not a redirect loop");
    await page.goForward({ waitUntil: "networkidle" });
    await verifyApplication("Browser back and forward");

    for (const route of ["/", "/sell/", "/how-it-works/", "/calculator/", "/compare/space-vs-primary-wave/", "/guides/how-to-sell-music-rights/", "/blog/beatbread-vs-catalog-buyers/"]) {
      await page.goto(origin + route, { waitUntil: "networkidle" });
      const links = page.locator('a[href="/apply/"]:visible');
      const labels = await links.evaluateAll(nodes => nodes.map(node => node.textContent));
      for (let index = 0; index < labels.length; index++) {
        if (index) await page.goto(origin + route, { waitUntil: "networkidle" });
        await page.locator('a[href="/apply/"]:visible').nth(index).click({ noWaitAfter: true });
        await verifyApplication(`${route}: ${labels[index].trim()} (${index + 1})`);
      }
    }

    // Exercise router-generated destinations, not just the current DOM hrefs.
    await page.goto(origin + "/", { waitUntil: "networkidle" });
    await page.evaluate(() => {
      history.pushState({}, "", "/apply?ref=qa-routing&utm_source=navigation-test#review");
      dispatchEvent(new PopStateEvent("popstate"));
    });
    await verifyApplication("Programmatic navigation preserves query and hash", "?ref=qa-routing&utm_source=navigation-test#review");
    await page.goto(origin + "/", { waitUntil: "networkidle" });
    await page.evaluate(() => {
      history.pushState({}, "", "/marketplace");
      dispatchEvent(new PopStateEvent("popstate"));
    });
    await verifyApplication("Existing marketplace redirect");

    for (const route of ["/apply", "/apply/"]) {
      await page.goto(origin + route, { waitUntil: "networkidle" });
      await verifyApplication(`Direct ${route}`);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(origin + "/", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Open menu", exact: true }).click();
    await page.locator('nav.fixed a[href="/apply/"]:visible').click({ noWaitAfter: true });
    await verifyApplication("Mobile menu");
    await page.screenshot({ path: path.join(output, "apply-mobile.png"), fullPage: false });
    await page.getByRole("button", { name: /^(Start review|Request a free catalog review)$/ }).click();
    assert(await page.locator('input[type="email"]').evaluate(input => input.validity.valueMissing && document.activeElement === input));
    results.push("Required-field validation without submitting a lead");

    const noScript = await browser.newContext({ javaScriptEnabled: false });
    const fallback = await noScript.newPage();
    await fallback.goto(origin + "/");
    await fallback.locator('nav a[href="/apply/"]').first().click();
    assert.equal(new URL(fallback.url()).pathname, "/apply/");
    assert.equal(await fallback.locator("h1").textContent(), "We buy your music catalog.");
    await noScript.close();
    results.push("No-JavaScript links retain the correct static destination");
  }
  assert.deepEqual(errors, [], "Browser errors");
  assert.equal(await page.evaluate(() => sessionStorage.getItem("qa-legacy-apply-mounted")), null, "The retired form must never render, even briefly");
  // Older baselines may prefetch the retired module; it must never mount.
  console.log(JSON.stringify({ origin, passed: results.length, results, errors, legacyFormMounted: false, legacyPrefetchRequests: legacyRequests.length, submissions: 0 }, null, 2));
} finally {
  await writeFile(path.join(output, "results.json"), JSON.stringify({ origin, results }, null, 2) + "\n");
  await browser.close();
}

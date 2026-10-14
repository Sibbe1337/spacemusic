import assert from "node:assert/strict";

const [originArg = "https://spacemusic.io", ...extra] = process.argv.slice(2);
assert(!extra.length, "Usage: node scripts/check-homepage-social.mjs [ORIGIN]");
const origin = new URL(originArg).origin;
const canonical = "https://spacemusic.io/";
const imageUrl = "https://spacemusic.io/social/space-catalog-v1.png";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const request = (url, options = {}) => fetch(url, { redirect: "manual", signal: AbortSignal.timeout(20000), ...options });
const response = await request(origin + "/");
assert.equal(response.status, 200);
assert.match(response.headers.get("content-type"), /^text\/html/);
if (origin === "https://spacemusic.io") assert(!/noindex/i.test(response.headers.get("x-robots-tag") || ""));
const html = await response.text();

function inspect({ html = null } = {}) {
  const doc = html === null ? document : new DOMParser().parseFromString(html, "text/html");
  const names = ["description", "twitter:card", "twitter:title", "twitter:description", "twitter:image", "twitter:image:alt"];
  const properties = ["og:title", "og:description", "og:type", "og:url", "og:image", "og:image:type", "og:image:width", "og:image:height", "og:image:alt"];
  return {
    title: [...doc.querySelectorAll("head title")].map(node => node.textContent),
    canonical: [...doc.querySelectorAll('head link[rel="canonical"]')].map(node => node.getAttribute("href")),
    meta: Object.fromEntries([...names.map(name => [name, `head meta[name="${name}"]`]), ...properties.map(name => [name, `head meta[property="${name}"]`])].map(([name, selector]) => [name, [...doc.querySelectorAll(selector)].map(node => node.getAttribute("content"))])),
    theme: [...doc.querySelectorAll('head meta[name="theme-color"]')].map(node => ({ content: node.getAttribute("content"), media: node.getAttribute("media") })),
  };
}

function check(data, stage) {
  assert.equal(data.title.length, 1, `${stage}: one title`);
  assert.deepEqual(data.canonical, [canonical]);
  for (const [name, values] of Object.entries(data.meta)) {
    assert.equal(values.length, 1, `${stage}: ${name} must occur once`);
    assert(values[0], `${stage}: ${name} must not be empty`);
  }
  assert.deepEqual(data.meta["og:type"], ["website"], `${stage}: homepage is not an article`);
  assert.deepEqual(data.meta["og:url"], [canonical]);
  assert.deepEqual(data.meta["og:image"], [imageUrl]);
  assert.deepEqual(data.meta["twitter:image"], [imageUrl]);
  assert.deepEqual(data.meta["twitter:card"], ["summary_large_image"]);
  assert.equal(data.theme.length, 2);
  assert.deepEqual(data.theme.map(meta => meta.media).sort(), ["(prefers-color-scheme: dark)", "(prefers-color-scheme: light)"]);
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const context = await browser.newContext();
  await context.route("**/*", async route => {
    const host = new URL(route.request().url()).hostname;
    if (host === "plausible.io" || host.endsWith(".plausible.io")) return route.abort();
    return route.continue();
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const raw = await page.evaluate(inspect, { html });
  check(raw, "Raw HTML");

  const imageResponse = await request(origin + new URL(imageUrl).pathname);
  assert.equal(imageResponse.status, 200);
  assert.match(imageResponse.headers.get("content-type"), /^image\/png/);
  const png = Buffer.from(await imageResponse.arrayBuffer());
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  assert.equal(width, Number(raw.meta["og:image:width"][0]));
  assert.equal(height, Number(raw.meta["og:image:height"][0]));
  assert(width >= 1200 && Math.abs(width / height - 1.91) < 0.03);
  assert(png.length < 5_000_000);

  for (const agent of ["facebookexternalhit/1.1", "Twitterbot/1.0", "LinkedInBot/1.0"]) {
    const botResponse = await request(origin + "/", { headers: { "User-Agent": agent } });
    assert.equal(botResponse.status, 200, agent);
    check(await page.evaluate(inspect, { html: await botResponse.text() }), agent);
    const botImage = await request(origin + new URL(imageUrl).pathname, { headers: { "User-Agent": agent } });
    assert.equal(botImage.status, 200, `${agent}: image`);
    assert(png.equals(Buffer.from(await botImage.arrayBuffer())), `${agent}: identical image`);
  }
  console.log(`Raw HTML and image checks passed: ${width}x${height}, ${png.length} bytes, 3 sharing-bot user agents.`);

  await page.goto(origin + "/", { waitUntil: "networkidle", timeout: 30000 });
  const rendered = await page.evaluate(inspect);
  check(rendered, "Rendered HTML");
  assert.deepEqual(rendered, raw, "Metadata must survive hydration unchanged");
  for (const colorScheme of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme });
    const matches = await page.evaluate(() => [...document.querySelectorAll('meta[name="theme-color"]')].filter(node => matchMedia(node.media).matches).length);
    assert.equal(matches, 1, `${colorScheme}: exactly one applicable theme color`);
  }

  const articleResponse = await page.goto(origin + "/blog/beatbread-vs-catalog-buyers/", { waitUntil: "networkidle", timeout: 30000 });
  const articleRaw = await page.evaluate(inspect, { html: await articleResponse.text() });
  assert.deepEqual(await page.evaluate(inspect), articleRaw, "Keep article metadata unchanged before and after rendering");
  assert.deepEqual(await page.locator('head meta[property="og:type"]').evaluateAll(nodes => nodes.map(node => node.content)), ["article"], "Keep article metadata unchanged");
  await page.locator('a[href="/"]').first().click();
  await page.waitForURL(origin + "/");
  await page.waitForFunction(() => document.querySelector('head meta[property="og:url"]')?.content === "https://spacemusic.io/");
  assert.deepEqual(await page.evaluate(inspect), raw, "Homepage metadata after client-side article navigation");
  await page.goBack();
  await page.waitForURL(origin + "/blog/beatbread-vs-catalog-buyers/");
  await page.waitForFunction(() => document.querySelector('head meta[property="og:type"]')?.content === "article");
  assert.deepEqual(await page.evaluate(inspect), articleRaw, "Homepage image metadata must not leak into an article");
  await page.goForward();
  await page.waitForURL(origin + "/");
  await page.waitForFunction(() => document.querySelector('head meta[property="og:url"]')?.content === "https://spacemusic.io/");
  assert.deepEqual(await page.evaluate(inspect), raw, "Homepage metadata after forward navigation");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(inspect), raw, "Homepage metadata on mobile");
  assert.deepEqual(errors, [], "Unexpected browser errors");
  console.log(JSON.stringify({ origin, metadata: "Single, consistent values before and after rendering", image: { url: imageUrl, width, height, bytes: png.length }, themeColor: "One matching value per color scheme", articleType: "Preserved", clientNavigation: "Passed", mobile: "Passed", note: "HTTP and browser checks; external sharing caches and AI-visibility gains are not verified." }, null, 2));
} finally {
  await browser.close();
}

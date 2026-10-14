import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [baselineArg, candidateArg, ...extra] = process.argv.slice(2);
assert(baselineArg && candidateArg && !extra.length, "Usage: node scripts/check-home-fonts.mjs BASELINE_ORIGIN CANDIDATE_ORIGIN");
const baseline = new URL(baselineArg).origin;
const candidate = new URL(candidateArg).origin;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const manifest = JSON.parse(await readFile(new URL("../marketing/fonts/manifest.json", import.meta.url), "utf8"));
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const output = fileURLToPath(new URL("../tmp/home-font-checks-20260907/", import.meta.url));
await mkdir(output, { recursive: true });

function inspect({ html = null } = {}) {
  const doc = html === null ? document : new DOMParser().parseFromString(html, "text/html");
  return {
    title: doc.title,
    meta: [...doc.querySelectorAll("head meta")].map(node => node.outerHTML).sort(),
    canonical: [...doc.querySelectorAll('link[rel="canonical"]')].map(node => node.getAttribute("href")),
    schema: [...doc.querySelectorAll('script[type="application/ld+json"]')].map(node => JSON.parse(node.textContent)),
    text: doc.body.textContent,
  };
}
const browser = await chromium.launch({ channel: "chrome", headless: true });
async function comparePixels(first, second) {
  if (first.equals(second)) return { changedPixels: 0, changedFraction: 0 };
  const page = await browser.newPage();
  try {
    return await page.evaluate(async files => {
      const images = await Promise.all(files.map(async data => createImageBitmap(await (await fetch("data:image/png;base64," + data)).blob())));
      if (images[0].width !== images[1].width || images[0].height !== images[1].height) throw new Error("Screenshot dimensions changed");
      const pixels = images.map(image => {
        const canvas = document.createElement("canvas");
        canvas.width = image.width;
        canvas.height = image.height;
        const context = canvas.getContext("2d");
        context.drawImage(image, 0, 0);
        return new Uint32Array(context.getImageData(0, 0, canvas.width, canvas.height).data.buffer);
      });
      let changedPixels = 0;
      for (let i = 0; i < pixels[0].length; i++) if (pixels[0][i] !== pixels[1][i]) changedPixels++;
      return { changedPixels, changedFraction: changedPixels / pixels[0].length };
    }, [first.toString("base64"), second.toString("base64")]);
  } finally { await page.close(); }
}
try {
  const probe = await browser.newPage();
  const oldHtml = await (await fetch(baseline + "/")).text();
  const newResponse = await fetch(candidate + "/");
  assert.equal(newResponse.status, 200);
  const newHtml = await newResponse.text();
  assert.deepEqual(await probe.evaluate(inspect, { html: newHtml }), await probe.evaluate(inspect, { html: oldHtml }), "Keep all raw metadata, schema and page content unchanged");
  const preloads = await probe.evaluate(html => [...new DOMParser().parseFromString(html, "text/html").querySelectorAll('link[rel="preload"][as="font"]')].map(node => ({ href: node.getAttribute("href"), type: node.type, crossOrigin: node.crossOrigin })), newHtml);
  assert.deepEqual(preloads.map(link => link.href), manifest.preloads.map(file => `/${file}`));
  assert(preloads.every(link => link.type === "font/woff2" && link.crossOrigin === "anonymous"));
  for (const file of manifest.files) {
    const response = await fetch(candidate + "/" + file.path, { redirect: "manual" });
    assert.equal(response.status, 200, file.path);
    if (file.path.endsWith(".woff2")) assert.match(response.headers.get("content-type"), /^(font\/woff2|application\/font-woff2)/);
    assert.equal(sha256(Buffer.from(await response.arrayBuffer())), file.sha256, file.path);
  }
  await probe.close();
  const results = [];
  for (const width of [390, 1440]) {
    for (const javaScriptEnabled of [true, false]) {
      const captures = [];
      for (const [label, origin] of [["baseline", baseline], ["candidate", candidate]]) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, javaScriptEnabled, reducedMotion: "reduce" });
        await context.route("**/*plausible.io/api/event*", route => route.abort());
        const page = await context.newPage();
        const requests = [];
        const errors = [];
        page.on("request", request => requests.push(request.url()));
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(origin + "/", { waitUntil: "networkidle", timeout: 30000 });
        await page.evaluate(() => document.fonts.ready);
        const fonts = await page.evaluate(() => [...document.fonts].filter(font => font.status === "loaded").map(font => ({ family: font.family.replaceAll('"', ''), weight: font.weight, style: font.style })).sort((a, b) => a.family.localeCompare(b.family)));
        assert(fonts.some(font => font.family === "Fraunces"), `${label}: heading font loaded`);
        assert(fonts.some(font => font.family === "Plus Jakarta Sans"), `${label}: body font loaded`);
        const state = await page.evaluate(inspect);
        const geometry = await page.locator("h1, main, header, footer").evaluateAll(nodes => nodes.map(node => {
          const rect = node.getBoundingClientRect();
          const css = getComputedStyle(node);
          return { tag: node.tagName, x: rect.x, y: rect.y, width: rect.width, height: rect.height, fontFamily: css.fontFamily, fontWeight: css.fontWeight, fontSize: css.fontSize };
        }));
        const png = await page.screenshot({ fullPage: true, animations: "disabled", path: path.join(output, `${label}-${width}-${javaScriptEnabled ? "js" : "no-js"}.png`) });
        assert.deepEqual(errors, [], `${label}: browser errors`);
        if (label === "candidate") {
          assert(!requests.some(url => /^https:\/\/fonts\.(?:googleapis|gstatic)\.com\//.test(url)), "Homepage must not request third-party font resources");
          const actualFonts = requests.filter(url => new URL(url).pathname.endsWith(".woff2"));
          assert.deepEqual(actualFonts.map(url => new URL(url).pathname).sort(), manifest.preloads.map(file => `/${file}`).sort(), "Load each used font once, without unused subsets");
        }
        captures.push({ state, geometry, fonts, png });
        await context.close();
      }
      const { png: oldPng, ...oldState } = captures[0];
      const { png: newPng, ...newState } = captures[1];
      assert.deepEqual(newState, oldState, `${width}px: preserve text, metadata, fonts and exact layout geometry`);
      const difference = await comparePixels(oldPng, newPng);
      // Allow only tiny browser rasterization noise, not text or layout changes.
      assert(difference.changedFraction <= 0.00001, `${width}px: screenshot changed (${JSON.stringify(difference)})`);
      results.push({ width, javaScriptEnabled, ...difference });
    }
  }
  console.log(JSON.stringify({ baseline, candidate, results, fontAssets: manifest.files.length, thirdPartyFontRequests: 0, note: "Identical fonts and layout with at most 0.001% pixel noise, including without JavaScript; metadata and content preserved." }, null, 2));
} finally {
  await browser.close();
}

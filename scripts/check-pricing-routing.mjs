import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const [originArg, baselineArg, ...extra] = process.argv.slice(2);
assert(originArg && !extra.length, "Usage: node scripts/check-pricing-routing.mjs ORIGIN [RELEASE_DIRECTORY]");
const origin = new URL(originArg).origin;
const canonical = "https://spacemusic.io/pricing.md";
const baseline = baselineArg ? path.resolve(baselineArg) + path.sep : fileURLToPath(new URL("../tmp/calculator-review-v2-20260909/", import.meta.url));
const expected = await readFile(baseline + "pricing.md");
const request = (url, options = {}) => fetch(url, { redirect: "manual", signal: AbortSignal.timeout(20000), ...options });
let checks = 0;
for (const suffix of ["/pricing.md", "/pricing.md?utm_source=audit"]) {
  for (const method of ["GET", "HEAD"]) {
    const response = await request(origin + suffix, { method });
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), /^text\/markdown(?:;|$)/i);
    assert.equal(response.headers.get("link"), `<${canonical}>; rel="canonical"`);
    if (origin === "https://spacemusic.io") assert(!/noindex/i.test(response.headers.get("x-robots-tag") || ""));
    if (method === "GET") assert(expected.equals(Buffer.from(await response.arrayBuffer())));
    checks++;
  }
}
for (const suffix of ["/pricing.md/", "/pricing.md/?utm_source=audit"]) {
  for (const method of ["GET", "HEAD"]) {
    const response = await request(origin + suffix, { method });
    assert.equal(response.status, 301);
    const location = new URL(response.headers.get("location"), origin);
    assert.equal(location.origin, origin);
    assert.equal(location.pathname, "/pricing.md");
    assert.equal(location.search, new URL(origin + suffix).search, "Preserve query parameters on the redirect");
    const final = await request(location.href);
    assert.equal(final.status, 200);
    assert.equal(final.headers.get("link"), `<${canonical}>; rel="canonical"`);
    assert(expected.equals(Buffer.from(await final.arrayBuffer())));
    checks++;
  }
}
for (const agent of ["Googlebot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot"]) {
  const response = await request(origin + "/pricing.md", { headers: { "User-Agent": agent } });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("link"), `<${canonical}>; rel="canonical"`);
  assert(expected.equals(Buffer.from(await response.arrayBuffer())));
  checks++;
}
for (const route of ["/", "/apply/", "/calculator/", "/sell/", "/pricing", "/pricing/", "/robots.txt", "/sitemap.xml", "/llms.txt"]) {
  const response = await request(origin + route);
  assert.equal(response.status, 200, route);
  assert(!(response.headers.get("link") || "").includes(canonical), `Pricing header leaked to ${route}`);
  if (route === "/llms.txt") assert.equal(response.headers.get("link"), '<https://spacemusic.io/llms.txt>; rel="canonical"');
  if (route === "/sitemap.xml") assert((await readFile(baseline + "sitemap.xml")).equals(Buffer.from(await response.arrayBuffer())));
  checks++;
}
if (origin === "https://spacemusic.io") {
  for (const url of ["http://spacemusic.io/pricing.md", "https://www.spacemusic.io/pricing.md", "http://www.spacemusic.io/pricing.md"]) {
    const response = await request(url);
    assert.equal(response.status, 301);
    assert.equal(new URL(response.headers.get("location"), url).href, canonical);
    checks++;
  }
}
console.log(JSON.stringify({ origin, checks, canonical, markdown: "byte-identical", sitemap: "byte-identical", note: "HTTP checks only, not indexing or ranking verification" }, null, 2));

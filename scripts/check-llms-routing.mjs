import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const [originArg = "https://spacemusic.io", expectedFile, ...extra] = process.argv.slice(2);
assert(!extra.length, "Usage: node scripts/check-llms-routing.mjs [ORIGIN] [EXPECTED_TEXT_FILE]");
const origin = new URL(originArg).origin;
const canonical = "https://spacemusic.io/llms.txt";
const expected = await readFile(expectedFile || fileURLToPath(new URL("../marketing/ai/llms.txt", import.meta.url)));
const request = (url, options = {}) => fetch(url, { redirect: "manual", signal: AbortSignal.timeout(20000), ...options });
const cases = [];
for (const suffix of ["/llms.txt", "/llms.txt?utm_source=audit"]) {
  for (const method of ["GET", "HEAD"]) {
    const response = await request(origin + suffix, { method });
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), /^text\/plain;\s*charset=utf-8$/i);
    assert.equal(response.headers.get("link"), `<${canonical}>; rel="canonical"`);
    if (origin === "https://spacemusic.io") assert(!/noindex/i.test(response.headers.get("x-robots-tag") || ""));
    if (method === "GET") assert(expected.equals(Buffer.from(await response.arrayBuffer())), "Keep the text content identical");
    cases.push(`${method} ${suffix}`);
  }
}
for (const suffix of ["/llms.txt/", "/llms.txt/?utm_source=audit"]) {
  for (const method of ["GET", "HEAD"]) {
    const response = await request(origin + suffix, { method });
    assert.equal(response.status, 301, `Trailing slash must not return the homepage: ${method} ${suffix}`);
    const location = new URL(response.headers.get("location"), origin);
    assert.equal(location.origin, origin);
    assert.equal(location.pathname, "/llms.txt");
    const final = await request(location.href);
    assert.equal(final.status, 200);
    assert.equal(final.headers.get("link"), `<${canonical}>; rel="canonical"`);
    assert(expected.equals(Buffer.from(await final.arrayBuffer())));
    cases.push(`${method} ${suffix} -> 301 -> text`);
  }
}
for (const agent of ["Googlebot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot"]) {
  const response = await request(origin + "/llms.txt", { headers: { "User-Agent": agent } });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("link"), `<${canonical}>; rel="canonical"`);
  assert(expected.equals(Buffer.from(await response.arrayBuffer())));
}
for (const route of ["/", "/apply/", "/sell/", "/robots.txt", "/pricing.md", "/blog/sell-music-catalog-lump-sum-2026/", "/compare/space-vs-primary-wave/"]) {
  const response = await request(origin + route);
  assert.equal(response.status, 200, route);
  assert(!(response.headers.get("link") || "").includes(canonical), `Canonical header leaked to ${route}`);
}
if (origin === "https://spacemusic.io") {
  for (const url of ["http://spacemusic.io/llms.txt", "https://www.spacemusic.io/llms.txt", "http://www.spacemusic.io/llms.txt"]) {
    const response = await request(url);
    assert.equal(response.status, 301);
    assert.equal(new URL(response.headers.get("location"), url).href, canonical);
    cases.push(`${url} -> 301 -> canonical`);
  }
}
console.log(JSON.stringify({ origin, canonical, cases, botUserAgentChecks: 4, unrelatedRouteChecks: 7, textContent: "byte-identical", note: "HTTP smoke tests, not proof of indexing or real crawler visits" }, null, 2));

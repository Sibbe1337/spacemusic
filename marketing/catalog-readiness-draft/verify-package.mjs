import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(root, "../..");
const pages = ["index.html", "sample.html", "review.html", "sources.html"];
const urls = new Set();
for (const page of pages) {
  const html = await readFile(path.join(root, "preview", page), "utf8");
  for (const match of html.matchAll(/href="(https:\/\/[^"<>]+)"/g))
    urls.add(match[1].replaceAll("&amp;", "&"));
}
const sourceChecks = [];
for (const url of urls) {
  try {
    const response = await fetch(url, {
      signal: AbortSignal.timeout(20000),
      headers: { "User-Agent": "SPACE-Draft-Source-Check/1.0" },
    });
    await response.arrayBuffer();
    sourceChecks.push({
      url,
      status: response.status,
      finalUrl: response.url,
      contentType: response.headers.get("content-type"),
    });
  } catch (error) {
    sourceChecks.push({ url, error: error.message });
  }
}
const release = "tmp/calculator-review-v2-20260909";
const liveCheck = JSON.parse(
  execFileSync(
    process.execPath,
    [
      path.join(repo, "scripts/verify-release-files.mjs"),
      path.join(repo, release),
      "https://spacemusic.io",
    ],
    { encoding: "utf8", timeout: 180000 },
  ),
);
assert.equal(liveCheck.mismatches.length, 0);
assert.equal(liveCheck.publicFiles, 333);
const sitemap = await readFile(path.join(repo, release, "sitemap.xml"), "utf8");
assert.equal([...sitemap.matchAll(/<loc>/g)].length, 139);
const pdf = await readFile(
  path.join(repo, "output/pdf/space-catalog-readiness-sample.pdf"),
);
assert(
  pdf.equals(await readFile(path.join(root, "preview/sample-report.pdf"))),
);
const summary = {
  checkedAt: new Date().toISOString(),
  sourceChecks,
  productionSnapshot: release,
  production: liveCheck,
  sitemapUrls: 139,
  pdfSha256: createHash("sha256").update(pdf).digest("hex"),
  pdfBytes: pdf.length,
  previewPdfIdentical: true,
};
await writeFile(
  path.join(root, "qa/package-results.json"),
  JSON.stringify(summary, null, 2),
);
console.log(JSON.stringify(summary, null, 2));
assert(
  sourceChecks.every((row) => row.status === 200),
  "Some external destinations need review; see package-results.json",
);

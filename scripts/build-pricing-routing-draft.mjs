import assert from "node:assert/strict";
import { cp, mkdir, readFile, readdir, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [outputArg, ...extra] = process.argv.slice(2);
assert(outputArg && !extra.length, "Usage: node scripts/build-pricing-routing-draft.mjs FRESH_OUTPUT");
const project = fileURLToPath(new URL("../", import.meta.url));
const baseline = "tmp/calculator-review-v2-20260909";
const release = await readFile(path.join(project, "marketing/RELEASE.md"), "utf8");
assert(release.includes(`Current verified release directory: \`${baseline}\``), "Production baseline changed; review this draft before rebuilding");
const source = await realpath(path.join(project, baseline));
const outputPath = path.resolve(outputArg);
const output = path.join(await realpath(path.dirname(outputPath)), path.basename(outputPath));
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep), "Use a separate output directory");
const before = {
  _headers: '/llms.txt\n  Link: <https://spacemusic.io/llms.txt>; rel="canonical"\n',
  _redirects: '/llms.txt/ /llms.txt 301\n',
};
const additions = {
  _headers: '\n/pricing.md\n  Link: <https://spacemusic.io/pricing.md>; rel="canonical"\n',
  _redirects: '/pricing.md/ /pricing.md 301\n',
};
const files = [];
for (const name of await readdir(source, { recursive: true })) {
  if ((await stat(path.join(source, name))).isFile()) files.push(name);
}
assert(!files.some((name) => ["_worker.js", "_routes.json"].includes(name) || name.startsWith("functions/")), "Review non-static hosting first");
for (const [name, expected] of Object.entries(before)) {
  assert.equal(await readFile(path.join(source, name), "utf8"), expected, `Review changed ${name}`);
}
const sitemap = await readFile(path.join(source, "sitemap.xml"), "utf8");
assert.equal((sitemap.match(/<loc>/g) || []).length, 139);
assert(sitemap.includes("<loc>https://spacemusic.io/pricing.md</loc>"));
assert.match(await readFile(path.join(source, "pricing.md"), "utf8"), /^# SPACE Pricing and Offer Policy\n/);
await mkdir(output);
await cp(source, output, { recursive: true });
for (const name of Object.keys(before)) await writeFile(path.join(output, name), before[name] + additions[name]);
for (const name of files.filter((name) => !Object.hasOwn(before, name))) {
  assert((await readFile(path.join(source, name))).equals(await readFile(path.join(output, name))), `Public file changed: ${name}`);
}
assert.deepEqual((await readdir(output, { recursive: true })).sort(), (await readdir(source, { recursive: true })).sort());
console.log(JSON.stringify({ output, status: "local draft, not deployed", preservedPublicFiles: files.length - 2, changedHostingFiles: Object.keys(before), sitemapUrls: 139 }, null, 2));

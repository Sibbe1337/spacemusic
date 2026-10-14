import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, realpath, writeFile } from "node:fs/promises";
import path from "node:path";

const [sourceArg, outputArg, ...extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra.length, "Usage: node scripts/build-apply-navigation-release.mjs VERIFIED_SOURCE FRESH_OUTPUT");
const source = await realpath(sourceArg);
const output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep));
const hash = value => createHash("sha256").update(value).digest("hex").slice(0, 12);
async function files(directory, prefix = "") {
  const result = [];
  for (const item of await readdir(directory, { withFileTypes: true })) {
    assert(!item.isSymbolicLink());
    const relative = path.join(prefix, item.name);
    if (item.isDirectory()) result.push(...await files(path.join(directory, item.name), relative));
    else result.push(relative);
  }
  return result.sort();
}
const inventory = await files(source);
assert(!inventory.includes("_worker.js") && !inventory.includes("_routes.json"));
const home = await readFile(path.join(source, "index.html"), "utf8");
assert(!home.includes("data-space-design"), "Do not publish the unfinished design with this navigation fix");
const entryPath = home.match(/<script type="module" crossorigin src="\/([^\"]+)"/)?.[1];
assert(entryPath?.startsWith("assets/"));
const entry = await readFile(path.join(source, entryPath), "utf8");
const oldForm = "ApplicationForm-DRjdd2L1.js";
assert.equal(entry.split(oldForm).length, 3, "Review the current application dependency and lazy import");
assert(entry.includes('path:"/apply",element:e.jsx(y,{})'));
const application = await readFile(path.join(source, "apply/index.html"), "utf8");
assert(application.includes("We buy your music catalog."));
assert(application.includes('src="/apply/assets/index-1Mu13qxd.js"'));
assert(application.includes('href="https://spacemusic.io/apply/"'));
const bridge = await readFile(new URL("../marketing/application-route/CanonicalApplication.mjs", import.meta.url), "utf8");
assert(inventory.includes("assets/vendor-DhPEFgb5.js"));
const bridgePath = `assets/CanonicalApplication-${hash(bridge)}.js`;
const nextEntry = entry.replaceAll(oldForm, path.basename(bridgePath));
const nextEntryPath = `assets/index-apply-navigation-${hash(nextEntry)}.js`;
assert.equal(nextEntry.replaceAll(path.basename(bridgePath), oldForm), entry);
assert(!inventory.includes(bridgePath) && !inventory.includes(nextEntryPath));
await mkdir(output);
await cp(source, output, { recursive: true });
await writeFile(path.join(output, bridgePath), bridge);
await writeFile(path.join(output, nextEntryPath), nextEntry);
let changed = 0;
for (const relative of inventory) {
  const original = await readFile(path.join(source, relative));
  if (relative.endsWith(".html") && original.toString().includes(`/${entryPath}`)) {
    const updated = original.toString().replaceAll(`/${entryPath}`, `/${nextEntryPath}`);
    assert.equal(updated.replaceAll(`/${nextEntryPath}`, `/${entryPath}`), original.toString());
    assert.equal(updated.split(/<body\b[^>]*>/i)[1], original.toString().split(/<body\b[^>]*>/i)[1]);
    await writeFile(path.join(output, relative), updated);
    changed++;
  } else {
    assert(original.equals(await readFile(path.join(output, relative))), `${relative}: unexpected modification`);
  }
}
assert.equal(changed, 134, "Expected only the marketing pages, not the standalone application");
assert.deepEqual(await files(output), [...inventory, bridgePath, nextEntryPath].sort());
console.log(JSON.stringify({ output, updatedMarketingPages: changed, newAssets: [bridgePath, nextEntryPath], standaloneApplication: "All files unchanged", contentAndSEO: "All unchanged", design: "No design preview changes included", originalAssets: "All preserved" }, null, 2));

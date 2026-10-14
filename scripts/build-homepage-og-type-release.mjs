import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, realpath, writeFile } from "node:fs/promises";
import path from "node:path";

const [sourceArg, outputArg, ...extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra.length, "Usage: node scripts/build-homepage-og-type-release.mjs SOURCE FRESH_OUTPUT");
const source = await realpath(sourceArg);
const output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep), "Use a separate output directory");

async function files(directory, prefix = "") {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = path.join(prefix, entry.name);
    assert(!entry.isSymbolicLink(), `Unexpected symlink: ${relative}`);
    if (entry.isDirectory()) result.push(...await files(path.join(directory, entry.name), relative));
    else result.push(relative);
  }
  return result.sort();
}

const inventory = await files(source);
assert(!inventory.includes("_worker.js") && !inventory.includes("_routes.json"), "Expected a static release");
for (const name of ["_headers", "_redirects"]) {
  const expected = await readFile(new URL(`../marketing/ai/cloudflare/${name}`, import.meta.url));
  assert(expected.equals(await readFile(path.join(source, name))), `Review changed hosting configuration: ${name}`);
}

const homepage = await readFile(path.join(source, "index.html"), "utf8");
assert(homepage.includes('rel="canonical" href="https://spacemusic.io/"'), "Unexpected homepage canonical");
assert(homepage.includes('property="og:type" content="website"'), "Raw HTML should already identify a website");
const entryRelative = homepage.match(/<script type="module" crossorigin src="\/([^\"]+)"/)?.[1];
assert(entryRelative?.startsWith("assets/"), "Missing entry module");
const entry = await readFile(path.join(source, entryRelative), "utf8");
const homeRelative = entry.match(/assets\/Index-[\w-]+\.js/)?.[0];
assert(homeRelative, "Missing homepage module");
const home = await readFile(path.join(source, homeRelative), "utf8");
const anchor = 'canonical:"/",image:"https://spacemusic.io/social/space-catalog-v1.png",schema:[P,I,W,F]';
assert.equal(home.split(anchor).length, 2, "Homepage changed; review the metadata call before patching");
const imageTags = [
  ["property", "og:image:type"],
  ["property", "og:image:width"],
  ["property", "og:image:height"],
  ["property", "og:image:alt"],
  ["name", "twitter:image:alt"],
].map(([attribute, key]) => {
  const matches = [...homepage.matchAll(new RegExp(`<meta ${attribute}="${key}" content="([^"&]*)">`, "g"))];
  assert.equal(matches.length, 1, `Review homepage image metadata: ${key}`);
  const [tag, content] = matches[0];
  return { tag, managedTag: tag.replace("<meta ", '<meta data-rh="true" '), element: `e.jsx("meta",{${attribute}:${JSON.stringify(key)},content:${JSON.stringify(content)}})` };
});
const navAnchor = 'schema:[P,I,W,F]}),e.jsx(u,{})';
assert.equal(home.split(navAnchor).length, 2, "Review homepage component structure");
// Match the article template: Helmet owns optional image metadata on SPA navigation.
const nextHome = home.replace(anchor, `type:"website",${anchor}`).replace(navAnchor, `schema:[P,I,W,F]}),e.jsxs(p,{children:[${imageTags.map(tag => tag.element).join(",")}]}),e.jsx(u,{})`);
const hash = text => createHash("sha256").update(text).digest("hex").slice(0, 12);
const nextHomeRelative = `assets/Index-og-type-${hash(nextHome)}.js`;
const nextEntry = entry.replaceAll(path.basename(homeRelative), path.basename(nextHomeRelative));
const nextEntryRelative = `assets/index-og-type-${hash(nextEntry)}.js`;
assert.notEqual(nextEntry, entry);

// Version both runtime assets so cached entry modules remain valid during rollout.
await mkdir(output);
await cp(source, output, { recursive: true });
await writeFile(path.join(output, nextHomeRelative), nextHome);
await writeFile(path.join(output, nextEntryRelative), nextEntry);
let updatedHtml = 0;
for (const relative of inventory.filter(name => name.endsWith(".html"))) {
  const original = await readFile(path.join(source, relative), "utf8");
  let next = original.replaceAll(`/${entryRelative}`, `/${nextEntryRelative}`);
  if (relative === "index.html") {
    for (const { tag, managedTag } of imageTags) next = next.replace(tag, managedTag);
  }
  assert.equal(next.split(/<body\b[^>]*>/i)[1], original.split(/<body\b[^>]*>/i)[1], `Body changed: ${relative}`);
  if (next !== original) {
    await writeFile(path.join(output, relative), next);
    updatedHtml++;
  }
}
assert(updatedHtml > 0);

for (const relative of inventory) {
  const original = await readFile(path.join(source, relative));
  const candidate = await readFile(path.join(output, relative));
  if (relative.endsWith(".html")) {
    let restored = candidate.toString().replaceAll(`/${nextEntryRelative}`, `/${entryRelative}`);
    if (relative === "index.html") {
      for (const { tag, managedTag } of imageTags) restored = restored.replace(managedTag, tag);
    }
    assert.equal(restored, original.toString(), `Unexpected HTML change: ${relative}`);
  } else {
    assert(original.equals(candidate), `Existing asset changed: ${relative}`);
  }
}
assert.deepEqual(await files(output), [...inventory, nextHomeRelative, nextEntryRelative].sort());
console.log(JSON.stringify({ output, updatedHtml, newAssets: [nextHomeRelative, nextEntryRelative], preservedFiles: inventory.length, note: "Homepage type and ownership of existing image tags corrected; all content, metadata values, prior assets and hosting rules retained." }, null, 2));

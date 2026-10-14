import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const [sourceArg, outputArg] = process.argv.slice(2);
assert(sourceArg && outputArg, "Usage: node scripts/apply-homepage-social-preview.mjs SOURCE OUTPUT");
const source = path.resolve(sourceArg);
const output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep), "Use a separate output directory");
await mkdir(output);

const imageRelative = "social/space-catalog-v1.png";
const imageUrl = `https://spacemusic.io/${imageRelative}`;
const imageFile = path.join(projectRoot, "marketing", imageRelative);
const png = await readFile(imageFile);
assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a", "Expected a PNG image");
const width = png.readUInt32BE(16);
const height = png.readUInt32BE(20);
assert(width >= 1200 && Math.abs(width / height - 1.91) < 0.03, "Expected a wide social image");
assert(png.length < 5_000_000, "Image must be below 5 MB");

const homepage = await readFile(path.join(source, "index.html"), "utf8");
assert(homepage.includes('rel="canonical" href="https://spacemusic.io/"'), "Unexpected homepage canonical");
assert(!homepage.includes('property="og:image"'), "Homepage already has an image; review before replacing");
const entryRelative = homepage.match(/<script type="module" crossorigin src="\/([^\"]+)"/)[1];
const entry = await readFile(path.join(source, entryRelative), "utf8");
const homeRelative = entry.match(/assets\/Index-[\w-]+\.js/)[0];
const homeModule = await readFile(path.join(source, homeRelative), "utf8");
const homeAnchor = 'canonical:"/",schema:[P,I,W,F]';
assert.equal(homeModule.split(homeAnchor).length, 2, "Unexpected homepage module; review the current build");

// Keep React Helmet's metadata consistent with the HTML seen by link crawlers.
const nextHome = homeModule.replace(homeAnchor, `canonical:"/",image:"${imageUrl}",schema:[P,I,W,F]`);
const digest = (content) => createHash("sha256").update(content).digest("hex").slice(0, 12);
const nextHomeRelative = `assets/Index-social-${digest(nextHome)}.js`;
const nextEntry = entry.replaceAll(path.basename(homeRelative), path.basename(nextHomeRelative));
const nextEntryRelative = `assets/index-social-${digest(nextEntry)}.js`;

const alt = "SPACE: Sell your music catalog. One direct buyer. One clear offer. Free evaluation. No obligation.";
const imageTags = [
  `<meta data-rh="true" property="og:image" content="${imageUrl}">`,
  `<meta property="og:image:type" content="image/png">`,
  `<meta property="og:image:width" content="${width}">`,
  `<meta property="og:image:height" content="${height}">`,
  `<meta property="og:image:alt" content="${alt}">`,
  `<meta data-rh="true" name="twitter:image" content="${imageUrl}">`,
  `<meta name="twitter:image:alt" content="${alt}">`,
].join("\n");
const oldCard = '<meta data-rh="true" name="twitter:card" content="summary">';
const newCard = oldCard.replace('content="summary"', 'content="summary_large_image"');
assert(homepage.includes(oldCard), "Unexpected Twitter card markup");

await cp(source, output, { recursive: true });
await mkdir(path.join(output, "social"), { recursive: true });
await cp(imageFile, path.join(output, imageRelative));
await writeFile(path.join(output, nextHomeRelative), nextHome);
await writeFile(path.join(output, nextEntryRelative), nextEntry);

async function htmlFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await htmlFiles(file));
    else if (entry.name.endsWith(".html")) files.push(file);
  }
  return files;
}

let updatedEntryReferences = 0;
for (const file of await htmlFiles(output)) {
  const original = await readFile(file, "utf8");
  let next = original.replaceAll(`/${entryRelative}`, `/${nextEntryRelative}`);
  if (next !== original) updatedEntryReferences++;
  if (file === path.join(output, "index.html")) {
    next = next.replace(oldCard, `${imageTags}\n${newCard}`);
  }
  assert.equal(next.split(/<body[^>]*>/i)[1], original.split(/<body[^>]*>/i)[1], "Page content must stay identical");
  if (next !== original) await writeFile(file, next);
}

console.log(JSON.stringify({
  output,
  imageUrl,
  width,
  height,
  imageBytes: png.length,
  updatedEntryReferences,
  newAssets: [nextHomeRelative, nextEntryRelative, imageRelative],
  note: "Existing assets retained; page content, URLs, canonicals, robots, sitemap and GEO files preserved.",
}, null, 2));

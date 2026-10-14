import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, realpath, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [sourceArg, outputArg, ...extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra.length, "Usage: node scripts/build-home-font-release.mjs VERIFIED_SOURCE FRESH_OUTPUT");
const source = await realpath(sourceArg);
const output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep), "Use a separate output directory");
const fontDirectory = fileURLToPath(new URL("../marketing/fonts/", import.meta.url));
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(await readFile(path.join(fontDirectory, "manifest.json"), "utf8"));
const fontCss = await readFile(path.join(fontDirectory, "fonts.css"), "utf8");
assert.equal(sha256(fontCss), manifest.cssSha256);
assert.equal(manifest.preloads.length, 2);
for (const file of manifest.files) {
  assert(/^fonts\/[a-z0-9-]+(?:\.woff2|-OFL\.txt)$/.test(file.path), "Unexpected font asset path");
  assert.equal(sha256(await readFile(path.join(fontDirectory, path.basename(file.path)))), file.sha256, file.path);
}
for (const name of ["_headers", "_redirects"]) {
  const expected = await readFile(new URL(`../marketing/ai/cloudflare/${name}`, import.meta.url));
  assert(expected.equals(await readFile(path.join(source, name))), `Review changed hosting rule: ${name}`);
}

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
const homepage = await readFile(path.join(source, "index.html"), "utf8");
assert(homepage.includes('rel="canonical" href="https://spacemusic.io/"'));
const entryPath = homepage.match(/<script type="module" crossorigin src="\/([^\"]+)"/)?.[1];
assert(entryPath, "Missing current entry script");
const entry = await readFile(path.join(source, entryPath), "utf8");
const homeModule = entry.match(/assets\/Index-[\w-]+\.js/)?.[0];
assert(homeModule && inventory.includes(homeModule), "Missing current homepage module");
const stylesheetTag = homepage.match(/<link rel="stylesheet" crossorigin href="(\/assets\/[^"]+\.css)">/);
assert(stylesheetTag, "Review changed homepage stylesheet markup");
const cssPath = stylesheetTag[1].slice(1);
const originalCss = await readFile(path.join(source, cssPath), "utf8");
const imports = manifest.families.map(family => `@import"${family.cssUrl}";`).join("");
assert(originalCss.startsWith(imports), "Expected the two verified Google Fonts imports");
const styles = originalCss.slice(imports.length);
assert(!styles.includes("@import"), "Review additional imported stylesheets");
const nextCss = fontCss + styles;
const nextCssPath = `assets/index-local-fonts-${sha256(nextCss).slice(0, 12)}.css`;
const newFiles = [...manifest.files.map(file => file.path), nextCssPath];
for (const file of newFiles) assert(!inventory.includes(file), `Do not overwrite existing assets: ${file}`);

const fontHints = homepage.match(/^.*<link[^>]+href="(?:\/\/|https:\/\/)fonts\.(?:googleapis|gstatic)\.com"[^>]*>\s*$/gm) || [];
assert.equal(fontHints.length, 4, "Review existing font connection hints");
const preloads = manifest.preloads.map(file => `    <link rel="preload" href="/${file}" as="font" type="font/woff2" crossorigin>`).join("\n");
let nextHomepage = homepage.replace(stylesheetTag[1], `/${nextCssPath}`);
for (const tag of fontHints) nextHomepage = nextHomepage.replace(tag, "");
const marker = "    <!-- Preconnect to improve font LCP -->";
assert.equal(nextHomepage.split(marker).length, 2);
nextHomepage = nextHomepage.replace(marker, `    <!-- Preload the unchanged above-the-fold fonts and homepage module -->\n${preloads}\n    <link rel="modulepreload" crossorigin href="/${homeModule}">`);
assert.equal(nextHomepage.split(/<body\b[^>]*>/i)[1], homepage.split(/<body\b[^>]*>/i)[1], "Homepage content must not change");

// Keep full blocking layout CSS for reliable first paint and no-JavaScript rendering.
await mkdir(output);
await cp(source, output, { recursive: true });
await mkdir(path.join(output, "fonts"));
for (const file of manifest.files) await cp(path.join(fontDirectory, path.basename(file.path)), path.join(output, file.path));
await writeFile(path.join(output, nextCssPath), nextCss);
await writeFile(path.join(output, "index.html"), nextHomepage);
for (const file of inventory.filter(file => file !== "index.html")) {
  assert((await readFile(path.join(source, file))).equals(await readFile(path.join(output, file))), `Unrelated file changed: ${file}`);
}
assert.deepEqual(await files(output), [...inventory, ...newFiles].sort());
console.log(JSON.stringify({ output, changedExistingFiles: ["index.html"], preservedExistingFiles: inventory.length - 1, newFiles, cssBytes: Buffer.byteLength(nextCss), note: "Same font bytes, weights, ranges, swap behavior and layout rules; other routes and all runtime scripts unchanged." }, null, 2));

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, realpath, writeFile } from "node:fs/promises";
import path from "node:path";

const [sourceArg, outputArg, ...extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra.length, "Usage: node scripts/build-clarity-release.mjs VERIFIED_SOURCE FRESH_OUTPUT");
const source = await realpath(sourceArg);
const output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const design = new URL("../marketing/design/", import.meta.url);
const fonts = new URL("fonts/", design);
const manifest = JSON.parse(await readFile(new URL("manifest.json", fonts), "utf8"));
const fontCss = await readFile(new URL("fonts.css", fonts), "utf8");
assert.equal(sha(fontCss), manifest.cssSha256);
const overlay = await readFile(new URL("clarity.css", design), "utf8");
const enhance = await readFile(new URL("enhance.js", design), "utf8");
const scriptPath = `assets/space-clarity-${sha(enhance).slice(0, 12)}.js`;
async function inventory(directory, prefix = "") {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    assert(!entry.isSymbolicLink());
    const name = path.join(prefix, entry.name);
    if (entry.isDirectory()) result.push(...await inventory(path.join(directory, entry.name), name));
    else result.push(name);
  }
  return result.sort();
}
const files = await inventory(source);
assert(!files.includes("_worker.js") && !files.includes("_routes.json"));
assert.equal(files.filter(file => file.endsWith(".html")).length, 135, "Review changes to the protected page inventory");
assert.equal((await readFile(path.join(source, "sitemap.xml"), "utf8")).match(/<loc>/g)?.length, 137);
await mkdir(output);
await cp(source, output, { recursive: true });
for (const file of manifest.files) {
  assert(/^[a-z0-9-]+(?:\.woff2|-OFL\.txt)$/.test(file.name));
  const bytes = await readFile(new URL(file.name, fonts));
  assert.equal(sha(bytes), file.sha256);
  assert(!files.includes(`fonts/${file.name}`));
  await writeFile(path.join(output, "fonts", file.name), bytes);
}
await writeFile(path.join(output, scriptPath), enhance);
const styles = new Map();
const changed = [];
for (const file of files.filter(file => file.endsWith(".html"))) {
  const original = await readFile(path.join(source, file), "utf8");
  assert(!original.includes("data-space-design="), "Build from the unmodified baseline");
  let html = original;
  const stylesheetTags = [...original.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*>/g)];
  assert(stylesheetTags.length > 0, `${file}: missing base CSS`);
  for (const [tag] of stylesheetTags) {
    const relative = tag.match(/href="\/([^"]+)"/)?.[1];
    assert(relative && files.includes(relative), `${file}: unknown stylesheet`);
    if (!styles.has(relative)) {
      const base = (await readFile(path.join(source, relative), "utf8"))
        .replace(/@import\s*(?:url\()?"https:\/\/fonts\.googleapis\.com\/[^"\n]+"\)?;/g, "")
        .replace(/@font-face\s*\{[^}]+\}/g, "");
      assert(!base.includes("fonts.googleapis.com"), `${relative}: review remaining font imports`);
      const css = fontCss + base + "\n" + overlay;
      const next = `assets/space-clarity-${sha(css).slice(0, 12)}.css`;
      assert(!files.includes(next));
      await writeFile(path.join(output, next), css);
      styles.set(relative, next);
    }
    html = html.replace(tag, tag.replace(`/${relative}`, `/${styles.get(relative)}`));
  }
  // Only presentation-related head tags change. Every body byte remains intact.
  html = html.replace(/<link\b[^>]*(?:fonts\.(?:googleapis|gstatic)\.com|as="font")[^>]*>\s*/g, "");
  const kind = file === "index.html" ? "home" : file.startsWith("apply/") ? "apply" : "content";
  html = html.replace(/<html\b/, `<html data-space-design="clarity" data-space-page="${kind}"`);
  const hint = manifest.preloads.map(href => `<link rel="preload" href="${href}" as="font" type="font/woff2" crossorigin>`).join("\n");
  html = html.replace("</head>", `${hint}\n<script defer src="/${scriptPath}"></script>\n</head>`);
  assert.equal(html.split(/<body\b[^>]*>/i)[1], original.split(/<body\b[^>]*>/i)[1], `${file}: body changed`);
  const protectedHead = text => (text.split(/<body\b/i)[0].match(/<title\b[^>]*>[\s\S]*?<\/title>|<meta\b[^>]*>|<link\b[^>]*rel="canonical"[^>]*>|<script\b[^>]*type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/g) || []);
  assert.deepEqual(protectedHead(html), protectedHead(original), `${file}: SEO metadata changed`);
  await writeFile(path.join(output, file), html);
  changed.push(file);
}
for (const file of files.filter(file => !changed.includes(file))) {
  assert((await readFile(path.join(source, file))).equals(await readFile(path.join(output, file))), `${file}: existing asset changed`);
}
console.log(JSON.stringify({ output, htmlPages: changed.length, bodyBytes: "Identical for every HTML page", metadata: "Identical titles, metadata, canonicals and schema", originalAssets: "All preserved byte for byte", styles: Object.fromEntries(styles), scriptPath, newFiles: (await inventory(output)).filter(file => !files.includes(file)) }, null, 2));

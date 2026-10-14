import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = fileURLToPath(new URL("../marketing/fonts/", import.meta.url));
const agent = "Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36";
const families = [
  { name: "Fraunces", slug: "fraunces", query: "Fraunces:opsz,wght@9..144,500..700", subsets: ["vietnamese", "latin-ext", "latin"] },
  { name: "Plus Jakarta Sans", slug: "plus-jakarta-sans", licensePath: "plusjakartasans", query: "Plus+Jakarta+Sans:wght@300..700", subsets: ["cyrillic-ext", "vietnamese", "latin-ext", "latin"] },
];
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
async function download(url) {
  const response = await fetch(url, { headers: { "User-Agent": agent }, signal: AbortSignal.timeout(20000) });
  assert.equal(response.status, 200, url);
  return Buffer.from(await response.arrayBuffer());
}

// Store provider declarations and hashes so later builds never depend on a changing API.
await mkdir(directory);
const manifest = { fetchedAt: new Date().toISOString(), userAgent: agent, families: [], files: [], preloads: [] };
const declarations = [];
for (const family of families) {
  const cssUrl = `https://fonts.googleapis.com/css2?family=${family.query}&display=swap`;
  const original = (await download(cssUrl)).toString();
  const faces = [...original.matchAll(/\/\*\s*([^*]+?)\s*\*\/\s*(@font-face\s*\{[^}]+\})/g)];
  assert.deepEqual(faces.map(match => match[1]), family.subsets, `Review changed subsets for ${family.name}`);
  await writeFile(path.join(directory, `${family.slug}.google.css`), original);
  for (const [, subset, face] of faces) {
    assert(face.includes(`font-family: '${family.name}'`));
    assert(face.includes("font-display: swap;"));
    const urls = [...face.matchAll(/url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.woff2)\)/g)].map(match => match[1]);
    assert.equal(urls.length, 1);
    const bytes = await download(urls[0]);
    assert.equal(bytes.subarray(0, 4).toString(), "wOF2", urls[0]);
    const digest = sha256(bytes);
    const relative = `fonts/${family.slug}-${subset}-${digest.slice(0, 12)}.woff2`;
    await writeFile(path.join(directory, path.basename(relative)), bytes);
    declarations.push(`/* ${family.name}: ${subset} */\n${face.replace(urls[0], `/${relative}`)}`);
    manifest.files.push({ path: relative, source: urls[0], sha256: digest, bytes: bytes.length });
    if (subset === "latin") manifest.preloads.push(relative);
  }
  const licenseUrl = `https://raw.githubusercontent.com/google/fonts/main/ofl/${family.licensePath || family.slug}/OFL.txt`;
  const license = await download(licenseUrl);
  assert(license.toString().includes("SIL OPEN FONT LICENSE Version 1.1"));
  assert(license.toString().includes("redistributed freely"));
  const relative = `fonts/${family.slug}-OFL.txt`;
  await writeFile(path.join(directory, path.basename(relative)), license);
  manifest.files.push({ path: relative, source: licenseUrl, sha256: sha256(license), bytes: license.length });
  manifest.families.push({ name: family.name, cssUrl, cssSha256: sha256(original), licenseUrl });
}
const css = declarations.join("\n") + "\n";
manifest.cssSha256 = sha256(css);
await writeFile(path.join(directory, "fonts.css"), css);
await writeFile(path.join(directory, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(JSON.stringify({ directory, fonts: manifest.files.filter(file => file.path.endsWith(".woff2")).length, licenses: families.length, preloads: manifest.preloads }, null, 2));

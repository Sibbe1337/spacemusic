import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";

const directory = new URL("../marketing/design/fonts/", import.meta.url);
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const provider = "https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap";
async function download(url) {
  const response = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36" },
    signal: AbortSignal.timeout(20000),
  });
  assert.equal(response.status, 200, url);
  return Buffer.from(await response.arrayBuffer());
}
await mkdir(directory, { recursive: true });
const original = (await download(provider)).toString();
const manifest = { provider, fetchedAt: new Date().toISOString(), files: [], preloads: [] };
const declarations = [];
for (const [, subset, face] of original.matchAll(/\/\*\s*([^*]+?)\s*\*\/\s*(@font-face\s*\{[^}]+\})/g)) {
  assert(/^[a-z-]+$/.test(subset));
  assert(face.includes("font-family: 'Inter'") && face.includes("font-display: swap"));
  const url = face.match(/url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.woff2)\)/)?.[1];
  assert(url, "Expected WOFF2 provider response");
  const bytes = await download(url);
  assert.equal(bytes.subarray(0, 4).toString(), "wOF2");
  const name = `inter-${subset}-${sha(bytes).slice(0, 12)}.woff2`;
  await writeFile(new URL(name, directory), bytes);
  manifest.files.push({ name, sha256: sha(bytes), source: url, bytes: bytes.length });
  if (subset === "latin") manifest.preloads.push(`/fonts/${name}`);
  declarations.push(`/* Inter: ${subset} */\n${face.replace(url, `/fonts/${name}`)}`);
}
assert.equal(manifest.preloads.length, 1);
const licenseUrl = "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/OFL.txt";
const license = await download(licenseUrl);
assert(license.toString().includes("SIL OPEN FONT LICENSE Version 1.1"));
await writeFile(new URL("inter-OFL.txt", directory), license);
manifest.files.push({ name: "inter-OFL.txt", sha256: sha(license), source: licenseUrl, bytes: license.length });
const css = declarations.join("\n") + "\n";
manifest.cssSha256 = sha(css);
await writeFile(new URL("fonts.css", directory), css);
await writeFile(new URL("provider.css", directory), original);
await writeFile(new URL("manifest.json", directory), JSON.stringify(manifest, null, 2) + "\n");
console.log(JSON.stringify(manifest, null, 2));

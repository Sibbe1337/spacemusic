import assert from "node:assert/strict";
import { cp, mkdir, readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [sourceArg, outputArg, ...extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra.length, "Usage: node scripts/build-llms-routing-release.mjs SOURCE OUTPUT");
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep), "Use a separate output directory");
const project = fileURLToPath(new URL("../", import.meta.url));
const files = [];
for (const name of await readdir(source, { recursive: true })) {
  if ((await stat(path.join(source, name))).isFile()) files.push(name);
}
for (const config of ["_headers", "_redirects", "_worker.js", "_routes.json"]) {
  assert(!files.includes(config), `Review existing ${config} before changing routing`);
}
assert((await readFile(path.join(source, "llms.txt"))).equals(await readFile(path.join(project, "marketing/ai/llms.txt"))), "Use the current verified text file");
const configs = {
  _headers: '/llms.txt\n  Link: <https://spacemusic.io/llms.txt>; rel="canonical"\n',
  _redirects: '/llms.txt/ /llms.txt 301\n',
};
for (const [name, expected] of Object.entries(configs)) {
  assert.equal(await readFile(path.join(project, "marketing/ai/cloudflare", name), "utf8"), expected, "This release must only affect llms.txt");
}
await mkdir(output);
await cp(source, output, { recursive: true });
for (const name of Object.keys(configs)) await cp(path.join(project, "marketing/ai/cloudflare", name), path.join(output, name));
for (const name of files) assert((await readFile(path.join(source, name))).equals(await readFile(path.join(output, name))), `Public file changed: ${name}`);
const added = (await readdir(output, { recursive: true })).filter((name) => !files.includes(name) && Object.keys(configs).includes(name));
assert.deepEqual(added.sort(), Object.keys(configs).sort());
console.log(JSON.stringify({ output, preservedPublicFiles: files.length, addedHostingConfiguration: added, htmlAndContentChanges: 0, requiresRoutingVerification: true }, null, 2));

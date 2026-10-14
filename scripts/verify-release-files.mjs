import assert from "node:assert/strict";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";

const [directoryArg, originArg = "https://spacemusic.io", ...extra] = process.argv.slice(2);
assert(directoryArg && !extra.length, "Usage: node scripts/verify-release-files.mjs DIRECTORY [ORIGIN]");
const root = path.resolve(directoryArg), origin = new URL(originArg).origin;
assert(/^https?:\/\//.test(origin));
// Pages parses these configuration files; it does not serve them as public assets.
const configs = new Set(["_headers", "_redirects"]);
const publicFiles = [], controlFiles = [];
for (const file of await readdir(root, { recursive: true })) {
  if (!(await stat(path.join(root, file))).isFile()) continue;
  assert(!["_worker.js", "_routes.json"].includes(file), "Review the verifier for a non-static release");
  (configs.has(file) ? controlFiles : publicFiles).push(file);
}
const mismatches = [];
for (let start = 0; start < publicFiles.length; start += 8) {
  await Promise.all(publicFiles.slice(start, start + 8).map(async (file) => {
    const url = origin + "/" + file.replace(/(^|\/)index\.html$/, "$1");
    try {
      const response = await fetch(url, { redirect: "manual", signal: AbortSignal.timeout(20000) });
      const body = Buffer.from(await response.arrayBuffer());
      if (response.status !== 200 || !(await readFile(path.join(root, file))).equals(body)) {
        mismatches.push({ file, status: response.status });
      }
    } catch (error) { mismatches.push({ file, error: error.message }); }
  }));
}
console.log(JSON.stringify({ origin, publicFiles: publicFiles.length, hostingConfigurationNotServed: controlFiles, mismatches }, null, 2));
assert.equal(mismatches.length, 0, "Live files do not match the release");

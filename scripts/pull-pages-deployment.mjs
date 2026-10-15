import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

// Downloads every file of a Cloudflare Pages deployment into DIRECTORY using the
// deployment's own file manifest, so a new release starts from the exact live artifact.
// _headers/_redirects are not served by Pages; copy them from the committed bundle mirror.
//
// Usage: CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... \
//   node scripts/pull-pages-deployment.mjs DIRECTORY [DEPLOYMENT_ID|production] [PROJECT]

const [dirArg, deploymentArg = "production", project = "spacemusic", ...extra] = process.argv.slice(2);
assert(dirArg && !extra.length, "Usage: node scripts/pull-pages-deployment.mjs DIRECTORY [DEPLOYMENT_ID|production] [PROJECT]");
const { CLOUDFLARE_API_TOKEN: token, CLOUDFLARE_ACCOUNT_ID: account } = process.env;
assert(token && account, "Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID");
const root = path.resolve(dirArg);
const api = `https://api.cloudflare.com/client/v4/accounts/${account}/pages/projects/${project}`;

async function cf(endpoint) {
  const res = await fetch(api + endpoint, { headers: { Authorization: `Bearer ${token}` } });
  const body = await res.json();
  assert(body.success, `Cloudflare API ${endpoint} failed: ${JSON.stringify(body.errors)}`);
  return body.result;
}

let deploymentId = deploymentArg;
if (deploymentArg === "production") {
  const list = await cf("/deployments?env=production&per_page=1");
  deploymentId = list[0].id;
}
const deployment = await cf(`/deployments/${deploymentId}`);
const files = Object.entries(deployment.files || {});
assert(files.length > 0, "Deployment has no file manifest");

// Pages hashes assets as blake3(base64(content) + extension) truncated to 32 hex chars.
let blake3 = null;
for (const candidate of [process.env.BLAKE3_WASM_PATH, "blake3-wasm"].filter(Boolean)) {
  try {
    blake3 = createRequire(import.meta.url)(candidate);
    break;
  } catch {}
}

const failures = [];
let verified = 0;
for (let i = 0; i < files.length; i += 8) {
  await Promise.all(
    files.slice(i, i + 8).map(async ([file, hash]) => {
      const urlPath = file.replace(/(^|\/)index\.html$/, "$1").replace(/\.html$/, "");
      try {
        const res = await fetch(deployment.url + urlPath, { signal: AbortSignal.timeout(30000) });
        assert.equal(res.status, 200, `HTTP ${res.status}`);
        const bytes = Buffer.from(await res.arrayBuffer());
        if (blake3) {
          const ext = path.extname(file).slice(1);
          const digest = blake3.hash(bytes.toString("base64") + ext).toString("hex").slice(0, 32);
          assert.equal(digest, hash, "content hash mismatch");
          verified++;
        }
        const dest = path.join(root, file);
        await mkdir(path.dirname(dest), { recursive: true });
        await writeFile(dest, bytes);
      } catch (error) {
        failures.push({ file, error: error.message });
      }
    }),
  );
}
console.log(
  JSON.stringify(
    { deployment: deployment.short_id, url: deployment.url, files: files.length, hashVerified: verified, failures },
    null,
    2,
  ),
);
assert.equal(failures.length, 0, "Some deployment files could not be pulled");

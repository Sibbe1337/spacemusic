import { mkdir, readFile, writeFile, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const build = path.join(here, 'build');
const frontend = path.join(build, 'frontend');
const backend = path.join(build, 'backend');
for (const dir of [path.join(frontend, 'public/workspace'), path.join(frontend, 'api/portal'), backend]) await mkdir(dir, { recursive: true });
const manifest = {};
const copy = async (source, destination) => {
  const bytes = await readFile(path.join(root, source));
  manifest[source] = createHash('sha256').update(bytes).digest('hex');
  await writeFile(destination, bytes);
};
for (const name of ['client.mjs', 'portal.css']) await copy(`services/catalog_review_ui/${name}`, path.join(frontend, 'public/workspace', name));
await copy('services/catalog_review_preview/ui/review.css', path.join(frontend, 'public/workspace/review.css'));
await copy('marketing/identity-20260916/space-wordmark.svg', path.join(frontend, 'public/workspace/space-wordmark.svg'));
await copy('marketing/design/fonts/inter-latin-c940764593d0.woff2', path.join(frontend, 'public/workspace/inter.woff2'));
await copyFile(path.join(frontend, 'public/workspace/inter.woff2'), path.join(frontend, 'public/inter.woff2'));
await copy('services/catalog_review_ui/app.mjs', path.join(frontend, 'public/workspace/app.mjs'));
const appFile = path.join(frontend, 'public/workspace/app.mjs');
const app = await readFile(appFile, 'utf8');
const autoboot = "if (typeof window !== 'undefined' && window.document.querySelector('#content')) createApp();";
if (!app.includes(autoboot)) throw new Error('UI boot contract changed; review preview adapter');
await writeFile(appFile, app.replace(autoboot, '// Started by the separate read-only preview adapter.'));
let html = await readFile(path.join(root, 'services/catalog_review_ui/index.html'), 'utf8');
html = html.replace('src="/workspace/app.mjs"', 'src="/workspace/preview.mjs"')
  .replace('</head>', '<link rel="stylesheet" href="/workspace/preview.css">\n  </head>')
  .replace('<title>Catalog review | SPACE</title>', '<title>Portal preview | SPACE</title>')
  .replace('<strong>Integration test</strong>', '<strong>Design preview</strong>')
  .replace('Integration test / synthetic only', 'Read-only preview / fictional records')
  .replace('<div class="workspace">', `<section class="preview-switcher" aria-labelledby="preview-heading">
      <h2 id="preview-heading">Explore the catalog review</h2>
      <nav aria-label="Preview stages">
        <a data-scenario="draft" href="/workspace/?scenario=draft">01 &nbsp; Catalog &amp; documents</a>
        <a data-scenario="submitted" href="/workspace/?scenario=submitted">02 &nbsp; Submitted</a>
        <a data-scenario="followup" href="/workspace/?scenario=followup">03 &nbsp; Information requested</a>
        <a data-scenario="completed" href="/workspace/?scenario=completed">04 &nbsp; Supplement received</a>
        <a data-scenario="reviewer" href="/workspace/?scenario=reviewer">05 &nbsp; Reviewer view</a>
      </nav>
      <p id="preview-status" role="status">Loading fictional example records. This preview cannot accept uploads, edits, payments or real customer information.</p>
    </section><div class="workspace">`);
await writeFile(path.join(frontend, 'public/workspace/index.html'), html);
for (const name of ['preview.mjs', 'preview.css']) await copyFile(path.join(here, name), path.join(frontend, 'public/workspace', name));
await copyFile(path.join(here, 'gateway.mjs'), path.join(frontend, 'api/portal/workspace.mjs'));
await writeFile(path.join(frontend, 'public/robots.txt'), 'User-agent: *\nDisallow: /\n');
await writeFile(path.join(frontend, 'package.json'), JSON.stringify({ name: 'space-review-preview', private: true, type: 'module', engines: { node: '24.x' } }, null, 2));
await writeFile(path.join(frontend, 'vercel.json'), JSON.stringify({
  $schema: 'https://openapi.vercel.sh/vercel.json', framework: null,
  outputDirectory: 'public', cleanUrls: true, trailingSlash: false,
  functions: { 'api/portal/workspace.mjs': { maxDuration: 10 } },
  redirects: [{ source: '/', destination: '/workspace', permanent: false }],
  rewrites: [{ source: '/workspace', destination: '/workspace/index.html' }],
  headers: [{ source: '/(.*)', headers: [
    { key: 'X-Robots-Tag', value: 'noindex, nofollow, noarchive' },
    { key: 'Cache-Control', value: 'no-store' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'no-referrer' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
    { key: 'Content-Security-Policy', value: "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" },
  ] }],
}, null, 2));
for (const name of ['server.mjs', 'scenarios.mjs']) await copyFile(path.join(here, name), path.join(backend, name));
await writeFile(path.join(backend, 'package.json'), JSON.stringify({ name: 'space-review-preview-api', private: true, type: 'module', engines: { node: '24.x' }, scripts: { start: 'node server.mjs' } }, null, 2));
await writeFile(path.join(backend, 'railway.json'), JSON.stringify({ $schema: 'https://railway.com/railway.schema.json', build: { builder: 'RAILPACK' }, deploy: { startCommand: 'node server.mjs', healthcheckPath: '/healthz', healthcheckTimeout: 30, restartPolicyType: 'ON_FAILURE', restartPolicyMaxRetries: 3, numReplicas: 1 } }, null, 2));
await writeFile(path.join(build, 'source-manifest.json'), JSON.stringify(manifest, null, 2));
console.log('Built isolated frontend/backend allowlists. No customer data, secrets or production server included.');

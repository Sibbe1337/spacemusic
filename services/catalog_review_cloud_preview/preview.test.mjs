import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { createServer } from './server.mjs';
import { workspaceFor, SCENARIOS } from './scenarios.mjs';
import { proxyWorkspace } from './gateway.mjs';
import { validateWorkspace } from '../catalog_review_ui/app.mjs';

for (const scenario of SCENARIOS) test(`current UI accepts ${scenario} synthetic contract`, () => {
  const value = validateWorkspace(workspaceFor(scenario));
  assert.equal(value.environment, 'test');
  assert.equal(value.role, scenario === 'reviewer' ? 'reviewer' : 'owner');
  assert.equal(value.capabilities.toolost, false);
  if (value.submission) assert.equal(value.submission.snapshot.documents.length, 2);
  if (['completed', 'reviewer'].includes(scenario)) assert.equal(value.documents.length, 3);
});

test('scenario records are isolated and the original submission is immutable across stages', () => {
  const first = workspaceFor('completed');
  first.draft.rights[0].title = 'Changed';
  assert.notEqual(workspaceFor('completed').draft.rights[0].title, 'Changed');
  assert.notEqual(first.submission.snapshot.draft.rights[0].title, 'Changed');
  assert.throws(() => workspaceFor('customer-123'));
});

test('Railway preview permits exact reads only, including healthy HEAD', async t => {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(`${base}/healthz`, { method: 'HEAD' })).status, 200);
  for (const scenario of SCENARIOS) {
    const result = await fetch(`${base}/preview/${scenario}`);
    assert.equal(result.status, 200);
    assert.match(result.headers.get('x-robots-tag'), /noindex/);
    assert.equal(result.headers.get('cache-control'), 'no-store');
    assert.equal(result.headers.get('access-control-allow-origin'), null);
    validateWorkspace(await result.json());
  }
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']) {
    assert.equal((await fetch(`${base}/preview/draft`, { method })).status, 405);
  }
  for (const route of ['/preview/draft?email=example', '/api/portal/documents', '/.env', '/preview/unknown']) {
    assert.equal((await fetch(base + route)).status, 404);
  }
});

function mockResponse() {
  return { headers: {}, setHeader(key, value) { this.headers[key] = value; }, end(value) { this.value = JSON.parse(value); } };
}
const request = (headers = {}) => ({ method: 'GET', url: '/api/portal/workspace', headers });
const backend = 'https://example-preview.up.railway.app';
const reply = () => new Response(JSON.stringify(workspaceFor('draft')), { headers: { 'Content-Type': 'application/json' } });

test('gateway calls only the fixed Railway endpoint without forwarding browser credentials', async () => {
  const res = mockResponse();
  await proxyWorkspace(request({ authorization: 'secret', cookie: 'private', 'x-preview-scenario': 'draft' }), res, {
    backend, fetchImpl: async (url, options) => {
      assert.equal(url, backend + '/preview/draft');
      assert.deepEqual(options.headers, { Accept: 'application/json' });
      assert.equal(options.redirect, 'error');
      return reply();
    },
  });
  assert.equal(res.statusCode, 200);
});

for (const target of [undefined, 'https://evil.example/', 'http://localhost/', 'https://user@example-preview.up.railway.app/', backend + '/arbitrary', backend + '?url=secret']) {
  test(`gateway refuses invalid configuration ${target}`, async () => {
    const res = mockResponse();
    await proxyWorkspace(request(), res, { backend: target, fetchImpl: () => assert.fail('Must not fetch') });
    assert.equal(res.statusCode, 503);
  });
}

test('gateway rejects writes, parameters and unknown scenarios before any provider request', async () => {
  for (const req of [{ ...request(), method: 'POST' }, { ...request(), url: '/api/portal/workspace?token=x' }, request({ 'x-preview-scenario': '../private' }), request({ 'content-length': '10' })]) {
    const res = mockResponse();
    await proxyWorkspace(req, res, { backend, fetchImpl: () => assert.fail('Must not fetch') });
    assert.ok([400, 405].includes(res.statusCode));
  }
});

test('gateway fails closed on timeout, excessive size, non-JSON or production records', async () => {
  const cases = [
    () => Promise.reject(new Error('secret upstream details')),
    () => new Response('x'.repeat(70000), { headers: { 'Content-Type': 'application/json' } }),
    () => new Response('<html>upstream</html>'),
    () => new Response(JSON.stringify({ ...workspaceFor('draft'), environment: 'production' }), { headers: { 'Content-Type': 'application/json' } }),
  ];
  for (const fetchImpl of cases) {
    const res = mockResponse();
    await proxyWorkspace(request(), res, { backend, fetchImpl });
    assert.equal(res.statusCode, 502);
    assert.doesNotMatch(JSON.stringify(res.value), /secret upstream details/);
  }
});

test('preview build is allowlisted and local browser exercises all current UI stages', async t => {
  const result = spawnSync(process.execPath, [new URL('./build.mjs', import.meta.url).pathname], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(await readFile(new URL('./build/frontend/vercel.json', import.meta.url), 'utf8'));
  assert.ok(config.headers[0].headers.some(header => header.key === 'X-Robots-Tag' && header.value.includes('noindex')));
  const runtime = createRequire(`${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json`);
  const { chromium } = runtime('playwright');
  const api = createServer();
  await new Promise(resolve => api.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => api.close(resolve)));
  const apiOrigin = `http://127.0.0.1:${api.address().port}`;
  const types = { '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
  const files = new Map();
  for (const name of ['index.html', 'app.mjs', 'client.mjs', 'review.css', 'portal.css', 'preview.mjs', 'preview.css', 'inter.woff2', 'space-wordmark.svg']) {
    files.set('/workspace/' + name, await readFile(new URL('./build/frontend/public/workspace/' + name, import.meta.url)));
  }
  const frontend = http.createServer(async (req, res) => {
    const path = new URL(req.url, 'http://localhost').pathname;
    if (path === '/api/portal/workspace') return proxyWorkspace(req, res, {
      backend, fetchImpl: (url, options) => fetch(apiOrigin + new URL(url).pathname, options),
    });
    const resolved = ['/workspace', '/workspace/'].includes(path) ? '/workspace/index.html' : path === '/inter.woff2' ? '/workspace/inter.woff2' : path;
    const file = files.get(resolved);
    if (!file) { res.writeHead(404); res.end(); return; }
    for (const { key, value } of config.headers[0].headers) res.setHeader(key, value);
    res.setHeader('Content-Type', types[resolved.slice(resolved.lastIndexOf('.'))]);
    res.end(file);
  });
  await new Promise(resolve => frontend.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => frontend.close(resolve)));
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  t.after(() => browser.close());
  const page = await browser.newPage();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { assert.equal(req.method(), 'GET'); assert.match(req.url(), /^http:\/\/127\.0\.0\.1:/); });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    for (const scenario of SCENARIOS) {
      await page.goto(`http://127.0.0.1:${frontend.address().port}/workspace/?scenario=${scenario}`);
      await page.waitForFunction(() => document.querySelector('#preview-status').textContent.includes('loaded from the isolated preview API'));
      await page.waitForFunction(() => document.querySelector('main').getAttribute('aria-busy') === 'false');
      assert.equal(await page.locator('[aria-current="page"]').getAttribute('data-scenario'), scenario);
      assert.equal(await page.locator('main input:enabled, main textarea:enabled, main select:enabled').count(), 0);
      assert.equal(await page.locator('main button:enabled:not([data-action="refresh"])').count(), 0);
      assert.ok(await page.locator('main h1').count());
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
      if (scenario === 'reviewer') assert.match(await page.locator('main').textContent(), /reviewer/i);
    }
  }
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: new URL('./build/preview-desktop.png', import.meta.url).pathname, fullPage: true });
  assert.deepEqual(errors, []);
});

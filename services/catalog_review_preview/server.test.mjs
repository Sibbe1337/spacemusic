import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createPreviewServer } from './server.mjs';

const server = createPreviewServer();
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
test.after(() => new Promise(resolve => server.close(resolve)));
function request(url, { method = 'GET', headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, path: url, method, headers }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({ status: response.statusCode, headers: response.headers, body: Buffer.concat(chunks).toString() }));
    });
    req.on('error', reject); req.end();
  });
}
test('local shell is noindex, no-store, not frameable, and cannot contact any provider', async () => {
  const response = await request('/');
  assert.equal(response.status, 200);
  assert.match(response.headers['x-robots-tag'], /noindex/);
  assert.equal(response.headers['cache-control'], 'no-store');
  assert.match(response.headers['content-security-policy'], /connect-src 'none'/);
  assert.match(response.headers['content-security-policy'], /frame-ancestors 'none'/);
  assert.match(response.headers['content-security-policy'], /form-action 'none'/);
  assert.match(response.body, /Synthetic data only/);
  assert.match(response.body, /<noscript>/);
  assert.doesNotMatch(response.body, /plausible|typeform|resend|https:\/\//i);
});
test('only explicit public preview assets are served', async () => {
  for (const path of ['/app.mjs', '/review.css', '/model.mjs', '/fixtures.mjs', '/storage.mjs', '/space-wordmark.svg', '/inter.woff2']) assert.equal((await request(path)).status, 200, path);
});
test('filesystem, arbitrary routes, callbacks and query strings are not exposed', async () => {
  for (const path of ['/server.mjs', '/README.md', '/.env', '/../../README.md', '/%2e%2e/README.md', '/api/portal/', '/api/integrations/toolost/callback', '/?code=secret', '/app.mjs?x=1']) assert.equal((await request(path)).status, 404, path);
});
test('mutations cannot create an application or upload content', async () => {
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) assert.equal((await request('/', { method })).status, 405);
});
test('DNS rebinding and alternate hostnames fail closed', async () => {
  for (const host of ['evil.example', `localhost:${port}`, 'spacemusic.io', '127.0.0.1:1']) assert.equal((await request('/', { headers: { host } })).status, 403);
});
test('external top-level navigation works, cross-site embedded/fetch access does not', async () => {
  assert.equal((await request('/', { headers: { 'sec-fetch-site': 'cross-site', 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document' } })).status, 200);
  assert.equal((await request('/', { headers: { 'sec-fetch-site': 'cross-site', 'sec-fetch-mode': 'cors' } })).status, 403);
  assert.equal((await request('/fixtures.mjs', { headers: { 'sec-fetch-site': 'cross-site' } })).status, 403);
});
test('HEAD returns headers but no body', async () => {
  const result = await request('/', { method: 'HEAD' });
  assert.equal(result.status, 200); assert.equal(result.body, '');
});

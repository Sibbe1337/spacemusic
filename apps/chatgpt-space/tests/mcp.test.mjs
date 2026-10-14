import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { get } from 'node:http';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { createHttpServer, stopHttpServer } from '../server/http.mjs';
import { WIDGET_URI } from '../server/mcp.mjs';
import { snapshotSchema } from '../shared/contract.mjs';

let server, client, base;
before(async () => {
  server = createHttpServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  base = `http://127.0.0.1:${server.address().port}`;
  client = new Client({ name: 'space-contract-tests', version: '1.0.0' });
  await client.connect(new StreamableHTTPClientTransport(new URL(`${base}/mcp`)));
});
after(async () => { await client?.close(); server?.closeAllConnections(); await new Promise(resolve => server.close(resolve)); });

test('real MCP handshake discovers exactly three read-only, closed-world demo tools', async () => {
  const { tools } = await client.listTools();
  assert.equal(tools.length, 3);
  for (const tool of tools) {
    assert.match(tool.description, /^Use this when/);
    assert.deepEqual(tool.annotations, { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true });
    assert.equal(tool._meta.ui.resourceUri, WIDGET_URI);
    assert.equal(tool.inputSchema.additionalProperties, false);
    assert.ok(tool.outputSchema);
  }
});
test('all tools execute over HTTP with text fallback and schema-valid structured results', async () => {
  const inputs = [['space_list_demo_catalogs', {}]];
  for (const case_id of ['demo-harbor', 'demo-juniper', 'demo-northline']) {
    inputs.push(['space_review_demo_catalog', { case_id }], ['space_compare_demo_buyers', { case_id }]);
  }
  for (const [name, args] of inputs) {
    const value = await client.callTool({ name, arguments: args });
    assert.notEqual(value.isError, true);
    assert.equal(snapshotSchema.safeParse(value.structuredContent).success, true);
    assert.match(value.content[0].text, /Fictional/);
  }
});
test('resource discovery and read return a self-contained MCP Apps widget with narrow CSP', async () => {
  assert.equal((await client.listResources()).resources[0].uri, WIDGET_URI);
  const { contents } = await client.readResource({ uri: WIDGET_URI });
  assert.equal(contents[0].mimeType, 'text/html;profile=mcp-app');
  assert.deepEqual(contents[0]._meta.ui.csp, { connectDomains: [], resourceDomains: [] });
  assert.match(contents[0].text, /Fictional data only/);
  assert.doesNotMatch(contents[0].text, /<script[^>]+src=|<link[^>]+href=|SPACE_SCRIPT|SPACE_FONT_DATA/);
});
test('unknown IDs, unbounded extra parameters and write operations are rejected', async () => {
  for (const [name, args] of [
    ['space_review_demo_catalog', { case_id: 'customer-42' }],
    ['space_review_demo_catalog', { case_id: 'demo-harbor', file: '/private/customer.pdf' }],
    ['space_list_demo_catalogs', { query: 'person@example.com' }],
    ['send_to_buyer', { case_id: 'demo-harbor' }],
  ]) {
    const result = await client.callTool({ name, arguments: args });
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent, undefined);
  }
});
test('private files, portal routes and OAuth discovery are not exposed', async () => {
  for (const path of ['/private/', '/server/fixtures.mjs', '/api/intake/typeform', '/.env', '/.well-known/oauth-authorization-server']) {
    assert.equal((await fetch(base + path)).status, 404);
  }
});
test('untrusted origins including marketing subdomains are refused', async () => {
  for (const origin of ['https://spacemusic.io', 'https://review.spacemusic.io', 'null', 'https://evil.example']) {
    assert.equal((await fetch(`${base}/mcp`, { method: 'POST', headers: { Origin: origin } })).status, 403);
  }
  // Node fetch normalizes Host; use the raw HTTP client to exercise DNS-rebinding protection.
  const status = await new Promise((resolve, reject) => {
    get(base, { headers: { Host: 'evil.example' } }, response => {
      resolve(response.statusCode); response.resume();
    }).on('error', reject);
  });
  assert.equal(status, 403);
});
test('the local preview receives real transport responses and noindex headers', async () => {
  const response = await fetch(base);
  assert.equal(response.status, 200);
  assert.match(response.headers.get('x-robots-tag'), /noindex/);
  assert.match(response.headers.get('content-security-policy'), /frame-ancestors 'none'/);
  assert.match(await response.text(), /Not connected to ChatGPT/);
});
test('oversized, malformed and wrong content-type requests fail closed', async () => {
  for (const [body, type, status] of [
    ['{', 'application/json', 400], ['[]', 'application/json', 400],
    ['{}', 'text/plain', 415], ['x'.repeat(17000), 'application/json', 413],
  ]) {
    assert.equal((await fetch(`${base}/mcp`, { method: 'POST', headers: { 'Content-Type': type }, body })).status, status);
  }
});
test('widget inline bundle parses after HTML embedding, including literal dollar substitutions', () => {
  const html = readFileSync(new URL('../dist/widget.html', import.meta.url), 'utf8');
  const script = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  const check = spawnSync(process.execPath, ['--input-type=module', '--check'], { input: script, encoding: 'utf8' });
  assert.equal(check.status, 0, check.stderr);
});
test('public origin configuration cannot add credentials, paths or plain HTTP', () => {
  for (const origin of ['http://example.com', 'https://example.com/private', 'https://key@example.com', 'https://example.com/?secret=x']) {
    assert.throws(() => createHttpServer({ origin }));
  }
});

test('shutdown closes an active SDK client and persistent MCP event stream', { timeout: 3000 }, async () => {
  const instance = createHttpServer();
  instance.listen(0, '127.0.0.1'); await once(instance, 'listening');
  const url = new URL(`http://127.0.0.1:${instance.address().port}/mcp`);
  const active = new Client({ name: 'shutdown-test', version: '1.0.0' });
  let request;
  try {
    await active.connect(new StreamableHTTPClientTransport(url));
    const response = await new Promise((resolve, reject) => {
      request = get(url, { headers: { Accept: 'text/event-stream' } }, resolve).on('error', reject);
    });
    assert.equal(response.statusCode, 200);
    response.on('error', () => {});
    const stopped = stopHttpServer(instance);
    await stopped;
    assert.equal(instance.listening, false);
  } finally {
    request?.destroy();
    await active.close();
    await stopHttpServer(instance);
  }
});

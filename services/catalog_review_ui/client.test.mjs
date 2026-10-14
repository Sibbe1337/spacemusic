import test from 'node:test';
import assert from 'node:assert/strict';
import { createClient, PortalError, errorMessage } from './client.mjs';

const response = (body = {}, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const ID = '10000000-0000-4000-8000-000000000001';

test('only fixed same-origin endpoints; no cache, redirects, referrers or ambient cross-origin credentials', async () => {
  const calls = [];
  const client = createClient({ fetchImpl: async (path, options) => { calls.push({ path, ...options }); return response(); } });
  await client.exchange('memory-only-invitation');
  client.setCsrf('test-csrf');
  await client.workspace();
  await client.save(3, { source: 'documents' });
  await client.submit({ request_id: ID, revision: 3, consent: true });
  await client.question({ request_id: ID, body: 'Synthetic question' });
  await client.reply(ID, { request_id: ID, body: 'Synthetic reply' });
  await client.deletion();
  await client.access(ID, 'synthetic@example.com');
  for (const call of calls) {
    assert.match(call.path, /^\/api\/portal\//);
    assert.equal(call.credentials, 'same-origin');
    assert.equal(call.mode, 'same-origin');
    assert.equal(call.cache, 'no-store');
    assert.equal(call.redirect, 'error');
    assert.equal(call.referrerPolicy, 'no-referrer');
    assert.ok(call.signal instanceof AbortSignal);
  }
  assert.equal(calls[0].headers['X-CSRF-Token'], undefined);
  assert.equal(calls[1].headers['X-CSRF-Token'], undefined);
  assert.equal(calls[2].headers['X-CSRF-Token'], 'test-csrf');
  assert.deepEqual(JSON.parse(calls[2].body), { revision: 3, draft: { source: 'documents' } });
  assert.equal(calls.at(-1).headers['X-CSRF-Token'], undefined);
  await assert.rejects(client.reply('https://outside.invalid/path', {}), PortalError);
  assert.equal(calls.length, 8);
});

test('HTTP failures never consume or expose server error bodies', async () => {
  for (const status of [401, 403, 409, 429, 500]) {
    let read = false;
    const client = createClient({ fetchImpl: async () => ({ ok: false, status, json() { read = true; throw Error('PRIVATE'); } }) });
    await assert.rejects(client.workspace(), error => {
      assert.equal(error.status, status);
      assert.doesNotMatch(error.message + errorMessage(error), /PRIVATE/);
      return true;
    });
    assert.equal(read, false);
  }
});

test('HTML, malformed JSON and network exceptions become generic errors', async () => {
  for (const fetchImpl of [
    async () => new Response('<html>PRIVATE</html>', { headers: { 'Content-Type': 'text/html' } }),
    async () => new Response('PRIVATE', { headers: { 'Content-Type': 'application/json' } }),
    async () => { throw new Error('PRIVATE token and network internals'); },
  ]) {
    const client = createClient({ fetchImpl });
    await assert.rejects(client.workspace(), error => error instanceof PortalError && !error.message.includes('PRIVATE'));
  }
});

test('timeout includes response-body reads and settles even if fetch ignores abort', async () => {
  let signal;
  const client = createClient({ timeoutMs: 8, fetchImpl: async (_, options) => {
    signal = options.signal;
    return { ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), json: () => new Promise(() => {}) };
  } });
  await assert.rejects(client.workspace(), error => error.kind === 'timeout');
  assert.equal(signal.aborted, true);
});

test('clearing cancels in-flight work; logout uses captured CSRF and removes it afterwards', async () => {
  let calls = 0;
  const client = createClient({ fetchImpl: async (_, options) => {
    calls += 1;
    if (options.method === 'GET') return new Promise(() => {});
    assert.equal(options.headers['X-CSRF-Token'], 'csrf-before-clear');
    return new Response(null, { status: 204 });
  } });
  client.setCsrf('csrf-before-clear');
  const reading = client.workspace();
  const cancelled = assert.rejects(reading, error => error.kind === 'cancelled');
  await client.logout();
  await cancelled;
  await assert.rejects(client.save(0, {}), error => error.status === 401);
  assert.equal(calls, 2);
});

test('binary upload sends the original file, encoded filename and stable upload ID', async () => {
  const file = new File(['synthetic'], 'test statement.csv');
  const client = createClient({ fetchImpl: async (path, options) => {
    assert.equal(path, '/api/portal/documents');
    assert.equal(options.body, file);
    assert.equal(options.headers['Content-Type'], 'application/octet-stream');
    assert.equal(options.headers['X-Document-Name'], 'test%20statement.csv');
    assert.equal(options.headers['X-Upload-Id'], ID);
    assert.equal(options.headers['X-CSRF-Token'], 'csrf');
    return response({ document_id: ID, status: 'quarantined' }, 202);
  } });
  client.setCsrf('csrf');
  await client.upload(file, ID);
});

test('downloads require an authorized attachment response, not HTML or inline documents', async () => {
  for (const headers of [{ 'Content-Type': 'text/html' }, { 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'inline' }]) {
    const client = createClient({ fetchImpl: async () => new Response('PRIVATE', { headers }) });
    await assert.rejects(client.download(ID), error => error.kind === 'response');
  }
});

test('question upload uses scoped raw bytes and existing headers; invalid IDs never reach fetch', async () => {
  const file = new File(['synthetic,question'], 'question statement.csv');
  const calls = [];
  const client = createClient({ fetchImpl: async (path, options) => { calls.push({ path, options }); return response({ document_id: ID, status: 'quarantined' }, 202); } });
  await assert.rejects(client.uploadQuestion(ID, file, ID), error => error.status === 401);
  client.setCsrf('question-csrf');
  await client.uploadQuestion(ID, file, ID);
  assert.equal(calls[0].path, `/api/portal/questions/${ID}/documents`);
  assert.equal(calls[0].options.method, 'POST'); assert.equal(calls[0].options.body, file);
  assert.equal(calls[0].options.headers['X-Upload-Id'], ID);
  assert.equal(calls[0].options.headers['X-Document-Name'], 'question%20statement.csv');
  assert.equal(calls[0].options.headers['Content-Type'], 'application/octet-stream');
  assert.equal(calls[0].options.headers['X-CSRF-Token'], 'question-csrf');
  assert.equal(calls[0].options.credentials, 'same-origin');
  for (const bad of ['../../outside', 'https://outside.invalid', `${ID}?override=true`]) {
    await assert.rejects(client.uploadQuestion(bad, file, ID), PortalError);
    await assert.rejects(client.uploadQuestion(ID, file, bad), PortalError);
  }
  assert.equal(calls.length, 1);
});

test('question and reply defaults are explicit without dropping supplied attachment IDs', async () => {
  const bodies = [];
  const client = createClient({ fetchImpl: async (_, options) => { bodies.push(JSON.parse(options.body)); return response(); } });
  client.setCsrf('csrf');
  await client.question({ request_id: ID, body: 'Text question' });
  await client.question({ request_id: ID, body: 'Evidence question', request_documents: true });
  await client.reply(ID, { request_id: ID, body: 'Text reply' });
  await client.reply(ID, { request_id: ID, body: 'Evidence reply', document_ids: [ID] });
  assert.deepEqual(bodies, [
    { request_id: ID, body: 'Text question', request_documents: false },
    { request_id: ID, body: 'Evidence question', request_documents: true },
    { request_id: ID, body: 'Text reply', document_ids: [] },
    { request_id: ID, body: 'Evidence reply', document_ids: [ID] },
  ]);
});

test('case export requires a JSON attachment and keeps the fixed same-origin read-only contract', async () => {
  const client = createClient({ fetchImpl: async (path, options) => {
    assert.equal(path, '/api/portal/export'); assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
    assert.equal(options.headers['X-CSRF-Token'], undefined); assert.equal(options.headers.Accept, 'application/json');
    assert.equal(options.cache, 'no-store'); assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'same-origin');
    return new Response('{"synthetic":true}', { headers: { 'Content-Type': 'application/json; charset=utf-8', 'Content-Disposition': 'attachment; filename="export.json"' } });
  } });
  const blob = await client.exportCase(); assert.equal(await blob.text(), '{"synthetic":true}');
  for (const headers of [{ 'Content-Type': 'application/json' }, { 'Content-Type': 'application/json', 'Content-Disposition': 'inline' },
    { 'Content-Type': 'text/html', 'Content-Disposition': 'attachment' }, { 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment' }]) {
    const rejected = createClient({ fetchImpl: async () => new Response('PRIVATE', { headers }) });
    await assert.rejects(rejected.exportCase(), error => error.kind === 'response');
  }
});

test('continued interest sends only the stable request ID with CSRF and rejects invalid IDs before fetch', async () => {
  const calls = [];
  const client = createClient({ fetchImpl: async (path, options) => {
    calls.push(path); assert.equal(path, '/api/portal/continue-interest'); assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { request_id: ID }); assert.equal(options.headers['X-CSRF-Token'], 'interest-csrf');
    return response({ recorded: true, created: false });
  } });
  await assert.rejects(client.continueInterest(ID), error => error.status === 401);
  client.setCsrf('interest-csrf');
  await assert.rejects(client.continueInterest('not-a-uuid'), PortalError);
  await client.continueInterest(ID); await client.continueInterest(ID);
  assert.equal(calls.length, 2);
});

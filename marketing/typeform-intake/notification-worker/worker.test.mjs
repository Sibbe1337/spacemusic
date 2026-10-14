import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHmac } from 'node:crypto';
import worker, { FORM_ID, EMAIL_FIELD_ID, INBOX, receive, deliver, parseNotification,
  encryptEmail, decryptEmail, safeEmail, verifySignature, notificationMessage, boundedBody } from './worker.mjs';

const now = Date.parse('2026-09-15T19:00:00Z');
const secret = 'synthetic-webhook-test-secret-not-for-production';
const encryption = 'ab'.repeat(32);
const payload = () => ({ event_id: 'test-event', event_type: 'form_response', form_response: {
  form_id: FORM_ID, token: 'test-response-12345678', response_type: 'completed',
  submitted_at: new Date(now).toISOString(), answers: [{ field: { id: EMAIL_FIELD_ID }, type: 'email', email: 'owner@example.com' },
    { field: { id: 'unrelated' }, type: 'text', text: 'PRIVATE ROYALTIES 999999, DO NOT SEND' }],
} });
const signature = (body) => 'sha256=' + createHmac('sha256', secret).update(body).digest('base64');
function request(data = payload(), sig) {
  const body = JSON.stringify(data);
  return new Request('https://worker.example/typeform', { method: 'POST', headers: {
    'Content-Type': 'application/json', 'Typeform-Signature': sig ?? signature(body),
  }, body });
}
function db() {
  const sql = new DatabaseSync(':memory:');
  sql.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
  return { sql, prepare(query) {
    const statement = sql.prepare(query);
    const wrapped = (params = []) => ({ bind(...values) { return wrapped(values); },
      async first() { return statement.get(...params) || null; },
      async all() { return { results: statement.all(...params) }; },
      async run() { return { meta: statement.run(...params) }; },
    });
    return wrapped();
  } };
}
function env() { return { DB: db(), SEND_ENABLED: 'false', TYPEFORM_WEBHOOK_SECRET: secret,
  REPLY_ENCRYPTION_KEY: encryption, RESEND_API_KEY: 'test-key-never-live' }; }
const ctx = () => { const tasks = []; return { tasks, waitUntil(promise) { tasks.push(promise); } }; };
const accepted = () => Response.json({ id: '12345678-1234-1234-1234-123456789abc' });
async function queued() {
  const e = env(); const c = ctx();
  assert.equal((await receive(request(), e, c, now)).status, 202);
  await Promise.all(c.tasks);
  e.SEND_ENABLED = 'true';
  return [e, e.DB.sql.prepare('SELECT * FROM notifications').get().id];
}

test('raw-body signature: correct, tampered, missing, truncated and wrong secret', async () => {
  const bytes = new TextEncoder().encode(JSON.stringify(payload()));
  assert.equal(await verifySignature(bytes, signature(bytes), secret), true);
  assert.equal(await verifySignature(new Uint8Array([...bytes, 32]), signature(bytes), secret), false);
  for (const sig of [null, '', 'sha256=x', signature(bytes).slice(0, -1)]) assert.equal(await verifySignature(bytes, sig, secret), false);
  assert.equal(await verifySignature(bytes, signature(bytes), 'wrong'.repeat(10)), false);
});
test('valid complete response extracts only normalized date, digest and reply email', async () => {
  const item = await parseNotification(payload(), now);
  assert.deepEqual(Object.keys(item).sort(), ['email', 'id', 'is_test', 'submitted_at']);
  assert.match(item.id, /^[a-f0-9]{64}$/);
  assert.equal(item.email, 'owner@example.com');
});
test('observed Typeform wire IDs, not editor refs, select email and identify QA completions', async () => {
  const p = payload();
  p.form_response.answers = [
    { field: { id: 'oY3yxQa3CAD3', ref: '3581eeb5-a11f-45bd-88e3-0713d4474afb', type: 'email' }, type: 'email', email: INBOX },
    { field: { id: 'cIEzRJe4jZWW', ref: '7a65518f-c26e-4e4d-b747-a168808badf9', type: 'short_text' }, type: 'text', text: 'TEST ONLY - SPACE QA WIRE FORMAT' },
  ];
  assert.equal((await parseNotification(p, now)).is_test, 1);
  p.form_response.answers[1].text = 'Not a test';
  assert.equal((await parseNotification(p, now)).is_test, 0);
  p.form_response.answers[0].field.id = p.form_response.answers[0].field.ref;
  await assert.rejects(parseNotification(p, now), /response_email/);
});
test('partial, other form and other event are not queued', async () => {
  for (const change of [p => p.event_type = 'form_response_partial', p => p.form_response.form_id = 'different', p => p.form_response.response_type = 'partial']) {
    const p = payload(); change(p); assert.equal(await parseNotification(p, now), null);
  }
});
test('missing, duplicate, spoofed field and header injection emails rejected', async () => {
  for (const change of [p => p.form_response.answers = [], p => p.form_response.answers.push(p.form_response.answers[0]),
    p => p.form_response.answers[0].field.id = 'wrong-field', p => p.form_response.answers[0].email = 'a@example.com\r\nBcc: stolen@example.com']) {
    const p = payload(); change(p); await assert.rejects(parseNotification(p, now));
  }
  assert.equal(safeEmail('jose+test@example.com'), true);
  assert.equal(safeEmail('josé@example.com'), true);
  for (const email of ['bad', 'bad@example', '<a@example.com>', 'a@b.com,b@b.com']) assert.equal(safeEmail(email), false);
});
test('stale/future/invalid timestamps and invalid references rejected', async () => {
  for (const date of ['bad', new Date(now - 8 * 86400000).toISOString(), new Date(now + 3600000).toISOString()]) {
    const p = payload(); p.form_response.submitted_at = date; await assert.rejects(parseNotification(p, now));
  }
  const p = payload(); p.form_response.token = '../secret'; await assert.rejects(parseNotification(p, now));
});
test('encryption is bound to response digest; key and ciphertext tampering fail closed', async () => {
  const cipher = await encryptEmail('owner@example.com', 'digest', encryption);
  assert.ok(!cipher.includes('owner'));
  assert.equal(await decryptEmail(cipher, 'digest', encryption), 'owner@example.com');
  await assert.rejects(decryptEmail(cipher, 'different', encryption));
  await assert.rejects(decryptEmail(cipher, 'digest', 'cd'.repeat(32)));
  await assert.rejects(encryptEmail('owner@example.com', 'digest', 'short'));
});
test('duplicate and concurrent webhook deliveries create one durable record, no raw answers', async () => {
  const e = env(); const c = ctx();
  const statuses = await Promise.all(Array.from({ length: 8 }, async () => (await receive(request(), e, c, now)).status));
  await Promise.all(c.tasks);
  assert.ok(statuses.every(status => status === 202));
  const rows = e.DB.sql.prepare('SELECT * FROM notifications').all();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].attempts, 0);
  assert.ok(!JSON.stringify(rows).includes('owner@example.com'));
  assert.ok(!JSON.stringify(rows).includes('PRIVATE ROYALTIES'));
});
test('storage failure returns retryable status, never acknowledges a lost notification', async () => {
  const e = env(); e.DB = { prepare() { throw new Error('test-db-offline'); } };
  const p = payload(); p.form_response.submitted_at = new Date().toISOString();
  assert.equal((await worker.fetch(request(p), e, ctx())).status, 503);
});
test('unsigned, wrong MIME, too large, unknown path, GET and query requests rejected', async () => {
  const e = env();
  assert.equal((await receive(request(payload(), 'wrong'), e, ctx(), now)).status, 401);
  for (const [req, status] of [
    [new Request('https://worker.example/typeform'), 405],
    [new Request('https://worker.example/'), 404],
    [new Request('https://worker.example/typeform?token=x'), 400],
    [new Request('https://worker.example/typeform', { method: 'POST', body: 'x' }), 415],
    [new Request('https://worker.example/typeform', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': '9999999' } }), 413],
  ]) assert.equal((await receive(req, e, ctx(), now)).status, status);
});
test('bounded streaming read enforces limit even without Content-Length', async () => {
  await assert.rejects(boundedBody(new Response('123456789').body, 3));
});
test('sender always uses fixed inbox and excludes financial answers', () => {
  const body = notificationMessage({ id: '1'.repeat(64), submitted_at: '2026-09-15T19:00:00Z' }, 'owner@example.com');
  assert.deepEqual(body.to, [INBOX]);
  assert.equal(body.reply_to, 'owner@example.com');
  assert.ok(body.text.includes('https://admin.typeform.com/'));
  assert.ok(!body.text.includes('owner@example.com'));
});
test('concurrent dispatch sends once; accepted status is not called delivered; encrypted reply cleared', async () => {
  const [e, id] = await queued(); let calls = 0;
  const sender = async (url, options) => { calls++; assert.equal(url, 'https://api.resend.com/emails');
    assert.equal(options.redirect, 'manual'); assert.match(options.headers['Idempotency-Key'], /^space-intake-v1-/);
    assert.deepEqual(JSON.parse(options.body).to, [INBOX]); return accepted(); };
  await Promise.all(Array.from({ length: 10 }, () => deliver(id, e, sender, now)));
  assert.equal(calls, 1);
  const row = e.DB.sql.prepare('SELECT * FROM notifications').get();
  assert.equal(row.status, 'accepted'); assert.equal(row.reply_cipher, null);
  await deliver(id, e, sender, now + 600000); assert.equal(calls, 1);
});
test('timeout and provider failures keep durable state and retry the exact message/idempotency key', async () => {
  const [e, id] = await queued(); const calls = [];
  await deliver(id, e, async (_url, options) => { calls.push(options); throw new Error('timeout'); }, now);
  let row = e.DB.sql.prepare('SELECT * FROM notifications').get();
  assert.equal(row.status, 'pending'); assert.equal(row.attempts, 1); assert.ok(row.reply_cipher);
  await deliver(id, e, async (_url, options) => { calls.push(options); return accepted(); }, now + 60001);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].body, calls[1].body);
  assert.equal(calls[0].headers['Idempotency-Key'], calls[1].headers['Idempotency-Key']);
  row = e.DB.sql.prepare('SELECT * FROM notifications').get(); assert.equal(row.status, 'accepted');
});
test('retry window stops before provider idempotency expiry instead of risking another email', async () => {
  const [e, id] = await queued();
  await deliver(id, e, async () => { throw new Error('offline'); }, now);
  let calls = 0;
  await deliver(id, e, async () => { calls++; return accepted(); }, now + 21 * 3600000);
  assert.equal(calls, 0);
  const row = e.DB.sql.prepare('SELECT * FROM notifications').get();
  assert.equal(row.status, 'failed'); assert.equal(row.reply_cipher, null);
});
test('worker recovers an abandoned send lease without changing the first attempt', async () => {
  const [e, id] = await queued();
  e.DB.sql.prepare('UPDATE notifications SET first_attempt=?, lease_until=?, lease_token=?').run(now, now + 60000, 'abandoned');
  let calls = 0;
  await deliver(id, e, async () => { calls++; return accepted(); }, now + 60001);
  assert.equal(calls, 1);
  assert.equal(e.DB.sql.prepare('SELECT first_attempt FROM notifications').get().first_attempt, now);
});
test('malformed 200 receipt is retried, not marked accepted', async () => {
  const [e, id] = await queued();
  await deliver(id, e, async () => Response.json({ id: 'not-a-receipt' }), now);
  assert.equal(e.DB.sql.prepare('SELECT status FROM notifications').get().status, 'pending');
});

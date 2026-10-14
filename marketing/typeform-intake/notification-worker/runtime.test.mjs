import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHmac } from 'node:crypto';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
import { build } from 'esbuild';
import { FORM_ID, EMAIL_FIELD_ID } from './worker.mjs';

test('real Workers runtime sends one notification through mocked Resend', async () => {
  let calls = 0;
  const secret = 'synthetic-runtime-secret-never-production';
  const bundle = await build({ entryPoints: [new URL('./entry.mjs', import.meta.url).pathname], bundle: true, format: 'esm', write: false });
  const mf = new Miniflare(convertV4MiniflareOptions({ modules: true, script: bundle.outputFiles[0].text,
    compatibilityDate: '2026-09-15', d1Databases: ['DB'],
    bindings: { TYPEFORM_WEBHOOK_SECRET: secret, REPLY_ENCRYPTION_KEY: 'ab'.repeat(32),
      RESEND_API_KEY: 'synthetic-key', SEND_ENABLED: 'true' },
    outboundService: async request => {
      assert.equal(request.url, 'https://api.resend.com/emails'); calls++;
      return Response.json({ id: '12345678-1234-1234-1234-123456789abc' });
    },
  }));
  try {
    const database = await mf.getD1Database('DB');
    for (const sql of readFileSync(new URL('./schema.sql', import.meta.url), 'utf8').split(';').filter(s => s.trim())) await database.prepare(sql).run();
    const body = JSON.stringify({ event_type: 'form_response', form_response: {
      form_id: FORM_ID, token: 'TEST_RUNTIME_12345678', submitted_at: new Date().toISOString(),
      answers: [{ field: { id: EMAIL_FIELD_ID }, type: 'email', email: 'owner@example.com' }],
    } });
    const response = await mf.dispatchFetch('https://worker.example/typeform', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Typeform-Signature': 'sha256=' + createHmac('sha256', secret).update(body).digest('base64') }, body });
    assert.equal(response.status, 202);
    let row;
    for (let i = 0; i < 30; i++) {
      row = await database.prepare('SELECT status, error_code FROM notifications').first();
      if (row?.status === 'accepted' || row?.error_code) break;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    assert.equal(row?.status, 'accepted', JSON.stringify(row));
    assert.equal(calls, 1);
  } finally { await mf.dispose(); }
});

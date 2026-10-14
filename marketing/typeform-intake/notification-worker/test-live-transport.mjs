// Owner-only synthetic transport check, NOT evidence of a Typeform submission.
import assert from 'node:assert/strict';
import { readFileSync, statSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { createHmac } from 'node:crypto';
import { FORM_ID, EMAIL_FIELD_ID, NAME_FIELD_ID, INBOX } from './worker.mjs';
const directory = join(homedir(), 'Library/Application Support/SpaceMusic/typeform-intake');
const keyFile = join(directory, 'typeform-webhook-secret');
assert.equal(statSync(keyFile).mode & 0o077, 0);
const secret = readFileSync(keyFile, 'utf8').trim();
const fixtureFile = join(directory, 'transport-test-20260915.json');
if (!existsSync(fixtureFile)) writeFileSync(fixtureFile, JSON.stringify({
  event_id: 'synthetic-transport-check-20260915-01', event_type: 'form_response',
  form_response: { form_id: FORM_ID, token: 'TEST_ONLY_TRANSPORT_20260915_01', response_type: 'completed',
    submitted_at: new Date().toISOString(), answers: [
      { field: { id: EMAIL_FIELD_ID }, type: 'email', email: INBOX },
      { field: { id: NAME_FIELD_ID }, type: 'text', text: 'TEST ONLY - SPACE QA TRANSPORT 20260915-01' },
    ] },
}), { flag: 'wx', mode: 0o600 });
const fixture = JSON.parse(readFileSync(fixtureFile, 'utf8'));
assert.equal(fixture.form_response.token, 'TEST_ONLY_TRANSPORT_20260915_01');
assert.equal(fixture.form_response.answers[0].email, INBOX);
// Preserve the existing test reference so reruns cannot create a second alert.
fixture.form_response.answers[0].field.id = EMAIL_FIELD_ID;
fixture.form_response.answers[1].field.id = NAME_FIELD_ID;
const body = JSON.stringify(fixture);
const signature = 'sha256=' + createHmac('sha256', secret).update(body).digest('base64');
for (let i = 0; i < 2; i++) {
  const result = await fetch('https://space-intake-notifications.samplehubkupp.workers.dev/typeform', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Typeform-Signature': signature },
    redirect: 'error', body, signal: AbortSignal.timeout(20000),
  });
  console.log(JSON.stringify({ attempt: i + 1, status: result.status, message: await result.text() }));
  assert.equal(result.status, 202);
}
console.log('Same signed synthetic event sent twice. Verify exactly one accepted TEST_ONLY notification in D1 and Resend. No Typeform record was created by this script.');

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { createStaffApp, createStaffClient, StaffError, validateStaffSession, googleAuthorizationUrl, credentialOptions, credentialJSON } from './staff.mjs';

const require = createRequire(new URL('../seller_ui/package.json', import.meta.url));
const { JSDOM } = require('jsdom');
const html = await readFile(new URL('./staff.html', import.meta.url), 'utf8');
const ID = index => `20000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
const START = Date.parse('2026-09-18T10:00:00Z');
const iso = offset => new Date(START + offset).toISOString();
const json = (body = {}, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const session = (overrides = {}) => ({ principal_id: ID(1), display_name: 'Fictional operator', role: 'operator', state: 'active', uv_at: iso(0), expires_at: iso(3600000), csrf: 'staff-csrf', ...overrides });
const receipt = (overrides = {}) => ({ intake_id: ID(2), source: 'typeform', form_id: 'fixture-form', inquiry_kind: 'owner', submitted_at: iso(-60000), received_at: iso(-30000), workspace_id: null, ...overrides });
const detail = (overrides = {}) => ({ intake_id: ID(2), source: 'typeform', form_id: 'fixture-form', response_id: 'fixture-source-reference', email: 'synthetic@example.com', inquiry_kind: 'owner', submitted_at: iso(-60000), landing_path: '/apply/', mapping_version: 1, ...overrides });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const credentialId = Buffer.from('synthetic-credential-identifier').toString('base64url');
const options = (kind = 'get') => ({ challenge_id: ID(40), publicKey: {
  challenge: Buffer.from('synthetic-server-challenge').toString('base64url'), timeout: 120000,
  ...(kind === 'create' ? { rp: { id: 'review.test', name: 'SPACE staff review' }, user: { id: 'AQIDBA', name: 'Fictional operator', displayName: 'Fictional operator' }, pubKeyCredParams: [{ type: 'public-key', alg: -7 }], authenticatorSelection: { userVerification: 'required' }, excludeCredentials: [] }
    : { rpId: 'review.test', userVerification: 'required', allowCredentials: [{ type: 'public-key', id: credentialId }] }),
} });
const signedCredential = (kind = 'get', id = credentialId) => ({ id, type: 'public-key', rawId: Buffer.from(id, 'base64url'), response: {
  clientDataJSON: Buffer.from('synthetic-client-data'),
  ...(kind === 'create' ? { attestationObject: Buffer.from('synthetic-attestation'), getTransports: () => ['usb'] }
    : { authenticatorData: Buffer.from('synthetic-authenticator-data'), signature: Buffer.from('synthetic-signature'), userHandle: null }),
}, getClientExtensionResults: () => ({}) });

function fixture(t, { initial = session(), timeoutMs = 1000, production = false } = {}) {
  const dom = new JSDOM(production ? html.replace('data-environment="test"', 'data-environment="production"') : html,
    { url: 'https://review.test/staff/?private=query#private-fragment', runScripts: 'outside-only' });
  const win = dom.window;
  for (const key of ['localStorage', 'sessionStorage', 'indexedDB']) Object.defineProperty(win, key, { get() { throw Error('No browser storage'); } });
  Object.defineProperty(win, 'isSecureContext', { value: true, configurable: true });
  const credentials = { create: async () => signedCredential('create'), get: async () => signedCredential() };
  Object.defineProperty(win.navigator, 'credentials', { value: credentials });
  const queue = [initial instanceof Response ? initial : json(initial)];
  const calls = [], unexpected = [], navigations = [];
  const timers = new Set(); let currentTime = START, sequence = 100;
  const client = createStaffClient({ timeoutMs, fetchImpl: async (path, options) => {
    const call = { path, options, body: options.body ? JSON.parse(options.body) : undefined }; calls.push(call);
    if (!queue.length) { unexpected.push(path); throw Error('Unexpected mock request'); }
    const result = queue.shift(); return typeof result === 'function' ? result(call) : result;
  } });
  const app = createStaffApp({ window: win, client, now: () => currentTime, uuid: () => ID(sequence++), navigate: url => navigations.push(url),
    schedule: (fn, delay) => { const timer = { fn, at: currentTime + delay }; timers.add(timer); return timer; }, unschedule: timer => timers.delete(timer),
  });
  const doc = win.document;
  const get = selector => { const element = doc.querySelector(selector); assert.ok(element, selector); return element; };
  const click = selector => get(selector).click();
  const set = (selector, value) => { const input = get(selector); input.value = value; input.dispatchEvent(new win.Event('input', { bubbles: true })); };
  const submit = selector => get(selector).dispatchEvent(new win.Event('submit', { bubbles: true, cancelable: true }));
  async function idle() {
    for (let attempt = 0; attempt < 150; attempt++) {
      if (get('main').getAttribute('aria-busy') === 'false') return;
      await new Promise(resolve => setTimeout(resolve, 2));
    }
    assert.fail('Staff app did not become idle');
  }
  async function openReceipt(item = detail(), listed = receipt()) {
    queue.push(json({ intakes: [listed] })); click('[data-action=list]'); await idle();
    queue.push(json(item)); click(`[data-intake="${item.intake_id}"]`); await idle();
  }
  t.after(() => { app.destroy(); win.close(); assert.deepEqual(unexpected, []); });
  return { win, doc, credentials, get, click, set, submit, idle, openReceipt, queue, calls, navigations, timers,
    text: () => doc.body.textContent,
    advance(ms) { currentTime += ms; for (const timer of [...timers]) if (timer.at <= currentTime) { timers.delete(timer); timer.fn(); } },
  };
}

test('staff bootstrap scrubs URL and only reads session; reviewer never calls operator intake', async t => {
  for (const role of ['reviewer', 'operator']) {
    await t.test(role, async t => {
      const f = fixture(t, { initial: session({ role }) }); await f.idle();
      assert.equal(f.win.location.href, 'https://review.test/staff/');
      assert.equal(f.calls.length, 1); assert.equal(f.calls[0].path, '/api/staff/session'); assert.equal(f.calls[0].options.method, 'GET');
      assert.equal(Boolean(f.doc.querySelector('[data-action=list]')), role === 'operator');
      assert.equal(f.navigations.length, 0); assert.match(f.text(), /supervised operator process/);
      assert.equal(f.doc.querySelector('[data-action=assign]'), null);
    });
  }
});

test('Google sign-in is explicit, POSTs an empty body and navigates only to validated authorization URL', async t => {
  const f = fixture(t, { initial: json({}, 401) }); await f.idle();
  assert.equal(f.navigations.length, 0);
  const url = `https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=${encodeURIComponent('https://review.test/api/staff/oidc/callback')}&response_type=code&state=server-state&client_id=server-client`;
  f.queue.push(call => { assert.deepEqual(call.body, {}); assert.equal(call.path, '/api/staff/oidc/start'); assert.equal(call.options.headers['X-CSRF-Token'], undefined); return json({ authorization_url: url }); });
  f.click('[data-action=sign-in]'); await f.idle();
  assert.deepEqual(f.navigations, [url]); assert.doesNotMatch(f.doc.documentElement.outerHTML, /server-state|server-client/);
  for (const invalid of ['https://evil.invalid/', url.replace('accounts.google.com', 'accounts.google.com.evil.invalid'), url.replace('response_type=code', 'response_type=token'), `${url}&state=other`, url.replace('review.test%2Fapi', 'outside.invalid%2Fapi')]) {
    assert.throws(() => googleAuthorizationUrl(invalid, 'https://review.test'), StaffError);
  }
});

test('two separately supervised registrations and signed confirmations do not grant UV until server verification', async t => {
  const enrolling = session({ state: 'enrolling', uv_at: null });
  const f = fixture(t, { initial: enrolling }); await f.idle();
  for (let key = 1; key <= 2; key++) {
    const id = Buffer.from(`synthetic-distinct-credential-${key}`).toString('base64url');
    let created = false, asserted = false;
    f.credentials.create = async request => {
      created = true; assert.equal(request.publicKey.authenticatorSelection.userVerification, 'required');
      assert.ok(request.publicKey.challenge instanceof Uint8Array); assert.ok(request.signal); return signedCredential('create', id);
    };
    f.credentials.get = async request => { asserted = true; assert.equal(request.publicKey.userVerification, 'required'); return signedCredential('get', id); };
    const permit = `supervised_permit_${String(key).repeat(32)}`;
    f.set('#staff-permit', permit); const oldPermit = f.get('#staff-permit');
    f.queue.push(call => { assert.deepEqual(call.body, { permit }); return json(options('create')); }, call => {
      assert.equal(call.path, '/api/staff/enrollment/verify'); assert.equal(call.body.credential.id, id);
      assert.equal(call.body.credential.response.attestationObject, Buffer.from('synthetic-attestation').toString('base64url'));
      return json({ credential_id: id, confirmation_required: true });
    });
    f.submit('#staff-enroll-form'); await f.idle();
    assert.equal(created, true); assert.equal(oldPermit.value, ''); assert.doesNotMatch(f.doc.documentElement.outerHTML, new RegExp(permit));
    assert.ok(f.get('[data-action=confirm-key]')); assert.equal(f.get('[data-action=list]').disabled, true);
    assert.equal(f.doc.querySelector('[data-action=approve]'), null);
    f.queue.push(call => { assert.deepEqual(call.body, { confirm_credential: id }); return json(options()); }, call => {
      assert.equal(call.body.confirmation, true); assert.equal(call.body.credential.id, id); assert.ok(call.body.credential.response.signature);
      return json({ confirmed: true });
    }, json(key === 1 ? enrolling : session({ uv_at: null })));
    f.click('[data-action=confirm-key]'); await f.idle(); assert.equal(asserted, true);
    assert.equal(f.get('[data-action=list]').disabled, true);
  }
  assert.equal(f.doc.querySelector('#staff-enroll-form'), null); assert.ok(f.get('[data-action=verify]'));
  f.queue.push(json(options()), json({ uv_expires_at: iso(300000) }), json(session()));
  f.click('[data-action=verify]'); await f.idle();
  assert.equal(f.get('[data-action=list]').disabled, false);
  assert.match(f.text(), /Fresh passkey verification confirmed by the server/);
  assert.equal(f.calls.filter(call => call.path === '/api/staff/intakes').length, 0);
});

test('lost enrollment acknowledgement retains exact credential for signed confirmation, not a fake MFA shortcut', async t => {
  const f = fixture(t, { initial: session({ state: 'enrolling', uv_at: null }) }); await f.idle();
  f.set('#staff-permit', 'supervised_permit_'.padEnd(48, 'a'));
  f.queue.push(json(options('create')), () => { throw Error('lost acknowledgement'); });
  f.submit('#staff-enroll-form'); await f.idle();
  assert.match(f.text(), /Registration outcome is unconfirmed/);
  f.queue.push(json(session({ state: 'enrolling', uv_at: null }))); f.click('[data-action=refresh-session]'); await f.idle();
  f.queue.push(call => { assert.deepEqual(call.body, { confirm_credential: credentialId }); return json(options()); }, json({ confirmed: true }), json(session({ state: 'enrolling', uv_at: null })));
  f.click('[data-action=confirm-key]'); await f.idle();
  assert.ok(f.get('#staff-enroll-form')); assert.equal(f.get('[data-action=list]').disabled, true);
  assert.equal(f.calls.filter(call => call.path.endsWith('/enrollment/options')).length, 1);
});

test('cancelled or unavailable passkey never verifies; consumed permit is scrubbed and never automatically reused', async t => {
  const f = fixture(t, { initial: session({ state: 'enrolling', uv_at: null }) }); await f.idle();
  f.credentials.create = async () => { throw new f.win.DOMException('PRIVATE_PROVIDER', 'NotAllowedError'); };
  f.set('#staff-permit', 'supervised_permit_'.padEnd(48, 'a')); f.queue.push(json(options('create')));
  f.submit('#staff-enroll-form'); await f.idle();
  assert.equal(f.calls.length, 2); assert.equal(f.get('#staff-permit').value, '');
  assert.match(f.text(), /ask your supervisor for a new permit/i); assert.doesNotMatch(f.text(), /PRIVATE_PROVIDER/);
  assert.equal(f.get('[data-action=list]').disabled, true);
  assert.equal(f.doc.activeElement.id, 'staff-message');
});

test('UV verification acknowledgement without fresh session proof cannot unlock protected actions', async t => {
  const f = fixture(t, { initial: session({ uv_at: null }) }); await f.idle();
  f.queue.push(json(options()), json({ uv_expires_at: iso(300000) }), json(session({ uv_at: null })));
  f.click('[data-action=verify]'); await f.idle();
  assert.equal(f.get('[data-action=list]').disabled, true); assert.equal(f.get('#staff-workspace-id').disabled, true);
  assert.match(f.text(), /fresh authority is not visible/);
  assert.equal(f.calls.filter(call => call.path === '/api/staff/intakes').length, 0);
});

test('wrong RP or non-required UV options fail closed before invoking browser credentials', async t => {
  const f = fixture(t, { initial: session({ uv_at: null }) }); await f.idle();
  let used = false; f.credentials.get = async () => { used = true; return signedCredential(); };
  const bad = options(); bad.publicKey.rpId = 'evil.invalid'; f.queue.push(json(bad));
  f.click('[data-action=verify]'); await f.idle();
  assert.equal(used, false); assert.equal(f.calls.length, 2); assert.equal(f.get('[data-action=list]').disabled, true);
  const weak = options(); weak.publicKey.userVerification = 'preferred';
  assert.throws(() => credentialOptions(weak, 'get', f.win), StaffError);
});

test('approval requires owner-authority checkbox, singleflights and preserves exact request across refresh', async t => {
  const f = fixture(t, { timeoutMs: 12 }); await f.idle(); await f.openReceipt();
  assert.equal(f.get('[data-action=approve]').disabled, true); f.click('[data-action=approve]'); assert.equal(f.calls.length, 3);
  f.click('#staff-owner-authority');
  const approval = f.get('[data-action=approve]'); f.queue.push(() => new Promise(() => {})); approval.click(); approval.click(); await f.idle();
  const original = f.calls.at(-1).body;
  assert.deepEqual(original, { request_id: ID(100), owner_authority_confirmed: true });
  assert.equal(f.calls.filter(call => call.path.endsWith('/approve')).length, 1);
  f.queue.push(json(session())); f.click('[data-action=refresh-session]'); await f.idle();
  f.queue.push(json({ intakes: [receipt({ workspace_id: ID(3) })] })); f.click('[data-action=list]'); await f.idle();
  assert.ok(f.get('[data-action=retry-mutation]')); assert.doesNotMatch(f.get('#staff-message').textContent, /Admission confirmed/);
  f.queue.push(call => { assert.equal(call.path, `/api/staff/intakes/${ID(2)}/approve`); assert.deepEqual(call.body, original); return json({ workspace_id: ID(3), slot: 1, created: false }); });
  f.click('[data-action=retry-mutation]'); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=retry-mutation]'), null);
  assert.equal(f.get('#staff-workspace-id').value, ID(3)); assert.equal(f.navigations.length, 0);
  assert.match(f.text(), /not confirmation of invitation delivery or reviewer assignment/);
});

test('409 admission conflicts need an authoritative list refresh before discarding the unresolved request', async t => {
  const f = fixture(t); await f.idle(); await f.openReceipt(); f.click('#staff-owner-authority');
  f.queue.push(json({}, 409)); f.click('[data-action=approve]'); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=discard-mutation]'), null);
  f.queue.push(json({}, 503)); f.click('[data-action=list]'); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=discard-mutation]'), null);
  f.queue.push(json({ intakes: [receipt({ workspace_id: ID(3) })] })); f.click('[data-action=list]'); await f.idle();
  const calls = f.calls.length; f.click('[data-action=discard-mutation]'); assert.equal(f.calls.length, calls);
  assert.equal(f.doc.querySelector('[data-action=retry-mutation]'), null); assert.match(f.text(), /not confirmed saved/);
});

test('partnership and already-admitted intake cannot be approved by this UI', async t => {
  for (const [item, listed] of [[detail({ inquiry_kind: 'partnership' }), receipt({ inquiry_kind: 'partnership' })], [detail(), receipt({ workspace_id: ID(3) })]]) {
    await t.test(item.inquiry_kind + String(listed.workspace_id), async t => {
      const f = fixture(t); await f.idle(); await f.openReceipt(item, listed);
      assert.equal(f.doc.querySelector('[data-action=approve]'), null); assert.equal(f.doc.querySelector('#staff-owner-authority'), null);
    });
  }
});

test('manual receipt is optional, requires duplicate review and retains identical submitted fields on unknown acknowledgement', async t => {
  const f = fixture(t); await f.idle(); f.submit('#staff-manual-form'); assert.equal(f.calls.length, 1);
  f.set('#staff-email', 'synthetic@example.com'); f.set('#staff-submitted', iso(-60000)); f.set('#staff-landing', '/sell/');
  f.submit('#staff-manual-form'); assert.equal(f.calls.length, 1);
  f.click('#staff-manual-attested'); f.queue.push(() => { throw Error('offline'); }); f.submit('#staff-manual-form'); await f.idle();
  const original = f.calls.at(-1).body;
  assert.deepEqual(original, { receipt_id: ID(100), email: 'synthetic@example.com', submitted_at: iso(-60000), landing_path: '/sell/' });
  f.set('#staff-email', 'replacement@example.com');
  f.queue.push(json(session())); f.click('[data-action=refresh-session]'); await f.idle();
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ status: 'pending_review', intake_id: ID(2), created: false }, 202); });
  f.click('[data-action=retry-mutation]'); await f.idle();
  assert.equal(f.get('#staff-email').value, ''); assert.equal(f.get('#staff-manual-attested').checked, false);
  assert.match(f.text(), /no pilot admission was made/); assert.equal(f.calls.filter(call => call.path.endsWith('/approve')).length, 0);
});

test('context is established by explicit POST before navigation, never inferred from workspace ID', async t => {
  const f = fixture(t, { initial: session({ role: 'reviewer' }) }); await f.idle();
  f.set('#staff-workspace-id', '../../outside'); f.submit('#staff-context-form'); assert.equal(f.calls.length, 1);
  f.set('#staff-workspace-id', ID(3));
  const gate = deferred(); f.queue.push(call => { assert.equal(call.path, `/api/staff/workspaces/${ID(3)}/context`); assert.deepEqual(call.body, {}); assert.equal(call.options.headers['X-CSRF-Token'], 'staff-csrf'); return gate.promise; });
  f.submit('#staff-context-form'); assert.equal(f.navigations.length, 0);
  gate.resolve(new Response(null, { status: 204 })); await f.idle();
  assert.deepEqual(f.navigations, ['/workspace/']); assert.equal(f.doc.querySelector('#staff-workspace-id'), null);
});

test('reviewers load assigned UUIDs and establish context without any operator intake request', async t => {
  const f = fixture(t, { initial: session({ role: 'reviewer' }) }); await f.idle();
  f.queue.push(call => { assert.equal(call.path, '/api/staff/workspaces'); assert.equal(call.options.method, 'GET'); return json({ workspace_ids: [ID(3), ID(4)] }); });
  f.click('[data-action=workspaces]'); await f.idle();
  assert.equal(f.doc.querySelectorAll('[data-workspace]').length, 2); assert.equal(f.navigations.length, 0);
  f.queue.push(call => { assert.equal(call.path, `/api/staff/workspaces/${ID(4)}/context`); return json({ workspace_id: ID(4) }); });
  f.click(`[data-workspace="${ID(4)}"]`); await f.idle();
  assert.deepEqual(f.navigations, ['/workspace/']); assert.equal(f.calls.some(call => call.path.includes('/intakes')), false);
});

test('empty or malformed assigned list offers no invented assignment action or unsafe workspace path', async t => {
  const f = fixture(t, { initial: session({ role: 'reviewer' }) }); await f.idle();
  f.queue.push(json({ workspace_ids: [] })); f.click('[data-action=workspaces]'); await f.idle();
  assert.match(f.text(), /No assigned workspaces are available/);
  assert.equal(f.doc.querySelector('[data-action=assign]'), null);
  for (const workspace_ids of [['../../outside'], [ID(3), ID(3)], [null]]) {
    f.queue.push(json({ workspace_ids })); f.click('[data-action=workspaces]'); await f.idle();
    assert.match(f.get('#staff-message').textContent, /incomplete or unsupported/); assert.equal(f.doc.querySelector('[data-workspace]'), null);
  }
});

test('401/403 clear PII, pending request identity and permit inputs; fresh sessions never resume mutations', async t => {
  for (const status of [401, 403]) {
    await t.test(String(status), async t => {
      const f = fixture(t); await f.idle(); await f.openReceipt(detail({ email: 'PRIVATE@example.com' }));
      f.set('#staff-email', 'PRIVATE_UNSENT@example.com'); const detached = f.get('#staff-email');
      f.click('#staff-owner-authority'); f.queue.push(json({}, status)); f.click('[data-action=approve]'); await f.idle();
      assert.equal(detached.value, ''); assert.doesNotMatch(f.text(), /PRIVATE|Fictional operator|fixture-source-reference/);
      assert.equal(f.doc.querySelector('[data-action=retry-mutation]'), null); assert.equal(f.timers.size, 0);
      f.queue.push(json(session())); f.click('[data-action=refresh-session]'); await f.idle();
      assert.equal(f.get('#staff-email').value, ''); assert.equal(f.calls.filter(call => call.path.endsWith('/approve')).length, 1);
    });
  }
});

test('logout clears immediately, aborts passkey prompt and ignores late signed proof', async t => {
  const f = fixture(t, { initial: session({ uv_at: null }) }); await f.idle();
  const late = deferred(); let signal;
  f.credentials.get = request => { signal = request.signal; return late.promise; };
  f.queue.push(json(options())); f.click('[data-action=verify]');
  for (let attempt = 0; attempt < 50 && !signal; attempt++) await new Promise(resolve => setTimeout(resolve, 2));
  assert.ok(signal);
  f.queue.push(() => { throw Error('offline'); }); f.click('[data-action=logout]'); await f.idle();
  assert.equal(signal.aborted, true); assert.doesNotMatch(f.text(), /Fictional operator/);
  late.resolve(signedCredential()); await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(f.calls.filter(call => call.path.endsWith('/assertion/verify')).length, 0);
  assert.match(f.text(), /server logout could not be confirmed/);
});

test('session expiry and page suspension wipe intake PII and ignore late detail responses', async t => {
  for (const reason of ['expiry', 'pagehide']) {
    await t.test(reason, async t => {
      const f = fixture(t, { initial: session({ expires_at: iso(1000) }) }); await f.idle();
      f.queue.push(json({ intakes: [receipt()] })); f.click('[data-action=list]'); await f.idle();
      const late = deferred(); f.queue.push(() => late.promise); f.click(`[data-intake="${ID(2)}"]`);
      if (reason === 'expiry') f.advance(1001); else f.win.dispatchEvent(new f.win.Event('pagehide'));
      late.resolve(json(detail({ email: 'PRIVATE_LATE@example.com' }))); await f.idle();
      assert.equal(f.doc.querySelector('#staff-email'), null); assert.doesNotMatch(f.text(), /PRIVATE_LATE|Fictional operator/);
      assert.equal(f.timers.size, 0);
    });
  }
});

test('fresh UV expiry clears private receipts and requires another signed assertion', async t => {
  const f = fixture(t); await f.idle(); await f.openReceipt(detail({ email: 'PRIVATE_UV@example.com' }));
  f.set('#staff-email', 'PRIVATE_MANUAL@example.com'); f.advance(300001);
  assert.doesNotMatch(f.text(), /PRIVATE_UV|PRIVATE_MANUAL/); assert.equal(f.get('#staff-email').value, '');
  assert.equal(f.get('[data-action=list]').disabled, true); assert.equal(f.get('#staff-workspace-id').disabled, true);
  assert.match(f.text(), /Verify again before continuing/);
});

test('authoritative session refresh removing UV and intake-list removal clear protected details', async t => {
  const f = fixture(t); await f.idle(); await f.openReceipt(detail({ email: 'PRIVATE_REMOVED@example.com' }));
  f.queue.push(json({ intakes: [] })); f.click('[data-action=list]'); await f.idle();
  assert.doesNotMatch(f.text(), /PRIVATE_REMOVED/); assert.equal(f.doc.querySelector('[data-action=approve]'), null);
  await f.openReceipt(detail({ email: 'PRIVATE_REFRESH@example.com' }));
  f.set('#staff-email', 'PRIVATE_UNSENT@example.com');
  f.queue.push(json(session({ uv_at: null }))); f.click('[data-action=refresh-session]'); await f.idle();
  assert.doesNotMatch(f.text(), /PRIVATE_REFRESH|PRIVATE_UNSENT/); assert.equal(f.get('#staff-email').value, '');
  assert.equal(f.get('[data-action=list]').disabled, true);
});

test('staff response validation and malicious receipt content fail closed or render as text', async t => {
  assert.throws(() => validateStaffSession(session({ state: 'suspended' })), StaffError);
  assert.throws(() => validateStaffSession(session({ expires_at: 'forever' })), StaffError);
  const f = fixture(t); await f.idle();
  const attack = '<img src=x onerror=alert(1)>';
  await f.openReceipt(detail({ email: attack, response_id: attack, form_id: attack }), receipt({ source: attack }));
  assert.equal(f.doc.querySelector('main img, main script, main [onerror]'), null); assert.ok(f.text().includes(attack));
  f.queue.push(json({ intakes: [{ ...receipt(), intake_id: '../outside' }] })); f.click('[data-action=list]'); await f.idle();
  assert.match(f.get('#staff-message').textContent, /incomplete or unsupported/);
});

test('staff UI preserves approved local assets, labels and explicit production environment copy', async t => {
  const f = fixture(t, { production: true }); await f.idle();
  assert.match(f.get('.preview-notice').textContent, /Private pilot/); assert.doesNotMatch(f.get('.preview-notice').textContent, /Synthetic/);
  for (const input of f.doc.querySelectorAll('main input, main select')) assert.ok(input.labels.length, input.outerHTML);
  for (const element of f.doc.querySelectorAll('[aria-describedby]')) assert.ok(f.doc.getElementById(element.getAttribute('aria-describedby')));
  const ids = [...f.doc.querySelectorAll('[id]')].map(item => item.id); assert.equal(new Set(ids).size, ids.length);
  for (const element of f.doc.querySelectorAll('[src], link[href]')) assert.match(element.getAttribute('src') || element.getAttribute('href'), /^\/(workspace|staff)\//);
  assert.equal(f.get('meta[name=referrer]').content, 'no-referrer');
  assert.equal(f.doc.querySelector('input[name=mfa], [data-action=assign]'), null);
});

test('staff client enforces same-origin CSRF, fixed endpoints, cancellation and private error bodies', async () => {
  const calls = [];
  const client = createStaffClient({ fetchImpl: async (path, options) => { calls.push({ path, options }); return json({}); } });
  await assert.rejects(client.approve(ID(2), {}), error => error.status === 401);
  client.setCsrf('csrf'); await client.signIn(); await client.session(); await client.approve(ID(2), { request_id: ID(3), owner_authority_confirmed: true });
  for (const call of calls) {
    assert.match(call.path, /^\/api\/staff\//); assert.equal(call.options.credentials, 'same-origin'); assert.equal(call.options.mode, 'same-origin');
    assert.equal(call.options.cache, 'no-store'); assert.equal(call.options.redirect, 'error'); assert.equal(call.options.referrerPolicy, 'no-referrer');
  }
  assert.throws(() => client.detail('../../outside'), StaffError);
  assert.equal(calls[0].options.headers['X-CSRF-Token'], undefined); assert.equal(calls[2].options.headers['X-CSRF-Token'], 'csrf');
  let read = false;
  const failed = createStaffClient({ fetchImpl: async () => ({ ok: false, status: 403, json() { read = true; throw Error('PRIVATE'); } }) });
  await assert.rejects(failed.session(), error => error.status === 403 && !error.message.includes('PRIVATE')); assert.equal(read, false);
  const hanging = createStaffClient({ fetchImpl: async () => new Promise(() => {}) });
  const unresolved = hanging.session(); const cancelled = assert.rejects(unresolved, error => error.kind === 'cancelled'); hanging.clear(); await cancelled;
});

test('credential JSON preserves actual signed bytes and uses native serializer when available', () => {
  const dom = new JSDOM('', { url: 'https://review.test/' });
  const value = credentialJSON(signedCredential(), dom.window);
  assert.equal(value.response.signature, Buffer.from('synthetic-signature').toString('base64url'));
  assert.equal(value.response.userHandle, null); assert.equal(value.rawId, credentialId);
  const native = { id: credentialId, type: 'public-key', toJSON: () => ({ id: credentialId, response: { actual: 'native-proof' } }) };
  assert.deepEqual(credentialJSON(native, dom.window), native.toJSON());
  dom.window.close();
});

test('local browser: actual WebAuthn enrollment, confirmation, UV, approval retry and assigned context', { skip: !process.env.CATALOG_UI_BROWSER_TEST }, async t => {
  const runtime = createRequire(`${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json`);
  const { chromium } = runtime('playwright');
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  t.after(() => browser.close());
  const context = await browser.newContext({ viewport: { width: 1365, height: 1000 } });
  const page = await context.newPage();
  const errors = [], unexpected = [], approvals = [], registrations = [], assertions = [];
  let confirmed = 0, fresh = false;
  page.on('pageerror', error => errors.push(error.message));
  await page.clock.setFixedTime(new Date(START));
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  const addAuthenticator = () => cdp.send('WebAuthn.addVirtualAuthenticator', { options: { protocol: 'ctap2', transport: 'usb', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  let authenticator = await addAuthenticator();
  const assets = new Map([
    ['/staff/', ['services/catalog_review_ui/staff.html', 'text/html']],
    ['/staff/staff.mjs', ['services/catalog_review_ui/staff.mjs', 'text/javascript']],
    ['/workspace/portal.css', ['services/catalog_review_ui/portal.css', 'text/css']],
    ['/workspace/review.css', ['services/catalog_review_preview/ui/review.css', 'text/css']],
    ['/workspace/space-wordmark.svg', ['marketing/identity-20260916/space-wordmark.svg', 'image/svg+xml']],
    ['/workspace/inter.woff2', ['marketing/design/fonts/inter-latin-c940764593d0.woff2', 'font/woff2']],
    ['/inter.woff2', ['marketing/design/fonts/inter-latin-c940764593d0.woff2', 'font/woff2']],
  ]);
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== 'https://review.test') { unexpected.push(request.url()); return route.abort(); }
    const asset = assets.get(url.pathname);
    if (asset) return route.fulfill({ contentType: asset[1], body: await readFile(new URL(`../../${asset[0]}`, import.meta.url)) });
    if (url.pathname === '/api/staff/session') return route.fulfill({ json: session({ state: confirmed < 2 ? 'enrolling' : 'active', uv_at: fresh ? iso(0) : null }) });
    if (url.pathname === '/api/staff/enrollment/options') {
      const value = options('create'); value.publicKey.excludeCredentials = registrations.map(id => ({ type: 'public-key', id }));
      return route.fulfill({ json: value });
    }
    if (url.pathname === '/api/staff/enrollment/verify') {
      const value = request.postDataJSON(); registrations.push(value.credential.id);
      assert.ok(Buffer.from(value.credential.response.attestationObject, 'base64url').length > 100);
      assert.equal(JSON.parse(Buffer.from(value.credential.response.clientDataJSON, 'base64url')).type, 'webauthn.create');
      return route.fulfill({ json: { credential_id: value.credential.id, confirmation_required: true } });
    }
    if (url.pathname === '/api/staff/assertion/options') {
      const value = options(); const body = request.postDataJSON();
      value.publicKey.allowCredentials = (body.confirm_credential ? [body.confirm_credential] : registrations).map(id => ({ type: 'public-key', id }));
      return route.fulfill({ json: value });
    }
    if (url.pathname === '/api/staff/assertion/verify') {
      const value = request.postDataJSON(); assertions.push(value);
      assert.ok(Buffer.from(value.credential.response.signature, 'base64url').length > 60);
      assert.equal(JSON.parse(Buffer.from(value.credential.response.clientDataJSON, 'base64url')).type, 'webauthn.get');
      if (value.confirmation) { confirmed += 1; return route.fulfill({ json: { confirmed: true } }); }
      fresh = true; return route.fulfill({ json: { uv_expires_at: iso(300000) } });
    }
    if (url.pathname === '/api/staff/intakes') return route.fulfill({ json: { intakes: [receipt({ workspace_id: approvals.length ? ID(3) : null })] } });
    if (url.pathname === `/api/staff/intakes/${ID(2)}`) return route.fulfill({ json: detail() });
    if (url.pathname === `/api/staff/intakes/${ID(2)}/approve`) {
      approvals.push(request.postData());
      if (approvals.length === 1) return route.abort('connectionfailed');
      return route.fulfill({ json: { workspace_id: ID(3), slot: 1, created: false } });
    }
    if (url.pathname === '/api/staff/workspaces') return route.fulfill({ json: { workspace_ids: [ID(3)] } });
    if (url.pathname === `/api/staff/workspaces/${ID(3)}/context`) {
      assert.equal(request.method(), 'POST'); assert.equal((await request.allHeaders())['x-csrf-token'], 'staff-csrf');
      return route.fulfill({ json: { workspace_id: ID(3) } });
    }
    if (url.pathname === '/workspace/') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Mock assigned workspace</title><main>Assigned workspace opened</main>' });
    unexpected.push(request.url()); return route.abort();
  });
  const idle = () => page.waitForFunction(() => document.querySelector('main')?.getAttribute('aria-busy') === 'false');
  await page.goto('https://review.test/staff/'); await page.locator('#staff-permit').waitFor(); await idle();
  for (let key = 1; key <= 2; key++) {
    await page.locator('#staff-permit').fill(`supervised_permit_${String(key).repeat(32)}`);
    await page.getByRole('button', { name: 'Register primary or backup passkey', exact: true }).click(); await idle();
    assert.equal(await page.locator('[data-action=list]').isDisabled(), true);
    await page.getByRole('button', { name: 'Confirm this passkey with a signed assertion', exact: true }).click(); await idle();
    if (key === 1) { await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId: authenticator.authenticatorId }); authenticator = await addAuthenticator(); }
  }
  assert.equal(registrations.length, 2); assert.notEqual(registrations[0], registrations[1]);
  assert.equal(await page.locator('[data-action=list]').isDisabled(), true);
  await page.getByRole('button', { name: 'Verify with passkey', exact: true }).click(); await idle();
  assert.equal(assertions.length, 3); assert.equal(assertions[2].confirmation, false);
  assert.equal(await page.locator('[data-action=list]').isDisabled(), false);
  await page.getByRole('button', { name: 'Refresh intake list', exact: true }).click(); await idle();
  await page.locator('[data-intake]').click(); await idle();
  await page.locator('#staff-owner-authority').focus(); await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Approve this pilot admission', exact: true }).click(); await idle();
  await page.getByRole('button', { name: 'Refresh intake list', exact: true }).click(); await idle();
  await page.getByRole('button', { name: 'Retry exact request', exact: true }).click(); await idle();
  assert.equal(approvals.length, 2); assert.equal(approvals[1], approvals[0]);
  await page.getByRole('button', { name: 'Refresh assigned workspaces', exact: true }).click(); await idle();
  await page.evaluate(() => document.fonts.ready);
  assert.match(await page.locator('body').evaluate(element => getComputedStyle(element).fontFamily), /Inter/);
  for (const width of [1365, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')].filter(element => element.getBoundingClientRect().right > innerWidth + 1).map(element => ({ tag: element.tagName, id: element.id, text: element.textContent.slice(0, 90), right: element.getBoundingClientRect().right })));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Overflow at ${width}px: ${JSON.stringify(overflow)}`);
  }
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  await page.locator('[data-workspace]').click(); await page.waitForURL('https://review.test/workspace/');
  assert.match(await page.locator('main').innerText(), /Assigned workspace opened/);
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
});

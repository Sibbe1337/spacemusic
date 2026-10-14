import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { initialize, embedOptions, sourceMetadata, FORM_ENDPOINT } from './intake.mjs';
const require = createRequire(new URL('../../services/seller_ui/package.json', import.meta.url));
const { JSDOM } = require('jsdom');
const body = readFileSync(new URL('./apply-body.html', import.meta.url), 'utf8');
function fixture() {
  const dom = new JSDOM('<!doctype html><html><head></head><body>' + body + '</body></html>', { url: 'https://spacemusic.io/apply/?email=private@example.com#token-secret' });
  const win = dom.window, doc = win.document;
  const events = []; const options = [];
  win.AbortSignal.timeout = () => undefined;
  win.spaceFunnel = { sources: () => ({ landing_path: '/calculator/', apply_source_path: '/sell/', email: 'do-not-copy@example.com' }),
    publicPath: value => ['/calculator/', '/sell/'].includes(value) ? value : '',
    track: value => events.push(value), once: value => events.push(value),
  };
  win.embed = { createWidget(id, opts) { options.push(opts); const frame = doc.createElement('iframe'); opts.container.append(frame); opts.onReady(); } };
  initialize(win, doc, '/apply/assets/test-sdk.js');
  return { win, doc, events, options, close: () => dom.window.close() };
}
async function tick() { await new Promise(resolve => setTimeout(resolve, 0)); }
async function start(f) { f.doc.getElementById('start-intake').click(); await tick(); }
function values(f) {
  const form = f.doc.getElementById('short-form');
  form.elements.email.value = 'test@example.com'; form.elements.artistLabel.value = 'Example Artist';
  return form;
}
function submit(f, form) { form.dispatchEvent(new f.win.Event('submit', { bubbles: true, cancelable: true })); }

test('SSR retains H1, initial copy, metadata-independent native fallback and no iframe until click', () => {
  const f = fixture();
  assert.equal(f.doc.querySelectorAll('h1').length, 1);
  assert.equal(f.doc.querySelector('h1').textContent, 'We buy your music catalog.');
  assert.equal(f.doc.querySelector('iframe'), null);
  assert.equal(f.doc.querySelector('form').action, FORM_ENDPOINT);
  assert.ok(body.includes('No upload is needed now.')); f.close();
});
test('hidden metadata only uses known public paths, never query, fragment, email or arbitrary parameters', () => {
  const f = fixture();
  assert.deepEqual(sourceMetadata(f.win), { landing_path: '/calculator/', apply_source_path: '/sell/' });
  f.win.spaceFunnel.sources = () => ({ landing_path: '/apply/?secret=x', apply_source_path: 'https://example.com/', email: 'private' });
  assert.deepEqual(sourceMetadata(f.win), {}); f.close();
});
test('SDK never forwards browser query, shares GA, enables Hubspot, or grants microphone/camera', async () => {
  const f = fixture(); await start(f);
  const o = f.options[0]; assert.deepEqual(o.transitiveSearchParams, []);
  assert.deepEqual(o.tracking, {}); assert.equal(o.disableTracking, true);
  assert.equal(o.shareGaInstance, false); assert.equal(o.hubspot, false);
  assert.equal(o.iframeProps.referrerpolicy, 'no-referrer'); assert.equal(o.iframeProps.allow, '');
  assert.ok(!JSON.stringify(o.hidden).includes('private@example.com')); f.close();
});
test('Typeform start and completed callback are distinct, once-only events with no response identifier', async () => {
  const f = fixture(); await start(f); const o = f.options[0];
  assert.deepEqual(f.events, []);
  o.onStarted({ responseId: 'PRIVATE_TOKEN' }); o.onStarted({ responseId: 'PRIVATE_TOKEN' });
  assert.deepEqual(f.events, ['intake_started']);
  assert.equal(f.doc.getElementById('intake-confirmation').hidden, true);
  o.onSubmit({ responseId: 'PRIVATE_TOKEN' }); o.onSubmit({ responseId: 'PRIVATE_TOKEN' });
  assert.deepEqual(f.events, ['intake_started', 'intake_submitted']);
  assert.equal(f.doc.getElementById('intake-confirmation').hidden, false); f.close();
});
test('double start mounts one form; fallback opens explicitly without a POST', async () => {
  const f = fixture(); let requests = 0; f.win.fetch = async () => { requests++; };
  f.doc.getElementById('start-intake').click(); f.doc.getElementById('start-intake').click(); await tick();
  assert.equal(f.options.length, 1);
  f.doc.getElementById('short-form-details').open = true; await tick();
  assert.equal(f.doc.getElementById('typeform-container').hidden, true);
  assert.equal(requests, 0); f.close();
});
test('an iframe that never becomes ready can retry without duplicating it or erasing a ready form', async () => {
  const f = fixture(); let callbacks, timer, refreshes = 0, mounts = 0;
  f.win.setTimeout = callback => { timer = callback; return 1; };
  f.win.clearTimeout = () => { timer = undefined; };
  f.win.embed.createWidget = (id, opts) => {
    mounts++; callbacks = opts; opts.container.append(f.doc.createElement('iframe'));
    return { refresh() { refreshes++; callbacks.onReady(); } };
  };
  await start(f); assert.equal(mounts, 1); timer();
  assert.match(f.doc.getElementById('start-intake').textContent, /Try loading/);
  await start(f); assert.equal(refreshes, 1); assert.equal(mounts, 1);
  assert.equal(timer, undefined); assert.equal(f.doc.querySelectorAll('iframe').length, 1);
  callbacks.onStarted();
  f.doc.getElementById('short-form-details').open = true; await tick();
  await start(f); assert.equal(refreshes, 1); assert.equal(mounts, 1); f.close();
});
test('invalid short form never posts and never reports success', async () => {
  const f = fixture(); let count = 0; f.win.fetch = async () => { count++; };
  submit(f, f.doc.querySelector('form')); await tick();
  assert.equal(count, 0); assert.equal(f.doc.getElementById('intake-confirmation').hidden, true); f.close();
});
test('short-form success waits for receiver; double-click posts once; no silent Typeform duplicate', async () => {
  const f = fixture(); let resolve; let count = 0;
  f.win.fetch = (url, options) => { count++; assert.equal(url, FORM_ENDPOINT);
    assert.equal(options.body.get('consentMarketing'), 'false');
    assert.equal(options.body.get('firstName'), '');
    assert.equal(options.body.has('territories'), false);
    assert.equal(options.body.get('landing_path'), '/calculator/');
    return new Promise(r => { resolve = r; }); };
  const form = values(f); submit(f, form); submit(f, form);
  assert.equal(count, 1); assert.ok(!f.events.includes('application_submitted'));
  resolve({ ok: true }); await tick();
  assert.ok(f.events.includes('application_submitted')); assert.equal(f.options.length, 0); f.close();
});
test('short-form failures and retries preserve values and do not fabricate acceptance', async () => {
  const f = fixture(); let count = 0;
  f.win.fetch = async () => ({ ok: ++count > 1 });
  const form = values(f); submit(f, form); await tick();
  assert.equal(form.elements.email.value, 'test@example.com');
  assert.equal(f.doc.getElementById('short-form-error').hidden, false);
  assert.ok(!f.events.includes('application_submitted'));
  submit(f, form); await tick(); assert.equal(count, 2);
  assert.equal(f.doc.getElementById('intake-confirmation').hidden, false); f.close();
});
test('blocked analytics/storage do not prevent either completion path', async () => {
  const f = fixture(); f.win.spaceFunnel = new Proxy({}, { get() { throw new Error('blocked'); } });
  await start(f); f.options[0].onStarted(); f.options[0].onSubmit();
  assert.equal(f.doc.getElementById('intake-confirmation').hidden, false); f.close();
  const g = fixture(); delete g.win.spaceFunnel; g.win.fetch = async () => ({ ok: true });
  submit(g, values(g)); await tick(); assert.equal(g.doc.getElementById('intake-confirmation').hidden, false); g.close();
});
test('completion in either path disables a late submission in the other path', async () => {
  const f = fixture(); await start(f); let count = 0; f.win.fetch = async () => { count++; return { ok: true }; };
  f.options[0].onSubmit(); submit(f, values(f)); await tick(); assert.equal(count, 0); f.close();
});

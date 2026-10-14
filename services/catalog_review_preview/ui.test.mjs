import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import * as fixtureModule from './fixtures.mjs';
import * as modelModule from './model.mjs';
import * as storageModule from './storage.mjs';

const require = createRequire(new URL('../seller_ui/package.json', import.meta.url));
const { JSDOM } = require('jsdom');
const html = await readFile(new URL('./ui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('./ui/app.mjs', import.meta.url), 'utf8');
const modules = { '/fixtures.mjs': fixtureModule, '/model.mjs': modelModule, '/storage.mjs': storageModule };
// Run the real event handlers against a DOM, without executing remote resources.
const linked = app.replace(/^import \{([^}]+)\} from '([^']+)';$/gm, (_, names, url) => {
  if (!modules[url]) throw new Error('Unexpected preview dependency');
  return `const {${names}} = window.__testModules[${JSON.stringify(url)}];`;
});

function fixture(t, { blockedStorage = false } = {}) {
  const dom = new JSDOM(html, { url: 'http://127.0.0.1:4197/', runScripts: 'outside-only' });
  t.after(() => dom.window.close());
  const win = dom.window;
  win.__testModules = modules;
  if (blockedStorage) Object.defineProperty(win, 'sessionStorage', { get() { throw new Error('Blocked'); } });
  win.fetch = () => { throw new Error('No network calls allowed in this prototype'); };
  const originalTimeout = win.setTimeout.bind(win);
  win.setTimeout = callback => originalTimeout(callback, 1);
  win.eval(linked);
  const doc = win.document;
  const click = selector => { const element = doc.querySelector(selector); assert.ok(element, selector); element.click(); };
  const set = (name, value) => {
    const input = doc.querySelector(`[name="${name}"]`); assert.ok(input, name);
    input.value = value;
    input.dispatchEvent(new win.Event('input', { bubbles: true }));
    input.dispatchEvent(new win.Event('change', { bubbles: true }));
  };
  const submit = selector => doc.querySelector(selector).dispatchEvent(new win.Event('submit', { bubbles: true, cancelable: true }));
  const reset = scenario => { doc.querySelector('#scenario').value = scenario; click('#restart'); };
  async function until(predicate) {
    for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 2)); }
    assert.fail('UI did not reach expected state');
  }
  return { win, doc, click, set, submit, reset, until, text: () => doc.querySelector('main').textContent };
}

function manual(f) {
  f.click('[data-action="start"]');
  f.click('[name="source"][value="manual"]'); f.submit('#source-form');
  f.click('[name="release"][value="demo-release-1"]'); f.submit('#selection-form');
}
function fillRights(f, ownership = 'shared') {
  f.set('ownership', ownership); f.set('scope', 'masters'); f.set('obligations', 'unknown');
  if (ownership !== 'unknown') f.set('share', '50');
}
async function toSummary(f) {
  manual(f); fillRights(f); f.submit('#rights-form');
  await f.until(() => !!f.doc.querySelector('[data-action="summary"]'));
  f.click('[data-document="statement"]'); f.click('[data-action="summary"]');
}

test('manual UI journey produces one locked demo submission, with no real file control', async t => {
  const f = fixture(t); await toSummary(f);
  assert.equal(f.doc.querySelector('input[type=file]'), null);
  f.click('#confirm-scope'); f.click('[data-action="submit"]'); f.click('[data-action="submit"]');
  await f.until(() => f.text().includes('DEMO-001-v1'));
  assert.equal(f.doc.querySelectorAll('[data-action="submit"]').length, 0);
  assert.ok(f.text().includes('Version 1'));
  f.click('.wordmark'); assert.ok(f.text().includes('DEMO-001-v1'));
});
test('save failure preserves all field values and retries with no premature advancement', async t => {
  const f = fixture(t); f.reset('save-error'); manual(f); fillRights(f);
  f.submit('#rights-form'); await f.until(() => f.text().includes('Simulated save failure'));
  assert.equal(f.doc.querySelector('[name=share]').value, '50');
  assert.equal(f.doc.querySelector('[name=ownership]').value, 'shared');
  f.submit('#rights-form'); await f.until(() => !!f.doc.querySelector('[data-action="summary"]'));
  assert.equal(f.doc.querySelector('#announcement').textContent, 'Demo choices saved in this tab.');
});
test('unknown ownership disables percentage and saves without a null-field exception', async t => {
  const f = fixture(t); manual(f); fillRights(f, 'unknown');
  assert.equal(f.doc.querySelector('[name=share]').disabled, true);
  f.submit('#rights-form'); await f.until(() => !!f.doc.querySelector('[data-action="summary"]'));
  f.click('#missing-evidence'); f.click('[data-action="summary"]');
  assert.ok(f.text().includes('Not yet confirmed')); assert.ok(!f.text().includes('0%'));
});
test('submission failure never shows a receipt; retry succeeds once', async t => {
  const f = fixture(t); f.reset('submission-error'); await toSummary(f);
  f.click('#confirm-scope'); f.click('[data-action="submit"]');
  await f.until(() => f.text().includes('Simulated save failure'));
  assert.ok(!f.text().includes('DEMO-001-v1'));
  assert.equal(f.doc.querySelector('#confirm-scope').checked, true);
  f.click('[data-action="submit"]');
  await f.until(() => f.text().includes('DEMO-001-v1'));
  assert.equal(f.doc.querySelector('#announcement').textContent, 'Demo submission saved. Nothing sent to SPACE.');
});
test('failed validation focuses an alert, does not erase values and never submits', async t => {
  const f = fixture(t); manual(f); fillRights(f); f.set('share', '101');
  f.submit('#rights-form'); await f.until(() => f.text().includes('up to 100'));
  await f.until(() => f.doc.querySelector('#screen-error').textContent.length > 0);
  assert.equal(f.doc.activeElement.id, 'screen-error');
  assert.equal(f.doc.querySelector('[name=share]').value, '101');
  assert.equal(f.doc.querySelector('[data-action="submit"]'), null);
});
test('missing evidence requires an explicit disclosure before summary', async t => {
  const f = fixture(t); manual(f); fillRights(f); f.submit('#rights-form');
  await f.until(() => !!f.doc.querySelector('[data-action="summary"]'));
  f.click('[data-action="summary"]'); assert.ok(f.doc.querySelector('#screen-error').textContent);
  f.click('#missing-evidence'); f.click('[data-action="summary"]');
  assert.ok(f.text().includes('No documents attached; flagged for follow-up.'));
});
test('expired session preserves the rights draft, not just completed answers', t => {
  const f = fixture(t); manual(f); fillRights(f); f.click('#expire-session');
  assert.ok(f.text().includes('Your place'));
  f.click('[data-action="resume-session"]');
  assert.equal(f.doc.querySelector('[name=share]').value, '50');
});
test('blocked storage still supports a complete submission with an honest persistence notice', async t => {
  const f = fixture(t, { blockedStorage: true }); await toSummary(f);
  assert.match(f.doc.querySelector('#save-state').textContent, /Memory-only/);
  f.click('#confirm-scope'); f.click('[data-action="submit"]');
  await f.until(() => f.text().includes('DEMO-001-v1'));
});
test('help opens an accessible explanation without abandoning the current step', t => {
  const f = fixture(t); f.click('[data-action="start"]');
  f.click('a[href="#help"]');
  assert.equal(f.doc.querySelector('#help').open, true);
  assert.equal(f.doc.activeElement.parentElement.id, 'help');
  assert.ok(f.text().includes('A simple place'));
});
test('sample attachment keeps keyboard focus on its replacement control', async t => {
  const f = fixture(t); manual(f); fillRights(f); f.submit('#rights-form');
  await f.until(() => !!f.doc.querySelector('[data-action="summary"]'));
  f.doc.querySelector('[data-document="statement"]').focus();
  f.click('[data-document="statement"]');
  assert.equal(f.doc.activeElement.dataset.document, 'statement');
  assert.match(f.doc.activeElement.textContent, /Remove sample/);
});

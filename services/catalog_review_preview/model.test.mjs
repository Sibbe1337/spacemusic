import test from 'node:test';
import assert from 'node:assert/strict';
import { initialState, transition, canVisit, submissionIssues } from './model.mjs';
import { decimalToMinor, summarizeMonths, MONTHS, RELEASES } from './fixtures.mjs';
import { createSession } from './storage.mjs';

const releases = RELEASES.map(row => row.id);
const run = (state, ...events) => events.reduce(transition, state);
function importing(scenario = 'standard') {
  return run(initialState(scenario), { type: 'start' }, { type: 'source', source: 'toolost' }, { type: 'authorize' }, { type: 'authorize-result' }, { type: 'confirm-account' });
}
function rightsStep() {
  return run(initialState(), { type: 'start' }, { type: 'source', source: 'manual' }, { type: 'select', ids: [releases[0]] });
}
const rightsEvent = { type: 'rights', ownership: 'owned', scope: 'masters', share: '100', obligations: 'unknown' };
function ready() {
  return run(rightsStep(), rightsEvent, { type: 'add-document', id: 'statement' }, { type: 'navigate', step: 'summary' }, { type: 'confirm-scope', value: true });
}

test('standard read-only journey imports only fixtures and submits one immutable version', () => {
  let state = importing();
  for (let i = 0; i < 3; i++) state = transition(state, { type: 'import-tick', run: state.run });
  assert.equal(state.importStatus, 'complete');
  state = run(state, { type: 'navigate', step: 'coverage' }, { type: 'navigate', step: 'selection' }, { type: 'select', ids: releases.slice(0, 2) }, rightsEvent, { type: 'add-document', id: 'statement' }, { type: 'navigate', step: 'summary' }, { type: 'confirm-scope', value: true }, { type: 'submit' });
  const submitted = JSON.stringify(state.submission);
  assert.equal(state.status, 'submitted');
  assert.equal(state.submission.selected.length, 2);
  assert.strictEqual(transition(state, { type: 'submit' }), state);
  assert.throws(() => transition(state, rightsEvent), /read-only/);
  assert.throws(() => transition(state, { type: 'navigate', step: 'selection' }));
  state = run(state, { type: 'request-information' }, { type: 'reply', id: 'partial' });
  assert.equal(state.status, 'under_review');
  assert.equal(JSON.stringify(state.submission), submitted);
});

test('manual route needs no provider connection', () => {
  const state = rightsStep();
  assert.equal(state.connection, 'disconnected'); assert.equal(state.step, 'rights');
});
test('future or arbitrary release IDs cannot be selected', () => {
  const state = run(initialState(), { type: 'start' }, { type: 'source', source: 'manual' });
  for (const ids of [[], ['future-release'], [releases[0], 'unknown']]) assert.throws(() => transition(state, { type: 'select', ids }));
});
test('duplicate selection IDs are deduplicated', () => {
  const state = run(initialState(), { type: 'start' }, { type: 'source', source: 'manual' }, { type: 'select', ids: [releases[0], releases[0]] });
  assert.equal(state.selected.length, 1);
});
test('import does not start until account confirmation', () => {
  const state = run(initialState(), { type: 'start' }, { type: 'source', source: 'toolost' }, { type: 'authorize' }, { type: 'authorize-result' });
  assert.equal(state.importStatus, 'idle'); assert.deepEqual(state.releases, []);
});
test('wrong-account cancellation never imports data', () => {
  const state = run(initialState('wrong-account'), { type: 'start' }, { type: 'source', source: 'toolost' }, { type: 'authorize' }, { type: 'authorize-result' }, { type: 'cancel-authorization' });
  assert.equal(state.connection, 'disconnected'); assert.deepEqual(state.releases, []);
});
test('permission refusal has a document fallback', () => {
  let state = run(initialState('cancelled'), { type: 'start' }, { type: 'source', source: 'toolost' }, { type: 'authorize' });
  assert.throws(() => transition(state, { type: 'authorize-result' }), /Permission/);
  state = run(state, { type: 'cancel-authorization' }, { type: 'source', source: 'manual' });
  assert.equal(state.step, 'selection');
});
test('partial import resumes from checkpoint without resetting releases', () => {
  let state = importing('partial');
  state = run(state, { type: 'import-tick', run: state.run }, { type: 'import-tick', run: state.run });
  assert.equal(state.importStatus, 'partial'); assert.equal(state.checkpoint, 2);
  const ids = [...state.releases];
  state = run(state, { type: 'retry-import' }, { type: 'import-tick', run: state.run });
  assert.equal(state.checkpoint, 3); assert.equal(state.importStatus, 'complete'); assert.deepEqual(state.releases, ids);
});
test('empty catalog allows documents but not direct release selection', () => {
  let state = importing('empty');
  for (let i = 0; i < 3; i++) state = transition(state, { type: 'import-tick', run: state.run });
  assert.equal(canVisit(state, 'selection'), false);
  state = run(state, { type: 'navigate', step: 'source' }, { type: 'source', source: 'manual' });
  assert.equal(state.releases.length, 3);
});
test('stale job callbacks and late ticks after disconnect are ignored', () => {
  let state = importing();
  assert.strictEqual(transition(state, { type: 'import-tick', run: 999 }), state);
  const oldRun = state.run;
  state = run(state, { type: 'navigate', step: 'settings' }, { type: 'disconnect' });
  assert.equal(state.importStatus, 'cancelled');
  assert.strictEqual(transition(state, { type: 'import-tick', run: oldRun }), state);
});
test('expired session freezes import and resumes only by explicit demo action', () => {
  let state = importing();
  state = transition(state, { type: 'expire' });
  assert.equal(canVisit(state, 'settings'), false);
  assert.strictEqual(transition(state, { type: 'import-tick', run: state.run }), state);
  state = transition(state, { type: 'resume-session' });
  assert.equal(state.step, 'import');
});
test('rights drafts survive expiry and do not imply saved completed rights', () => {
  const state = run(rightsStep(), { type: 'edit-rights', field: 'share', value: '50' }, { type: 'expire' }, { type: 'resume-session' });
  assert.equal(state.rightsDraft.share, '50'); assert.equal(state.rights, null);
});
test('rights boundary validates percentages including zero, negatives and excessive precision', () => {
  for (const share of ['', '0', '-1', '100.01', '101', 'Infinity', '1e2', '<script>', '10.001', 50, null]) assert.throws(() => transition(rightsStep(), { ...rightsEvent, share }));
  for (const share of ['0.01', '50', '100', '99.99', '100.00']) assert.equal(transition(rightsStep(), { ...rightsEvent, share }).rights.share, share);
});
test('unknown ownership preserves unknown rather than invented 0%', () => {
  const state = transition(rightsStep(), { ...rightsEvent, ownership: 'unknown', share: '' });
  assert.equal(state.rights.share, null);
});
test('only supported rights values enter snapshots', () => {
  for (const field of ['ownership', 'scope', 'obligations']) assert.throws(() => transition(rightsStep(), { ...rightsEvent, [field]: '<script>' }));
});
test('only bundled synthetic documents may be attached', () => {
  const state = transition(rightsStep(), rightsEvent);
  assert.throws(() => transition(state, { type: 'add-document', id: '/etc/passwd' }));
  const attached = run(state, { type: 'add-document', id: 'statement' }, { type: 'add-document', id: 'statement' });
  assert.equal(attached.documents.length, 1);
});
test('missing evidence can be disclosed, never silently treated as complete', () => {
  let state = transition(rightsStep(), rightsEvent);
  assert.equal(canVisit(state, 'summary'), false);
  state = run(state, { type: 'missing-evidence', value: true }, { type: 'navigate', step: 'summary' }, { type: 'confirm-scope', value: true }, { type: 'submit' });
  assert.equal(state.submission.missingEvidence, true); assert.deepEqual(state.submission.documents, []);
});
test('review scope confirmation is required and editing clears it', () => {
  const state = transition(ready(), { type: 'confirm-scope', value: false });
  assert.throws(() => transition(state, { type: 'submit' }), /Confirm/);
  assert.equal(submissionIssues(state).length, 1);
  const changed = run(ready(), { type: 'navigate', step: 'documents' }, { type: 'remove-document', id: 'statement' });
  assert.equal(changed.consent, false); assert.equal(canVisit(changed, 'summary'), false);
});
test('initial state cannot skip into review or status via URL', () => {
  for (const step of ['account', 'selection', 'summary', 'status', 'documents', 'unknown']) assert.equal(canVisit(initialState(), step), false);
});
test('unknown events and scenarios fail closed', () => {
  assert.throws(() => initialState('live')); assert.throws(() => transition(initialState(), { type: 'live-connect' }));
});
test('exact money arithmetic retains negative adjustments', () => {
  assert.equal(decimalToMinor('-24.50'), -2450n);
  assert.equal(decimalToMinor('0.10') + decimalToMinor('0.20'), 30n);
  assert.equal(summarizeMonths(MONTHS, 'EUR').totalMinor, '756000');
});
test('unknown currency blocks totals, never defaults to USD or EUR', () => {
  for (const currency of [null, undefined, '']) assert.equal(summarizeMonths(MONTHS, currency).totalMinor, null);
});
test('no reported months is unknown, not a confirmed zero', () => {
  assert.equal(summarizeMonths([], 'EUR').totalMinor, null);
  assert.equal(summarizeMonths([{ period: '2026-01', amount: '0.00' }], 'EUR').totalMinor, '0');
});
test('duplicate or invalid periods and amounts are not silently added', () => {
  assert.throws(() => summarizeMonths([MONTHS[0], MONTHS[0]], 'EUR'));
  assert.throws(() => summarizeMonths([{ period: '2026-13', amount: '1.00' }], 'EUR'));
  for (const value of ['1,000.00', '1.001', 'NaN', 0.1]) assert.throws(() => decimalToMinor(value));
});

function memoryStorage() {
  const data = new Map();
  return { getItem: key => data.get(key), setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key), data };
}
test('reload reconstructs guarded demo state including import checkpoint', () => {
  const storage = memoryStorage(); const session = createSession(storage);
  for (const event of [{ type: 'start' }, { type: 'source', source: 'toolost' }, { type: 'authorize' }, { type: 'authorize-result' }, { type: 'confirm-account' }]) session.dispatch(event);
  session.dispatch({ type: 'import-tick', run: session.state.run });
  const loaded = createSession(storage);
  assert.deepEqual(loaded.state, session.state); assert.equal(loaded.restored, true);
});
test('blocked storage permits the full manual journey in memory', () => {
  const storage = { getItem() { throw new Error(); }, setItem() { throw new Error(); }, removeItem() { throw new Error(); } };
  const session = createSession(storage);
  session.dispatch({ type: 'start' }); session.dispatch({ type: 'source', source: 'manual' });
  assert.equal(session.state.step, 'selection'); assert.equal(session.persistent, false);
});
test('malformed or injected persisted sessions reset instead of trusting snapshots', () => {
  for (const raw of ['{', JSON.stringify({ version: 1, scenario: 'standard', events: [{ type: 'submit' }] }), JSON.stringify({ version: 1, scenario: 'standard', events: [{ type: 'source', source: 'https://evil.example' }] })]) {
    const storage = memoryStorage(); storage.setItem('space-catalog-review-design-v1', raw);
    assert.equal(createSession(storage).state.step, 'invitation');
  }
});
test('reset erases old snapshot and selects only a known scenario', () => {
  const session = createSession(memoryStorage()); session.dispatch({ type: 'start' });
  session.reset('partial'); assert.equal(session.state.scenario, 'partial'); assert.equal(session.state.submission, null);
  assert.throws(() => session.reset('production'));
});
test('deletion and disconnect are separate from the submitted package', () => {
  let state = transition(ready(), { type: 'submit' });
  const snapshot = JSON.stringify(state.submission);
  state = run(state, { type: 'navigate', step: 'settings' }, { type: 'disconnect' }, { type: 'request-deletion' });
  assert.equal(state.deletionRequested, true); assert.equal(JSON.stringify(state.submission), snapshot);
});
test('a new source cannot inherit another source selection and rights answers', () => {
  let state = ready();
  state = run(state, { type: 'navigate', step: 'source' }, { type: 'source', source: 'toolost' });
  assert.deepEqual(state.selected, []); assert.equal(state.rights, null);
  assert.equal(canVisit(state, 'summary'), false); assert.deepEqual(state.documents, []);
});
test('submitted packages cannot restart through the invitation route', () => {
  const state = transition(ready(), { type: 'submit' });
  assert.equal(canVisit(state, 'invitation'), false);
  assert.throws(() => transition(state, { type: 'start' }));
});

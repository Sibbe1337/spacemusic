import test from 'node:test';
import assert from 'node:assert/strict';
import { createDeskState } from '../web/state.mjs';
import { snapshot, toolResult } from '../server/domain.mjs';

const result = (id = 'demo-harbor') => toolResult(snapshot('review', id));
function harness(callTool) {
  const seen = [], errors = [], loading = [];
  return { seen, errors, loading, state: createDeskState({ callTool,
    render: value => seen.push(value), report: (...args) => errors.push(args),
    busy: value => loading.push(value), clear: () => {} }) };
}
test('initial host results and later host results render without a new widget', () => {
  const h = harness();
  h.state.receive(result());
  h.state.receive(result('demo-juniper'));
  assert.equal(h.seen.length, 2);
  assert.equal(h.state.snapshot.selected.id, 'demo-juniper');
});
test('a newer host notification wins over an older in-flight tool response', async () => {
  let resolve;
  const h = harness(() => new Promise(done => { resolve = done; }));
  const pending = h.state.run('space_review_demo_catalog', { case_id: 'demo-harbor' });
  h.state.receive(result('demo-juniper'));
  resolve(result());
  await pending;
  assert.equal(h.state.snapshot.selected.id, 'demo-juniper');
});
test('rapid requests cannot replace the latest selection with stale data', async () => {
  const pending = [];
  const h = harness(() => new Promise(done => pending.push(done)));
  const first = h.state.run('space_review_demo_catalog', { case_id: 'demo-harbor' });
  const second = h.state.run('space_review_demo_catalog', { case_id: 'demo-northline' });
  pending[1](result('demo-northline')); await second;
  pending[0](result()); await first;
  assert.equal(h.state.snapshot.selected.id, 'demo-northline');
});
test('failed request keeps previous data and retry uses the same explicit arguments', async () => {
  const calls = [];
  const h = harness(async (name, args) => {
    calls.push({ name, args });
    if (calls.length === 1) throw new Error('offline');
    return result('demo-juniper');
  });
  h.state.receive(result());
  await h.state.run('space_review_demo_catalog', { case_id: 'demo-juniper' });
  assert.equal(h.state.snapshot.selected.id, 'demo-harbor');
  assert.equal(h.errors[0][1], true);
  await h.state.retry();
  assert.deepEqual(calls[0], calls[1]);
  assert.equal(h.state.snapshot.selected.id, 'demo-juniper');
  assert.equal(h.loading.at(-1), false);
});
test('malformed and error tool results do not replace the current data', () => {
  const h = harness(); h.state.receive(result());
  h.state.receive({ structuredContent: { dataMode: 'live' } });
  h.state.receive({ ...result('demo-juniper'), isError: true });
  assert.equal(h.state.snapshot.selected.id, 'demo-harbor');
  assert.equal(h.errors.length, 2);
});
test('cancellation invalidates outstanding work', async () => {
  let resolve;
  const h = harness(() => new Promise(done => { resolve = done; }));
  const pending = h.state.run('space_review_demo_catalog', { case_id: 'demo-harbor' });
  h.state.cancel(); resolve(result()); await pending;
  assert.equal(h.state.snapshot, null);
  assert.equal(h.loading.at(-1), false);
});

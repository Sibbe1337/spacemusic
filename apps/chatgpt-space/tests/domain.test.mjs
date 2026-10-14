import test from 'node:test';
import assert from 'node:assert/strict';
import { cases, buyerProfiles } from '../server/fixtures.mjs';
import { snapshot, compareProfile, toolResult } from '../server/domain.mjs';
import { snapshotSchema, caseInputSchema, noInputSchema } from '../shared/contract.mjs';

test('all demo views satisfy their versioned output contract and stay fictional', () => {
  for (const item of cases) {
    for (const view of ['overview', 'review', 'buyers']) {
      const data = snapshot(view, item.id);
      assert.equal(snapshotSchema.safeParse(data).success, true);
      assert.equal(data.dataMode, 'synthetic');
      assert.equal(data.sharingEnabled, false);
      assert.match(toolResult(data).content[0].text, /Fictional/);
    }
  }
});
test('only the three fixed demo IDs are accepted; no URLs, documents or extra fields', () => {
  for (const input of [{}, { case_id: '../../private' }, { case_id: 'customer-1' },
    { case_id: 'demo-harbor', email: 'private@example.com' }, { case_id: 'https://example.com/file' }]) {
    assert.equal(caseInputSchema.safeParse(input).success, false);
  }
  assert.equal(noInputSchema.safeParse({ query: 'private' }).success, false);
  assert.throws(() => snapshot('review', 'not-a-case'));
});
test('snapshots cannot mutate the underlying fixtures or later tool responses', () => {
  const first = snapshot('review', 'demo-harbor');
  first.selected.checks[0].status = 'missing';
  first.cases[0].name = 'Changed';
  assert.equal(snapshot('review', 'demo-harbor').selected.checks[0].status, 'provided');
  assert.equal(snapshot().cases[0].name, 'Harbor Sessions');
  assert.deepEqual(snapshot('buyers', 'demo-harbor'), snapshot('buyers', 'demo-harbor'));
});
test('a potentially fitting fictional profile still requires human review and seller permission', () => {
  const match = snapshot('buyers', 'demo-northline').matches.find(item => item.id === 'profile-c');
  assert.equal(match.status, 'potential');
  assert.match(match.reasons.join(' '), /not a verified buyer match/);
  assert.match(match.reasons.join(' '), /seller permission/);
  assert.match(match.reasons.join(' '), /Sharing is disabled/);
});
test('supplied income does not override missing ownership and agreement evidence', () => {
  const match = snapshot('buyers', 'demo-harbor').matches[0];
  assert.equal(match.status, 'blocked');
  assert.match(match.reasons.join(' '), /Ownership & splits/);
  assert.match(match.reasons.join(' '), /Existing agreements/);
});
test('unclear publishing income blocks financial comparisons', () => {
  const match = snapshot('buyers', 'demo-juniper').matches[1];
  assert.equal(match.status, 'blocked');
  assert.match(match.reasons.join(' '), /Financial comparison blocked/);
});
test('currencies are never converted and rights outside the profile do not match', () => {
  assert.match(snapshot('buyers', 'demo-northline').matches[0].reasons[0], /Currency differs/);
  assert.equal(snapshot('buyers', 'demo-northline').matches[1].status, 'outside_scope');
});
for (const [field, value] of [['currency', null], ['basis', 'gross'], ['period', 'unknown'],
  ['scope', 'sold_share_only'], ['annual', NaN], ['annual', Infinity], ['annual', -1]]) {
  test(`ambiguous financial field ${field}=${value} blocks a fit`, () => {
    const item = structuredClone(cases[2]);
    item.finance[field] = value;
    assert.equal(compareProfile(item, buyerProfiles[2]).status, 'blocked');
  });
}
test('zero revenue and income below the hypothetical threshold do not qualify', () => {
  for (const income of [0, 74999]) {
    const item = structuredClone(cases[2]);
    item.finance.annual = income;
    assert.equal(compareProfile(item, buyerProfiles[2]).status, 'blocked');
  }
});
test('fictional sources resolve and supplied counts describe presence, not scores', () => {
  for (const item of cases) {
    const data = snapshot('review', item.id).selected;
    assert.equal(data.provided, data.checks.filter(check => check.status === 'provided').length);
    for (const check of data.checks) assert.ok(data.sources.some(source => source.id === check.sourceId));
    assert.equal(Object.hasOwn(data, 'valuation'), false);
    assert.equal(Object.hasOwn(data, 'readinessScore'), false);
  }
});
test('inconsistent host snapshots are rejected before replacing the visible page', () => {
  const data = snapshot('review', 'demo-harbor');
  data.selected = null;
  assert.equal(snapshotSchema.safeParse(data).success, false);
});

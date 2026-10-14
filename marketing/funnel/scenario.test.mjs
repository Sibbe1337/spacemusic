import assert from 'node:assert/strict';
import { scenario, netFromReceipts } from './scenario.mjs';
assert.deepEqual(scenario('1000', '4', '50'), { annual: 12000, total: 24000 });
assert.deepEqual(scenario('0', '4', '50'), { annual: 0, total: 0 });
assert.equal(scenario(1000, 4, 0).total, 0);
assert.equal(scenario(1000, 4, 100).total, 48000);
for (const invalid of ['', ' ', null, undefined, NaN, Infinity, 'hello', '1,000', '1e3', '-1']) {
  assert.equal(scenario(invalid, 4, 50), null, `income ${invalid}`);
  assert.equal(scenario(1000, invalid, 50), null, `multiple ${invalid}`);
  assert.equal(scenario(1000, 4, invalid), null, `share ${invalid}`);
}
for (const share of [-1, 101, Infinity]) assert.equal(scenario(1000, 4, share), null);
assert.equal(scenario(1000, 0, 50), null);
assert.equal(scenario(Number.MAX_VALUE, 4, 50), null);
assert.equal(scenario('1000.5', '4.5', '50').total, 27013.5);
assert.equal(netFromReceipts('1000', '50', '15'), 350);
assert.equal(netFromReceipts('1000', '70', '40'), null);
assert.equal(netFromReceipts('1000', '', '15'), null);
assert.equal(netFromReceipts('1000', '100', '0'), 0);
console.log('Scenario: 47 valid, invalid, boundary and deduction assertions passed');

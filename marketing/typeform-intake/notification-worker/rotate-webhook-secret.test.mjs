import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { rotateSigningSecret } from './rotate-webhook-secret.mjs';

test('signing rotation retries the same staged key and preserves local state on remote failure', () => {
  const dir = mkdtempSync(join(tmpdir(), 'space-key-rotation-'));
  try {
    const path = join(dir, 'typeform-webhook-secret');
    const old = 'ab'.repeat(32);
    writeFileSync(path, old, { mode: 0o600 });
    let attempted;
    assert.throws(() => rotateSigningSecret(dir, key => { attempted = key; throw new Error('simulated offline'); }));
    assert.equal(readFileSync(path, 'utf8'), old);
    assert.notEqual(attempted, old);
    assert.equal(rotateSigningSecret(dir, key => assert.equal(key, attempted)), 'rotated');
    assert.equal(readFileSync(path, 'utf8'), attempted);
    assert.equal(statSync(path).mode & 0o077, 0);
    assert.equal(rotateSigningSecret(dir, () => assert.fail('Must not rotate again')), 'already_current');
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

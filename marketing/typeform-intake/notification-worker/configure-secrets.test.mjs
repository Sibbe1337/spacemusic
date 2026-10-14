import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, existsSync, readFileSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { initializeSecret } from './configure-secrets.mjs';

test('missing local key cannot overwrite an existing remote encryption key', () => {
  const dir = mkdtempSync(join(tmpdir(), 'space-secret-test-'));
  try {
    const file = join(dir, 'key'); let installs = 0;
    assert.throws(() => initializeSecret(file, 'REPLY_ENCRYPTION_KEY', () => ['REPLY_ENCRYPTION_KEY'], () => installs++), /never be overwritten/);
    assert.equal(installs, 0); assert.equal(existsSync(file), false);
  } finally { rmSync(dir, { recursive: true }); }
});
test('first initialization is private and cannot regenerate a local key', () => {
  const dir = mkdtempSync(join(tmpdir(), 'space-secret-test-'));
  try {
    const file = join(dir, 'key'); let installs = 0;
    initializeSecret(file, 'REPLY_ENCRYPTION_KEY', () => [], (name, value) => {
      installs++; assert.match(value, /^[a-f0-9]{64}$/); assert.equal(statSync(file).mode & 0o077, 0);
    });
    const previous = readFileSync(file);
    assert.throws(() => initializeSecret(file, 'REPLY_ENCRYPTION_KEY', () => [], () => installs++), /not be regenerated/);
    assert.deepEqual(readFileSync(file), previous); assert.equal(installs, 1);
  } finally { rmSync(dir, { recursive: true }); }
});
test('remote verification failure does not create or install a key', () => {
  const dir = mkdtempSync(join(tmpdir(), 'space-secret-test-'));
  try {
    const file = join(dir, 'key');
    assert.throws(() => initializeSecret(file, 'REPLY_ENCRYPTION_KEY', () => { throw new Error('unavailable'); }, () => assert.fail()), /unavailable/);
    assert.equal(existsSync(file), false);
  } finally { rmSync(dir, { recursive: true }); }
});

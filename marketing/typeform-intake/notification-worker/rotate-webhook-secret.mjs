import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import { existsSync, lstatSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

function privateKey(path) {
  const stat = lstatSync(path);
  assert(stat.isFile() && !stat.isSymbolicLink() && (stat.mode & 0o077) === 0, 'Key must be an owner-only regular file');
  const key = readFileSync(path, 'utf8');
  assert(/^[a-f0-9]{64}$/.test(key), 'Invalid signing key format');
  return key;
}

export function rotateSigningSecret(directory, install) {
  const stat = lstatSync(directory);
  assert(stat.isDirectory() && !stat.isSymbolicLink() && (stat.mode & 0o077) === 0, 'Private directory required');
  const currentPath = join(directory, 'typeform-webhook-secret');
  const current = privateKey(currentPath);
  // Keep one staged key across uncertain attempts; never rotate again on retry.
  const stagedPath = join(directory, 'typeform-webhook-secret.rotation-20260916');
  if (!existsSync(stagedPath)) writeFileSync(stagedPath, randomBytes(32).toString('hex'), { flag: 'wx', mode: 0o600 });
  const replacement = privateKey(stagedPath);
  if (current === replacement) return 'already_current';
  install(replacement);
  const nextPath = `${currentPath}.${randomUUID()}.next`;
  writeFileSync(nextPath, replacement, { flag: 'wx', mode: 0o600 });
  renameSync(nextPath, currentPath);
  return 'rotated';
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = join(homedir(), 'Library/Application Support/SpaceMusic/typeform-intake');
  const status = rotateSigningSecret(directory, key => {
    const result = spawnSync(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'secret', 'put', 'TYPEFORM_WEBHOOK_SECRET'], {
      cwd: dirname(fileURLToPath(import.meta.url)), input: key, encoding: 'utf8', timeout: 120000,
    });
    // Do not log stdin, provider bodies or credential values on failure.
    assert(result.status === 0, 'Remote update failed or is uncertain; retry with the retained staged key');
  });
  console.log(JSON.stringify({ status, secret: 'TYPEFORM_WEBHOOK_SECRET', typeformUserHandoffRequired: true }));
}

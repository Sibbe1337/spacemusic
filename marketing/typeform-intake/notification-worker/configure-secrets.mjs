import assert from 'node:assert/strict';
import { readFileSync, statSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const directory = join(homedir(), 'Library/Application Support/SpaceMusic/typeform-intake');
function privateRead(file) {
  assert.equal(statSync(file).mode & 0o077, 0, 'Credential must be owner-only');
  return readFileSync(file, 'utf8').trim();
}
function put(name, value) {
  const result = spawnSync(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'secret', 'put', name], {
    cwd: import.meta.dirname, input: value, encoding: 'utf8',
    env: { ...process.env, WRANGLER_SEND_METRICS: 'false' },
  });
  assert.equal(result.status, 0, `Secret installation failed for ${name}; inspect account permissions without printing credentials.`);
  console.log(`${name}: installed in Cloudflare managed secrets`);
}
function remoteSecretNames() {
  const result = spawnSync(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'secret', 'list'], {
    cwd: import.meta.dirname, encoding: 'utf8', env: { ...process.env, WRANGLER_SEND_METRICS: 'false' },
  });
  assert.equal(result.status, 0, 'Cannot verify installed secrets; initialization denied');
  const secrets = JSON.parse(result.stdout);
  assert.ok(Array.isArray(secrets));
  return secrets.map(secret => secret.name);
}

export function initializeSecret(file, name, list = remoteSecretNames, install = put) {
  assert.ok(!list().includes(name), 'An installed secret must never be overwritten by initialization');
  assert.ok(!existsSync(file), 'An existing local secret must not be regenerated');
  writeFileSync(file, randomBytes(32).toString('hex'), { mode: 0o600, flag: 'wx' });
  install(name, privateRead(file));
}

export function configure(mode, install = put) {
mkdirSync(directory, { recursive: true, mode: 0o700 });
if (mode === 'sender') {
  const resend = privateRead(join(homedir(), 'Library/Application Support/SpaceMusic/seller-portal-local/resend-test-key'));
  assert.match(resend, /^re_[A-Za-z0-9_]+$/);
  // Refreshing the sender must not rotate the key for pending encrypted notifications.
  install('RESEND_API_KEY', resend);
} else if (mode === 'webhook') {
  const secret = privateRead(join(directory, 'typeform-webhook-secret'));
  assert.ok(secret.length >= 32 && !/[\r\n]/.test(secret));
  install('TYPEFORM_WEBHOOK_SECRET', secret);
} else if (mode === 'initialize-encryption') {
  initializeSecret(join(directory, 'reply-encryption-key'), 'REPLY_ENCRYPTION_KEY');
} else if (mode === 'initialize-webhook') {
  initializeSecret(join(directory, 'typeform-webhook-secret'), 'TYPEFORM_WEBHOOK_SECRET');
} else throw new Error('Use sender, webhook, initialize-encryption or initialize-webhook. Never pass credentials as command-line arguments.');
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) configure(process.argv[2]);

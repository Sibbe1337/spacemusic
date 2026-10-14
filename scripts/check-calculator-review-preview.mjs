import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { playwrightModule } from './funnel-support.mjs';

const [origin, release, qa, mode, ...extra] = process.argv.slice(2);
const production = mode === '--production';
assert(release && qa && !extra.length && (!mode || production), 'Usage: ORIGIN RELEASE QA_DIRECTORY [--production]');
assert(production ? origin === 'https://spacemusic.io' : new URL(origin).hostname.endsWith('.spacemusic-a6n.pages.dev'), 'Use explicit production mode only for the public site');
await mkdir(qa, { recursive: true });
const checks = [
  ['focused-browser', ['scripts/check-calculator-review-browser.mjs', origin, path.join(qa, 'browser'), ...(production ? ['--production'] : [])]],
  ['apply-navigation', ['scripts/check-apply-navigation.mjs', origin, path.join(qa, 'apply')]],
  ['form-mocks', ['scripts/check-funnel.mjs', origin]],
  ['full-journey', ['scripts/check-journey.mjs', origin]],
  ['release-bytes', ['scripts/verify-release-files.mjs', release, origin]],
];
const results = [];
for (const [name, args] of checks) {
  let output = '';
  const exitCode = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, { env: { ...process.env, PLAYWRIGHT_MODULE: playwrightModule } });
    child.stdout.on('data', data => { output += data; process.stdout.write(data); });
    child.stderr.on('data', data => { output += data; process.stderr.write(data); });
    child.on('error', reject);
    child.on('exit', resolve);
  });
  await writeFile(path.join(qa, name + '.log'), output);
  results.push({ name, exitCode, completedAt: new Date().toISOString() });
  await writeFile(path.join(qa, 'checks.json'), JSON.stringify({ origin, release, results }, null, 2));
  assert.equal(exitCode, 0, `Preview check failed: ${name}`);
}
console.log(JSON.stringify({ origin, checks: results.length, passed: true, environment: production ? 'production' : 'preview' }));

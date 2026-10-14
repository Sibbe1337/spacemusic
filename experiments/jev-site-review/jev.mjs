// Minimal TypeSafe System One client for public, non-personal inputs only.
// The key is read from the owner-only file created by ../jev-catalog-review/secrets.mjs
// (or TYPESAFE_API_KEY) and is never logged or written anywhere.
import {readFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const KEY_FILE = path.join(os.homedir(), 'Library/Application Support/SpaceMusic/jev-evaluation/typesafe-api-key');
const ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
export const MODEL = 'jev-latest';
export const USD_PER_MILLION_INPUT = 0.042; // published rate recorded by the catalog-review lab

function key() {
  const value = (process.env.TYPESAFE_API_KEY || readFileSync(KEY_FILE, 'utf8')).trim();
  if (!/^[\x21-\x7e]{20,512}$/.test(value)) throw new Error('missing_key');
  return value;
}

export async function ask(state, questions, {retries = 5} = {}) {
  const body = JSON.stringify({model: MODEL, state, questions});
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(ENDPOINT, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(60_000),
      headers: {authorization: `Bearer ${key()}`, 'content-type': 'application/json', accept: 'application/json'},
      body,
    }).catch(() => null);
    if (res?.ok) {
      const json = await res.json();
      for (const id of Object.keys(questions)) if (!json.answers?.[id]) throw new Error('invalid_response');
      return json;
    }
    const status = res?.status ?? 'network';
    await res?.body?.cancel();
    // Never include upstream bodies or headers in errors.
    if (attempt >= retries || ![429, 529, 500, 502, 503, 504, 'network'].includes(status)) throw new Error(`provider_http_${status}`);
    await new Promise(r => setTimeout(r, 1000 * 2 ** attempt));
  }
}

export async function pool(items, size, fn) {
  const out = new Array(items.length); let next = 0, done = 0;
  await Promise.all(Array.from({length: size}, async () => {
    while (next < items.length) {
      const i = next++; out[i] = await fn(items[i], i);
      if (++done % 25 === 0) process.stderr.write(`${done}/${items.length}\n`);
    }
  }));
  return out;
}

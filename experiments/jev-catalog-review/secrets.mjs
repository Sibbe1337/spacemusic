import { constants, lstatSync, mkdirSync, openSync, closeSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

export const KEY_DIRECTORY = join(homedir(), 'Library', 'Application Support', 'SpaceMusic', 'jev-evaluation');
export const KEY_FILE = join(KEY_DIRECTORY, 'typesafe-api-key');

export function validKey(value) {
  return typeof value === 'string' && /^[\x21-\x7e]{20,512}$/.test(value);
}

export function readJevKey(env = process.env) {
  if (env.TYPESAFE_API_KEY) {
    if (!validKey(env.TYPESAFE_API_KEY)) throw new Error('invalid_key');
    return env.TYPESAFE_API_KEY;
  }
  let fd;
  try {
    const dir = lstatSync(KEY_DIRECTORY), file = lstatSync(KEY_FILE);
    if (!dir.isDirectory() || dir.isSymbolicLink() || (dir.mode & 0o077)
      || !file.isFile() || file.isSymbolicLink() || (file.mode & 0o077)
      || file.uid !== process.getuid() || dir.uid !== process.getuid() || file.size > 513) throw new Error();
    fd = openSync(KEY_FILE, constants.O_RDONLY | constants.O_NOFOLLOW);
    const key = readFileSync(fd, 'utf8').trim();
    if (!validKey(key)) throw new Error();
    return key;
  } catch {
    throw new Error('key_missing_or_unsafe');
  } finally { if (fd !== undefined) closeSync(fd); }
}

async function configure() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) throw new Error('terminal_required');
  process.stdout.write('Paste the TypeSafe API key (input is hidden), then press Enter. Ctrl-C cancels.\n');
  const key = await new Promise((resolve, reject) => {
    let value = '';
    process.stdin.setRawMode(true);
    process.stdin.resume();
    function finish(error) {
      process.stdin.off('data', read);
      process.stdin.setRawMode(false);
      process.stdin.pause();
      if (error) reject(new Error(error)); else resolve(value);
    }
    function read(bytes) {
      for (const char of bytes.toString('utf8')) {
        if (char === '\u0003' || char === '\u0004') return finish('cancelled');
        if (char === '\r' || char === '\n') return finish();
        if (char === '\u007f' || char === '\b') value = value.slice(0, -1);
        else value += char;
        if (value.length > 512) return finish('invalid_key');
      }
    }
    process.stdin.on('data', read);
  });
  if (!validKey(key)) throw new Error('invalid_key');
  mkdirSync(KEY_DIRECTORY, { recursive: true, mode: 0o700 });
  const dir = lstatSync(KEY_DIRECTORY);
  if (!dir.isDirectory() || dir.isSymbolicLink() || (dir.mode & 0o077) || dir.uid !== process.getuid()) {
    throw new Error('unsafe_key_directory');
  }
  const fd = openSync(KEY_FILE, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
  try { writeFileSync(fd, key, 'utf8'); } finally { closeSync(fd); }
  process.stdout.write('Saved outside the repository with owner-only access. No API call was made.\n');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  configure().catch(error => {
    const safe = ['terminal_required', 'cancelled', 'invalid_key', 'unsafe_key_directory'];
    console.error(safe.includes(error.message) ? error.message : 'Could not save key; existing keys are never overwritten.');
    process.exitCode = 1;
  });
}

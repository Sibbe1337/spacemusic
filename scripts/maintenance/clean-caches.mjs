import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const CACHE_NAMES = new Set(['__pycache__', '.pytest_cache', '.ruff_cache']);
const SCAN_ROOTS = ['services', 'libs', 'tests', 'scripts', 'experiments', 'marketing'];
const SKIP = new Set([
  'node_modules', '.git', '.venv', 'venv', 'private', 'tmp', 'output',
  'build', 'dist', '.wrangler', '.vercel', '.railway', 'results', 'qa',
]);

function allowedFile(kind, relative) {
  if (kind === '__pycache__') return /^[^/]+\.py[co]$/.test(relative);
  if (kind === '.pytest_cache') {
    return ['.gitignore', 'CACHEDIR.TAG', 'README.md',
      'v/cache/nodeids', 'v/cache/lastfailed', 'v/cache/stepwise'].includes(relative);
  }
  return ['.gitignore', 'CACHEDIR.TAG'].includes(relative)
    || /^\d+\.\d+\.\d+\/\d+$/.test(relative);
}

function inspect(root, relative, tracked) {
  const target = path.join(root, relative);
  const kind = path.basename(relative);
  const files = [], directories = [];
  let reason = null;
  function walk(directory) {
    const stat = fs.lstatSync(directory);
    if (!stat.isDirectory() || stat.isSymbolicLink()) {
      reason = 'symlink or non-directory';
      return;
    }
    directories.push(directory);
    for (const name of fs.readdirSync(directory)) {
      const absolute = path.join(directory, name);
      const stat = fs.lstatSync(absolute);
      const local = path.relative(target, absolute).split(path.sep).join('/');
      const repoPath = path.relative(root, absolute).split(path.sep).join('/');
      if (stat.isSymbolicLink()) reason = 'symlink inside cache';
      else if (stat.isDirectory()) walk(absolute);
      else if (!stat.isFile() || !allowedFile(kind, local)) reason = 'unexpected contents';
      else if (tracked.has(repoPath)) reason = 'contains a Git-tracked file';
      else files.push({ absolute, size: stat.size, ino: stat.ino, mtimeMs: stat.mtimeMs });
    }
  }
  walk(target);
  return { path: relative, reason, files, directories, bytes: files.reduce((n, f) => n + f.size, 0) };
}

export function inspectCaches(root, tracked = new Set()) {
  const results = [];
  function scan(directory) {
    // A nested checkout or worktree is a separate project, even inside a scan root.
    if (fs.existsSync(path.join(directory, '.git'))) return;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.isSymbolicLink() || !entry.isDirectory() || SKIP.has(entry.name)) continue;
      const absolute = path.join(directory, entry.name);
      if (CACHE_NAMES.has(entry.name)) results.push(inspect(root, path.relative(root, absolute), tracked));
      else scan(absolute);
    }
  }
  for (const name of CACHE_NAMES) {
    const absolute = path.join(root, name);
    if (fs.existsSync(absolute)) results.push(inspect(root, name, tracked));
  }
  for (const name of SCAN_ROOTS) {
    const absolute = path.join(root, name);
    if (fs.existsSync(absolute) && !fs.lstatSync(absolute).isSymbolicLink()) scan(absolute);
  }
  return results.sort((a, b) => a.path.localeCompare(b.path));
}

export function cleanCaches(root, { apply = false, tracked = new Set() } = {}) {
  const results = inspectCaches(root, tracked);
  if (!apply) return results;
  for (const candidate of results) {
    if (candidate.reason) continue;
    const current = inspect(root, candidate.path, tracked);
    if (current.reason) { candidate.reason = current.reason; continue; }
    // Never recursively remove a directory: unexpected/new files must survive.
    for (const file of current.files) {
      const stat = fs.lstatSync(file.absolute);
      if (!stat.isFile() || stat.ino !== file.ino || stat.size !== file.size || stat.mtimeMs !== file.mtimeMs) {
        throw new Error(`Cache changed during cleanup: ${candidate.path}`);
      }
      fs.unlinkSync(file.absolute);
    }
    for (const directory of current.directories.reverse()) fs.rmdirSync(directory);
    candidate.removed = true;
  }
  return results;
}

export function main(args) {
  if (args.length > 1 || (args.length && args[0] !== '--apply')) {
    throw new Error('Usage: node scripts/maintenance/clean-caches.mjs [--apply]');
  }
  const tracked = new Set(execFileSync('git', ['ls-files', '-z'], {
    cwd: ROOT, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
  }).split('\0').filter(Boolean));
  const apply = args[0] === '--apply';
  const results = cleanCaches(ROOT, { apply, tracked });
  for (const result of results) {
    console.log(`${result.reason ? 'KEEP' : result.removed ? 'REMOVED' : 'WOULD REMOVE'} ${result.path}${result.reason ? ` (${result.reason})` : ` (${result.files.length} files, ${result.bytes} bytes)`}`);
  }
  console.log(`${apply ? 'Cleanup' : 'Dry run'}: ${results.filter(r => !r.reason).length} disposable caches; ${results.filter(r => r.reason).length} protected. tmp/, private/, dependencies and vendor state are never cleaned.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}

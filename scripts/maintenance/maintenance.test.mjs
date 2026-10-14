import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawnSync } from 'node:child_process';
import { cleanCaches } from './clean-caches.mjs';
import { ENTRY_POINTS, checkProject, releasePaths } from './project-check.mjs';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'space-maintenance-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const put = (name, content = 'fixture') => {
    fs.mkdirSync(path.dirname(path.join(root, name)), { recursive: true });
    fs.writeFileSync(path.join(root, name), content);
    return path.join(root, name);
  };
  return { root, put };
}

test('dry run never deletes and only apply removes known bytecode', t => {
  const { root, put } = fixture(t);
  const cached = put('services/demo/__pycache__/app.cpython-312.pyc');
  const source = put('services/demo/app.py');
  assert.equal(cleanCaches(root).length, 1);
  assert.ok(fs.existsSync(cached));
  assert.equal(cleanCaches(root, { apply: true })[0].removed, true);
  assert.ok(!fs.existsSync(cached));
  assert.ok(fs.existsSync(source));
  assert.deepEqual(cleanCaches(root, { apply: true }), []);
});

test('source-like or unrecognized contents protect the entire cache', t => {
  const { root, put } = fixture(t);
  const cached = put('tests/__pycache__/test.cpython-312.pyc');
  const source = put('tests/__pycache__/notes.txt');
  assert.equal(cleanCaches(root, { apply: true })[0].reason, 'unexpected contents');
  assert.ok(fs.existsSync(source) && fs.existsSync(cached));
});

test('tracked cache files protect the entire cache', t => {
  const { root, put } = fixture(t);
  const relative = 'libs/__pycache__/module.pyc';
  const cached = put(relative);
  assert.equal(cleanCaches(root, { apply: true, tracked: new Set([relative]) })[0].reason, 'contains a Git-tracked file');
  assert.ok(fs.existsSync(cached));
});

test('release snapshots, private data, dependencies and provider state are excluded', t => {
  const { root, put } = fixture(t);
  const dirs = ['tmp', 'private', 'output', 'node_modules', '.wrangler', '.vercel', '.railway',
    'services/demo/node_modules', 'services/demo/.venv', 'services/demo/private',
    'services/demo/build', 'experiments/demo/results'];
  const files = dirs.map(dir => put(`${dir}/__pycache__/important.pyc`));
  assert.deepEqual(cleanCaches(root, { apply: true }), []);
  for (const file of files) assert.ok(fs.existsSync(file));
});

test('a nested repository is not traversed', t => {
  const { root, put } = fixture(t);
  put('experiments/other/.git', 'gitdir: elsewhere');
  const cached = put('experiments/other/__pycache__/app.pyc');
  assert.deepEqual(cleanCaches(root, { apply: true }), []);
  assert.ok(fs.existsSync(cached));
});

test('symlink scan roots and cache entries never lead to deletion', t => {
  const { root, put } = fixture(t);
  const original = put('private/source.pyc');
  fs.mkdirSync(path.join(root, 'tests/__pycache__'), { recursive: true });
  fs.symlinkSync(original, path.join(root, 'tests/__pycache__/source.pyc'));
  fs.symlinkSync(path.join(root, 'private'), path.join(root, 'services'));
  assert.equal(cleanCaches(root, { apply: true })[0].reason, 'symlink inside cache');
  assert.ok(fs.existsSync(original));
});

test('a root cache symlink is protected', t => {
  const { root, put } = fixture(t);
  const original = put('private/source.pyc');
  fs.symlinkSync(path.join(root, 'private'), path.join(root, '__pycache__'));
  assert.equal(cleanCaches(root, { apply: true })[0].reason, 'symlink or non-directory');
  assert.ok(fs.existsSync(original));
});

test('known pytest and Ruff files can be regenerated', t => {
  const { root, put } = fixture(t);
  put('.pytest_cache/v/cache/nodeids', '[]');
  put('.pytest_cache/README.md');
  put('.ruff_cache/0.15.4/12345');
  put('.ruff_cache/CACHEDIR.TAG');
  assert.equal(cleanCaches(root, { apply: true }).filter(r => r.removed).length, 2);
});

test('unknown pytest files and Ruff directory layouts are retained', t => {
  const { root, put } = fixture(t);
  put('.pytest_cache/user-notes.md');
  put('.ruff_cache/customer/info.json');
  assert.equal(cleanCaches(root, { apply: true }).filter(r => r.reason).length, 2);
});

test('unknown cleanup arguments are rejected', () => {
  const result = spawnSync(process.execPath, ['scripts/maintenance/clean-caches.mjs', '--all'], { cwd: ROOT, encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Usage:/);
});

test('release record provides bounded relative snapshot paths', () => {
  const text = fs.readFileSync(path.join(ROOT, 'marketing/RELEASE.md'), 'utf8');
  const paths = releasePaths(text);
  assert.equal(Object.keys(paths).length, 3);
  assert.throws(() => releasePaths(text.replace(paths.production, 'tmp/../../private')));
  assert.throws(() => releasePaths('missing release'));
});

test('missing project/release files report errors rather than being recreated', t => {
  const { root, put } = fixture(t);
  put('marketing/RELEASE.md', 'Current verified release directory: `tmp/current`\nImmediate rollback: complete `tmp/rollback`\nCandidate `tmp/candidate`');
  const result = checkProject(root);
  assert.ok(result.errors.some(e => e.includes('Missing entry point')));
  assert.ok(result.errors.some(e => e.includes('Missing production artifact')));
  assert.ok(!fs.existsSync(path.join(root, 'tmp')));
});

test('project guards report unexpected sitemap drift', t => {
  const { root, put } = fixture(t);
  for (const file of ENTRY_POINTS) put(file);
  put('marketing/RELEASE.md', 'Current verified release directory: `tmp/current`\nImmediate rollback: complete `tmp/rollback`\nCandidate `tmp/candidate`');
  for (const dir of ['current', 'rollback', 'candidate']) {
    for (const file of ['index.html', 'apply/index.html', 'robots.txt', '_headers', '_redirects']) put(`tmp/${dir}/${file}`);
    put(`tmp/${dir}/sitemap.xml`, `<urlset><url><loc>https://spacemusic.io/${dir === 'candidate' ? 'new/' : ''}</loc></url></urlset>`);
  }
  assert.equal(checkProject(root).errors.length, 1);
  assert.match(checkProject(root).errors[0], /Sitemap differs/);
});

test('new entry-point documentation has no broken local Markdown links', () => {
  const documents = [...ENTRY_POINTS.filter(p => !p.startsWith('marketing/') && !p.startsWith('services/') && !p.startsWith('experiments/')), 'scripts/README.md', 'experiments/README.md', 'services/catalog_review/README.md', 'services/catalog_review_ui/README.md', 'docs/maintenance/20260928-cleanup.md', 'folderstructure.md'];
  for (const file of new Set(documents)) {
    const text = fs.readFileSync(path.join(ROOT, file), 'utf8');
    for (const match of text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
      const target = match[1];
      if (/^(https?:|mailto:|#)/.test(target)) continue;
      assert.ok(fs.existsSync(path.resolve(ROOT, path.dirname(file), target.split('#')[0])), `${file} -> ${target}`);
    }
  }
});

test('private/vendor state is ignored while current source and snapshots stay visible', () => {
  const ignored = ['private/example.csv', '.wrangler/state/example', '.vercel/project.json', '.railway/state.json', 'marketing/example/.dev.vars'];
  const source = ['services/catalog_review/dealflow.py', 'marketing/RELEASE.md', 'tmp/editorial-preview-v5-20260916/index.html', 'docs/PROJECT-MAP.md'];
  const result = execFileSync('git', ['check-ignore', '--no-index', '--stdin'], {
    cwd: ROOT, encoding: 'utf8', input: [...ignored, ...source].join('\n') + '\n',
  }).trim().split('\n');
  assert.deepEqual(result, ignored);
});

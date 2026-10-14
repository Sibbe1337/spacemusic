// Builds the authenticity release: reviewed text edits applied to the current
// production artifact. Everything not edited is copied byte for byte.
import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {SOURCE, loadSite, loadEdits, applyToModules, applyToHtml, rerender, loadInjects, injectRendered, loadDocs, applyFileEdit} from './authentic-support.mjs';
import {serve, playwrightModule} from './funnel-support.mjs';

const [output, manifestPath] = process.argv.slice(2);
assert(output && manifestPath, 'Usage: FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(SOURCE)), 'Keep production immutable');
const release = await readFile('marketing/RELEASE.md', 'utf8');
assert(release.startsWith('# Current Marketing Release\n\nProduction: https://29e7801c.'), 'Rebase if production changed');
const hash = s => createHash('sha256').update(s).digest('hex');

const site = await loadSite();
const only = process.env.EDIT_FILES ? process.env.EDIT_FILES.split(',') : undefined;
const edits = await loadEdits(undefined, only);
const editFiles = [...new Set(edits.map(e => e.file))];
// Conflicts: the same text edited differently by two files.
const byFind = new Map();
for (const e of edits) {
  const prev = byFind.get(e.find);
  assert(!prev || prev.replace === e.replace, `Conflicting edits for "${e.find.slice(0, 60)}" in ${prev?.file} and ${e.file}`);
  byFind.set(e.find, e);
}
const unique = [...byFind.values()];
for (const a of unique) for (const b of unique)
  if (a !== b && b.find.includes(a.find)) console.warn(`WARN nested finds: "${a.find.slice(0, 40)}" (${a.file}) inside "${b.find.slice(0, 40)}" (${b.file})`);

const {stats, changed} = applyToModules(site, unique);
const missing = unique.filter((_, i) => stats[i].js === 0);
const modules = new Map(changed);
let growing = true;
while (growing) {
  growing = false;
  for (const n of site.active) if (!modules.has(n) && site.deps(n).some(d => modules.has(d))) { modules.set(n, site.codes.get(n)); growing = true; }
}
const revision = hash([...modules.keys()].sort().map(n => n + modules.get(n)).join('\n') + JSON.stringify(unique)).slice(0, 12);
const mapping = new Map([...modules.keys()].map(n => [n, `${n.split('-').slice(0, 2).join('-')}-authentic-${hash(n + revision).slice(0, 12)}.js`]));
const rewrite = text => { for (const [a, b] of mapping) text = text.replaceAll(a, b); return text; };

await mkdir(output); await cp(SOURCE, output, {recursive: true});
for (const [n, code] of modules) await writeFile(path.join(output, 'assets', mapping.get(n)), rewrite(code));
const htmlCounts = unique.map(() => 0);
const changedPages = [];
for (const f of site.htmlFiles) {
  const before = await readFile(path.join(SOURCE, f), 'utf8');
  const {html, counts} = applyToHtml(before, unique, f);
  counts.forEach((c, i) => { htmlCounts[i] += c; });
  const next = rewrite(html);
  if (next !== before) await writeFile(path.join(output, f), next);
  if (counts.some(Boolean)) changedPages.push(f);
}
const docs = await loadDocs(undefined, only);
for (const [dest, from] of Object.entries(docs.files)) await writeFile(path.join(output, dest), rewrite(await readFile(from, 'utf8')));
for (const fe of docs.fileEdits) await writeFile(path.join(output, fe.file), applyFileEdit(await readFile(path.join(output, fe.file), 'utf8'), fe));
for (const np of docs.newPages) {
  await mkdir(path.dirname(path.join(output, np.file)), {recursive: true});
  await writeFile(path.join(output, np.file), await readFile(path.join(output, np.template), 'utf8'));
}
if (docs.newPages.length) await rerender(output, docs.newPages.map(n => n.file), {serve, playwrightModule}, {head: true});
const rerenderPages = [...new Set(unique.flatMap(e => e.rerender ?? []))];
if (rerenderPages.length) await rerender(output, rerenderPages, {serve, playwrightModule});
const injected = {};
for (const inj of await loadInjects(undefined, only)) injected[inj.selector] = await injectRendered(output, site.htmlFiles.filter(f => !f.startsWith('apply/')), inj, {serve, playwrightModule});
const htmlOnlyMissing = unique.filter((_, i) => stats[i].js > 0 && htmlCounts[i] === 0);
const sourceHashes = {};
for (const f of site.inventory) sourceHashes[f] = hash(await readFile(path.join(SOURCE, f)));
await mkdir(path.dirname(manifestPath), {recursive: true});
await writeFile(manifestPath, JSON.stringify({source: SOURCE, output, revision, entry: mapping.get(site.entry), modules: [...mapping], changedModules: [...changed.keys()],
  edits: unique.length, editFiles, rerenderPages, injected, newFiles: Object.keys(docs.files), newPages: docs.newPages.map(n => n.file), fileEdits: docs.fileEdits.map(e => e.file), changedPages: [...new Set([...changedPages, ...rerenderPages, ...Object.values(injected).flat()])], missing: missing.map(e => `${e.file}#${e.index}`), notInHtml: htmlOnlyMissing.map(e => `${e.file}#${e.index}`),
  sourceHashes, sitemapUrls: 141, status: 'PREVIEW ONLY; no production promotion authorized'}, null, 2) + '\n');
console.log(JSON.stringify({output, revision, edits: unique.length, changedModules: changed.size, renamedModules: modules.size, changedPages: changedPages.length,
  missingInJs: missing.length, notInHtml: htmlOnlyMissing.length}, null, 2));

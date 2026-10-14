// Usage: node scripts/authentic-check.mjs [edit-file.json ...]
// Reports, for each edit, how often its `find` occurs in active JS literals and
// prerendered HTML of the production release. Every edit must match somewhere.
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {loadSite, loadEdits, applyToModules, applyToHtml} from './authentic-support.mjs';

const only = process.argv.slice(2).map(f => path.basename(f));
const site = await loadSite();
const edits = await loadEdits(undefined, only.length ? only : undefined);
const {stats} = applyToModules(site, edits);
const html = edits.map(() => ({n: 0, pages: new Set()}));
for (const f of site.htmlFiles) {
  const {counts} = applyToHtml(await readFile(path.join(site.source, f), 'utf8'), edits, f);
  counts.forEach((c, i) => { if (c) { html[i].n += c; html[i].pages.add(f); } });
}
let bad = 0;
edits.forEach((e, i) => {
  const ok = stats[i].js + html[i].n > 0;
  const warn = stats[i].js > 0 && html[i].n === 0 ? ' WARN: not in HTML (split by markup?)' : stats[i].js === 0 && html[i].n > 0 ? ' WARN: HTML only' : '';
  if (!ok) bad++;
  if (!ok || warn || process.env.VERBOSE) console.log(`${ok ? 'ok ' : 'MISSING'} ${e.file}#${e.index} js=${stats[i].js} html=${html[i].n}${warn} :: ${e.find.slice(0, 70)}`);
});
console.log(`${edits.length} edits, ${bad} missing`);
process.exitCode = bad ? 1 : 0;

// Idea 1: for every page, Jev picks the most useful next pages among the site's
// hub pages. Output: marketing/growth-20260930/next-steps.json ({path: [target, target]}).
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {JSDOM} from '../../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from '../../scripts/funnel-support.mjs';
import {ask, pool, USD_PER_MILLION_INPUT} from './jev.mjs';

const release = process.argv[2] || 'tmp/authentic-preview-v2-20260929';
export const TARGETS = JSON.parse(await readFile('marketing/growth-20260930/next-step-targets.json', 'utf8'));
const pages = (await files(release)).filter(f => f.endsWith('index.html') && !f.startsWith('apply/'));
const docs = [];
for (const f of pages) {
  const d = new JSDOM(await readFile(path.join(release, f), 'utf8')).window.document;
  const main = d.querySelector('main'); if (!main || !d.querySelector('footer')) continue;
  main.querySelectorAll('script,style').forEach(n => n.remove());
  docs.push({path: '/' + f.replace(/index\.html$/, ''), title: d.title, text: main.textContent.replace(/\s+/g, ' ').trim().slice(0, 900)});
}
const criteria = Object.fromEntries(Object.entries(TARGETS).map(([p, t]) => [p, `${t.label}: ${t.description}`]));
let tokens = 0;
const out = {};
const FUNNEL = ['/calculator/', '/guides/music-catalog-valuation-2026/', '/how-it-works/', '/compare/partial-sale-vs-full-sale/', '/guides/how-long-does-it-take-to-sell-a-music-catalog/'];
const funnelCriteria = Object.fromEntries(FUNNEL.map(p => [p, criteria[p]]));
await pool(docs, 6, async doc => {
  const r = await ask({page: doc}, {
    topical: {type: 'choice', criteria,
      instructions: 'A visitor has just read `page` on spacemusic.io. Which page goes deeper into the same subject the visitor came for, so it is the most natural thing to read next? Never the page they are already on.'},
    funnel: {type: 'choice', criteria: funnelCriteria,
      instructions: 'A visitor has just read `page` on spacemusic.io (SPACE buys music catalogs directly). If this visitor owns music and wants to find out what selling would mean for them, which page is the most helpful next step from where they are now?'},
  });
  tokens += r.usage?.input_tokens || 0;
  const rank = a => Object.entries(a.probabilities).filter(([p]) => p !== doc.path).sort((x, y) => y[1] - x[1]);
  const f = rank(r.answers.funnel)[0];
  const t = rank(r.answers.topical).find(([p]) => p !== f[0]);
  out[doc.path] = [{path: t[0], p: +t[1].toFixed(2), kind: 'topical'}, {path: f[0], p: +f[1].toFixed(2), kind: 'funnel'}];
});
const sorted = Object.fromEntries(Object.entries(out).sort());
await writeFile('marketing/growth-20260930/next-steps.json', JSON.stringify({release, model: 'jev', inputTokens: tokens, estUsd: +(tokens * USD_PER_MILLION_INPUT / 1e6).toFixed(4), pages: sorted}, null, 1));
const count = {}; for (const v of Object.values(out)) for (const t of v) count[t.path] = (count[t.path] || 0) + 1;
console.log(`${docs.length} pages; target usage:`, count, 'tokens', tokens);

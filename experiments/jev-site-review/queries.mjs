// Idea 2: classify each Search Console query by intent and pick the page on the
// site that should answer it, or "none" (a content gap). Aggregated, non-personal
// search queries only.
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {JSDOM} from '../../services/seller_ui/node_modules/jsdom/lib/api.js';
import {ask, pool, USD_PER_MILLION_INPUT} from './jev.mjs';

const release = process.argv[2] || 'tmp/motion-preview-v3-20260929';
const csvPath = process.argv[3] || 'experiments/jev-site-review/input/gsc-queries-2026-09-22.csv';
const sitemap = await readFile(path.join(release, 'sitemap.xml'), 'utf8');
const urls = [...sitemap.matchAll(/<loc>https:\/\/spacemusic\.io(\/[^<]*)<\/loc>/g)].map(m => m[1]);
const pages = {};
for (const u of urls) {
  const file = path.join(release, u.endsWith('/') ? u + 'index.html' : u);
  const html = await readFile(file, 'utf8').catch(() => null);
  if (!html) continue;
  const d = new JSDOM(html).window.document;
  pages[u] = `${d.title} — ${d.querySelector('meta[name=description]')?.content ?? ''}`.slice(0, 260);
}

function parseCsv(text) {
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true; else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; } else if (c !== '\r') cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
const [, ...rows] = parseCsv((await readFile(csvPath, 'utf8')).replace(/^﻿/, ''));
const queries = rows.filter(r => r[0]).map(([query, clicks, impressions, ctr, position]) => ({query, clicks: +clicks, impressions: +impressions, ctr, position: +position}));

const INTENT = {
  seller: 'Someone who owns music or a catalog and wants to know its value or how to sell or license it',
  artist_earnings: 'A creator asking what streams, platforms or royalties pay, or how royalties and registrations work',
  industry_research: 'Market research: valuation multiples, deal sizes, catalog market trends, or facts about music companies',
  buyer_investor: 'Someone who wants to buy music catalogs or invest in royalties',
  brand: 'Looking for SPACE or spacemusic.io specifically',
  off_topic: 'Not about music rights, royalties or the music business',
};
const pageCriteria = Object.fromEntries([...Object.keys(pages).map(p => [p, null]), ['none', 'No page listed in `pages` would satisfy this search well']]);
const BATCH = 8;
const batches = [];
for (let i = 0; i < queries.length; i += BATCH) batches.push(queries.slice(i, i + BATCH));
let inputTokens = 0;
const results = (await pool(batches, 4, async batch => {
  const state = {site: 'spacemusic.io: SPACE, a direct buyer of royalty-generating music catalogs', pages, queries: batch.map(q => q.query)};
  const questions = {};
  batch.forEach((_, i) => {
    questions[`${i}_intent`] = {type: 'choice', instructions: `What does the person searching \`queries[${i}]\` on Google most likely want?`, criteria: INTENT};
    questions[`${i}_page`] = {type: 'choice', instructions: `Which page in \`pages\` (keyed by path, value is title and description) would best satisfy the person searching \`queries[${i}]\`? Choose none if no page would satisfy it well.`, criteria: pageCriteria};
  });
  const r = await ask(state, questions);
  inputTokens += r.usage?.input_tokens || 0;
  return batch.map((q, i) => {
    const intent = r.answers[`${i}_intent`], page = r.answers[`${i}_page`];
    return {...q, intent: intent.choice, intent_conf: +intent.confidence.toFixed(2), page: page.choice, page_conf: +page.confidence.toFixed(2), p_none: +(page.probabilities.none ?? 0).toFixed(2), model: r.model};
  });
})).flat();

const out = 'experiments/jev-site-review/output'; await mkdir(out, {recursive: true});
await writeFile(`${out}/queries-all.json`, JSON.stringify({release, pages: Object.keys(pages).length, inputTokens, estUsd: +(inputTokens * USD_PER_MILLION_INPUT / 1e6).toFixed(4), results}, null, 1));
const esc = s => `"${String(s).replace(/"/g, '""')}"`;
await writeFile(`${out}/queries.csv`, ['query,impressions,clicks,position,intent,intent_conf,page,page_conf,p_none',
  ...results.sort((a, b) => b.impressions - a.impressions).map(r => [esc(r.query), r.impressions, r.clicks, r.position, r.intent, r.intent_conf, r.page, r.page_conf, r.p_none].join(','))].join('\n') + '\n');
console.log(JSON.stringify({queries: results.length, pages: Object.keys(pages).length, inputTokens, model: results[0]?.model}, null, 1));

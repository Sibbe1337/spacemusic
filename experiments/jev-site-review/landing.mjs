// Landing-page review for the top organic entry pages (Plausible + Search Console):
// 1) does the first screen answer the queries people arrive with,
// 2) which honest title/description candidate would earn the most clicks,
// 3) does each candidate truthfully describe the page.
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {ask, pool, USD_PER_MILLION_INPUT} from './jev.mjs';

const release = 'tmp/motion-preview-v3-20260929';
const Q = JSON.parse(await readFile('experiments/jev-site-review/output/queries-all.json', 'utf8')).results;
const text = async p => {
  const html = await readFile(path.join(release, p, 'index.html'), 'utf8');
  const main = html.split('<main').slice(1).join('<main').replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/g, '');
  return main.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
};
const PAGES = {
  'guides/music-catalog-valuation-2026': [
    ['Music Catalog Valuation: Method, Example & Review — SPACE', 'Understand music catalog valuation, calculate a hypothetical sale from net income, and prepare the documents for an individual catalog review.'],
    ['How Much Is a Music Catalog Worth? Valuation Guide 2026 — SPACE', 'How catalog value is set: net income, the rights sold, risk and the multiple a buyer assumes. A worked example, then a free individual review.'],
    ['Music Catalog Valuation 2026: Multiples, Method and a Worked Example', 'What a valuation multiple means, what moves it up or down, and how to calculate a hypothetical sale from your own net income.'],
    ['Music Catalog Valuation Multiples 2026: How Catalogs Are Priced', 'Why catalogs are priced as a multiple of annual net income, what raises or lowers that multiple, and how to model your own catalog.'],
    ['How to Value a Music Catalog (2026): Step-by-Step Guide — SPACE', 'Value a music catalog in four steps: document net income, define the rights sold, assess risk, and test an assumed multiple.'],
  ],
  'calculator': [
    ['Music Catalog Value Calculator: Build a Sale Scenario — SPACE', 'Calculate a hypothetical catalog sale from monthly net income, your assumed multiple and the share sold. Request a free individual catalog review.'],
    ['Music Catalog Value Calculator (Free): What Could Your Catalog Sell For?', 'Enter monthly net royalties, an assumed multiple and the share you would sell to see a hypothetical sale value. Then request a free review.'],
    ['How Much Is My Music Catalog Worth? Free Calculator — SPACE', 'A free calculator for a hypothetical catalog sale based on your net royalties. No sign-up. Request an individual review when you want a real offer.'],
    ['Free Music Catalog Calculator: Estimate a Sale From Your Royalties', 'Turn your monthly net royalties into a hypothetical sale value for 50%, 75% or 100% of your catalog. Free, instant, no obligation.'],
  ],
  'streaming-rates/deezer-2026': [
    ['Deezer Pay Per Stream (2026) — Estimate Royalties and Offer Range — SPACE', ''],
    ['How Much Does Deezer Pay Per Stream in 2026? — SPACE', "How Deezer's artist-centric model calculates payouts, why there is no fixed per-stream rate, and how to estimate from your own statements."],
    ['Deezer Pay Per Stream 2026: How Payouts Are Calculated', "Deezer does not publish a fixed rate per stream. How its artist-centric model works and how to estimate your royalties from real statements."],
  ],
  'compare/major-label-vs-independent': [
    ['Major Label vs. Independent: The Right Path for Ambient Music Creators — SPACE', ''],
    ['Major Label vs Independent Label: Key Differences for Artists — SPACE', 'Ownership, royalties, advances and creative control compared, with what each path means for your catalog later.'],
    ['Independent Label vs Major Label: Ownership, Royalties and Control', 'How major and independent labels differ on ownership, royalty share, advances and control, and what that means for your catalog.'],
  ],
};
const LIKELY = {
  very_unlikely: 'Would almost certainly scroll past: the result does not match what they searched for',
  unlikely: 'Probably would not click: partly related but misses the main thing they want',
  maybe: 'Might click: relevant but not clearly the answer they want',
  likely: 'Would probably click: clearly addresses what they searched for',
  very_likely: 'Would almost certainly click: looks like exactly the answer they want',
};
const W = {very_unlikely: 0, unlikely: 1, maybe: 2, likely: 3, very_likely: 4};
let tokens = 0;
const report = [];
for (const [p, cands] of Object.entries(PAGES)) {
  const qs = Q.filter(q => q.page === '/' + p + '/' && q.intent !== 'off_topic').sort((a, b) => b.impressions - a.impressions).slice(0, 12);
  const body = await text(p);
  const firstScreen = body.slice(0, 900), full = body.slice(0, 6000);
  const questions = {};
  qs.forEach((q, i) => { questions[`fit_${i}`] = {type: 'noul', instructions: `Someone searched Google for \`queries[${i}]\` and landed on this page. \`first_screen\` is what they see before scrolling. Does the first screen directly answer what they searched for, so they would keep reading?`, criteria: {true: 'The first screen answers or clearly promises the specific thing searched for', false: 'The first screen is about something related but does not answer the search'}}; });
  cands.forEach((c, j) => {
    questions[`true_${j}`] = {type: 'noul', instructions: `Does the search result \`candidates[${j}]\` (title and description) accurately describe \`page_text\`, without promising anything the page does not contain (for example a table of market multiples, a fixed per-stream rate, or an offer)?`};
    qs.forEach((q, i) => { questions[`ctr_${j}_${i}`] = {type: 'choice', instructions: `On a Google results page, someone who searched \`queries[${i}]\` sees the result \`candidates[${j}]\`. How likely are they to click it?`, criteria: LIKELY}; });
  });
  const state = {queries: qs.map(q => q.query), first_screen: firstScreen, page_text: full, candidates: cands.map(([title, description]) => ({title, description: description || '(no description; Google picks a snippet)'}))};
  const r = await ask(state, questions);
  tokens += r.usage?.input_tokens || 0;
  const imp = qs.reduce((s, q) => s + q.impressions, 0) || 1;
  const fit = qs.map((q, i) => ({query: q.query, impressions: q.impressions, answered: +r.answers[`fit_${i}`].noul.toFixed(2)}));
  const scored = cands.map(([title, description], j) => {
    const ev = qs.reduce((s, q, i) => s + q.impressions * Object.entries(r.answers[`ctr_${j}_${i}`].probabilities).reduce((a, [k, v]) => a + W[k] * v, 0), 0) / imp;
    return {title, description, clickScore: +ev.toFixed(2), truthful: +r.answers[`true_${j}`].noul.toFixed(2)};
  });
  report.push({page: '/' + p + '/', queries: qs.length, impressions: imp, firstScreenAnswerRate: +(fit.reduce((s, f) => s + f.answered * f.impressions, 0) / imp).toFixed(2), fit, candidates: scored.sort((a, b) => b.clickScore - a.clickScore)});
}
await writeFile('experiments/jev-site-review/output/landing.json', JSON.stringify({model: 'jev', inputTokens: tokens, estUsd: +(tokens * USD_PER_MILLION_INPUT / 1e6).toFixed(4), report}, null, 1));
for (const r of report) {
  console.log(`\n${r.page}  queries=${r.queries} impressions=${r.impressions} first-screen answer rate=${r.firstScreenAnswerRate}`);
  r.fit.filter(f => f.answered < .5).slice(0, 5).forEach(f => console.log(`   not answered: ${f.query} (${f.impressions}) ${f.answered}`));
  r.candidates.forEach(c => console.log(`   ${c.clickScore}  truthful=${c.truthful}  ${c.title}`));
}
console.log('\ntokens', tokens);

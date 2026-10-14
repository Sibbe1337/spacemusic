// Idea 6: can an AI answer engine quote this page? Jev judges whether the opening
// of each page answers its main question (H1) in a self-contained, quotable sentence.
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {JSDOM} from '../../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from '../../scripts/funnel-support.mjs';
import {ask, pool, USD_PER_MILLION_INPUT} from './jev.mjs';

const release = process.argv[2];
const pages = (await files(release)).filter(f => f.endsWith('index.html') && !f.startsWith('apply/'));
const docs = [];
for (const f of pages) {
  const d = new JSDOM(await readFile(path.join(release, f), 'utf8')).window.document;
  const main = d.querySelector('main'); const h1 = d.querySelector('h1');
  if (!main || !h1) continue;
  main.querySelectorAll('script,style,nav').forEach(n => n.remove());
  const paras = [...main.querySelectorAll('p')].map(p => p.textContent.replace(/\s+/g, ' ').trim()).filter(t => t.length > 60).slice(0, 2);
  docs.push({path: '/' + f.replace(/index\.html$/, ''), title: d.title, h1: h1.textContent.trim(), opening: paras.join(' ')});
}
let tokens = 0;
const results = await pool(docs, 6, async doc => {
  const r = await ask({page: {title: doc.title, heading: doc.h1, opening: doc.opening}}, {
    answers: {type: 'noul', instructions: 'An AI assistant is asked the question behind `page.heading`. Does `page.opening` contain one self-contained sentence that directly answers it, so the assistant could quote that sentence on its own without the rest of the page?',
      criteria: {true: 'A quotable sentence in the opening directly answers the heading', false: 'The opening introduces, sells or describes the page without directly answering'}},
    specific: {type: 'choice', instructions: 'How specific and factual is the answer in `page.opening` to the question behind `page.heading`?',
      criteria: {vague: 'Generic or promotional, no concrete facts', some: 'Some concrete facts but hedged or incomplete', specific: 'Concrete, factual and complete enough to cite'}},
  });
  tokens += r.usage?.input_tokens || 0;
  return {...doc, answers: +r.answers.answers.noul.toFixed(2), specific: r.answers.specific.choice};
});
await writeFile('marketing/growth-20260930/ai-answers.json', JSON.stringify({release, inputTokens: tokens, estUsd: +(tokens * USD_PER_MILLION_INPUT / 1e6).toFixed(4), results}, null, 1));
const fail = results.filter(r => r.answers < 0.5);
console.log(`${results.length} pages; ${fail.length} without a quotable answer in the opening; tokens ${tokens}`);

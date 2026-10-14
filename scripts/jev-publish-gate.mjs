// Publish gate: every sentence that is new compared with the production release is
// checked by Jev for invented promises, unsourced figures, policy conflicts and
// invented credentials. Fails unless each flagged sentence is fixed or allowlisted.
// Usage: node scripts/jev-publish-gate.mjs CANDIDATE_DIR [PRODUCTION_DIR]
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {extractSentences, checkSentences, maxScore} from '../experiments/jev-site-review/claims-lib.mjs';

const [candidate, base] = process.argv.slice(2);
if (!candidate) { console.error('Usage: node scripts/jev-publish-gate.mjs CANDIDATE_DIR [PRODUCTION_DIR]'); process.exit(2); }
const release = await readFile('marketing/RELEASE.md', 'utf8');
const production = base || release.match(/Current verified release directory: `([^`]+)`/)[1];
const THRESHOLD = Number(process.env.GATE_THRESHOLD || 0.5);
const allowPath = 'marketing/jev-gate-allowlist.json';
const allow = new Map(JSON.parse(await readFile(allowPath, 'utf8').catch(() => '{"items":[]}')).items.map(x => [x.text, x.reason]));
const [cand, prod] = await Promise.all([extractSentences(candidate), extractSentences(production)]);
const fresh = [...cand.sentences.values()].filter(s => !prod.sentences.has(s.text));
const policy = await readFile(path.join(candidate, 'pricing.md'), 'utf8');
const {results, inputTokens} = fresh.length ? await checkSentences(fresh, policy) : {results: [], inputTokens: 0};
const flagged = results.filter(r => maxScore(r) >= THRESHOLD);
const blocking = flagged.filter(r => !allow.has(r.text));
const report = {candidate, production, newSentences: fresh.length, flagged: flagged.length, allowlisted: flagged.length - blocking.length, blocking, inputTokens, threshold: THRESHOLD};
await writeFile(path.join(candidate, '..', path.basename(candidate) + '-jev-gate.json'), JSON.stringify(report, null, 1));
console.log(`Jev gate: ${fresh.length} new sentences, ${flagged.length} flagged, ${blocking.length} blocking (threshold ${THRESHOLD}).`);
for (const r of blocking) console.log(`  BLOCK ${maxScore(r).toFixed(2)} ${r.urls[0]} :: ${r.text.slice(0, 160)}`);
if (blocking.length) console.log(`Fix the text, or add {"text": ..., "reason": ...} to ${allowPath} after a human review.`);
process.exitCode = blocking.length ? 1 : 0;

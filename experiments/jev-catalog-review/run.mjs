import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { CORPUS_SHA256, loadCorpus } from './corpus.mjs';
import { EXPERIMENT, JEV_INPUT_USD_PER_MILLION, PROMPT_VERSION, evaluate, summarize } from './core.mjs';
import { createRunner, providerModels } from './providers.mjs';
import { readJevKey, validKey } from './secrets.mjs';

export function parseOptions(args) {
  const options = { provider: 'rules', liveSynthetic: false, repeats: 1 };
  const seen = new Set();
  for (let index = 0; index < args.length; index++) {
    const flag = args[index];
    if (seen.has(flag)) throw new Error('invalid_arguments');
    seen.add(flag);
    if (flag === '--live-synthetic') options.liveSynthetic = true;
    else if (flag === '--provider') options.provider = args[++index];
    else if (flag === '--repeats') {
      const value = args[++index];
      if (!/^[1-3]$/.test(value ?? '')) throw new Error('invalid_arguments');
      options.repeats = Number(value);
    } else throw new Error('invalid_arguments');
  }
  if (!['rules', 'jev', 'llm', 'all'].includes(options.provider)) throw new Error('invalid_arguments');
  // Each remote call is an explicit opt-in. No .env files or project secrets are read.
  if (['jev', 'llm'].includes(options.provider) && !options.liveSynthetic) throw new Error('live_flag_required');
  if (options.provider === 'all' && options.repeats > 1) throw new Error('all_supports_one_repeat_use_separate_provider_runs');
  return options;
}

export function reportMarkdown(report) {
  const lines = [
    '# SPACE: synthetic Jev evaluation', '',
    `Run: ${report.run_id}`, `Started (UTC): ${report.started_at}`, `Status: ${report.status}`, '',
    '**Synthetic development examples only. Not a customer-data or production approval.**', '',
    'Reference answers were authored with this experiment, not independently reviewed. No held-out accuracy claim.',
    'Rules are a deliberately simple lexical baseline. Jev and the LLM are not simulated; unavailable runs remain unmeasured.', '',
    '| Provider | Repeat | Completed | Correct decisions (failures included) | Success-only p50 / p95 ms | Estimated API cost USD |',
    '| --- | --- | --- | --- | --- | --- |',
  ];
  for (const run of report.runs) {
    const s = run.summary;
    lines.push(`| ${run.provider} (${run.status}) | ${run.repeat} | ${s.completed}/${s.cases} | ${s.decisions_correct}/${s.decisions_total} | ${s.latency_ms.p50?.toFixed(2) ?? 'n/a'} / ${s.latency_ms.p95?.toFixed(2) ?? 'n/a'} | ${run.estimated_api_cost_usd?.toFixed(6) ?? 'unknown'} |`);
  }
  lines.push('', '## Availability', '');
  for (const [provider, status] of Object.entries(report.availability)) lines.push(`- ${provider}: ${status}`);
  lines.push('', '## Findings', '');
  for (const run of report.runs) {
    lines.push(`### ${run.provider}, repeat ${run.repeat}`, '',
      `- Missing draft checklist questions: ${run.summary.completion_questions_missing}. Extra questions: ${run.summary.completion_questions_extra}. Evaluated against ${run.summary.completion_questions_evaluated_against} reference questions in completed cases.`,
      `- Field counts: ${Object.entries(run.summary.by_field).map(([k, v]) => `${k} ${v.correct}/${v.total}`).join('; ')}.`,
      `- Language counts: ${Object.entries(run.summary.by_language).map(([k, v]) => `${k} ${v.correct}/${v.total}`).join('; ')}.`,
      `- All-attempt latency p50/p95: ${run.summary.all_attempt_latency_ms.p50?.toFixed(2) ?? 'n/a'} / ${run.summary.all_attempt_latency_ms.p95?.toFixed(2) ?? 'n/a'} ms; includes failed requests.`,
      `- High-confidence errors (Jev only, diagnostic threshold 0.9): ${run.provider === 'jev' ? run.summary.high_confidence_errors : 'not applicable'}.`,
      '- All source documents are retained by deterministic code, including adverse terms. This is not evidence that the model detected every risk.', '');
    for (const row of run.rows) {
      if (row.status === 'error') lines.push(`- ${row.case_id}: ${row.error}. No automatic retry; cost may be unknown.`);
      else if (row.evaluation.mismatches.length) lines.push(`- ${row.case_id}: differing fields ${row.evaluation.mismatches.join(', ')}.`);
    }
    lines.push('');
  }
  lines.push('## Limits and next gates', '',
    '- No ownership verification, valuation, financial calculation, customer rejection, message dispatch or buyer sharing.',
    '- Jev confidence is not a measured probability of correctness on SPACE data. All outputs need human review, even above the diagnostic 0.9 threshold.',
    '- Checklist comparison measures consequences of document/intent classification, not legal or financial completeness.',
    '- API latency excludes ingestion, PDF/OCR, storage, human review and downstream report writing. Human time saved is unmeasured.',
    '- Only Jev has a recorded price basis: USD 0.042 per million input tokens, vendor documentation checked 2026-09-24; output free. Estimates are not invoices. Failed calls may cost extra.',
    '- LLM token usage is recorded, but its cost is unknown until the applicable account pricing is verified. Rules have zero API fees, not zero operating cost.',
    '- Document ranking/filtering and buyer matching are deferred. This experiment only tests intake/document classification and draft follow-up checklists.',
    '- Obtain independent reference labels, broader held-out multilingual examples, provider terms/residency/retention approval and a separate production decision before any real-data integration.',
    '- No API key, raw provider response or customer data is stored in this report.', '',
    '## Sources', '',
    '- https://docs.typesafe.ai/api', '- https://docs.typesafe.ai/models',
    '- https://docs.typesafe.ai/model-jaggedness/jev-1.13',
    '- https://typesafe.ai/legal/privacy-policy', '- https://typesafe.ai/legal/data-processing',
    '- https://developers.openai.com/api/docs/guides/structured-outputs', '',
    `Corpus SHA-256: ${report.corpus_sha256}`, `Prompt version: ${report.prompt_version}`, '');
  return lines.join('\n');
}

export async function main(args = process.argv.slice(2)) {
  const options = parseOptions(args);
  const corpus = loadCorpus();
  const keys = {}, availability = { rules: 'local_available', jev: 'not_enabled', llm: 'not_enabled' };
  const selected = options.provider === 'all' ? ['rules', 'jev', 'llm'] : [options.provider];
  for (const provider of selected.filter(p => p !== 'rules')) {
    if (!options.liveSynthetic) continue;
    try {
      keys[provider] = provider === 'jev' ? readJevKey() : process.env.OPENAI_API_KEY;
      if (!validKey(keys[provider])) throw new Error();
      availability[provider] = 'configured_not_yet_verified';
    } catch { delete keys[provider]; availability[provider] = 'key_missing_or_unsafe'; }
  }
  if (options.provider !== 'all' && options.provider !== 'rules' && !keys[options.provider]) {
    throw new Error('key_missing_or_unsafe');
  }
  const report = {
    experiment: EXPERIMENT, run_id: randomUUID(), started_at: new Date().toISOString(),
    status: 'running', synthetic: true, corpus_sha256: CORPUS_SHA256,
    prompt_version: PROMPT_VERSION, runtime: process.version, options, availability, runs: [],
  };
  const directory = fileURLToPath(new URL(`./results/${report.run_id}/`, import.meta.url));
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  function save() {
    for (const [name, content] of [['results.json', JSON.stringify(report, null, 2)], ['REPORT.md', reportMarkdown(report)]]) {
      const temporary = join(directory, `${name}.tmp`);
      writeFileSync(temporary, content, { mode: 0o600 });
      renameSync(temporary, join(directory, name));
    }
  }
  const run = createRunner(corpus.cases, { liveSynthetic: options.liveSynthetic, keys });
  for (let repeat = 1; repeat <= options.repeats; repeat++) {
    const cohort = selected.filter(p => p === 'rules' || keys[p]).map(provider => ({
      provider, model: providerModels[provider], repeat, status: 'running', rows: [],
      estimated_api_cost_usd: provider === 'rules' ? 0 : null, summary: summarize([], corpus),
    }));
    report.runs.push(...cohort);
    save();
    // Interleave providers on the same case, reversing order on alternate cases.
    for (const [index, item] of corpus.cases.entries()) {
      for (const record of index % 2 ? [...cohort].reverse() : cohort) {
        if (record.status === 'stopped_after_error') continue;
        const result = await run(record.provider, item);
        const row = { case_id: item.id, ...result };
        if (row.status === 'ok') {
          row.evaluation = evaluate(item, row);
          availability[record.provider] = record.provider === 'rules' ? 'local_executed' : 'live_synthetic_executed';
        } else {
          record.status = 'stopped_after_error';
          availability[record.provider] = 'stopped_after_error';
        }
        record.rows.push(row);
        record.summary = summarize(record.rows, corpus);
        if (record.provider === 'jev') {
          record.estimated_api_cost_usd = record.summary.cost_may_be_incomplete ? null
            : record.summary.known_usage.input_tokens * JEV_INPUT_USD_PER_MILLION / 1_000_000;
        }
        save();
      }
    }
    for (const record of cohort) if (record.status === 'running') record.status = 'completed';
    // Do not repeat an uncertain or rejected remote run in a later round.
    if (cohort.some(r => r.status === 'stopped_after_error')) break;
  }
  report.status = report.runs.some(r => r.status === 'stopped_after_error') ? 'incomplete' : 'completed';
  report.completed_at = new Date().toISOString();
  save();
  console.log(`Synthetic evaluation report: ${join(directory, 'REPORT.md')}`);
  if (report.status === 'incomplete') process.exitCode = 1;
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    const safe = ['invalid_arguments', 'live_flag_required', 'all_supports_one_repeat_use_separate_provider_runs',
      'key_missing_or_unsafe', 'corpus_changed_review_required', 'invalid_corpus'];
    console.error(safe.includes(error.message) ? error.message : 'evaluation_failed');
    process.exitCode = 1;
  });
}

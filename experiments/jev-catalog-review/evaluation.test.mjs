import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadCorpus, CORPUS_SHA256 } from './corpus.mjs';
import { buildRequest, evaluate, JEV_MODEL, percentile, reviewDraft, rules, summarize, validateJev, validateLabels } from './core.mjs';
import { createRunner, LLM_MODEL, safeError } from './providers.mjs';
import { parseOptions, reportMarkdown } from './run.mjs';
import { readJevKey, validKey } from './secrets.mjs';

const corpus = loadCorpus();
const key = 'synthetic-key-not-a-real-credential';
const json = body => new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } });
function stubJev(request) {
  // This transport exercises parsing only; it is never used for benchmark results.
  return {
    model: JEV_MODEL,
    answers: Object.fromEntries(Object.entries(request.questions).map(([id, q]) => {
      const options = Object.keys(q.criteria);
      return [id, { type: 'choice', choice: options[0], confidence: 0.5,
        probabilities: Object.fromEntries(options.map((k, index) => [k, index === 0 ? 1 : 0])) }];
    })), usage: { input_tokens: 120, output_tokens: 25 },
  };
}

test('fixed synthetic corpus has 20 cases, 80 decisions, immutable labels', () => {
  assert.equal(corpus.cases.length, 20);
  assert.equal(summarize([], corpus).decisions_total, 80);
  assert.equal(CORPUS_SHA256.length, 64);
  assert.ok(Object.isFrozen(corpus.cases[0].documents));
  assert.throws(() => { corpus.cases[0].message = 'customer material'; });
});

test('provider requests contain no answer keys, critical annotations, language or case names', () => {
  for (const item of corpus.cases) {
    const request = buildRequest(item);
    assert.deepEqual(Object.keys(request.state).sort(), ['documents', 'message']);
    assert.equal(request.model, JEV_MODEL);
    assert.ok(!('expected' in request));
    assert.ok(!('critical_document_ids' in request.state));
    assert.ok(!('id' in request.state));
    assert.deepEqual(Object.keys(request.questions).sort(), Object.keys(item.expected).sort());
  }
});

test('long inputs are rejected, never truncated', () => {
  assert.throws(() => buildRequest({ ...corpus.cases[0], message: 'x'.repeat(30_000) }), /request_too_large/);
});

test('rules baseline is independent of labels and visibly imperfect', () => {
  let correct = 0;
  for (const item of corpus.cases) {
    const request = buildRequest(item);
    const result = rules(request);
    validateLabels(result.labels, request.questions);
    correct += evaluate(item, result).correct;
  }
  assert.equal(correct, 65);
});

test('all documents survive even hostile/misclassified critical evidence', () => {
  for (const item of corpus.cases) {
    const labels = Object.fromEntries(Object.keys(item.expected).map(k => [k, k.startsWith('document_') ? 'other' : 'unknown']));
    const result = evaluate(item, { labels, confidence: null });
    assert.equal(result.critical_documents_retained, true);
    assert.deepEqual(result.draft.retained_document_ids, item.documents.map(d => d.id));
    assert.equal(result.draft.financial_conclusions_allowed, false);
    assert.equal(result.draft.ownership_verified, false);
    assert.equal(result.draft.customer_messages_sent, false);
    assert.equal(result.draft.buyer_sharing_allowed, false);
  }
});

test('promise of statements and streams do not satisfy reference checklist', () => {
  for (const id of ['s15', 's17']) {
    const item = corpus.cases.find(c => c.id === id);
    assert.ok(reviewDraft(item, item.expected).questions.some(q => q.includes('supply royalty statements')));
  }
});

test('buyer and partnership requests do not become seller checklists', () => {
  for (const id of ['s07', 's08', 's19']) {
    const item = corpus.cases.find(c => c.id === id);
    assert.deepEqual(reviewDraft(item, item.expected).questions, []);
  }
});

test('unclear role or scope is a human clarification, never a rejection', () => {
  const item = corpus.cases.find(c => c.id === 's09');
  const draft = reviewDraft(item, item.expected);
  assert.equal(draft.status, 'draft_for_manual_review');
  assert.ok(draft.questions[0].includes('clarify'));
});

test('Jev response uses native probabilities and reported version', () => {
  const request = buildRequest(corpus.cases[0]);
  const result = validateJev(stubJev(request), request.questions);
  assert.equal(result.model, JEV_MODEL);
  assert.equal(result.confidence.role, 0.5);
});

test('unexpected upstream usage fields never reach the saved result', () => {
  const request = buildRequest(corpus.cases[0]);
  const body = stubJev(request);
  body.usage.debug = key;
  const result = validateJev(body, request.questions);
  assert.deepEqual(result.usage, { input_tokens: 120, output_tokens: 25 });
  assert.ok(!JSON.stringify(result).includes(key));
});

test('confident mistakes remain errors and never permit automatic action', () => {
  const item = corpus.cases[0];
  const result = evaluate(item, {
    labels: { ...item.expected, role: 'buyer' },
    confidence: Object.fromEntries(Object.keys(item.expected).map(k => [k, 1])),
  });
  assert.deepEqual(result.high_confidence_mismatches, ['role']);
  assert.equal(result.draft.buyer_sharing_allowed, false);
});

const mutations = {
  model: b => { b.model = 'jev-latest'; },
  missingAnswer: b => { delete b.answers.role; },
  extraAnswer: b => { b.answers.valuation = {}; },
  wrongType: b => { b.answers.role.type = 'noul'; },
  unknownLabel: b => { b.answers.role.choice = 'approve_payment'; },
  wrongWinner: b => { b.answers.role.choice = 'buyer'; },
  wrongSum: b => { b.answers.role.probabilities.seller = 0.8; },
  extraProbability: b => { b.answers.role.probabilities.extra = 0; },
  missingProbability: b => { delete b.answers.role.probabilities.buyer; },
  negative: b => { b.answers.role.probabilities.buyer = -0.1; },
  infinite: b => { b.answers.role.probabilities.buyer = Infinity; },
  nan: b => { b.answers.role.confidence = NaN; },
  boolean: b => { b.answers.role.confidence = true; },
  range: b => { b.answers.role.confidence = 1.01; },
  nullAnswer: b => { b.answers.role = null; },
  missingUsage: b => { delete b.usage; },
  negativeTokens: b => { b.usage.input_tokens = -1; },
  fractionalTokens: b => { b.usage.input_tokens = 1.5; },
};
for (const [name, mutate] of Object.entries(mutations)) {
  test(`reject malformed Jev response: ${name}`, () => {
    const request = buildRequest(corpus.cases[0]);
    const body = stubJev(request);
    mutate(body);
    assert.throws(() => validateJev(body, request.questions));
  });
}

test('default rules mode does not call network even with keys present', async () => {
  const run = createRunner(corpus.cases, { keys: { jev: key }, fetchImpl: () => assert.fail('network forbidden') });
  assert.equal((await run('rules', corpus.cases[0])).status, 'ok');
  assert.equal((await run('jev', corpus.cases[0])).error, 'live_not_enabled');
});

test('unrecognized providers and external cases cannot reach network', async () => {
  const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl: () => assert.fail('network forbidden') });
  assert.equal((await run('jev', { ...corpus.cases[0], message: 'not approved' })).error, 'unapproved_fixture');
  assert.equal((await run('https://untrusted.example', corpus.cases[0])).error, 'live_not_enabled');
});

test('mutation after runner construction is rejected', async () => {
  const item = structuredClone(corpus.cases[0]);
  const run = createRunner([item], { liveSynthetic: true, keys: { jev: key }, fetchImpl: () => assert.fail('network forbidden') });
  item.message = 'different content';
  assert.equal((await run('jev', item)).error, 'unapproved_fixture');
});

test('direct runner imports cannot approve arbitrary input even before construction', () => {
  assert.throws(() => createRunner([{ ...corpus.cases[0], message: 'Not in reviewed corpus' }], {
    liveSynthetic: true, keys: { jev: key }, fetchImpl: () => assert.fail('network forbidden'),
  }), /unapproved_fixture/);
});

test('Jev transport uses exact HTTPS origin, no redirects and bounded timeout', async () => {
  const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl: async (url, init) => {
    assert.equal(url, 'https://api.typesafe.ai/v1/systemone');
    assert.equal(init.redirect, 'error');
    assert.equal(init.method, 'POST');
    assert.ok(init.signal instanceof AbortSignal);
    assert.equal(init.headers.authorization, `Bearer ${key}`);
    return json(stubJev(JSON.parse(init.body)));
  } });
  const result = await run('jev', corpus.cases[0]);
  assert.equal(result.status, 'ok');
  assert.ok(!JSON.stringify(result).includes(key));
});

for (const status of [301, 401, 429, 500, 529]) {
  test(`HTTP ${status} is redacted and not automatically retried`, async () => {
    let calls = 0;
    const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl: async () => {
      calls++;
      return new Response(`secret=${key}`, { status });
    } });
    const result = await run('jev', corpus.cases[0]);
    assert.equal(result.error, `provider_http_${status}`);
    assert.equal(calls, 1);
    assert.ok(!JSON.stringify(result).includes(key));
  });
}

test('transport exceptions and malformed bodies never echo content', async () => {
  for (const fetchImpl of [async () => { throw new Error(key); }, async () => new Response(key, { headers: { 'content-type': 'application/json' } })]) {
    const result = await createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl })('jev', corpus.cases[0]);
    assert.equal(result.status, 'error');
    assert.ok(!JSON.stringify(result).includes(key));
  }
  assert.equal(safeError(new Error(key)), 'request_failed_or_invalid_response');
});

test('HTML and oversized responses fail closed', async () => {
  for (const [body, type, expected] of [['oops', 'text/html', 'invalid_response_type'], ['x'.repeat(256_001), 'application/json', 'response_too_large']]) {
    const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl: async () => new Response(body, { headers: { 'content-type': type } }) });
    assert.equal((await run('jev', corpus.cases[0])).error, expected);
  }
});

test('60-call ceiling is shared across providers', async () => {
  let calls = 0;
  const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { jev: key }, fetchImpl: async (_url, init) => {
    calls++;
    return json(stubJev(JSON.parse(init.body)));
  } });
  for (let index = 0; index < 60; index++) assert.equal((await run('jev', corpus.cases[0])).status, 'ok');
  assert.equal((await run('jev', corpus.cases[0])).error, 'call_limit');
  assert.equal(calls, 60);
});

test('LLM baseline has matching rubrics, strict output and no invented confidence', async () => {
  const item = corpus.cases[0];
  const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { llm: key }, fetchImpl: async (url, init) => {
    assert.equal(url, 'https://api.openai.com/v1/chat/completions');
    const body = JSON.parse(init.body);
    assert.equal(body.model, LLM_MODEL);
    assert.equal(body.store, false);
    assert.equal(body.temperature, 0);
    assert.equal(body.response_format.json_schema.strict, true);
    assert.deepEqual(JSON.parse(body.messages[1].content), buildRequest(item).state);
    return json({ model: LLM_MODEL, choices: [{ finish_reason: 'stop', message: { content: JSON.stringify(item.expected) } }], usage: { prompt_tokens: 200, completion_tokens: 30 } });
  } });
  const result = await run('llm', item);
  assert.equal(result.status, 'ok');
  assert.equal(result.confidence, null);
  assert.deepEqual(result.usage, { input_tokens: 200, output_tokens: 30 });
});

for (const mode of ['refusal', 'truncated', 'wrong_labels', 'wrong_model']) {
  test(`LLM ${mode} is not reported as a successful result`, async () => {
    const item = corpus.cases[0];
    const body = { model: LLM_MODEL, choices: [{ finish_reason: 'stop', message: { content: JSON.stringify(item.expected) } }], usage: { prompt_tokens: 1, completion_tokens: 1 } };
    if (mode === 'refusal') body.choices[0].message.refusal = 'No';
    if (mode === 'truncated') body.choices[0].finish_reason = 'length';
    if (mode === 'wrong_labels') body.choices[0].message.content = '{"role":"seller"}';
    if (mode === 'wrong_model') body.model = 'different-model';
    const run = createRunner(corpus.cases, { liveSynthetic: true, keys: { llm: key }, fetchImpl: async () => json(body) });
    assert.equal((await run('llm', item)).status, 'error');
  });
}

test('failed and unrun cases remain in accuracy denominator', () => {
  const item = corpus.cases[0];
  const result = { labels: item.expected, confidence: null };
  const rows = [{ case_id: item.id, status: 'ok', ...result, elapsed_ms: 10, evaluation: evaluate(item, result) },
    { case_id: corpus.cases[1].id, status: 'error', elapsed_ms: 15000 }];
  const summary = summarize(rows, corpus);
  assert.equal(summary.completed, 1);
  assert.equal(summary.failed_or_unrun, 19);
  assert.equal(summary.decisions_correct, 5);
  assert.equal(summary.decisions_total, 80);
  assert.equal(summary.cost_may_be_incomplete, true);
  assert.equal(summary.latency_ms.p95, 10);
  assert.equal(summary.all_attempt_latency_ms.p95, 15000);
  assert.equal(summary.elapsed_attempts_ms, 15010);
  assert.equal(summary.human_review_time_saved, null);
});

test('missing models are unmeasured, not synthetic success', () => {
  const report = { run_id: 'test', status: 'completed', started_at: 'test', runs: [], availability: { jev: 'key_missing_or_unsafe' } };
  assert.match(reportMarkdown(report), /jev: key_missing_or_unsafe/);
  assert.match(reportMarkdown(report), /not simulated/);
});

test('percentiles are nearest rank, empty means unknown', () => {
  assert.equal(percentile([], 0.95), null);
  assert.equal(percentile([4, 1, 3, 2], 0.5), 2);
  assert.equal(percentile([4, 1, 3, 2], 0.95), 4);
});

test('CLI rejects arbitrary file/URL inputs and requires live opt-in', () => {
  for (const args of [['--input', '/private'], ['--endpoint', 'https://example.com'], ['--provider', 'jev'], ['--repeats', '100'], ['--live-synthetic', '--live-synthetic'], ['--provider', 'all', '--repeats', '3']]) {
    assert.throws(() => parseOptions(args));
  }
  assert.equal(parseOptions([]).provider, 'rules');
  assert.equal(parseOptions(['--provider', 'jev', '--live-synthetic', '--repeats', '3']).repeats, 3);
});

test('keys are validated without exposing their value', () => {
  assert.equal(validKey(key), true);
  for (const invalid of ['short', 'x'.repeat(513), `${key}\n`, `${key} `, `Bearer ${key}`]) assert.equal(validKey(invalid), false);
  assert.equal(readJevKey({ TYPESAFE_API_KEY: key }), key);
  assert.throws(() => readJevKey({ TYPESAFE_API_KEY: `secret\n${key}` }), { message: 'invalid_key' });
});

test('private key files require owner-only modes and no symlink', () => {
  const home = mkdtempSync(join(tmpdir(), 'space-jev-key-test-'));
  const directory = join(home, 'Library', 'Application Support', 'SpaceMusic', 'jev-evaluation');
  const path = join(directory, 'typesafe-api-key');
  const script = `import {readJevKey} from ${JSON.stringify(new URL('./secrets.mjs', import.meta.url).href)}; try { readJevKey({}); process.stdout.write('ok'); } catch { process.stdout.write('rejected'); }`;
  const read = () => spawnSync(process.execPath, ['--input-type=module', '-e', script], { env: { HOME: home }, encoding: 'utf8' }).stdout;
  try {
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    assert.equal(read(), 'rejected');
    writeFileSync(path, key, { mode: 0o644 });
    assert.equal(read(), 'rejected');
    rmSync(path);
    writeFileSync(path, key, { mode: 0o600 });
    assert.equal(read(), 'ok');
    rmSync(path);
    const target = join(home, 'other');
    writeFileSync(target, key, { mode: 0o600 });
    symlinkSync(target, path);
    assert.equal(read(), 'rejected');
  } finally { rmSync(home, { recursive: true, force: true }); }
});

test('key configuration refuses redirected input before creating any file', () => {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('./secrets.mjs', import.meta.url))], { input: key, encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /terminal_required/);
  assert.ok(!result.stdout.includes(key));
  assert.ok(!result.stderr.includes(key));
});

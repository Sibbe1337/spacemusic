import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { createApp, validateWorkspace } from './app.mjs';
import { createClient } from './client.mjs';

const require = createRequire(new URL('../seller_ui/package.json', import.meta.url));
const { JSDOM } = require('jsdom');
const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
const productionHtml = await readFile(new URL('./index.production.html', import.meta.url), 'utf8');
const ID = index => `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
const TOKEN = `${ID(1)}.${ID(2)}.${'a'.repeat(43)}`;
const START = Date.parse('2026-09-18T10:00:00Z');
const clone = value => JSON.parse(JSON.stringify(value));
const json = (body = {}, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const draft = () => ({ source: 'documents', rights: [{ release_reference: ID(3), title: 'Synthetic release', artist: 'Test artist', ownership: 'unknown', share_percent: null, rights_scope: 'unknown', obligations: 'unknown' }], document_ids: [], future_music_excluded: true });
const workspace = (overrides = {}) => ({ workspace_id: ID(1), role: 'owner', revision: 0, draft: null, documents: [], submission: null, questions: [], review_status: 'not_submitted', session_expires_at: '2026-09-18T11:00:00Z', csrf: 'synthetic-csrf', capabilities: { document_upload: false, toolost: false }, ...overrides });
const question = (overrides = {}) => ({ question_id: ID(8), body: 'Please explain the synthetic rights.', created_at: '2026-09-18T10:00:00Z', reply: null, ...overrides });
const submitted = (value = draft(), documents = []) => ({ submission_id: ID(9), revision: 1, created_at: '2026-09-18T10:01:00Z', snapshot: { draft: value, documents, missing_evidence: documents.length === 0 } });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

function fixture(t, { hash = `#invitation=${TOKEN}`, timeoutMs = 1000, shell = html } = {}) {
  const dom = new JSDOM(shell, { url: `https://review.test/workspace/?discard=this${hash}`, runScripts: 'outside-only' });
  const win = dom.window;
  for (const storage of ['localStorage', 'sessionStorage', 'indexedDB']) Object.defineProperty(win, storage, { get() { throw Error('Browser storage is forbidden'); } });
  const queue = [];
  const calls = [];
  const unexpected = [];
  let currentTime = START;
  let sequence = 100;
  const timers = new Set();
  const client = createClient({ timeoutMs, fetchImpl: async (path, options) => {
    const call = { path, options, body: options.headers['Content-Type'] === 'application/json' ? JSON.parse(options.body) : options.body };
    calls.push(call);
    if (!queue.length) { unexpected.push(path); throw Error('Unexpected test request'); }
    const next = queue.shift();
    return typeof next === 'function' ? next(call) : next;
  } });
  const app = createApp({ window: win, client, now: () => currentTime, uuid: () => ID(sequence++),
    schedule: (fn, delay) => { const timer = { fn, at: currentTime + delay }; timers.add(timer); return timer; },
    unschedule: timer => timers.delete(timer),
  });
  t.after(() => { app.destroy(); win.close(); assert.deepEqual(unexpected, []); });
  const doc = win.document;
  const get = selector => { const element = doc.querySelector(selector); assert.ok(element, selector); return element; };
  const click = selector => get(selector).click();
  const set = (selector, value) => {
    const input = get(selector);
    input.value = value;
    input.dispatchEvent(new win.Event('input', { bubbles: true }));
  };
  const submit = selector => get(selector).dispatchEvent(new win.Event('submit', { bubbles: true, cancelable: true }));
  async function until(predicate) {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (predicate()) return;
      await new Promise(resolve => setTimeout(resolve, 2));
    }
    assert.fail('UI did not reach the expected state');
  }
  const idle = () => until(() => doc.querySelector('main').getAttribute('aria-busy') === 'false');
  async function open(view = workspace()) {
    queue.push(json({ csrf: 'exchange-csrf' }), json(view));
    click('[data-action=open]');
    await idle();
    assert.match(doc.querySelector('main').textContent, /workspace/i);
  }
  return { win, doc, get, click, set, submit, until, idle, open, queue, calls, timers,
    text: () => doc.body.textContent,
    advance(ms) { currentTime += ms; for (const timer of [...timers]) if (timer.at <= currentTime) { timers.delete(timer); timer.fn(); } },
    selectFile(file, selector = '#synthetic-file') {
      const input = get(selector);
      Object.defineProperty(input, 'files', { value: [file], configurable: true });
      input.dispatchEvent(new win.Event('input', { bubbles: true }));
    },
  };
}

test('invitation is scrubbed immediately and consumed only by explicit POST; initial draft is document-free', async t => {
  const f = fixture(t);
  assert.equal(f.win.location.href, 'https://review.test/workspace/');
  assert.equal(f.win.history.state, null);
  assert.equal(f.calls.length, 0);
  assert.ok(!f.doc.documentElement.outerHTML.includes(TOKEN));
  await f.open();
  assert.deepEqual(f.calls[0].body, { token: TOKEN });
  assert.equal(f.calls[0].options.method, 'POST');
  assert.equal(f.calls[1].options.method, 'GET');
  assert.equal(f.get('#title-0').value, '');
  assert.equal(f.get('#share-0').disabled, true);
  assert.equal(f.doc.querySelector('input[type=file]'), null);
  assert.equal(f.doc.querySelector('#upload-button'), null);
  f.set('#title-0', 'New synthetic title');
  f.set('#artist-0', 'Fictional artist');
  f.set('#ownership-0', 'known');
  f.set('#share-0', '50.25');
  f.set('#scope-0', 'masters');
  f.set('#obligations-0', 'none_declared');
  f.queue.push(call => {
    assert.equal(call.path, '/api/portal/draft');
    assert.equal(call.body.revision, 0);
    assert.equal(call.body.draft.source, 'documents');
    assert.deepEqual(call.body.draft.document_ids, []);
    assert.equal(call.body.draft.future_music_excluded, true);
    assert.match(call.body.draft.rights[0].release_reference, /^[a-f\d-]{36}$/);
    assert.equal(call.body.draft.rights[0].share_percent, '50.25');
    assert.equal(call.options.headers['X-CSRF-Token'], 'synthetic-csrf');
    f.queue.push(json(workspace({ revision: 1, draft: call.body.draft })));
    return json({ revision: 1 });
  });
  f.submit('#draft-form'); await f.idle();
  assert.match(f.text(), /Draft saved and refreshed/);
  assert.equal(f.calls.at(-1).path, '/api/portal/workspace');
});

const document = (index, questionId = null, status = 'accepted_for_review') => ({ document_id: ID(index), question_id: questionId, filename: `synthetic-${index}.csv`, status });
const supplementWorkspace = (overrides = {}) => workspace({ draft: draft(), submission: submitted(), review_status: 'needs_information',
  capabilities: { document_upload: true, toolost: false }, questions: [question({ request_documents: true }), question({ question_id: ID(18), request_documents: true })], ...overrides });
const replyForm = (index = 8) => `[data-question-form="reply"][data-question-id="${ID(index)}"]`;
const uploadForm = (index = 8) => `[data-question-upload="${ID(index)}"]`;
const fileInput = (index = 8) => `#question-file-${ID(index)}`;
const selection = (docIndex = 5, questionIndex = 8) => `[data-question-document="${ID(docIndex)}"][data-document-question="${ID(questionIndex)}"]`;
const publishedReply = (body, documents, version = 1) => ({ body, created_at: '2026-09-18T10:02:00Z', document_ids: documents.map(item => item.document_id),
  supplement: documents.length ? { supplement_id: ID(60 + version), version, submission_id: ID(9), documents, created_at: '2026-09-18T10:02:00Z' } : null });

test('deal preparation link requires an explicit server capability and a submitted case', async t => {
  for (const role of ['owner', 'reviewer']) {
    await t.test(role, async t => {
      const f = fixture(t);
      const current = supplementWorkspace({ role, capabilities: { document_upload: false, toolost: false, dealflow: true } });
      await f.open(current);
      assert.equal(f.get('a[href="/dealflow/"]').textContent, 'Open the deal workspace');
    });
  }
  for (const enabled of [undefined, false, 'true']) {
    await t.test(String(enabled), async t => {
      const f = fixture(t);
      await f.open(supplementWorkspace({ capabilities: { document_upload: false, toolost: false, dealflow: enabled } }));
      assert.equal(f.doc.querySelector('a[href="/dealflow/"]'), null);
    });
  }
  await t.test('unsubmitted', async t => {
    const f = fixture(t);
    await f.open(workspace({ capabilities: { document_upload: false, toolost: false, dealflow: true } }));
    assert.equal(f.doc.querySelector('a[href="/dealflow/"]'), null);
  });
});

test('reviewer document request flag is explicit, immutable on retry and cleared after acknowledgement', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ role: 'reviewer', questions: [] });
  await f.open(server);
  assert.equal(f.doc.querySelector('input[type=file]'), null);
  f.click('#request-documents');
  f.set('#body-new', 'Please provide a synthetic statement.');
  f.queue.push(() => { throw Error('lost acknowledgement'); });
  f.submit('[data-question-form=question]'); await f.idle();
  const original = clone(f.calls.at(-1).body);
  assert.equal(original.request_documents, true);
  assert.equal(f.get('#request-documents').disabled, true);
  const checkbox = f.get('#request-documents');
  checkbox.checked = false; checkbox.dispatchEvent(new f.win.Event('input', { bubbles: true }));
  f.queue.push(json(server)); f.click('[data-action=refresh]'); f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.get('#request-documents').checked, true);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ created: false }); }, json({ ...server, questions: [question({ request_documents: true, body: original.body })] }));
  f.submit('[data-question-form=question]'); await f.idle();
  assert.equal(f.get('#request-documents').checked, false);
  assert.equal(f.get('#request-documents').disabled, false);
  assert.equal(f.get('#body-new').value, '');
  assert.match(f.text(), /Supporting documents requested/);
});

test('only open requested questions on a submitted owner workspace expose uploads', async t => {
  for (const overrides of [{ role: 'reviewer' }, { submission: null }, { capabilities: { document_upload: false, toolost: false } },
    { questions: [question({ request_documents: false })] }, { questions: [question({ request_documents: true, reply: publishedReply('Already answered', []) })] }]) {
    await t.test(JSON.stringify(overrides), async t => {
      const f = fixture(t); await f.open(supplementWorkspace(overrides));
      assert.equal(f.doc.querySelector('[data-question-upload]'), null);
      assert.equal(f.doc.querySelector('[data-question-document]'), null);
      if (overrides.submission !== null) assert.equal(f.doc.querySelector('#upload-form'), null);
    });
  }
});

test('question selection only accepts scoped accepted files, never original or another question files', async t => {
  const f = fixture(t);
  const documents = [document(5, ID(8)), document(6, ID(18)), document(7), document(10, ID(8), 'scanning'), document(11, ID(8), 'rejected'), document(12, ID(8), 'quarantined')];
  const server = supplementWorkspace({ documents });
  await f.open(server);
  assert.equal(f.doc.querySelector(selection(6, 8)), null);
  assert.equal(f.doc.querySelector(selection(7, 8)), null);
  for (const id of [10, 11, 12]) assert.equal(f.get(selection(id)).disabled, true);
  const forged = f.get(selection(5)).cloneNode(true);
  forged.dataset.questionDocument = ID(6); forged.checked = true;
  f.get(replyForm()).append(forged); forged.dispatchEvent(new f.win.Event('input', { bubbles: true }));
  f.click(selection(5)); f.click(selection(6, 18));
  f.set(`#body-${ID(8)}`, 'Only question one evidence.');
  f.queue.push(call => {
    assert.deepEqual(call.body.document_ids, [ID(5)]);
    server.questions[0].reply = publishedReply(call.body.body, [documents[0]]);
    f.queue.push(json(server)); return json({ created: true });
  });
  f.submit(replyForm()); await f.idle();
  assert.equal(f.get(selection(6, 18)).checked, true);
  assert.equal(f.doc.querySelector(replyForm()), null);
  assert.match(f.text(), /Published supplement version 1/);
  assert.equal(f.doc.querySelector('#catalog [data-download]'), null);
  assert.equal(f.doc.querySelector('#draft-form'), null);
});

test('question upload unknown acknowledgement retains exact bytes, ID and question across refresh', async t => {
  const f = fixture(t, { timeoutMs: 12 });
  const server = supplementWorkspace();
  await f.open(server);
  const file = new f.win.File(['synthetic,bytes\n1,2'], 'question statement.csv');
  f.selectFile(file, fileInput());
  const oldForm = f.get(uploadForm());
  f.queue.push(() => new Promise(() => {}));
  f.submit(uploadForm()); oldForm.dispatchEvent(new f.win.Event('submit', { bubbles: true })); await f.idle();
  const first = f.calls.at(-1);
  assert.equal(first.path, `/api/portal/questions/${ID(8)}/documents`);
  assert.equal(first.body, file);
  assert.match(f.text(), /timed out/);
  assert.equal(f.get(fileInput()).disabled, true);
  assert.equal(f.get(`${uploadForm(18)} fieldset`).disabled, true);
  assert.equal(f.get(`${replyForm()} button`).disabled, true);
  f.selectFile(new f.win.File(['wrong'], 'replacement.csv'), fileInput());
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.match(f.text(), /question statement.csv/);
  f.queue.push(call => {
    assert.equal(call.path, first.path); assert.equal(call.body, file);
    assert.equal(call.options.headers['X-Upload-Id'], first.options.headers['X-Upload-Id']);
    assert.equal(call.options.headers['X-Document-Name'], 'question%20statement.csv');
    return json({ document_id: ID(5), status: 'quarantined' }, 202);
  });
  f.submit(uploadForm()); await f.idle();
  assert.equal(f.get(fileInput()).disabled, false);
  assert.doesNotMatch(f.text(), /Selected: question statement.csv/);
  assert.equal(f.doc.querySelector(selection()), null);
  assert.match(f.text(), /has not been published/);
  assert.equal(f.calls.filter(call => call.path.endsWith('/documents')).length, 2);
});

test('document-status refresh preserves reply text and selections without auto-attaching new files', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ documents: [document(5, ID(8))] });
  await f.open(server);
  f.click(selection()); f.set(`#body-${ID(8)}`, 'Keep this draft reply.');
  f.selectFile(new f.win.File(['synthetic'], 'new.csv'), fileInput());
  f.queue.push(json({ document_id: ID(6), status: 'scanning' }, 202));
  f.submit(uploadForm()); await f.idle();
  server.documents.push(document(6, ID(8)));
  f.queue.push(json(server)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
  assert.equal(f.get(`#body-${ID(8)}`).value, 'Keep this draft reply.');
  assert.equal(f.get(selection()).checked, true);
  assert.equal(f.get(selection(6)).checked, false);
  f.queue.push(json(server)); f.click('[data-action=refresh]'); f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.get(selection()).checked, true);
});

test('unknown reply acknowledgement keeps body and IDs even when refresh already shows publication', async t => {
  const f = fixture(t);
  const documents = [document(5, ID(8)), document(6, ID(8)), document(7, ID(18))];
  const server = supplementWorkspace({ documents });
  await f.open(server);
  f.click(selection(5)); f.click(selection(7, 18));
  f.set(`#body-${ID(8)}`, 'Immutable evidence reply.');
  f.queue.push(call => {
    server.questions[0].reply = publishedReply(call.body.body, [documents[0]]);
    throw Error('committed but acknowledgement lost');
  });
  f.submit(replyForm()); await f.idle();
  const original = clone(f.calls.at(-1).body);
  assert.deepEqual(original.document_ids, [ID(5)]);
  f.queue.push(json(server)); f.click('[data-action=refresh-reply-status]'); await f.idle();
  assert.equal(f.get(`${replyForm()} textarea`).readOnly, true);
  assert.equal(f.get(`${replyForm(18)} button`).disabled, true);
  assert.equal(f.doc.querySelector('#unresolved-reply input[type=checkbox]'), null);
  assert.match(f.get('#unresolved-reply').textContent, /synthetic-5.csv/);
  f.set(`#body-${ID(8)}`, 'Do not send this replacement.');
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ created: false }); }, json(server));
  f.submit(replyForm()); await f.idle();
  assert.equal(f.doc.querySelector('#unresolved-reply'), null);
  assert.equal(f.get(selection(7, 18)).checked, true);
  assert.equal(f.get(`${replyForm(18)} button`).disabled, false);
});

test('acknowledged supplement with missing published version stays locked until matching authoritative refresh', async t => {
  const f = fixture(t);
  const documents = [document(5, ID(8))];
  const server = supplementWorkspace({ documents });
  await f.open(server); f.click(selection()); f.set(`#body-${ID(8)}`, 'Publish this evidence.');
  f.queue.push(json({ created: true }), json(server)); f.submit(replyForm()); await f.idle();
  assert.match(f.text(), /published version is not available yet/);
  assert.equal(f.get(`${replyForm()} button`).disabled, true);
  server.questions[0].reply = publishedReply('Publish this evidence.', documents);
  f.queue.push(json(server)); f.click('[data-action=refresh-reply-status]'); await f.idle();
  assert.equal(f.doc.querySelector('#unresolved-reply'), null);
  assert.equal(f.calls.filter(call => call.path.endsWith('/reply')).length, 1);
  assert.match(f.text(), /Published supplement version 1/);
});

test('409 supplement conflict discards only the attempted reply and its attachments after refresh', async t => {
  const f = fixture(t);
  const documents = [document(5, ID(8)), document(6, ID(18))];
  const server = supplementWorkspace({ documents });
  await f.open(server); f.click(selection()); f.click(selection(6, 18));
  f.set(`#body-${ID(8)}`, 'Attempted evidence reply.'); f.set(`#body-${ID(18)}`, 'Keep question two.');
  f.queue.push(json({}, 409)); f.submit(replyForm()); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=discard-unresolved-reply]'), null);
  server.questions[0].reply = publishedReply('Existing answer without my documents.', []);
  f.queue.push(json(server)); f.click('[data-action=refresh-reply-status]'); await f.idle();
  assert.match(f.get('#unresolved-reply').textContent, /synthetic-5.csv/);
  f.click('[data-action=discard-unresolved-reply]');
  assert.equal(f.get(selection(6, 18)).checked, true);
  assert.equal(f.get(`#body-${ID(18)}`).value, 'Keep question two.');
  assert.equal(f.doc.querySelector(replyForm()), null);
  assert.doesNotMatch(f.text(), /synthetic-5.csv/);
});

test('no longer accepted selections require explicit removal; rejection keeps text and selection', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ documents: [document(5, ID(8))] });
  await f.open(server); f.click(selection()); f.set(`#body-${ID(8)}`, 'Retain this reply.');
  f.queue.push(json({}, 422)); f.submit(replyForm()); await f.idle();
  assert.equal(f.get(selection()).checked, true);
  assert.equal(f.get(`#body-${ID(8)}`).value, 'Retain this reply.');
  server.documents[0].status = 'rejected';
  f.queue.push(json(server)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
  const calls = f.calls.length;
  f.submit(replyForm());
  assert.equal(f.calls.length, calls); assert.equal(f.doc.activeElement.id, 'screen-message');
  assert.match(f.text(), /Remove unavailable/);
  f.click('[data-action=remove-question-documents]');
  assert.equal(f.get(selection()).checked, false);
  f.queue.push(call => {
    assert.deepEqual(call.body.document_ids, []);
    server.questions[0].reply = publishedReply(call.body.body, []); f.queue.push(json(server)); return json({});
  });
  f.submit(replyForm()); await f.idle();
  assert.equal(f.doc.querySelector('[aria-label="Published supplement versions"]'), null);
});

test('40-file cap includes all questions, original files and acknowledged uploads not yet refreshed', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ documents: Array.from({ length: 39 }, (_, index) => document(200 + index, index % 2 ? ID(18) : null)) });
  await f.open(server); f.selectFile(new f.win.File(['synthetic'], 'last.csv'), fileInput());
  f.queue.push(json({ document_id: ID(500), status: 'quarantined' }, 202)); f.submit(uploadForm()); await f.idle();
  assert.equal(f.get(fileInput()).disabled, true); assert.equal(f.get(fileInput(18)).disabled, true);
  assert.match(f.text(), /40-file case limit/);
  const calls = f.calls.length;
  f.selectFile(new f.win.File(['synthetic'], 'over.csv'), fileInput(18));
  f.submit(uploadForm(18)); assert.equal(f.calls.length, calls);
});

test('at the cap an unresolved upload can still be replayed without adding another file', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ documents: Array.from({ length: 39 }, (_, index) => document(200 + index)) });
  await f.open(server); const file = new f.win.File(['synthetic'], 'last.csv'); f.selectFile(file, fileInput());
  f.queue.push(() => { throw Error('lost ack'); }); f.submit(uploadForm()); await f.idle();
  const id = f.calls.at(-1).options.headers['X-Upload-Id'];
  server.documents.push(document(500, ID(8)));
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get(`#question-upload-button-${ID(8)}`).disabled, false);
  f.queue.push(call => { assert.equal(call.body, file); assert.equal(call.options.headers['X-Upload-Id'], id); return json({ document_id: ID(500), status: 'accepted_for_review' }); });
  f.submit(uploadForm()); await f.idle();
  assert.equal(f.get(selection(500)).checked, false);
});

test('upload validation and definitive rejections allow clearing or replacing only that question file', async t => {
  const f = fixture(t); await f.open(supplementWorkspace());
  f.selectFile(new f.win.File(['bad'], 'bad.js'), fileInput());
  assert.match(f.text(), /Choose a synthetic PDF/); assert.equal(f.doc.activeElement.id, 'screen-message');
  f.selectFile(new f.win.File(['synthetic'], 'other.csv'), fileInput(18));
  f.selectFile(new f.win.File(['bad'], 'bad.pdf'), fileInput());
  f.queue.push(json({}, 415)); f.submit(uploadForm()); await f.idle();
  assert.equal(f.get(fileInput()).disabled, false);
  f.click(`${uploadForm()} [data-action=clear-question-file]`);
  assert.doesNotMatch(f.text(), /Selected: bad.pdf/); assert.match(f.text(), /Selected: other.csv/);
  assert.equal(f.doc.activeElement.id, `question-file-${ID(8)}`);
});

test('supplement version links and downloads work for reviewers without leaking staged files', async t => {
  const f = fixture(t);
  const published = document(5, ID(8));
  const staged = document(6, ID(18)); staged.filename = 'PRIVATE_STAGED.csv';
  const server = supplementWorkspace({ role: 'reviewer', documents: [published, staged] });
  server.questions[0].reply = publishedReply('Published evidence.', [published], 2);
  await f.open(server);
  assert.doesNotMatch(f.text(), /PRIVATE_STAGED/);
  assert.equal(f.doc.querySelector('input[type=file], [data-question-document]'), null);
  const link = f.get('[aria-label="Published supplement versions"] a');
  assert.equal(link.getAttribute('href'), `#supplement-${ID(62)}`);
  assert.ok(f.doc.querySelector(link.getAttribute('href')));
  assert.match(f.get('[data-download]').textContent, /synthetic-5.csv.*version 2/);
  let attachment;
  f.win.URL.createObjectURL = () => 'blob:published-supplement'; f.win.URL.revokeObjectURL = () => {};
  f.win.HTMLAnchorElement.prototype.click = function () { attachment = this.download; };
  f.queue.push(new Response('synthetic', { headers: { 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment' } }));
  f.click('[data-download]'); await f.idle();
  assert.equal(f.calls.at(-1).path, `/api/portal/documents/${ID(5)}`); assert.equal(attachment, 'catalog-document');
  assert.equal(f.doc.querySelector('iframe, object, embed'), null);
});

test('supplement controls have unique labels and descriptions and escape published filenames', async t => {
  const f = fixture(t);
  const server = supplementWorkspace({ documents: [document(5, ID(8)), document(6, ID(18))] });
  server.documents[0].filename = '<img src=x onerror=alert(1)>.csv';
  await f.open(server);
  const ids = [...f.doc.querySelectorAll('[id]')].map(element => element.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const input of f.doc.querySelectorAll('#questions input, #questions textarea')) assert.ok(input.labels.length, input.outerHTML);
  for (const element of f.doc.querySelectorAll('#questions [aria-describedby], #questions [aria-labelledby]')) {
    for (const id of (element.getAttribute('aria-describedby') || element.getAttribute('aria-labelledby')).split(' ')) assert.ok(f.doc.getElementById(id));
  }
  assert.equal(f.doc.querySelector('main img, main [onerror]'), null);
  assert.ok(f.text().includes(server.documents[0].filename));
});

test('supplement contracts reject malformed or mismatched publication and normalize older text-only responses', () => {
  const legacy = validateWorkspace(workspace({ documents: [{ document_id: ID(5), filename: 'old.csv', status: 'accepted_for_review' }], questions: [question({ reply: { body: 'Old reply', created_at: '2026-09-18T10:00:00Z' } })] }));
  assert.equal(legacy.documents[0].question_id, null); assert.equal(legacy.questions[0].request_documents, false);
  assert.deepEqual(legacy.questions[0].reply.document_ids, []); assert.equal(legacy.questions[0].reply.supplement, null);
  const valid = supplementWorkspace({ documents: [document(5, ID(8))] });
  valid.questions[0].reply = publishedReply('Evidence', valid.documents);
  assert.doesNotThrow(() => validateWorkspace(valid));
  for (const corrupt of [
    value => { value.questions[0].request_documents = 'true'; },
    value => { value.documents[0].question_id = '../../outside'; },
    value => { value.documents[0].question_id = ID(18); },
    value => { value.questions[0].reply.document_ids = [ID(6)]; },
    value => { value.questions[0].reply.document_ids.push(ID(5)); },
    value => { value.questions[0].reply.supplement = null; },
    value => { value.questions[0].reply.supplement.submission_id = ID(99); },
    value => { value.questions[0].reply.supplement.supplement_id = 'bad'; },
    value => { value.questions[0].reply.supplement.version = 0; },
    value => { value.questions[0].reply.supplement.documents[0].status = 'scanning'; },
    value => { value.questions[0].reply.supplement.documents[0].question_id = ID(18); },
    value => { value.questions[0].reply.supplement.created_at = 'invalid'; },
    value => { value.documents = Array.from({ length: 41 }, (_, index) => document(200 + index)); },
  ]) { const value = clone(valid); corrupt(value); assert.throws(() => validateWorkspace(value), /workspace request/); }
});

test('access loss clears selected supplements, unresolved uploads and reply state without revival', async t => {
  for (const status of [401, 403, 404]) {
    await t.test(String(status), async t => {
      const f = fixture(t); const server = supplementWorkspace({ documents: [document(5, ID(8))] });
      await f.open(server); f.click(selection()); f.set(`#body-${ID(8)}`, 'PRIVATE_REPLY');
      f.selectFile(new f.win.File(['PRIVATE_BYTES'], 'PRIVATE_FILE.csv'), fileInput());
      f.queue.push(() => { throw Error('offline'); }); f.submit(uploadForm()); await f.idle();
      const detached = f.get(`#body-${ID(8)}`);
      f.queue.push(json({}, status)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
      assert.equal(detached.value, ''); assert.equal(f.doc.querySelector('[data-question-upload]'), null);
      assert.doesNotMatch(f.text(), /PRIVATE_|synthetic-5/);
      f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
      assert.equal(f.get(selection()).checked, false); assert.equal(f.get(`#body-${ID(8)}`).value, '');
      assert.equal(f.get(`#question-upload-button-${ID(8)}`).disabled, true);
    });
  }
});

test('logout, expiry and page suspension erase pending supplement state and ignore late upload success', async t => {
  for (const action of ['logout', 'expiry', 'pagehide']) {
    await t.test(action, async t => {
      const f = fixture(t); const server = supplementWorkspace({ documents: [document(5, ID(8))], session_expires_at: '2026-09-18T10:00:01Z' });
      await f.open(server); f.click(selection()); f.set(`#body-${ID(8)}`, 'PRIVATE_PENDING');
      f.selectFile(new f.win.File(['PRIVATE_BYTES'], 'PRIVATE_FILE.csv'), fileInput());
      const late = deferred(); f.queue.push(() => late.promise); f.submit(uploadForm());
      if (action === 'logout') { f.queue.push(new Response(null, { status: 204 })); f.click('[data-action=logout]'); }
      else if (action === 'expiry') f.advance(1001);
      else f.win.dispatchEvent(new f.win.Event('pagehide'));
      late.resolve(json({ document_id: ID(5), status: 'accepted_for_review' })); await f.idle();
      assert.equal(f.doc.querySelector('[data-question-upload]'), null); assert.doesNotMatch(f.text(), /PRIVATE_|synthetic-5/);
      server.session_expires_at = '2026-09-18T11:00:00Z';
      f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
      assert.equal(f.get(selection()).checked, false); assert.equal(f.get(`#body-${ID(8)}`).value, '');
      assert.equal(f.get(`#question-upload-button-${ID(8)}`).disabled, true);
    });
  }
});

test('question upload errors retain immutable retry state without automatic requests', async t => {
  for (const failure of [() => json({}, 429), () => new Response('PRIVATE', { status: 503 }),
    () => new Response('<html>PRIVATE</html>', { headers: { 'Content-Type': 'text/html' } }), () => json({ document_id: 'bad', status: 'accepted_for_review' })]) {
    await t.test(String(failure), async t => {
      const f = fixture(t); await f.open(supplementWorkspace());
      const file = new f.win.File(['synthetic'], 'retry.csv'); f.selectFile(file, fileInput());
      f.queue.push(failure()); f.submit(uploadForm()); await f.idle();
      const first = f.calls.at(-1);
      assert.equal(f.calls.length, 3); assert.equal(f.get(fileInput()).disabled, true);
      assert.equal(f.doc.activeElement.id, 'screen-message'); assert.doesNotMatch(f.text(), /PRIVATE/);
      f.queue.push(call => {
        assert.equal(call.body, file); assert.equal(call.path, first.path);
        assert.equal(call.options.headers['X-Upload-Id'], first.options.headers['X-Upload-Id']);
        return json({ document_id: ID(5), status: 'rejected' });
      });
      f.submit(uploadForm()); await f.idle();
      assert.equal(f.get(fileInput()).disabled, false); assert.equal(f.get(`${replyForm()} button`).disabled, false);
    });
  }
});

test('unknown upload remains replayable after question closure and conflict discard requires a fresh GET', async t => {
  const f = fixture(t); const server = supplementWorkspace(); await f.open(server);
  f.set(`#body-${ID(18)}`, 'Keep unrelated reply.');
  f.selectFile(new f.win.File(['synthetic'], 'other.csv'), fileInput(18));
  const file = new f.win.File(['synthetic'], 'uncertain.csv'); f.selectFile(file, fileInput());
  f.queue.push(() => { throw Error('offline'); }); f.submit(uploadForm()); await f.idle();
  const first = f.calls.at(-1);
  server.questions[0].reply = publishedReply('Closed elsewhere', []);
  f.queue.push(json(server)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
  f.queue.push(call => { assert.equal(call.body, file); assert.equal(call.options.headers['X-Upload-Id'], first.options.headers['X-Upload-Id']); return json({}, 409); });
  f.submit(uploadForm()); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=discard-question-upload]'), null);
  f.queue.push(json({}, 503)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=discard-question-upload]'), null);
  f.queue.push(json(server)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
  const calls = f.calls.length;
  f.click('[data-action=discard-question-upload]');
  assert.equal(f.calls.length, calls); assert.equal(f.doc.querySelector(uploadForm()), null);
  assert.equal(f.get(`#body-${ID(18)}`).value, 'Keep unrelated reply.'); assert.match(f.text(), /Selected: other.csv/);
  assert.match(f.text(), /not confirmed saved or attached/);
});

test('server whitespace normalization does not leave an acknowledged reply locked', async t => {
  const f = fixture(t); const server = supplementWorkspace(); await f.open(server);
  f.set(`#body-${ID(8)}`, '  Synthetic reply with surrounding space.\n');
  f.queue.push(call => {
    assert.equal(call.body.body, '  Synthetic reply with surrounding space.\n');
    server.questions[0].reply = publishedReply(call.body.body.trim(), []); f.queue.push(json(server)); return json({});
  });
  f.submit(replyForm()); await f.idle();
  assert.equal(f.doc.querySelector('#unresolved-reply'), null);
  assert.match(f.text(), /Message received/);
});

test('already published server supplements may explicitly reuse original or previously published documents', () => {
  const original = document(5);
  const earlier = document(6, ID(8));
  const server = supplementWorkspace({ documents: [original, earlier], submission: submitted({ ...draft(), document_ids: [ID(5)] }, [original]) });
  server.questions[0].reply = publishedReply('First supplement', [earlier]);
  server.questions[1].reply = publishedReply('Explicit reuse', [original, earlier], 2);
  assert.doesNotThrow(() => validateWorkspace(server));
  delete server.questions[0].reply.supplement.documents[0].question_id;
  assert.doesNotThrow(() => validateWorkspace(server));
});

test('privacy actions are owner-only and do nothing on opening or refreshing the workspace', async t => {
  for (const role of ['owner', 'reviewer']) {
    await t.test(role, async t => {
      const f = fixture(t); const server = supplementWorkspace({ role }); await f.open(server);
      assert.equal(Boolean(f.doc.querySelector('#privacy [data-action=export]')), role === 'owner');
      assert.equal(Boolean(f.doc.querySelector('#privacy [data-action=continue-interest]')), role === 'owner');
      assert.equal(f.calls.length, 2);
      f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
      assert.equal(f.calls.length, 3); assert.equal(f.calls.at(-1).path, '/api/portal/workspace');
      assert.equal(f.calls.filter(call => /export|continue-interest/.test(call.path)).length, 0);
    });
  }
});

test('case export downloads a fixed JSON attachment, preserves unsaved evidence and revokes its URL on clearing', async t => {
  const f = fixture(t); const server = supplementWorkspace({ documents: [document(5, ID(8))] }); await f.open(server);
  f.click(selection()); f.set(`#body-${ID(8)}`, 'Unsaved evidence reply.');
  const revoked = []; let attachment;
  f.win.URL.createObjectURL = blob => { assert.match(blob.type, /^application\/json/); return 'blob:case-export'; };
  f.win.URL.revokeObjectURL = url => revoked.push(url);
  f.win.HTMLAnchorElement.prototype.click = function () { attachment = { href: this.href, download: this.download }; };
  f.queue.push(new Response('{"private":"PRIVATE_EXPORT_CONTENT"}', { headers: { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="untrusted.html"' } }));
  f.click('[data-action=export]'); await f.idle();
  assert.equal(f.calls.at(-1).path, '/api/portal/export'); assert.equal(f.calls.at(-1).options.method, 'GET');
  assert.deepEqual(attachment, { href: 'blob:case-export', download: 'space-review-export.json' });
  assert.equal(f.get(selection()).checked, true); assert.equal(f.get(`#body-${ID(8)}`).value, 'Unsaved evidence reply.');
  assert.doesNotMatch(f.text(), /PRIVATE_EXPORT_CONTENT|untrusted.html/);
  assert.equal(f.doc.querySelector('iframe, object, embed, a[download]'), null);
  assert.match(f.text(), /Keep this copy private/);
  f.win.dispatchEvent(new f.win.Event('pagehide')); assert.deepEqual(revoked, ['blob:case-export']);
});

test('continued interest uses explicit singleflight action and exact-ID retry after refresh', async t => {
  const f = fixture(t, { timeoutMs: 12 }); const server = supplementWorkspace(); await f.open(server);
  f.queue.push(() => new Promise(() => {}));
  const button = f.get('[data-action=continue-interest]'); button.click(); button.click(); await f.idle();
  const original = clone(f.calls.at(-1).body);
  assert.deepEqual(Object.keys(original), ['request_id']);
  assert.equal(f.calls.filter(call => call.path.endsWith('/continue-interest')).length, 1);
  assert.match(f.get('[data-action=continue-interest]').textContent, /Retry same/);
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.match(f.text(), /earlier request is still unresolved/);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ recorded: true, created: false }); });
  f.click('[data-action=continue-interest]'); await f.idle();
  assert.equal(f.get('[data-action=continue-interest]').disabled, true);
  assert.match(f.text(), /continued interest has been recorded/);
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get('[data-action=continue-interest]').disabled, true);
  assert.equal(f.calls.filter(call => call.path.endsWith('/continue-interest')).length, 2);
});

test('continued interest malformed acknowledgement and HTTP errors keep the same reference without auto-retry', async t => {
  for (const response of [() => json({ recorded: true }), () => json({ recorded: false, created: true }), () => json({}, 429), () => new Response('PRIVATE', { status: 500 })]) {
    await t.test(String(response), async t => {
      const f = fixture(t); await f.open(supplementWorkspace());
      f.queue.push(response()); f.click('[data-action=continue-interest]'); await f.idle();
      const original = f.calls.at(-1).body; assert.equal(f.calls.length, 3);
      assert.equal(f.doc.activeElement.id, 'screen-message'); assert.doesNotMatch(f.text(), /PRIVATE/);
      assert.equal(f.get('[data-action=continue-interest]').disabled, false);
      f.queue.push(call => { assert.deepEqual(call.body, original); return json({ recorded: true, created: true }); });
      f.click('[data-action=continue-interest]'); await f.idle();
      assert.equal(f.get('[data-action=continue-interest]').disabled, true);
    });
  }
});

test('privacy requests cannot replace or auto-send an unresolved supplement reply', async t => {
  const f = fixture(t); const server = supplementWorkspace({ documents: [document(5, ID(8))] }); await f.open(server);
  f.click(selection()); f.set(`#body-${ID(8)}`, 'Unresolved evidence reply.');
  f.queue.push(() => { throw Error('offline'); }); f.submit(replyForm()); await f.idle();
  const original = clone(f.calls.at(-1).body);
  assert.equal(f.get('[data-action=continue-interest]').disabled, true);
  f.click('[data-action=continue-interest]'); assert.equal(f.calls.length, 3);
  f.queue.push(new Response('<html>PRIVATE_EXPORT</html>', { headers: { 'Content-Type': 'text/html' } }));
  f.click('[data-action=export]'); await f.idle();
  assert.equal(f.get(`${replyForm()} textarea`).value, original.body); assert.doesNotMatch(f.text(), /PRIVATE_EXPORT/);
  f.queue.push(call => {
    assert.deepEqual(call.body, original); server.questions[0].reply = publishedReply(call.body.body, server.documents);
    f.queue.push(json(server)); return json({});
  });
  f.submit(replyForm()); await f.idle();
  assert.equal(f.get('[data-action=continue-interest]').disabled, false);
});

test('export access failure wipes the page and pending continued-interest ID', async t => {
  const f = fixture(t); const server = supplementWorkspace(); await f.open(server);
  f.queue.push(() => { throw Error('offline'); }); f.click('[data-action=continue-interest]'); await f.idle();
  const oldId = f.calls.at(-1).body.request_id;
  f.queue.push(json({}, 403)); f.click('[data-action=export]'); await f.idle();
  assert.equal(f.doc.querySelector('[data-action=export]'), null); assert.doesNotMatch(f.text(), /Synthetic release/);
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.doesNotMatch(f.get('[data-action=continue-interest]').textContent, /Retry/);
  f.queue.push(call => { assert.notEqual(call.body.request_id, oldId); return json({ recorded: true, created: true }); });
  f.click('[data-action=continue-interest]'); await f.idle();
});

test('clearing during an export or interest request ignores late success and does not download or record in UI', async t => {
  for (const action of ['export', 'continue-interest']) {
    await t.test(action, async t => {
      const f = fixture(t); await f.open(supplementWorkspace());
      let downloads = 0; f.win.URL.createObjectURL = () => { downloads += 1; return 'blob:unexpected'; };
      const late = deferred(); f.queue.push(() => late.promise); f.click(`[data-action=${action}]`);
      f.win.dispatchEvent(new f.win.Event('pagehide'));
      late.resolve(action === 'export' ? new Response('{}', { headers: { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment' } }) : json({ recorded: true, created: true }));
      await f.idle();
      assert.equal(downloads, 0); assert.equal(f.doc.querySelector('[data-action=continue-interest]'), null);
      assert.doesNotMatch(f.text(), /has been recorded|download started/);
    });
  }
});

test('test and production shells share approved assets and layout, with distinct persistent notices', () => {
  const testDom = new JSDOM(html); const pilotDom = new JSDOM(productionHtml);
  const testDoc = testDom.window.document; const pilotDoc = pilotDom.window.document;
  assert.equal(testDoc.documentElement.dataset.environment, 'test');
  assert.equal(pilotDoc.documentElement.dataset.environment, 'production');
  assert.deepEqual([...pilotDoc.querySelectorAll('*')].map(element => element.tagName), [...testDoc.querySelectorAll('*')].map(element => element.tagName));
  const assets = doc => [...doc.querySelectorAll('[src], link[href]')].map(element => element.getAttribute('src') || element.getAttribute('href'));
  assert.deepEqual(assets(pilotDoc), assets(testDoc));
  for (const url of assets(pilotDoc)) assert.match(url, /^\/workspace\//);
  assert.equal(pilotDoc.querySelector('meta[name=robots]').content, 'noindex,nofollow,noarchive');
  assert.equal(pilotDoc.querySelector('meta[name=referrer]').content, 'no-referrer');
  assert.match(testDoc.querySelector('.preview-notice').textContent, /Integration test.*Synthetic information only/);
  assert.match(pilotDoc.querySelector('.preview-notice').textContent, /Private pilot.*authorized to provide/);
  assert.match(pilotDoc.querySelector('#help').textContent, /does not confirm ownership or constitute an offer/);
  assert.doesNotMatch(pilotDoc.body.textContent, /synthetic|integration test|test workspace|test records/i);
  assert.equal(pilotDoc.querySelectorAll('script').length, 1);
  testDom.window.close(); pilotDom.window.close();
});

test('missing, staging or unknown shell markers retain test copy regardless of URL flags', async t => {
  for (const marker of ['', 'staging', 'unknown', 'test']) {
    await t.test(marker || 'missing', async t => {
      const shell = marker ? html.replace('data-environment="test"', `data-environment="${marker}"`) : html.replace(' data-environment="test"', '');
      const f = fixture(t, { shell, hash: `#invitation=${TOKEN}&environment=production&mode=production` });
      assert.match(f.text(), /integration test accepts synthetic information only/);
      assert.equal(f.calls.length, 0);
      await f.open(supplementWorkspace({ environment: 'staging' }));
      assert.match(f.get(fileInput()).labels[0].textContent, /Synthetic supporting document/);
      assert.match(f.get('#screen-message').textContent, /Use synthetic information only/);
      assert.equal(f.win.location.search, ''); assert.equal(f.win.location.hash, '');
    });
  }
});

test('production copy covers entry, upload validation, follow-up, deletion and privacy without test labels', async t => {
  const f = fixture(t, { shell: productionHtml });
  assert.match(f.text(), /private pilot/i); assert.doesNotMatch(f.text(), /synthetic|integration test|@example\.com/i);
  assert.equal(f.calls.length, 0);
  const value = draft(); value.rights[0].title = 'Catalog release'; value.rights[0].artist = '';
  const server = workspace({ environment: 'production', draft: value, capabilities: { document_upload: true, toolost: false } });
  await f.open(server);
  assert.equal(f.get('#upload-button').textContent, 'Upload supporting document');
  assert.match(f.get('#screen-message').textContent, /authorized to provide/);
  f.selectFile(new f.win.File(['invalid'], 'statement.js'));
  assert.match(f.get('#screen-message').textContent, /Choose a PDF, CSV or XLSX supporting document/);
  assert.doesNotMatch(f.text(), /synthetic|integration test|test UI|test workspace/i);
  server.submission = submitted(value); server.questions = [question({ body: 'Please provide the statement.', request_documents: true })];
  f.queue.push(json(server)); f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get(fileInput()).labels[0].childNodes[0].textContent, 'Supporting document');
  assert.match(f.get(`#limit-${ID(8)}`).textContent, /authorized to share/);
  f.click('[data-action=delete]');
  assert.match(f.get('#confirmation').textContent, /deletion of this review workspace/);
  assert.doesNotMatch(f.text(), /synthetic|integration test|test UI|test workspace/i);
  assert.ok(f.get('#privacy [data-action=export]')); assert.ok(f.get('#privacy [data-action=continue-interest]'));
  assert.equal(f.calls.filter(call => /export|continue-interest|deletion-request/.test(call.path)).length, 0);
});

test('production invitation recovery accepts the original non-test address and never claims email delivery', async t => {
  const f = fixture(t, { shell: productionHtml });
  f.queue.push(json({}, 401)); f.click('[data-action=open]'); await f.idle();
  assert.equal(f.get('#access-form button').textContent, 'Request access link');
  f.set('#recovery-email', 'not-an-email'); f.submit('#access-form');
  assert.equal(f.calls.length, 1); assert.match(f.get('#screen-message').textContent, /valid email address/);
  f.set('#recovery-email', 'owner@example.org');
  f.queue.push(call => { assert.deepEqual(call.body, { workspace_id: ID(1), email: 'owner@example.org' }); return json({ status: 'request_received' }, 202); });
  f.submit('#access-form'); await f.idle();
  assert.match(f.get('#screen-message').textContent, /If this address matches an eligible application/);
  assert.match(f.get('#screen-message').textContent, /not confirmation of delivery/);
  assert.doesNotMatch(f.text(), /synthetic|integration test|@example\.com|no real email/i);
  assert.equal(f.get('#recovery-email').value, '');
});

test('API environment can validate but never enable production copy; mismatches wipe private pending state', async t => {
  for (const [shell, initialEnvironment, mismatchedEnvironment] of [[html, 'test', 'production'], [productionHtml, 'production', 'test'], [productionHtml, 'production', 'staging']]) {
    await t.test(`${initialEnvironment} to ${mismatchedEnvironment}`, async t => {
      const f = fixture(t, { shell }); const server = supplementWorkspace({ environment: initialEnvironment, documents: [document(5, ID(8))] });
      await f.open(server); f.click(selection()); f.set(`#body-${ID(8)}`, 'PRIVATE_ENVIRONMENT_REPLY');
      f.selectFile(new f.win.File(['PRIVATE'], 'PRIVATE_ENVIRONMENT.csv'), fileInput());
      f.queue.push(() => { throw Error('offline'); }); f.submit(uploadForm()); await f.idle();
      server.environment = mismatchedEnvironment;
      f.queue.push(json(server)); f.click(`${uploadForm()} [data-action=refresh-question-documents]`); await f.idle();
      assert.match(f.text(), /environments do not match/); assert.doesNotMatch(f.text(), /PRIVATE_ENVIRONMENT/);
      assert.equal(f.doc.querySelector('[data-question-upload]'), null);
      assert.equal(f.doc.querySelector('#body-new'), null);
      if (initialEnvironment === 'test') assert.match(f.text(), /synthetic information only/i);
      else assert.doesNotMatch(f.text(), /synthetic information only/i);
      assert.equal(f.calls.filter(call => /continue-interest|export/.test(call.path)).length, 0);
    });
  }
  assert.throws(() => validateWorkspace(workspace({ environment: 'unknown' })));
});

test('local browser: Inter, mobile layout, keyboard operation and exact supplement retries', { skip: !process.env.CATALOG_UI_BROWSER_TEST }, async t => {
  const runtime = createRequire(`${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json`);
  const { chromium } = runtime('playwright');
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  t.after(() => browser.close());
  const context = await browser.newContext({ viewport: { width: 1365, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.clock.setFixedTime(new Date(START));
  const server = supplementWorkspace({ documents: [document(6, ID(18))] });
  const uploads = [];
  const replies = [];
  const interests = [];
  const unexpected = [];
  const assets = new Map([
    ['/workspace/', ['services/catalog_review_ui/index.html', 'text/html']],
    ['/workspace/app.mjs', ['services/catalog_review_ui/app.mjs', 'text/javascript']],
    ['/workspace/client.mjs', ['services/catalog_review_ui/client.mjs', 'text/javascript']],
    ['/workspace/portal.css', ['services/catalog_review_ui/portal.css', 'text/css']],
    ['/workspace/review.css', ['services/catalog_review_preview/ui/review.css', 'text/css']],
    ['/workspace/space-wordmark.svg', ['marketing/identity-20260916/space-wordmark.svg', 'image/svg+xml']],
    ['/workspace/inter.woff2', ['marketing/design/fonts/inter-latin-c940764593d0.woff2', 'font/woff2']],
    ['/inter.woff2', ['marketing/design/fonts/inter-latin-c940764593d0.woff2', 'font/woff2']],
  ]);
  await context.route('**/*', async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== 'https://review.test') { unexpected.push(request.url()); return route.abort(); }
    const asset = assets.get(url.pathname);
    if (asset) return route.fulfill({ body: await readFile(new URL(`../../${asset[0]}`, import.meta.url)), contentType: asset[1] });
    if (url.pathname === '/api/portal/workspace') return route.fulfill({ json: server });
    if (url.pathname === '/api/portal/continue-interest') {
      interests.push(request.postData());
      if (interests.length === 1) return route.abort('connectionfailed');
      return route.fulfill({ json: { recorded: true, created: false } });
    }
    if (url.pathname === `/api/portal/questions/${ID(8)}/documents`) {
      uploads.push({ bytes: request.postDataBuffer(), headers: await request.allHeaders() });
      if (uploads.length === 1) { server.documents.push(document(5, ID(8))); return route.abort('connectionfailed'); }
      return route.fulfill({ json: { document_id: ID(5), status: 'accepted_for_review' } });
    }
    if (url.pathname === `/api/portal/questions/${ID(8)}/reply`) {
      replies.push(request.postData());
      const payload = request.postDataJSON();
      if (replies.length === 1) { server.questions[0].reply = publishedReply(payload.body, [server.documents.find(item => item.document_id === ID(5))]); return route.abort('connectionfailed'); }
      return route.fulfill({ json: { created: false } });
    }
    unexpected.push(request.url()); return route.abort();
  });
  const idle = () => page.waitForFunction(() => document.querySelector('main').getAttribute('aria-busy') === 'false');
  await page.goto('https://review.test/workspace/');
  await page.getByRole('button', { name: 'Refresh existing session', exact: true }).focus();
  await page.keyboard.press('Enter'); await page.locator(fileInput()).waitFor(); await idle();
  await page.evaluate(() => document.fonts.ready);
  assert.match(await page.locator('body').evaluate(element => getComputedStyle(element).fontFamily), /Inter/);
  for (const width of [1365, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Overflow at ${width}px`);
  }
  await page.locator(fileInput()).setInputFiles({ name: 'synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from('synthetic,bytes\n1,2') });
  await page.locator(`${uploadForm()} button[type=submit]`).focus(); await page.keyboard.press('Enter'); await idle();
  await page.getByRole('button', { name: 'Refresh workspace', exact: true }).click(); await idle();
  await page.locator(`${uploadForm()} button[type=submit]`).click(); await idle();
  assert.equal(uploads.length, 2); assert.deepEqual(uploads[1].bytes, uploads[0].bytes);
  assert.equal(uploads[1].headers['x-upload-id'], uploads[0].headers['x-upload-id']);
  assert.equal(await page.locator(selection()).isChecked(), false);
  await page.locator(selection()).focus(); await page.keyboard.press('Space');
  await page.locator(`#body-${ID(8)}`).fill('Synthetic browser evidence reply.');
  await page.locator(`${replyForm()} button[type=submit]`).click(); await idle();
  await page.getByRole('button', { name: 'Refresh reply status', exact: true }).click(); await idle();
  await page.locator(`${replyForm()} button[type=submit]`).click(); await idle();
  assert.equal(replies.length, 2); assert.equal(replies[1], replies[0]);
  assert.deepEqual(JSON.parse(replies[0]).document_ids, [ID(5)]);
  assert.equal(await page.locator('#unresolved-reply').count(), 0);
  await page.getByRole('link', { name: 'Published supplement version 1', exact: true }).focus(); await page.keyboard.press('Enter');
  assert.match(page.url(), /#supplement-/);
  assert.equal(await page.locator(selection(6, 18)).isChecked(), false);
  assert.equal(interests.length, 0);
  await page.locator('[data-action=continue-interest]').focus(); await page.keyboard.press('Enter'); await idle();
  await page.getByRole('button', { name: 'Refresh workspace', exact: true }).click(); await idle();
  await page.locator('[data-action=continue-interest]').click(); await idle();
  assert.equal(interests.length, 2); assert.equal(interests[1], interests[0]);
  assert.equal(await page.locator('[data-action=continue-interest]').isDisabled(), true);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  // A fresh page receives only pilot copy from the server-selected shell.
  assets.set('/workspace/', ['services/catalog_review_ui/index.production.html', 'text/html']);
  server.environment = 'production';
  const pilot = await context.newPage();
  pilot.on('pageerror', error => errors.push(error.message));
  await pilot.clock.setFixedTime(new Date(START));
  await pilot.goto('https://review.test/workspace/');
  assert.equal(await pilot.locator('html').getAttribute('data-environment'), 'production');
  assert.match(await pilot.locator('.preview-notice').innerText(), /Private pilot/);
  assert.doesNotMatch(await pilot.locator('body').innerText(), /synthetic|integration test/i);
  assert.equal(interests.length, 2);
  await pilot.getByRole('button', { name: 'Refresh existing session', exact: true }).click();
  await pilot.locator(fileInput(18)).waitFor();
  assert.equal(await pilot.locator(fileInput(18)).evaluate(input => input.labels[0].childNodes[0].textContent), 'Supporting document');
  await pilot.setViewportSize({ width: 320, height: 900 });
  assert.ok(await pilot.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  assert.match(await pilot.locator('body').evaluate(element => getComputedStyle(element).fontFamily), /Inter/);
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); assert.equal(interests.length, 2);
});

test('refreshing an existing session without an invitation never sends an exchange', async t => {
  const f = fixture(t, { hash: '' });
  assert.equal(f.calls.length, 0);
  assert.equal(f.doc.querySelector('[data-action=open]'), null);
  f.queue.push(json(workspace({ draft: draft() })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].path, '/api/portal/workspace');
});

test('optional metadata defaults and actual backend review statuses are supported', async t => {
  const value = draft();
  delete value.rights[0].title; delete value.rights[0].artist;
  delete value.rights[0].rights_scope; delete value.rights[0].obligations;
  const f = fixture(t);
  await f.open(workspace({ draft: value, review_status: 'under_review' }));
  assert.equal(f.get('#title-0').value, '');
  assert.equal(f.get('#scope-0').value, 'unknown');
  assert.match(f.text(), /Under review/);
});

test('share validation focuses the error and unknown ownership always sends null', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.set('#ownership-0', 'known'); f.set('#share-0', '100.01');
  f.submit('#draft-form');
  assert.equal(f.calls.length, 2);
  assert.equal(f.doc.activeElement.id, 'screen-message');
  assert.equal(f.get('#share-0').value, '100.01');
  f.set('#ownership-0', 'unknown');
  assert.equal(f.get('#share-0').value, '');
  f.queue.push(call => {
    assert.equal(call.body.draft.rights[0].share_percent, null);
    f.queue.push(json(workspace({ draft: call.body.draft, revision: 1 })));
    return json({ revision: 1 });
  });
  f.submit('#draft-form'); await f.idle();
});

test('non-JSON save errors preserve all edits and never display raw details', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.set('#title-0', 'Unsaved synthetic title'); f.set('#obligations-0', 'present');
  f.queue.push(new Response('<b>PRIVATE_INTERNAL_ERROR</b>', { status: 500 }));
  f.submit('#draft-form'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Unsaved synthetic title');
  assert.equal(f.get('#obligations-0').value, 'present');
  assert.doesNotMatch(f.text(), /PRIVATE_INTERNAL_ERROR/);
  assert.equal(f.doc.activeElement.id, 'screen-message');
});

test('conflict cannot silently replace the form or reuse a newer revision without confirmation', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), revision: 4 }));
  f.set('#title-0', 'Unsaved conflict title');
  f.queue.push(json({ error: 'private' }, 409));
  f.submit('#draft-form'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Unsaved conflict title');
  assert.ok(f.get('#draft-form > fieldset').disabled);
  f.submit('#draft-form'); assert.equal(f.calls.length, 3);
  f.click('[data-action=refresh]');
  assert.equal(f.doc.activeElement.id, 'confirmation');
  assert.equal(f.calls.length, 3);
  f.click('[data-action=cancel]');
  assert.equal(f.get('#title-0').value, 'Unsaved conflict title');
  f.click('[data-action=refresh]');
  f.queue.push(json(workspace({ draft: draft(), revision: 5 })));
  f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Synthetic release');
  assert.equal(f.get('#draft-form > fieldset').disabled, false);
});

test('save acknowledgement followed by failed refresh preserves edits and blocks further writes', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.set('#artist-0', 'Unsaved artist');
  f.queue.push(json({ revision: 1 }), () => { throw Error('offline'); });
  f.submit('#draft-form'); await f.idle();
  assert.equal(f.get('#artist-0').value, 'Unsaved artist');
  assert.equal(f.get('#draft-form > fieldset').disabled, true);
  assert.match(f.text(), /offline/);
});

test('401 wipes private DOM, inputs, messages and references without resuming prior entries', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), questions: [question()] }));
  f.set('#title-0', 'PRIVATE_UNSAVED_TITLE');
  f.set(`#body-${ID(8)}`, 'PRIVATE_UNSENT_REPLY');
  const oldInput = f.get('#title-0');
  const oldReply = f.get(`#body-${ID(8)}`);
  f.queue.push(json({}, 401)); f.submit('#draft-form'); await f.idle();
  assert.equal(oldInput.value, '');
  assert.equal(oldReply.value, '');
  assert.doesNotMatch(f.text(), /PRIVATE_|Test artist|Synthetic release|Please explain/);
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.get('#progress').textContent, '');
  assert.match(f.text(), /session or invitation has expired/);
  f.queue.push(json(workspace({ draft: draft() })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Synthetic release');
  assert.doesNotMatch(f.text(), /PRIVATE_/);
});

test('expiry timer clears even offline and ignores a late successful response', async t => {
  const f = fixture(t);
  await f.open(workspace({ draft: draft(), session_expires_at: '2026-09-18T10:00:01Z' }));
  f.set('#title-0', 'PRIVATE_EXPIRING');
  const late = deferred(); f.queue.push(() => late.promise);
  f.submit('#draft-form');
  f.advance(1001);
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.doesNotMatch(f.text(), /PRIVATE_EXPIRING|Synthetic release/);
  late.resolve(json({ revision: 1 }));
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(f.calls.length, 3);
  assert.equal(f.doc.querySelector('#draft-form'), null);
});

test('403 clears inaccessible data; 429 preserves edits and does not auto-retry', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.set('#title-0', 'Rate-limited edit');
  f.queue.push(json({}, 429)); f.submit('#draft-form'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Rate-limited edit');
  assert.match(f.text(), /Too many requests/);
  assert.equal(f.calls.length, 3);
  f.queue.push(json({}, 403)); f.submit('#draft-form'); await f.idle();
  assert.equal(f.doc.querySelector('#title-0'), null);
  assert.match(f.text(), /does not have permission/);
});

test('submission double-click is blocked; uncertain retry keeps exactly the same ID and body', async t => {
  const f = fixture(t, { timeoutMs: 15 });
  await f.open(workspace({ draft: draft(), revision: 1 }));
  f.click('#consent');
  const lost = deferred(); f.queue.push(() => lost.promise);
  const button = f.get('[data-action=submit]'); button.click(); button.click();
  await f.idle();
  const original = f.calls.at(-1).body;
  assert.match(f.text(), /timed out/);
  assert.equal(f.calls.filter(call => call.path.endsWith('/submission')).length, 1);
  assert.equal(f.get('#draft-form > fieldset').disabled, true);
  f.queue.push(json(workspace({ draft: draft(), revision: 1 })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get('[data-action=submit]').disabled, false);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ submission_id: ID(9), created: false }); }, json(workspace({ draft: draft(), revision: 1, submission: submitted(), review_status: 'submitted' })));
  f.click('[data-action=submit]'); await f.idle();
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.doc.querySelector('[data-action=submit]'), null);
  assert.match(f.text(), /submitted snapshot is locked/);
  lost.resolve(json({ submission_id: ID(9) }));
});

test('acknowledged submission with refresh failure stays locked and does not POST again', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), revision: 1 }));
  f.click('#consent');
  f.queue.push(json({ submission_id: ID(9) }), json({}, 503));
  f.click('[data-action=submit]'); await f.idle();
  assert.equal(f.get('[data-action=submit]').disabled, true);
  assert.equal(f.get('#draft-form > fieldset').disabled, true);
  f.queue.push(json(workspace({ draft: draft(), revision: 1, submission: submitted() })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.calls.filter(call => call.path.endsWith('/submission')).length, 1);
});

test('locked snapshot, not mutable draft, is rendered; reviewers have no editing or deletion controls', async t => {
  const f = fixture(t);
  const current = draft(); current.rights[0].title = 'MUTABLE_NOT_SNAPSHOT';
  await f.open(workspace({ role: 'reviewer', draft: current, submission: submitted(), review_status: 'under_review' }));
  assert.doesNotMatch(f.text(), /MUTABLE_NOT_SNAPSHOT/);
  assert.match(f.text(), /Synthetic release/);
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.doc.querySelector('[data-action=delete]'), null);
  assert.equal(f.doc.querySelector('[data-action=submit]'), null);
  assert.ok(f.doc.querySelector('[data-question-form=question]'));
});

test('reviewer message length validation and uncertain retry are singleflight and idempotent', async t => {
  const f = fixture(t); await f.open(workspace({ role: 'reviewer', draft: draft() }));
  f.set('#body-new', 'x'.repeat(4001)); f.submit('[data-question-form=question]');
  assert.equal(f.calls.length, 2);
  assert.equal(f.doc.activeElement.id, 'screen-message');
  f.set('#body-new', 'A synthetic follow-up?');
  f.queue.push(() => { throw Error('offline'); });
  f.submit('[data-question-form=question]'); f.submit('[data-question-form=question]'); await f.idle();
  const original = f.calls.at(-1).body;
  assert.equal(f.get('#body-new').readOnly, true);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({ question_id: ID(8) }); }, json(workspace({ role: 'reviewer', draft: draft(), questions: [question({ body: original.body })] })));
  f.submit('[data-question-form=question]'); await f.idle();
  assert.equal(f.get('#body-new').value, '');
  assert.match(f.text(), /A synthetic follow-up/);
  assert.equal(f.calls.filter(call => call.path.endsWith('/questions')).length, 2);
});

test('owner replies keep their request ID and preserve unrelated unsaved draft edits', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), questions: [question()] }));
  f.set('#title-0', 'Unsaved owner title');
  f.set(`#body-${ID(8)}`, 'Synthetic owner reply');
  f.queue.push(() => { throw Error('offline'); });
  f.submit('[data-question-form=reply]'); await f.idle();
  const original = f.calls.at(-1).body;
  assert.equal(f.calls.at(-1).path, `/api/portal/questions/${ID(8)}/reply`);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({}); }, json(workspace({ draft: draft(), questions: [question({ reply: { body: original.body, created_at: '2026-09-18T10:02:00Z' } })] })));
  f.submit('[data-question-form=reply]'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Unsaved owner title');
  assert.equal(f.doc.querySelector('[data-question-form=reply]'), null);
  assert.match(f.text(), /Synthetic owner reply/);
});

test('XSS in release, filename, question and reply is text, never executable markup', async t => {
  const attack = '<img src=x onerror="window.injected=true"><script>window.injected=true</script>';
  const value = draft(); value.rights[0].title = attack; value.rights[0].artist = '"><svg onload=alert(1)>';
  const documents = [{ document_id: ID(5), filename: attack, status: 'accepted_for_review' }];
  value.document_ids = [ID(5)];
  const f = fixture(t);
  await f.open(workspace({ role: 'reviewer', draft: value, documents, capabilities: { document_upload: true, toolost: false }, questions: [question({ body: attack, reply: { body: attack, created_at: '2026-09-18T10:01:00Z' } })] }));
  assert.equal(f.doc.querySelectorAll('main img, main script, main svg, main [onerror], main [onload]').length, 0);
  assert.equal(f.win.injected, undefined);
  assert.ok(f.text().includes(attack));
  assert.equal(f.get('[data-download]').dataset.download, ID(5));
});

test('documents can only be selected when accepted; processing status is not a rights claim', async t => {
  const f = fixture(t);
  const documents = ['accepted_for_review', 'scanning', 'quarantined', 'rejected'].map((status, index) => ({ document_id: ID(10 + index), filename: `synthetic-${index}.csv`, status }));
  await f.open(workspace({ draft: draft(), documents }));
  assert.equal(f.get('[data-document="0"]').disabled, false);
  for (const index of [1, 2, 3]) assert.equal(f.get(`[data-document="${index}"]`).disabled, true);
  f.click('[data-document="0"]');
  f.queue.push(call => {
    assert.deepEqual(call.body.draft.document_ids, [ID(10)]);
    f.queue.push(json(workspace({ draft: call.body.draft, documents, revision: 1 })));
    return json({ revision: 1 });
  });
  f.submit('#draft-form'); await f.idle();
  assert.doesNotMatch(f.text(), /verified/i);
});

test('opt-in synthetic upload uses raw File and the same UUID on retry; no scan is implied', async t => {
  const f = fixture(t);
  await f.open(workspace({ draft: draft(), capabilities: { document_upload: true, toolost: false } }));
  const file = new f.win.File(['synthetic,csv'], 'fictional statement.csv');
  f.selectFile(file);
  f.queue.push(() => { throw Error('offline'); });
  f.submit('#upload-form'); await f.idle();
  const first = f.calls.at(-1);
  assert.equal(first.body, file);
  assert.equal(first.options.headers['X-Document-Name'], 'fictional%20statement.csv');
  assert.equal(f.get('#synthetic-file').disabled, true);
  f.queue.push(call => {
    assert.equal(call.body, file);
    assert.equal(call.options.headers['X-Upload-Id'], first.options.headers['X-Upload-Id']);
    return json({ document_id: ID(5), status: 'quarantined' }, 202);
  });
  f.submit('#upload-form'); await f.idle();
  assert.match(f.text(), /Upload recorded\. Document status: Awaiting checks/);
  assert.equal(f.calls.filter(call => call.path.endsWith('/documents')).length, 2);
  assert.equal(f.doc.querySelector('[data-document]'), null);
});

test('upload rejects invalid types and large files; no upload control after submission', async t => {
  const f = fixture(t);
  await f.open(workspace({ draft: draft(), capabilities: { document_upload: true, toolost: false } }));
  f.selectFile(new f.win.File(['script'], 'synthetic.js'));
  assert.match(f.text(), /Choose a synthetic PDF/);
  const large = new f.win.File(['x'], 'synthetic.csv');
  Object.defineProperty(large, 'size', { value: 25 * 1024 * 1024 + 1 });
  f.selectFile(large);
  assert.equal(f.get('#upload-button').disabled, true);
  assert.equal(f.calls.length, 2);
  f.queue.push(json(workspace({ draft: draft(), submission: submitted(), capabilities: { document_upload: true, toolost: false } })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.doc.querySelector('input[type=file]'), null);
  assert.match(f.text(), /upload is locked/);
});

test('logout clears immediately; a late request cannot repopulate the UI even if logout fails', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.set('#title-0', 'PRIVATE_LOGOUT');
  const pending = deferred(); f.queue.push(() => pending.promise);
  f.submit('#draft-form');
  f.queue.push(() => { throw Error('offline'); });
  f.click('[data-action=logout]');
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.doesNotMatch(f.text(), /PRIVATE_LOGOUT|Synthetic release/);
  await f.idle();
  assert.match(f.text(), /server logout could not be confirmed/);
  pending.resolve(json({ revision: 1 }));
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.calls.at(-1).options.method, 'DELETE');
  assert.equal(f.calls.at(-1).options.headers['X-CSRF-Token'], 'synthetic-csrf');
});

test('deletion requires confirmation and describes a request, not completed erasure', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.click('[data-action=delete]');
  assert.equal(f.calls.length, 2);
  assert.equal(f.doc.activeElement.id, 'confirmation');
  f.click('[data-action=cancel]');
  f.click('[data-action=delete]');
  f.queue.push(json({ status: 'deletion_requested', erasure_completed: false }));
  f.click('[data-action=confirm-delete]'); await f.idle();
  assert.equal(f.calls.at(-1).path, '/api/portal/deletion-request');
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.match(f.text(), /Erasure is not complete/);
  assert.doesNotMatch(f.text(), /Synthetic release/);
});

test('expired invitation recovery uses remembered workspace and generic original-email response', async t => {
  const f = fixture(t);
  f.queue.push(json({}, 401));
  f.click('[data-action=open]'); await f.idle();
  assert.ok(f.doc.querySelector('#access-form'));
  assert.equal(f.doc.querySelector('[data-action=open]'), null);
  f.set('#recovery-email', 'someone@real.invalid'); f.submit('#access-form');
  assert.equal(f.calls.length, 1);
  f.set('#recovery-email', 'synthetic@example.com');
  f.queue.push(call => {
    assert.deepEqual(call.body, { workspace_id: ID(1), email: 'synthetic@example.com' });
    assert.equal(call.options.headers['X-CSRF-Token'], undefined);
    return json({ status: 'request_received' }, 202);
  });
  f.submit('#access-form'); await f.idle();
  assert.match(f.text(), /Request recorded\. In this integration test no real email is sent/);
  assert.match(f.text(), /A usable link must be delivered/);
  assert.equal(f.get('#recovery-email').value, '');
  assert.equal(f.doc.querySelector('#draft-form'), null);
});

test('page suspension wipes private data; restored page does not auto-refresh', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.win.dispatchEvent(new f.win.Event('pagehide'));
  assert.equal(f.doc.querySelector('#draft-form'), null);
  f.win.dispatchEvent(new f.win.PageTransitionEvent('pageshow', { persisted: true }));
  assert.equal(f.calls.length, 2);
  assert.doesNotMatch(f.text(), /Synthetic release/);
});

test('missing required contract fields fail closed, not with an unbounded session', async t => {
  const f = fixture(t);
  const value = workspace(); delete value.session_expires_at;
  f.queue.push(json({ csrf: 'csrf' }), json(value));
  f.click('[data-action=open]'); await f.idle();
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.match(f.text(), /response is incomplete or unsupported/);
  assert.throws(() => validateWorkspace(workspace({ role: 'admin' })));
  assert.throws(() => validateWorkspace(workspace({ questions: [question({ question_id: '../../bad' })] })));
});

test('static shell uses only approved local assets, persistent notice, labels and responsive styles', async () => {
  const dom = new JSDOM(html);
  const doc = dom.window.document;
  for (const element of doc.querySelectorAll('[src], link[href]')) assert.match(element.getAttribute('src') || element.getAttribute('href'), /^\/workspace\//);
  assert.equal(doc.querySelector('meta[name=referrer]').content, 'no-referrer');
  assert.match(doc.querySelector('.preview-notice').textContent, /Integration test.*Synthetic/);
  const css = await readFile(new URL('./portal.css', import.meta.url), 'utf8');
  assert.match(css, /max-width: 560px/);
  assert.match(css, /focus-visible/);
  assert.match(css, /position: sticky/);
  dom.window.close();
});

test('legacy release references and null optional titles round-trip without sending empty strings', async t => {
  const value = draft();
  Object.assign(value.rights[0], { release_reference: 'release-one', title: null, artist: null });
  const f = fixture(t); await f.open(workspace({ draft: value }));
  assert.equal(f.get('#title-0').maxLength, 240);
  assert.equal(f.get('#artist-0').maxLength, 240);
  f.set('#title-0', '   ');
  f.queue.push(call => {
    assert.equal(call.body.draft.rights[0].title, null);
    assert.equal(call.body.draft.rights[0].artist, null);
    assert.equal(call.body.draft.rights[0].release_reference, 'release-one');
    f.queue.push(json(workspace({ draft: call.body.draft, revision: 1 })));
    return json({ revision: 1 });
  });
  f.submit('#draft-form'); await f.idle();
  assert.equal(f.get('#title-0').value, '');
});

test('failed confirmed refresh does not discard draft edits or unsent replies', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), questions: [question()] }));
  f.set('#artist-0', 'Keep this synthetic edit');
  f.set(`#body-${ID(8)}`, 'Keep this unsent reply');
  f.click('[data-action=refresh]');
  f.queue.push(json({}, 503));
  f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.get('#artist-0').value, 'Keep this synthetic edit');
  assert.equal(f.get(`#body-${ID(8)}`).value, 'Keep this unsent reply');
});

test('refreshing an unresolved message retains the exact request and its visible body', async t => {
  const f = fixture(t); await f.open(workspace({ role: 'reviewer', draft: draft() }));
  f.set('#body-new', 'Synthetic uncertain message');
  f.queue.push(() => { throw Error('offline'); });
  f.submit('[data-question-form=question]'); await f.idle();
  const original = f.calls.at(-1).body;
  f.click('[data-action=refresh]');
  f.queue.push(json(workspace({ role: 'reviewer', draft: draft() })));
  f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.get('#body-new').value, original.body);
  f.queue.push(call => { assert.deepEqual(call.body, original); return json({}); }, json(workspace({ role: 'reviewer', draft: draft(), questions: [question({ body: original.body })] })));
  f.submit('[data-question-form=question]'); await f.idle();
});

test('upload retry accepts all processed statuses and releases the file to allow continuing', async t => {
  for (const status of ['scanning', 'accepted_for_review', 'rejected']) {
    await t.test(status, async t => {
      const f = fixture(t);
      await f.open(workspace({ draft: draft(), capabilities: { document_upload: true, toolost: false } }));
      const file = new f.win.File(['synthetic'], 'test.csv');
      f.selectFile(file);
      f.queue.push(() => { throw Error('lost acknowledgement'); });
      f.submit('#upload-form'); await f.idle();
      const id = f.calls.at(-1).options.headers['X-Upload-Id'];
      f.queue.push(call => { assert.equal(call.options.headers['X-Upload-Id'], id); return json({ document_id: ID(5), status }, 202); });
      f.submit('#upload-form'); await f.idle();
      assert.match(f.text(), /Upload recorded/);
      assert.equal(f.get('#synthetic-file').disabled, false);
      assert.equal(f.get('#draft-form > fieldset').disabled, false);
      assert.doesNotMatch(f.text(), /Selected: test.csv/);
      f.click('#consent');
      assert.equal(f.get('[data-action=submit]').disabled, false);
    });
  }
});

test('definitively rejected upload permits replacing or clearing the file', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), capabilities: { document_upload: true, toolost: false } }));
  f.selectFile(new f.win.File(['not-pdf'], 'test.pdf'));
  f.queue.push(json({}, 422)); f.submit('#upload-form'); await f.idle();
  assert.equal(f.get('#synthetic-file').disabled, false);
  f.click('[data-action=clear-file]');
  assert.equal(f.get('#upload-button').disabled, true);
});

test('download 401 uses the same privacy boundary and clears the private view', async t => {
  const f = fixture(t);
  const value = draft(); value.document_ids = [ID(5)];
  await f.open(workspace({ role: 'reviewer', draft: value, documents: [{ document_id: ID(5), filename: 'synthetic.csv', status: 'accepted_for_review' }], capabilities: { document_upload: true, toolost: false } }));
  f.queue.push(json({}, 401)); f.click('[data-download]'); await f.idle();
  assert.equal(f.calls.at(-1).path, `/api/portal/documents/${ID(5)}`);
  assert.doesNotMatch(f.text(), /synthetic.csv|Synthetic release/);
  assert.equal(f.doc.querySelector('[data-download]'), null);
});

test('downloads are attachments only, never rendered, and their object URLs are revoked on clearing', async t => {
  const f = fixture(t);
  const value = draft(); value.document_ids = [ID(5)];
  await f.open(workspace({ role: 'reviewer', draft: value, documents: [{ document_id: ID(5), filename: 'synthetic.csv', status: 'accepted_for_review' }], capabilities: { document_upload: true, toolost: false } }));
  const revoked = [];
  let attachment;
  f.win.URL.createObjectURL = blob => { assert.equal(blob.type, 'application/octet-stream'); return 'blob:synthetic-test'; };
  f.win.URL.revokeObjectURL = url => revoked.push(url);
  f.win.HTMLAnchorElement.prototype.click = function () { attachment = { href: this.href, download: this.download }; };
  f.queue.push(new Response('synthetic,csv', { headers: { 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="catalog-document"' } }));
  f.click('[data-download]'); await f.idle();
  assert.deepEqual(attachment, { href: 'blob:synthetic-test', download: 'catalog-document' });
  assert.equal(f.doc.querySelector('iframe, object, embed, a[download]'), null);
  f.win.dispatchEvent(new f.win.Event('pagehide'));
  assert.deepEqual(revoked, ['blob:synthetic-test']);
});

test('new server revision under unsaved owner edits blocks overwriting after a reply refresh', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft(), questions: [question()] }));
  f.set('#title-0', 'Local unsaved title');
  f.set(`#body-${ID(8)}`, 'Synthetic reply');
  f.queue.push(json({}), json(workspace({ draft: draft(), revision: 9, questions: [question({ reply: { body: 'Synthetic reply', created_at: '2026-09-18T10:01:00Z' } })] })));
  f.submit('[data-question-form=reply]'); await f.idle();
  assert.equal(f.get('#title-0').value, 'Local unsaved title');
  assert.equal(f.get('#draft-form > fieldset').disabled, true);
});

test('an acknowledged submission without a snapshot remains locked rather than claiming completion', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.click('#consent');
  f.queue.push(json({ submission_id: ID(9) }), json(workspace({ draft: draft() })));
  f.click('[data-action=submit]'); await f.idle();
  assert.match(f.text(), /snapshot is not available yet/);
  assert.equal(f.get('#draft-form > fieldset').disabled, true);
  assert.equal(f.get('[data-action=submit]').disabled, true);
});

test('role changes clear the current view instead of merging owner and reviewer state', async t => {
  const f = fixture(t); await f.open(workspace({ draft: draft() }));
  f.queue.push(json(workspace({ role: 'reviewer', draft: draft() })));
  f.click('[data-action=refresh]'); await f.idle();
  assert.match(f.text(), /Workspace access changed/);
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.doc.querySelector('#body-new'), null);
});

test('save 404 after cross-session deletion clears private data and disables further editing', async t => {
  const f = fixture(t);
  await f.open(workspace({ draft: draft(), questions: [question()] }));
  f.set('#title-0', 'PRIVATE_DELETED_WORKSPACE_DRAFT');
  f.set(`#body-${ID(8)}`, 'PRIVATE_DELETED_WORKSPACE_REPLY');
  const detachedTitle = f.get('#title-0');
  const detachedReply = f.get(`#body-${ID(8)}`);
  f.queue.push(call => {
    assert.equal(call.path, '/api/portal/draft');
    return json({ error: 'workspace_unavailable' }, 404);
  });
  f.submit('#draft-form'); await f.idle();
  assert.equal(f.doc.querySelector('#draft-form'), null);
  assert.equal(f.doc.querySelector('[data-question-form]'), null);
  assert.equal(f.doc.querySelector('[data-action=submit]'), null);
  assert.equal(detachedTitle.value, '');
  assert.equal(detachedReply.value, '');
  assert.equal(f.get('#progress').textContent, '');
  assert.equal(f.timers.size, 0);
  assert.doesNotMatch(f.doc.documentElement.outerHTML, /PRIVATE_DELETED_|Synthetic release|Test artist|Please explain|workspace_unavailable/);
  assert.match(f.text(), /Private information has been cleared/);
  assert.equal(f.calls.length, 3);
  f.queue.push(json(workspace()));
  f.click('[data-action=refresh]'); await f.idle();
  assert.equal(f.get('#title-0').value, '');
  assert.equal(f.doc.querySelector('[data-question-form]'), null);
});

test('lost reply acknowledgement then refresh with committed reply retains same-ID retry and allows the next reply after acknowledgement', async t => {
  const f = fixture(t);
  const server = workspace({ draft: draft(), questions: [question(), question({ question_id: ID(18), body: 'Second synthetic question' })] });
  const firstForm = `[data-question-form="reply"][data-question-id="${ID(8)}"]`;
  const secondForm = `[data-question-form="reply"][data-question-id="${ID(18)}"]`;
  await f.open(server);
  f.set(`#body-${ID(8)}`, 'Synthetic committed reply');
  f.queue.push(call => {
    server.questions[0].reply = { body: call.body.body, created_at: '2026-09-18T10:01:00Z' };
    throw Error('Acknowledgement lost after commit');
  });
  f.submit(firstForm); await f.idle();
  const original = clone(f.calls.at(-1).body);
  f.click('[data-action=refresh]');
  f.queue.push(json(server));
  f.click('[data-action=confirm-refresh]'); await f.idle();
  assert.equal(f.calls.filter(call => call.path.endsWith('/reply')).length, 1);
  assert.match(f.text(), /earlier request is still unresolved/);
  assert.equal(f.get(`${firstForm} textarea`).value, original.body);
  assert.equal(f.get(`${firstForm} textarea`).readOnly, true);
  assert.equal(f.get(`${firstForm} button`).disabled, false);
  assert.equal(f.get(`${secondForm} button`).disabled, true);
  assert.doesNotMatch(f.get('#screen-message').textContent, /Message received/);
  f.queue.push(call => {
    assert.equal(call.path, `/api/portal/questions/${ID(8)}/reply`);
    assert.deepEqual(call.body, original);
    return json({ created: false });
  }, json(server));
  f.submit(firstForm); await f.idle();
  assert.equal(f.doc.querySelector(firstForm), null);
  assert.equal(f.get(`${secondForm} button`).disabled, false);
  f.set(`#body-${ID(18)}`, 'Synthetic second reply');
  f.queue.push(call => {
    assert.equal(call.path, `/api/portal/questions/${ID(18)}/reply`);
    assert.notEqual(call.body.request_id, original.request_id);
    assert.equal(call.body.body, 'Synthetic second reply');
    server.questions[1].reply = { body: call.body.body, created_at: '2026-09-18T10:02:00Z' };
    f.queue.push(json(server));
    return json({ created: true });
  });
  f.submit(secondForm); await f.idle();
  assert.equal(f.doc.querySelector('[data-question-form=reply]'), null);
  assert.match(f.text(), /Synthetic second reply/);
});

test('409 reply conflict requires authoritative refresh and explicit message-only discard', async t => {
  for (const existingBody of ['A different immutable answer', 'Synthetic attempted reply']) {
    await t.test(existingBody, async t => {
      const f = fixture(t);
      const server = workspace({ draft: draft(), questions: [question(), question({ question_id: ID(18), body: 'Second synthetic question' })] });
      const firstForm = `[data-question-form="reply"][data-question-id="${ID(8)}"]`;
      const secondForm = `[data-question-form="reply"][data-question-id="${ID(18)}"]`;
      await f.open(server);
      f.set('#title-0', 'Preserve unrelated draft edit');
      f.set(`#body-${ID(18)}`, 'Preserve unrelated unsent reply');
      f.set(`#body-${ID(8)}`, 'Synthetic attempted reply');
      f.queue.push(() => { throw Error('Uncertain request'); });
      f.submit(firstForm); await f.idle();
      const original = clone(f.calls.at(-1).body);
      f.queue.push(call => {
        assert.deepEqual(call.body, original);
        server.questions[0].reply = { body: existingBody, created_at: '2026-09-18T10:01:00Z' };
        return json({ error: 'reply_locked' }, 409);
      });
      f.submit(firstForm); await f.idle();
      assert.equal(f.doc.querySelector('[data-action=discard-unresolved-reply]'), null);
      assert.equal(f.get(`${secondForm} button`).disabled, true);
      f.queue.push(json(server));
      f.click('[data-action=refresh-reply-status]'); await f.idle();
      assert.equal(f.get('#title-0').value, 'Preserve unrelated draft edit');
      assert.equal(f.get(`#body-${ID(18)}`).value, 'Preserve unrelated unsent reply');
      assert.equal(f.get(`${firstForm} textarea`).value, original.body);
      assert.equal(f.get(`${firstForm} button`).disabled, true);
      assert.ok(f.get('#questions .reply').textContent.includes(existingBody));
      assert.equal(f.get(`${secondForm} button`).disabled, true);
      const beforeDiscard = f.calls.length;
      f.click('[data-action=discard-unresolved-reply]');
      assert.equal(f.calls.length, beforeDiscard);
      assert.equal(f.doc.querySelector(firstForm), null);
      assert.equal(f.get(`${secondForm} button`).disabled, false);
      assert.equal(f.get('#title-0').value, 'Preserve unrelated draft edit');
      assert.equal(f.get(`#body-${ID(18)}`).value, 'Preserve unrelated unsent reply');
      assert.match(f.get('#screen-message').textContent, /not confirmed saved/);
      f.queue.push(call => {
        assert.equal(call.path, `/api/portal/questions/${ID(18)}/reply`);
        assert.notEqual(call.body.request_id, original.request_id);
        assert.equal(call.body.body, 'Preserve unrelated unsent reply');
        server.questions[1].reply = { body: call.body.body, created_at: '2026-09-18T10:02:00Z' };
        f.queue.push(json(server));
        return json({ created: true });
      });
      f.submit(secondForm); await f.idle();
      assert.equal(f.doc.querySelector(secondForm), null);
      assert.equal(f.get('#title-0').value, 'Preserve unrelated draft edit');
    });
  }
});

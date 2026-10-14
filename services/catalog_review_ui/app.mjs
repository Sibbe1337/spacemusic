import { createClient, PortalError, errorMessage } from './client.mjs';

const UUID = /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i;
const REFERENCE = /^[A-Za-z0-9_-]{1,120}$/;
const DOCUMENT_STATUSES = ['quarantined', 'scanning', 'accepted_for_review', 'rejected'];
const OWNERSHIP = ['known', 'unknown'];
const SCOPE = ['masters', 'publishing', 'both', 'unknown'];
const OBLIGATIONS = ['none_declared', 'present', 'unknown'];
const copy = value => JSON.parse(JSON.stringify(value));
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const text = (value, max = 300) => typeof value === 'string' && value.length <= max;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const validShare = value => typeof value === 'string' && /^\d{1,3}(?:\.\d{1,2})?$/.test(value) && Number(value) > 0 && Number(value) <= 100;
const validDate = value => typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));

function draftShape(draft) {
  return object(draft) && draft.source === 'documents' && draft.future_music_excluded === true
    && Array.isArray(draft.rights) && draft.rights.length > 0 && draft.rights.length <= 200
    && draft.rights.every(right => object(right) && typeof right.release_reference === 'string' && REFERENCE.test(right.release_reference)
      && text(right.title, 240) && text(right.artist, 240) && OWNERSHIP.includes(right.ownership)
      && SCOPE.includes(right.rights_scope) && OBLIGATIONS.includes(right.obligations)
      && (right.ownership === 'unknown' ? right.share_percent === null : validShare(right.share_percent)))
    && new Set(draft.rights.map(right => right.release_reference)).size === draft.rights.length
    && Array.isArray(draft.document_ids) && draft.document_ids.length <= 40
    && draft.document_ids.every(id => typeof id === 'string' && UUID.test(id))
    && new Set(draft.document_ids).size === draft.document_ids.length;
}

function documentsShape(documents) {
  return Array.isArray(documents) && documents.length <= 40
    && documents.every(doc => object(doc) && UUID.test(doc.document_id) && text(doc.filename, 500) && text(doc.status, 80)
      && (doc.question_id === null || UUID.test(doc.question_id)))
    && new Set(documents.map(doc => doc.document_id)).size === documents.length;
}

function replyShape(reply, question, submission) {
  if (reply === null) return true;
  if (!object(reply) || !text(reply.body, 4000) || !validDate(reply.created_at)
    || !Array.isArray(reply.document_ids) || reply.document_ids.length > 40
    || !reply.document_ids.every(id => typeof id === 'string' && UUID.test(id))
    || new Set(reply.document_ids).size !== reply.document_ids.length) return false;
  if (reply.supplement === null) return reply.document_ids.length === 0;
  const supplement = reply.supplement;
  return question.request_documents && object(supplement) && UUID.test(supplement.supplement_id)
    && Number.isSafeInteger(supplement.version) && supplement.version > 0
    && UUID.test(supplement.submission_id) && supplement.submission_id === submission?.submission_id && validDate(supplement.created_at)
    && documentsShape(supplement.documents) && supplement.documents.length > 0
    && supplement.documents.length === reply.document_ids.length
    && supplement.documents.every(item => reply.document_ids.includes(item.document_id)
      && item.status === 'accepted_for_review');
}

export function validateWorkspace(view) {
  if (object(view)) {
    view = copy(view);
    const normalizeDocuments = documents => {
      if (Array.isArray(documents)) for (const item of documents) {
        if (object(item) && item.question_id === undefined) item.question_id = null;
      }
    };
    normalizeDocuments(view.documents);
    normalizeDocuments(view.submission?.snapshot?.documents);
    if (Array.isArray(view.questions)) for (const question of view.questions) {
      if (!object(question)) continue;
      if (question.request_documents === undefined) question.request_documents = false;
      if (object(question.reply)) {
        if (question.reply.document_ids === undefined) question.reply.document_ids = [];
        if (question.reply.supplement === undefined) question.reply.supplement = null;
        normalizeDocuments(question.reply.supplement?.documents);
      }
    }
    for (const draft of [view.draft, view.submission?.snapshot?.draft]) {
      if (Array.isArray(draft?.rights)) draft.rights = draft.rights.map(right => object(right)
        ? { title: '', artist: '', rights_scope: 'unknown', obligations: 'unknown', ...right,
          title: right.title ?? '', artist: right.artist ?? '' } : right);
    }
  }
  if (!object(view) || !text(view.workspace_id, 120) || !view.workspace_id
    || (view.environment !== undefined && !['test', 'staging', 'production'].includes(view.environment))
    || !['owner', 'reviewer'].includes(view.role) || !Number.isSafeInteger(view.revision) || view.revision < 0
    || !validDate(view.session_expires_at) || !text(view.csrf, 512) || !view.csrf || /[\r\n]/.test(view.csrf)
    || !text(view.review_status, 80) || !view.review_status
    || !object(view.capabilities) || typeof view.capabilities.document_upload !== 'boolean' || typeof view.capabilities.toolost !== 'boolean'
    || !(view.draft === null || draftShape(view.draft)) || !documentsShape(view.documents)
    || !Array.isArray(view.questions) || view.questions.length > 1000
    || !view.questions.every(question => object(question) && UUID.test(question.question_id) && text(question.body, 4000)
      && typeof question.request_documents === 'boolean' && validDate(question.created_at)
      && replyShape(question.reply, question, view.submission))
    || new Set(view.questions.map(question => question.question_id)).size !== view.questions.length
    || !(view.submission === null || (object(view.submission) && text(view.submission.submission_id, 120)
      && Number.isSafeInteger(view.submission.revision) && view.submission.revision >= 0 && validDate(view.submission.created_at)
      && object(view.submission.snapshot) && draftShape(view.submission.snapshot.draft)
      && documentsShape(view.submission.snapshot.documents)))) throw new PortalError('contract');
  const documents = [...view.documents, ...(view.submission?.snapshot.documents ?? []),
    ...view.questions.flatMap(question => question.reply?.supplement?.documents ?? [])];
  if (new Set(documents.map(item => item.document_id)).size > 40
    || view.submission?.snapshot.documents.some(item => item.question_id !== null)) throw new PortalError('contract');
  const supplementIds = new Set();
  for (const question of view.questions) {
    const supplement = question.reply?.supplement;
    if (!supplement) continue;
    if (supplementIds.has(supplement.supplement_id)) throw new PortalError('contract');
    supplementIds.add(supplement.supplement_id);
    for (const item of supplement.documents) {
      if (item.question_id !== null && view.documents.some(current => current.document_id === item.document_id && current.question_id !== item.question_id)) throw new PortalError('contract');
    }
  }
  return copy(view);
}

function newRight(uuid) {
  return { release_reference: uuid(), title: '', artist: '', ownership: 'unknown', share_percent: null, rights_scope: 'unknown', obligations: 'unknown' };
}

const docStatus = status => ({ accepted_for_review: 'Accepted for review', quarantined: 'Awaiting checks', scanning: 'Checks in progress', rejected: 'Not accepted' })[status] || 'Not available for selection';
const reviewStatus = status => ({ not_submitted: 'Not submitted', submitted: 'Submitted', needs_information: 'Information requested', under_review: 'Under review' })[status] || 'Review status unavailable';
const scopeLabel = value => ({ masters: 'Masters', publishing: 'Publishing', both: 'Masters and publishing', unknown: 'Not yet known' })[value];
const obligationsLabel = value => ({ none_declared: 'None declared', present: 'Existing obligations', unknown: 'Not yet known' })[value];
const options = (values, selected) => values.map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('');

export function createApp({ window: win = globalThis.window, client, now = () => Date.now(), uuid, schedule, unschedule } = {}) {
  // Capture once, then remove both fragment and query before any request or render.
  let invitation = new URLSearchParams(win.location.hash.slice(1)).get('invitation');
  let recoveryWorkspace = UUID.test(invitation?.split('.')[0]) ? invitation.split('.')[0] : null;
  let cleanAddress = true;
  try { win.history.replaceState(null, '', '/workspace/'); }
  catch { invitation = null; recoveryWorkspace = null; cleanAddress = false; }
  if (invitation && (invitation.length < 70 || invitation.length > 160)) invitation = null;
  client ??= createClient({ fetchImpl: win.fetch.bind(win) });
  uuid ??= () => win.crypto.randomUUID();
  schedule ??= (fn, delay) => win.setTimeout(fn, delay);
  unschedule ??= id => win.clearTimeout(id);
  const doc = win.document;
  // Only the server-rendered shell can enable pilot copy; URLs never choose it.
  const production = doc.documentElement.dataset.environment === 'production';
  const wording = (testCopy, pilotCopy) => production ? pilotCopy : testCopy;
  const main = doc.querySelector('#content');
  const rail = doc.querySelector('#progress');
  const announcement = doc.querySelector('#announcement');
  let view = null;
  let draft = null;
  let dirty = false;
  let needsRefresh = false;
  let pending = null;
  let consent = false;
  let busy = false;
  let confirmation = null;
  let message = '';
  let isError = false;
  let timer = null;
  let epoch = 0;
  let destroyed = false;
  let deletionUncertain = false;
  let recoveryEmail = '';
  let recoveryAvailable = false;
  let upload = null;
  let requestDocuments = false;
  let interest = null;
  const questionBodies = new Map();
  const questionDocuments = new Map();
  const questionUploads = new Map();
  const recordedUploads = new Set();
  const downloadUrls = new Set();

  const locked = () => Boolean(view?.submission || pending?.kind === 'submission');
  const hasStartedUpload = () => Boolean(upload?.started || [...questionUploads.values()].some(item => item.started));
  const canEdit = () => view?.role === 'owner' && !locked() && !needsRefresh && !pending && !busy && !hasStartedUpload();
  const hasUnsaved = () => dirty || [...questionBodies.values()].some(body => body.length > 0);
  const questionById = id => view?.questions.find(question => question.question_id === id);
  const openDocumentQuestion = id => Boolean(view?.role === 'owner' && view.submission && view.capabilities.document_upload
    && questionById(id)?.request_documents && questionById(id).reply === null);
  const canStageDocuments = id => openDocumentQuestion(id) && !busy && !needsRefresh && !pending && !hasStartedUpload();
  const scopedDocuments = id => view.documents.filter(item => item.question_id === id);
  const documentCount = () => new Set([...recordedUploads, ...(view?.documents ?? []).map(item => item.document_id),
    ...(view?.submission?.snapshot.documents ?? []).map(item => item.document_id),
    ...(view?.questions ?? []).flatMap(question => question.reply?.document_ids ?? [])]).size;
  const date = value => new Date(value).toLocaleString();
  const focus = id => doc.getElementById(id)?.focus();

  function wipe() {
    for (const input of main.querySelectorAll('input, textarea')) {
      input.value = '';
      input.removeAttribute('value');
      if (input.type === 'checkbox') input.checked = false;
      if (input.tagName === 'TEXTAREA') input.textContent = '';
    }
    main.replaceChildren();
    rail.replaceChildren();
    announcement.textContent = '';
  }

  function clearPrivate(reason, { keepClient = false, recovery = false } = {}) {
    const recoveryId = recovery && view?.role === 'owner' ? view.workspace_id : recovery ? recoveryWorkspace : null;
    epoch += 1;
    unschedule(timer);
    timer = null;
    if (!keepClient) client.clear();
    invitation = null;
    recoveryWorkspace = recoveryId;
    recoveryAvailable = Boolean(recoveryId);
    recoveryEmail = '';
    upload = null;
    for (const url of downloadUrls) win.URL.revokeObjectURL(url);
    downloadUrls.clear();
    view = null;
    draft = null;
    dirty = false;
    needsRefresh = false;
    pending = null;
    consent = false;
    busy = false;
    confirmation = null;
    deletionUncertain = false;
    questionBodies.clear();
    questionDocuments.clear();
    questionUploads.clear();
    recordedUploads.clear();
    requestDocuments = false;
    interest = null;
    message = reason;
    isError = false;
    wipe();
    if (!destroyed) render('screen-message');
  }

  function checkExpiry() {
    if (view && Date.parse(view.session_expires_at) <= now()) {
      clearPrivate('Your session expired. Private information and unsaved entries have been cleared. Open a new invitation or refresh an existing session.', { recovery: true });
      return true;
    }
    return false;
  }

  function armExpiry() {
    unschedule(timer);
    if (checkExpiry() || !view) return;
    timer = schedule(() => { if (!checkExpiry()) armExpiry(); }, Math.min(Date.parse(view.session_expires_at) - now(), 2147483647));
  }

  function feedback(value, error = false) {
    message = value;
    isError = error;
  }

  function failure(error) {
    // Error bodies are deliberately ignored, so every 404 fails closed.
    if ([401, 403, 404].includes(error?.status)) {
      clearPrivate(error?.status === 404 ? 'Workspace access could not be confirmed. Private information has been cleared. Refresh explicitly to check access.' : errorMessage(error), { recovery: error?.status === 401 });
      return;
    }
    if (error?.status === 409) needsRefresh = true;
    if (error?.status === 409 && pending?.kind === 'reply' && pending.conflict) {
      feedback('The server reports an existing immutable reply. Your attempted reply has not been confirmed saved. Refresh to review the existing answer before discarding only this unresolved reply.', true);
      return;
    }
    feedback(errorMessage(error), true);
  }

  async function run(action, fn) {
    if (busy || destroyed || checkExpiry() || !cleanAddress) return;
    const current = epoch;
    busy = true;
    feedback(`${action}...`);
    render();
    try { await fn(current); }
    catch (error) { if (epoch === current) failure(error); }
    finally {
      if (epoch === current && !destroyed) {
        busy = false;
        if (!checkExpiry()) render('screen-message');
      }
    }
  }

  async function load(current, { discard = false, replaceDraft = false } = {}) {
    let incoming;
    try { incoming = validateWorkspace(await client.workspace()); }
    catch (error) {
      if (current === epoch) failure(error);
      return false;
    }
    if (current !== epoch || destroyed || checkExpiry()) return false;
    if (incoming.environment !== undefined && (incoming.environment === 'production') !== production) {
      clearPrivate('The page and workspace environments do not match. Private information has been cleared. Open the correct workspace address before continuing.');
      return false;
    }
    if (Date.parse(incoming.session_expires_at) <= now()) {
      if (incoming.role === 'owner') recoveryWorkspace = incoming.workspace_id;
      clearPrivate('Your session expired. Private information has been cleared. Open a new invitation.', { recovery: true });
      return false;
    }
    if (view && (incoming.workspace_id !== view.workspace_id || incoming.role !== view.role)) {
      clearPrivate('Workspace access changed. Private information has been cleared. Explicitly refresh to check your access.');
      return false;
    }
    // An acknowledged mutation must be visible in the subsequent authoritative GET.
    if (pending?.kind === 'submission' && pending.acknowledged && !incoming.submission) {
      feedback('Submission was acknowledged, but the updated snapshot is not available yet. Editing stays locked. Refresh again; do not create another submission.', true);
      return false;
    }
    if (pending?.kind === 'reply' && pending.acknowledged) {
      const reply = incoming.questions.find(question => question.question_id === pending.questionId)?.reply;
      if (!reply || reply.body !== pending.payload.body.trim() || reply.document_ids.length !== pending.payload.document_ids.length
        || !reply.document_ids.every(id => pending.payload.document_ids.includes(id))) {
        feedback('Reply was acknowledged, but its published version is not available yet. The original reply and document selection stay locked. Refresh again; do not send another reply.', true);
        return false;
      }
    }
    const preserveDraft = dirty && view && !discard && !replaceDraft;
    const changedUnderEdits = preserveDraft && incoming.revision !== view.revision;
    client.setCsrf(incoming.csrf);
    view = incoming;
    invitation = null;
    recoveryWorkspace = incoming.role === 'owner' ? incoming.workspace_id : null;
    recoveryAvailable = false;
    if (!preserveDraft) {
      draft = copy(incoming.draft ?? { source: 'documents', rights: [newRight(uuid)], document_ids: [], future_music_excluded: true });
      dirty = incoming.draft === null;
    }
    needsRefresh = Boolean(changedUnderEdits);
    if (pending?.kind === 'reply' && pending.conflict) {
      pending.conflictObserved = incoming.questions.some(question => question.question_id === pending.questionId && question.reply !== null);
    }
    if (discard) { questionBodies.clear(); requestDocuments = false; }
    if (pending?.acknowledged || (pending?.kind === 'submission' && incoming.submission)) {
      if (pending.key) {
        questionBodies.delete(pending.key);
        questionDocuments.delete(pending.key);
        questionUploads.delete(pending.key);
      }
      if (pending.kind === 'question') requestDocuments = false;
      pending = null;
    }
    for (const [id, item] of questionUploads) {
      if (!item.started && !openDocumentQuestion(id)) questionUploads.delete(id);
      if (item.conflict) item.conflictObserved = true;
    }
    for (const id of questionDocuments.keys()) {
      if (!openDocumentQuestion(id) && pending?.questionId !== id) questionDocuments.delete(id);
    }
    consent = pending?.kind === 'submission';
    confirmation = null;
    armExpiry();
    return true;
  }

  function errorBox() {
    return `<div id="screen-message" class="screen-message ${isError ? 'error' : 'notice'}" role="${isError ? 'alert' : 'status'}" tabindex="-1">${escape(message)}</div>`;
  }

  function entry() {
    return `<section class="screen"><p class="eyebrow">${wording('Catalog review / test access', 'Catalog review / private pilot')}</p><h1>One place for your catalog review.</h1>
      <p class="intro">${wording('Open your invitation when you are ready. This integration test accepts synthetic information only.', 'Open your invitation when you are ready. This private workspace brings your existing catalog, supporting documents and reviewer follow-up together.')}</p>${errorBox()}
      <div class="split"><div><ul class="editorial-list"><li><h2>Confirm what belongs in the review.</h2><p>Describe existing releases and your rights. Future music is excluded.</p></li><li><h3>Keep the unknowns visible.</h3><p>You can start without documents. Missing evidence remains a follow-up, not a completed check.</p></li></ul>
      ${!cleanAddress ? '<p class="error">The invitation could not be removed from the address. Close this page and reopen it in a supported browser. No request has been sent.</p>' : `<div class="actions">${invitation ? `<button class="primary" data-action="open"${busy ? ' disabled' : ''}>Open invitation</button>` : ''}<button class="secondary" data-action="refresh"${busy ? ' disabled' : ''}>Refresh existing session</button></div>`}
      <p class="fine-print">No invitation is consumed by viewing this page. If an invitation request has an uncertain outcome, try refreshing the existing session before retrying.</p></div>
      <aside class="folio"><p class="folio-label">The review scope</p><h2>Existing music.<br>Clear boundaries.</h2><dl><div><dt>Source</dt><dd>Manual, document-based review</dd></div><div><dt>Unavailable</dt><dd>${wording('Too Lost import and document upload', 'Too Lost import')}</dd></div>${production ? '<div><dt>Documents</dt><dd>Supporting uploads when enabled for your workspace.</dd></div>' : ''}<div><dt>Access</dt><dd>Owners prepare the draft. Assigned reviewers can ask questions.</dd></div></dl></aside></div>
      ${recoveryAvailable && cleanAddress ? `<section class="review-section"><h2>Request another invitation</h2><p class="section-copy">${wording('Enter the original application email, using an @example.com test address.', 'Enter the email address used for your original application.')} An active invitation is not replaced. This request does not restore your old session or entries.</p><form id="access-form" autocomplete="off" novalidate><label class="field" for="recovery-email">Original application email<input id="recovery-email" name="email" type="email" maxlength="254" value="${escape(recoveryEmail)}"${busy ? ' disabled' : ''}></label><div class="actions"><button class="secondary" type="submit"${busy ? ' disabled' : ''}>${wording('Record access request', 'Request access link')}</button></div></form></section>` : ''}
      <section id="privacy" class="privacy-controls" tabindex="-1"><h2>Privacy</h2><p class="section-copy">No browser storage or analytics. An invitation stays in memory only until it is opened, cleared, or the page closes.</p><button class="text-button" data-action="clear">Clear this page</button></section></section>`;
  }

  function rightsForm() {
    return `<form id="draft-form" novalidate autocomplete="off"><fieldset${canEdit() ? '' : ' disabled'}><legend class="sr-only">Catalog draft</legend>
      ${draft.rights.map((right, index) => `<fieldset class="release-editor"><legend>Release ${index + 1}</legend><div class="form-grid">
        <label class="field" for="title-${index}">Release title (optional)<input id="title-${index}" data-right="${index}" name="title" type="text" maxlength="240" value="${escape(right.title)}"></label>
        <label class="field" for="artist-${index}">Artist (optional)<input id="artist-${index}" data-right="${index}" name="artist" type="text" maxlength="240" value="${escape(right.artist)}"></label>
        <label class="field" for="ownership-${index}">Ownership<select id="ownership-${index}" data-right="${index}" name="ownership">${options([['unknown', 'Not yet known'], ['known', 'Known share']], right.ownership)}</select></label>
        <label class="field" for="share-${index}">Your share (%)<input id="share-${index}" data-right="${index}" name="share_percent" type="text" inputmode="decimal" maxlength="6" aria-describedby="share-hint-${index}" value="${escape(right.share_percent)}"${right.ownership === 'unknown' ? ' disabled' : ''}><small id="share-hint-${index}">More than 0, up to 100. At most two decimal places.</small></label>
        <label class="field" for="scope-${index}">Rights scope<select id="scope-${index}" data-right="${index}" name="rights_scope">${options(SCOPE.map(value => [value, scopeLabel(value)]), right.rights_scope)}</select></label>
        <label class="field" for="obligations-${index}">Existing obligations<select id="obligations-${index}" data-right="${index}" name="obligations">${options(OBLIGATIONS.map(value => [value, obligationsLabel(value)]), right.obligations)}</select></label>
      </div>${draft.rights.length > 1 ? `<button class="text-button" type="button" data-action="remove-release" data-index="${index}">Remove release ${index + 1}</button>` : ''}</fieldset>`).join('')}
      <button class="secondary" type="button" data-action="add-release"${draft.rights.length >= 200 ? ' disabled' : ''}>Add another release</button>
      <section id="evidence" class="review-section section-anchor"><h2>Supporting documents</h2><p class="section-copy">Only documents accepted for review can be selected. Acceptance is a processing status, not confirmation of rights or accuracy.</p>
        ${view.documents.some(item => item.question_id === null) ? view.documents.map((item, index) => {
          if (item.question_id !== null) return '';
          const selected = draft.document_ids.includes(item.document_id);
          const accepted = item.status === 'accepted_for_review';
          return `<label class="document-choice"><input type="checkbox" data-document="${index}"${selected ? ' checked' : ''}${accepted ? '' : ' disabled'}><span>${escape(item.filename)}<small>${docStatus(item.status)}</small></span></label>${accepted && view.capabilities.document_upload ? `<button type="button" class="text-button" data-download="${item.document_id}">Download accepted document</button>` : ''}${selected && !accepted ? `<button type="button" class="text-button" data-action="remove-document" data-index="${index}">Remove unavailable document ${index + 1} from draft</button>` : ''}`;
        }).join('') : '<p class="section-copy">No documents available. You can submit a document-free draft for follow-up.</p>'}
        ${draft.document_ids.some(id => !view.documents.some(item => item.document_id === id)) ? '<p class="error">A selected document is no longer available.</p><button type="button" class="secondary" data-action="remove-missing-documents">Remove missing document references</button>' : ''}
      </section><p class="notice">Future music is excluded. Unknown rights and missing evidence will need follow-up.</p>
      <div class="actions"><button class="primary" type="submit">Save draft</button></div></fieldset>
      <p id="form-state" class="form-state" aria-live="polite">${needsRefresh ? 'Refresh required before another change.' : dirty ? 'Unsaved changes. Save before submitting.' : 'Server draft loaded.'}</p></form>`;
  }

  function draftSummary(value) {
    if (!value) return '<p class="empty-state">The owner has not saved a draft yet.</p>';
    return `<ul class="summary-list">${value.rights.map(right => `<li><h3>${escape(right.title || 'Untitled release')}</h3><p class="section-copy">${escape(right.artist || 'Artist not entered')}</p><dl><dt>Ownership</dt><dd>${right.ownership === 'known' ? `${escape(right.share_percent)}% declared` : 'Not yet known'}</dd><dt>Rights scope</dt><dd>${scopeLabel(right.rights_scope)}</dd><dt>Obligations</dt><dd>${obligationsLabel(right.obligations)}</dd></dl></li>`).join('')}</ul><p class="notice">Future music is excluded.</p>`;
  }

  function evidenceSummary(value, documents) {
    const chosen = documents.filter(item => item.question_id === null && value?.document_ids.includes(item.document_id));
    return `<section id="evidence" class="review-section section-anchor"><h2>Supporting documents</h2>${chosen.length ? `<ul class="summary-list">${chosen.map(item => `<li>${escape(item.filename)} <span class="status-tag">${docStatus(item.status)}</span>${item.status === 'accepted_for_review' && view.capabilities.document_upload ? ` <button class="text-button" data-download="${item.document_id}"${busy ? ' disabled' : ''}>Download accepted document</button>` : ''}</li>`).join('')}</ul><p class="section-copy">Document status is not confirmation of ownership or accuracy.</p>` : '<p class="notice warm">Missing evidence: no documents are attached. Further evidence is needed for review.</p>'}</section>`;
  }

  function submissionSection() {
    if (view.role !== 'owner' || view.submission) return '';
    const retry = pending?.kind === 'submission';
    return `<section class="review-section"><h2>Send this version for review</h2><p class="section-copy">Submission locks a snapshot of the saved draft. It does not establish rights or complete a review.</p>
      ${!draft.document_ids.length ? '<p class="notice warm">No evidence is attached. The reviewer will need to follow up.</p>' : ''}
      <label class="check-line"><input id="consent" type="checkbox"${consent ? ' checked' : ''}${busy || retry ? ' disabled' : ''}>I agree to send this saved version for catalog review, with future music excluded and missing evidence left for follow-up.</label>
      <button class="primary" data-action="submit"${busy || needsRefresh || dirty || !view.draft || !consent || upload || (pending && !retry) || pending?.acknowledged ? ' disabled' : ''}>${retry ? 'Retry same submission' : 'Submit saved draft'}</button>
      ${retry ? '<p class="fine-print">The same request reference and revision are retained in memory for retries. Editing remains locked while the outcome is unresolved.</p>' : ''}</section>`;
  }

  function questionForm(key, label, action, questionId = '') {
    const retry = pending?.key === key;
    const disabled = busy || needsRefresh || hasStartedUpload() || Boolean(pending && !retry) || Boolean(pending?.acknowledged) || Boolean(pending?.conflict);
    const request = retry ? pending.payload.request_documents : requestDocuments;
    const attachments = action === 'reply' ? replyDocuments(questionId, retry, disabled) : `<label class="check-line"><input id="request-documents" type="checkbox"${request ? ' checked' : ''}${disabled || retry || !view.submission || !view.capabilities.document_upload ? ' disabled' : ''} aria-describedby="request-documents-hint">Request supporting documents</label><p id="request-documents-hint" class="field-hint">${view.submission && view.capabilities.document_upload ? 'The owner can upload documents for this question and publish selected accepted files with their reply.' : 'Document requests are available after submission when document upload is enabled.'}</p>`;
    return `<form class="question-form" data-question-form="${action}" data-question-id="${questionId}" autocomplete="off" novalidate><label class="field" for="body-${key}">${label}<textarea id="body-${key}" data-question-key="${key}" maxlength="4000" required${disabled ? ' disabled' : ''}${retry ? ' readonly' : ''} aria-describedby="limit-${key}">${escape(retry ? pending.payload.body : questionBodies.get(key) || '')}</textarea><small id="limit-${key}">Up to 4,000 characters. ${wording('Use synthetic information only.', 'Include only information relevant to this review that you are authorized to share.')}</small></label>${attachments}<div class="actions"><button class="secondary" type="submit"${disabled || (!retry && questionUploads.has(questionId)) ? ' disabled' : ''}>${retry ? 'Retry same message' : action === 'question' ? 'Send question' : 'Send reply'}</button></div></form>`;
  }

  function replyDocuments(questionId, retry, disabled) {
    if (retry) {
      return `<div aria-label="Original document selection"><p class="field-hint">The reply body and selected document IDs are fixed for this retry.</p>${pending.documents.length
        ? `<ul class="summary-list">${pending.documents.map(item => `<li>${escape(item.filename)} <span class="status-tag">Selected for original reply</span></li>`).join('')}</ul>`
        : '<p class="field-hint">No documents attached to this reply.</p>'}</div>`;
    }
    if (!openDocumentQuestion(questionId)) return '';
    const selected = questionDocuments.get(questionId) ?? [];
    const documents = scopedDocuments(questionId);
    const unavailable = selected.filter(id => !documents.some(item => item.document_id === id && item.status === 'accepted_for_review'));
    return `<fieldset${disabled ? ' disabled' : ''} aria-describedby="documents-hint-${questionId}"><legend>Documents for this reply</legend><p id="documents-hint-${questionId}" class="field-hint">Only accepted files uploaded for this question can be selected. Staged files are private to you until you send the reply. The original submission will not change.</p>
      ${documents.map(item => `<label class="document-choice"><input id="question-document-${questionId}-${item.document_id}" type="checkbox" data-question-document="${item.document_id}" data-document-question="${questionId}"${selected.includes(item.document_id) ? ' checked' : ''}${item.status === 'accepted_for_review' ? '' : ' disabled'}><span>${escape(item.filename)}<small>${docStatus(item.status)}</small></span></label>`).join('') || '<p class="field-hint">No documents uploaded for this question. You can still send a text-only reply.</p>'}
      ${unavailable.length ? `<p class="error" role="alert">A selected document is no longer accepted or available. Remove it before replying.</p><button class="text-button" type="button" data-action="remove-question-documents" data-question-id="${questionId}">Remove unavailable selections</button>` : ''}</fieldset>`;
  }

  function questionUploadSection(question) {
    if (view.role !== 'owner') return '';
    const id = question.question_id;
    const item = questionUploads.get(id);
    if (!openDocumentQuestion(id) && !item?.started) return '';
    const disabled = busy || needsRefresh || Boolean(pending) || (hasStartedUpload() && !item?.started);
    const full = documentCount() >= 40;
    return `<form class="question-form" data-question-upload="${id}" novalidate><fieldset${disabled ? ' disabled' : ''}><legend>Upload for this question</legend><label class="field" for="question-file-${id}">${wording('Synthetic supporting document', 'Supporting document')}<input id="question-file-${id}" data-upload-question="${id}" type="file" accept=".pdf,.csv,.xlsx" aria-describedby="upload-hint-${id}"${item?.started || full || !openDocumentQuestion(id) ? ' disabled' : ''}><small id="upload-hint-${id}">PDF, CSV or XLSX, up to 25 MiB. Uploading queues checks; select an accepted file below to attach it to this reply. The case limit is 40 files, including the original submission and all questions.</small></label>
      ${full ? '<p class="notice warm">The 40-file case limit has been reached. Existing upload retries and accepted-file selections remain available.</p>' : ''}${item ? `<p class="section-copy">Selected: ${escape(item.file.name)} (${item.file.size} bytes)</p>` : ''}${item?.started ? '<p class="field-hint">Upload outcome unresolved. The same file bytes and upload reference are retained for retry, including after Refresh workspace. No other file can replace them.</p>' : ''}
      <div class="actions"><button id="question-upload-button-${id}" class="secondary" type="submit"${!item || (!item.started && full) ? ' disabled' : ''}>${item?.started ? 'Retry same upload' : 'Upload for this question'}</button>${item && !item.started ? `<button class="text-button" type="button" data-action="clear-question-file" data-question-id="${id}">Clear selected file</button>` : ''}</div></fieldset>${item?.conflict ? '<p class="notice warm">The server could not accept this upload. Refresh to review the workspace before retrying or discarding only this unresolved upload. It is not confirmed saved.</p>' : ''}<div class="actions"><button class="text-button" type="button" data-action="refresh-question-documents" data-question-id="${id}"${busy ? ' disabled' : ''}>Refresh document status</button>${item?.conflictObserved ? `<button class="text-button" type="button" data-action="discard-question-upload" data-question-id="${id}"${busy ? ' disabled' : ''}>Discard only this unresolved upload</button>` : ''}</div></form>`;
  }

  function supplementSection(supplement) {
    if (!supplement) return '';
    return `<section id="supplement-${supplement.supplement_id}" class="review-section section-anchor" aria-labelledby="supplement-title-${supplement.supplement_id}"><h3 id="supplement-title-${supplement.supplement_id}">Published supplement version ${supplement.version}</h3><p class="question-date">${escape(date(supplement.created_at))}</p><p class="field-hint">A separate, immutable supplement to the original submission. Document acceptance does not confirm rights or accuracy.</p><ul class="summary-list">${supplement.documents.map(item => `<li>${escape(item.filename)}${view.capabilities.document_upload ? ` <button class="text-button" data-download="${item.document_id}"${busy ? ' disabled' : ''}>Download ${escape(item.filename)} (supplement version ${supplement.version})</button>` : ''}</li>`).join('')}</ul></section>`;
  }

  function pendingReplySection() {
    if (view.role !== 'owner' || pending?.kind !== 'reply') return '';
    const explanation = pending.conflict
      ? 'The server reports an existing immutable reply. Your attempted reply is not confirmed saved. Review the existing answer before discarding only your unresolved reply; other unsaved entries will be kept.'
      : pending.acknowledged
        ? 'The server acknowledged this reply. Refresh to load the updated conversation.'
        : 'This reply is still unresolved. A visible answer does not identify your request. Retry the same message so the server can confirm its outcome.';
    return `<section id="unresolved-reply" class="notice" aria-labelledby="unresolved-reply-title"><h3 id="unresolved-reply-title">Unresolved reply</h3><p>${explanation}</p>
      ${questionForm(pending.key, 'Your original reply (read-only)', 'reply', pending.questionId)}
      <div class="actions"><button class="secondary" data-action="refresh-reply-status"${busy ? ' disabled' : ''}>Refresh reply status</button>${pending.conflict && pending.conflictObserved ? `<button class="text-button" data-action="discard-unresolved-reply"${busy ? ' disabled' : ''}>Discard only my unresolved reply</button>` : ''}</div></section>`;
  }

  function questionsSection() {
    return `<section id="questions" class="section-anchor review-section"><h2>Questions &amp; follow-up</h2><p class="section-copy">${view.role === 'reviewer' ? 'As the assigned reviewer, ask the owner about missing evidence or rights. The catalog draft is read-only.' : 'Reply to questions from your assigned reviewer. Replies do not change the submitted snapshot.'}</p>
      ${view.questions.some(question => question.reply?.supplement) ? `<nav aria-label="Published supplement versions"><ul class="editorial-list">${view.questions.filter(question => question.reply?.supplement).map(question => `<li><a href="#supplement-${question.reply.supplement.supplement_id}">Published supplement version ${question.reply.supplement.version}</a></li>`).join('')}</ul></nav>` : ''}
      ${view.questions.length ? `<ol class="question-list">${view.questions.map(question => `<li><h3>Reviewer question</h3><p class="question-date">${escape(date(question.created_at))}</p><p class="question-body">${escape(question.body)}</p>${question.request_documents ? '<p class="status-tag">Supporting documents requested</p>' : ''}${questionUploadSection(question)}${question.reply ? `<div class="reply"><h3>Owner reply</h3><p class="question-date">${escape(date(question.reply.created_at))}</p><p class="question-body">${escape(question.reply.body)}</p>${supplementSection(question.reply.supplement)}</div>` : view.role === 'owner' ? pending?.kind === 'reply' && pending.questionId === question.question_id ? '' : questionForm(question.question_id, 'Your reply', 'reply', question.question_id) : '<p class="section-copy">Awaiting the owner\'s reply.</p>'}</li>`).join('')}</ol>` : '<p class="section-copy">No questions yet. Missing evidence still needs follow-up.</p>'}
      ${pendingReplySection()}${view.role === 'reviewer' ? questionForm('new', 'Question for the owner', 'question') : ''}</section>`;
  }

  function privacySection() {
    return `<section id="privacy" class="privacy-controls section-anchor" tabindex="-1"><h2>Session &amp; privacy</h2><p class="section-copy">Refresh checks the server version. Unsaved entries stay in memory only. Logging out clears this page immediately, even if the connection fails.</p><p class="section-copy">Session expires: ${escape(date(view.session_expires_at))}</p>
      ${view.role === 'owner' ? `<p id="privacy-data-hint" class="field-hint">Export downloads the saved portal records as JSON, not the document files or unsaved entries. Source forms and email are separate. Keep the downloaded copy private; clearing this page cannot remove it.</p><div class="actions"><button class="text-button" data-action="export" aria-describedby="privacy-data-hint"${busy ? ' disabled' : ''}>Download case export</button><button class="text-button" data-action="continue-interest" aria-describedby="continue-interest-hint"${busy || needsRefresh || pending || hasStartedUpload() || interest?.acknowledged ? ' disabled' : ''}>${interest?.acknowledged ? 'Continued interest recorded' : interest ? 'Retry same continued-interest request' : 'I want to continue this review'}</button></div><p id="continue-interest-hint" class="field-hint">${interest?.acknowledged ? 'Your continued interest has been recorded. The submitted catalog is unchanged.' : interest ? 'The outcome is unresolved. Retry keeps the same request reference, including after Refresh workspace. Nothing retries automatically.' : 'Continuing explicitly records your interest as case activity. It does not change your submitted catalog or send a reply. Viewing, refreshing or exporting does not record continued interest.'}</p>` : ''}
      <div class="actions"><button class="secondary" data-action="refresh"${busy ? ' disabled' : ''}>Refresh workspace</button><button class="text-button" data-action="logout">Log out &amp; clear page</button>${view.role === 'owner' ? `<button class="text-button" data-action="delete"${busy ? ' disabled' : ''}>Request deletion</button>` : ''}</div>
      ${confirmation === 'refresh' ? '<div class="confirmation" id="confirmation" tabindex="-1" role="group" aria-labelledby="confirm-title"><h3 id="confirm-title">Replace your unsaved entries?</h3><p>Reloading the server version discards unsaved draft entries and unsent messages only after a successful refresh. Unresolved request references, upload bytes and question document selections are retained.</p><div class="actions"><button class="secondary" data-action="confirm-refresh">Reload server version</button><button class="text-button" data-action="cancel">Keep my entries</button></div></div>' : ''}
      ${confirmation === 'delete' ? `<div class="confirmation" id="confirmation" tabindex="-1" role="group" aria-labelledby="confirm-title"><h3 id="confirm-title">Confirm deletion request</h3><p>${wording('This requests deletion of this test workspace and stops access.', 'This requests deletion of this review workspace and stops access.')} It does not mean records have been erased. Unsaved entries will be cleared.</p><div class="actions"><button class="secondary" data-action="confirm-delete">Confirm deletion request</button><button class="text-button" data-action="cancel">Cancel</button></div></div>` : ''}
      ${deletionUncertain ? '<p class="notice warm">The deletion request could not be confirmed. Refresh to check access before retrying. No erasure has been confirmed.</p>' : ''}</section>`;
  }

  function workspace() {
    const snapshot = view.submission?.snapshot;
    return `<section class="screen"><p class="eyebrow">${view.role === 'owner' ? 'Owner workspace' : 'Assigned reviewer workspace'}</p><h1>${snapshot ? 'Your submitted catalog.' : view.role === 'owner' ? 'A clear view of your catalog.' : 'Review the catalog.'}</h1><p class="intro">${snapshot ? 'This snapshot is locked. Questions and replies remain separate from the version submitted.' : view.role === 'owner' ? 'Start with existing releases. Declare what you know, and leave the rest visible for follow-up.' : 'Read the owner\'s declarations and ask for clarification. Only the owner can edit or submit.'}</p>
      <div class="workspace-status"><span>${reviewStatus(view.review_status)}</span><span>Revision ${view.revision}</span>${view.submission ? `<span>Submitted revision ${view.submission.revision}</span>` : ''}</div>${errorBox()}
      ${snapshot && view.capabilities.dealflow === true ? '<section class="review-section"><h2>Deal preparation &amp; sharing</h2><p>Review evidence and recipient-specific presentation permissions. Nothing is automatically shared with buyers.</p><a href="/dealflow/">Open the deal workspace</a></section>' : ''}
      <section aria-label="Source availability"><div class="availability"><button class="secondary" disabled aria-describedby="availability-note">Connect Too Lost</button></div><p id="availability-note" class="field-hint">${wording('Too Lost import is not connected in this test UI.', 'Too Lost import is not connected in this private pilot.')}${view.capabilities.document_upload ? '' : ' Document upload is unavailable.'} Use existing accepted documents, or continue with missing evidence flagged.</p>${uploadSection()}</section>
      <section id="catalog" class="section-anchor review-section"><div class="section-title"><h2>${snapshot ? 'Locked submission snapshot' : 'Catalog & rights'}</h2>${locked() ? '<span class="status-tag">Read-only</span>' : ''}</div>
      ${snapshot ? `${draftSummary(snapshot.draft)}${evidenceSummary(snapshot.draft, snapshot.documents)}` : view.role === 'owner' ? rightsForm() : `${draftSummary(view.draft)}${evidenceSummary(view.draft, view.documents)}`}</section>
      ${submissionSection()}${questionsSection()}${privacySection()}</section>`;
  }

  function uploadSection() {
    if (!view.capabilities.document_upload || view.role !== 'owner') return '';
    if (locked()) return '<p class="field-hint">Document upload is locked with the submitted version. New documents can only be uploaded under an open follow-up question requesting them.</p>';
    const full = documentCount() >= 40;
    return `<form id="upload-form" novalidate><fieldset${busy || needsRefresh || pending ? ' disabled' : ''}><legend class="sr-only">${wording('Synthetic document upload', 'Supporting document upload')}</legend><label class="field" for="synthetic-file">${wording('Synthetic document only', 'Supporting document')}<input id="synthetic-file" type="file" accept=".pdf,.csv,.xlsx"${upload?.started || full ? ' disabled' : ''}><small>PDF, CSV or XLSX, up to 25 MiB. Uploading queues checks; it does not attach the file to your draft. The case limit is 40 files.</small></label>${full ? '<p class="notice warm">The 40-file case limit has been reached.</p>' : ''}${upload ? `<p class="section-copy">Selected: ${escape(upload.file.name)} (${upload.file.size} bytes)</p>` : ''}<div class="actions"><button id="upload-button" class="secondary" type="submit"${!upload || upload.acknowledged || (full && !upload.started) ? ' disabled' : ''}>${upload?.started ? 'Retry same upload' : wording('Upload synthetic document', 'Upload supporting document')}</button>${upload && !upload.started ? '<button type="button" class="text-button" data-action="clear-file">Clear selected file</button>' : ''}</div></fieldset></form>`;
  }

  function render(focusId) {
    if (destroyed) return;
    // Scrub controls before detaching them, including intermediate busy renders.
    wipe();
    main.innerHTML = view ? workspace() : entry();
    main.setAttribute('aria-busy', String(busy));
    rail.innerHTML = view ? `<p class="rail-kicker">${view.role === 'owner' ? 'Your workspace' : 'Review workspace'}</p><ol>${[['catalog', 'Catalog & rights'], ['evidence', 'Evidence'], ['questions', 'Follow-up']].map(([id, label], index) => `<li><a href="#${id}" class="rail-item"><span class="step-number">${index + 1}</span><span>${label}</span></a></li>`).join('')}</ol><div class="rail-foot"><strong>${view.submission ? 'Snapshot locked' : 'Document-based review'}</strong>Future music excluded.<br>Missing evidence stays visible.</div>` : '';
    announcement.textContent = message;
    if (focusId) focus(focusId);
  }

  function validateDraft() {
    for (let index = 0; index < draft.rights.length; index += 1) {
      const right = draft.rights[index];
      if (right.ownership === 'known' && !validShare(right.share_percent)) return `For release ${index + 1}, enter a share above 0 and up to 100, with at most two decimal places.`;
    }
    if (!draftShape(draft)) return 'Check the release fields before saving.';
    if (draft.document_ids.some(id => !view.documents.some(item => item.document_id === id && item.question_id === null && item.status === 'accepted_for_review'))) return 'Remove unavailable documents before saving. Only accepted documents can be selected.';
    return '';
  }

  async function refresh(discard = false) {
    await run('Refreshing workspace', async current => {
      if (await load(current, { discard })) feedback(pending || hasStartedUpload() || (interest && !interest.acknowledged) ? 'Workspace refreshed. The earlier request is still unresolved; retry it with the same request reference.' : 'Workspace refreshed from the server.');
    });
  }

  async function save() {
    if (!canEdit()) return;
    const invalid = validateDraft();
    if (invalid) { feedback(invalid, true); render('screen-message'); return; }
    await run('Saving draft', async current => {
      const payload = copy(draft);
      for (const right of payload.rights) {
        right.title = right.title.trim() || null;
        right.artist = right.artist.trim() || null;
      }
      await client.save(view.revision, payload);
      if (current !== epoch) return;
      needsRefresh = true;
      if (await load(current, { replaceDraft: true })) feedback('Draft saved and refreshed. Review the saved version before submitting.');
    });
  }

  async function mutate(kind, key, body, questionId) {
    if (!view || busy || needsRefresh || hasStartedUpload() || checkExpiry()) return;
    if (kind === 'submission' && (view.role !== 'owner' || view.submission || dirty || !view.draft || !consent || upload)) return;
    if (kind === 'question' && view.role !== 'reviewer') return;
    const retryingReply = kind === 'reply' && pending?.kind === 'reply' && pending.key === key && pending.questionId === questionId;
    if (kind === 'reply' && (view.role !== 'owner' || (!retryingReply && !view.questions.some(item => item.question_id === questionId && item.reply === null)))) return;
    if (pending && (pending.kind !== kind || pending.key !== key || pending.acknowledged || pending.conflict)) return;
    if (!pending) {
      const documentIds = kind === 'reply' ? [...(questionDocuments.get(questionId) ?? [])] : [];
      if (kind === 'reply' && questionUploads.has(questionId)) {
        feedback('Upload or clear the selected file before replying. Uploading alone does not attach it.', true); render('screen-message'); return;
      }
      if (documentIds.length && (!openDocumentQuestion(questionId)
        || documentIds.some(id => !scopedDocuments(questionId).some(item => item.document_id === id && item.status === 'accepted_for_review')))) {
        feedback('Remove unavailable document selections before replying. Only accepted files for this question can be attached.', true); render('screen-message'); return;
      }
      if (kind !== 'submission' && (!body.trim() || body.length > 4000)) {
        feedback('Enter a message between 1 and 4,000 characters.', true); render('screen-message'); return;
      }
      pending = { kind, key, questionId, acknowledged: false,
        documents: kind === 'reply' ? copy(scopedDocuments(questionId).filter(item => documentIds.includes(item.document_id))) : [],
        payload: kind === 'submission'
        ? { request_id: uuid(), revision: view.revision, consent: true }
        : kind === 'question' ? { request_id: uuid(), body, request_documents: Boolean(requestDocuments && view.submission && view.capabilities.document_upload) }
          : { request_id: uuid(), body, document_ids: documentIds } };
    }
    await run(kind === 'submission' ? 'Submitting saved draft' : 'Sending message', async current => {
      try {
        if (kind === 'submission') await client.submit(pending.payload);
        else if (kind === 'question') await client.question(pending.payload);
        else await client.reply(pending.questionId, pending.payload);
      } catch (error) {
        if (current === epoch && kind === 'reply' && error?.status === 409) {
          pending.conflict = true;
          pending.conflictObserved = false;
        } else if (current === epoch && [400, 401, 403, 404, 409, 422].includes(error?.status)) pending = null;
        throw error;
      }
      if (current !== epoch) return;
      pending.acknowledged = true;
      if (await load(current)) feedback(kind === 'submission' ? 'Submission received. The submitted snapshot is locked.' : 'Message received and workspace refreshed.');
    });
  }

  async function logout() {
    // Clear the DOM before awaiting the network; the client cancels older requests.
    clearPrivate('Private information has been cleared. Closing the server session...', { keepClient: true });
    const current = epoch;
    busy = true;
    render('screen-message');
    try {
      await client.logout();
      if (epoch === current) feedback('Logged out. Private information has been cleared.');
    } catch {
      if (epoch === current) feedback('This page is cleared, but server logout could not be confirmed. Close this tab. The server session may remain active until it expires.', true);
    } finally {
      if (epoch === current) { busy = false; render('screen-message'); }
    }
  }

  async function deletion() {
    if (view?.role !== 'owner' || confirmation !== 'delete') return;
    await run('Requesting deletion', async current => {
      try {
        const result = await client.deletion();
        if (current !== epoch) return;
        if (result?.erasure_completed !== false || result?.status !== 'deletion_requested') throw new PortalError('contract');
        clearPrivate('Deletion requested. Access has stopped and this page is cleared. Erasure is not complete; this is not confirmation that records have been erased.');
      } catch (error) {
        if (current === epoch) deletionUncertain = true;
        throw error;
      }
    });
  }

  async function requestAccess() {
    if (!recoveryAvailable || !recoveryWorkspace) return;
    const emailPattern = production ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/ : /^[a-zA-Z0-9._+-]+@example\.com$/;
    if (!emailPattern.test(recoveryEmail) || recoveryEmail.length > 254) {
      feedback(wording('Use the original application email with the @example.com test domain.', 'Enter a valid email address matching your original application.'), true); render('screen-message'); return;
    }
    await run('Recording access request', async current => {
      const result = await client.access(recoveryWorkspace, recoveryEmail);
      if (current !== epoch) return;
      if (result?.status !== 'request_received') throw new PortalError('contract');
      recoveryEmail = '';
      feedback(wording('Request recorded. In this integration test no real email is sent. A usable link must be delivered before access is possible.', 'Request received. If this address matches an eligible application, an access link will be sent. This is not confirmation of delivery. An existing active invitation is not replaced.'));
    });
  }

  async function uploadDocument() {
    if (!upload || upload.acknowledged || busy || needsRefresh || pending || locked() || view?.role !== 'owner' || !view.capabilities.document_upload) return;
    if (!upload.started && documentCount() >= 40) return;
    upload.started = true;
    await run(wording('Uploading synthetic document', 'Uploading supporting document'), async current => {
      let result;
      try { result = await client.upload(upload.file, upload.request_id); }
      catch (error) {
        if (current === epoch && [400, 413, 415, 422].includes(error?.status)) upload.started = false;
        throw error;
      }
      if (current !== epoch) return;
      if (!UUID.test(result?.document_id) || !DOCUMENT_STATUSES.includes(result?.status)) throw new PortalError('contract');
      recordedUploads.add(result.document_id);
      upload = null;
      feedback(`Upload recorded. Document status: ${docStatus(result.status)}. Refresh to check its current status. Only accepted documents can be selected; no rights have been confirmed.`);
    });
  }

  async function uploadQuestionDocument(questionId) {
    const item = questionUploads.get(questionId);
    if (!item || busy || needsRefresh || pending || view?.role !== 'owner' || !view.submission || !view.capabilities.document_upload
      || (!item.started && (!canStageDocuments(questionId) || documentCount() >= 40))) return;
    item.started = true;
    await run('Uploading document for this question', async current => {
      let result;
      try { result = await client.uploadQuestion(questionId, item.file, item.request_id); }
      catch (error) {
        if (current === epoch && [400, 413, 415, 422].includes(error?.status)) item.started = false;
        if (current === epoch && error?.status === 409) { item.conflict = true; item.conflictObserved = false; }
        throw error;
      }
      if (current !== epoch) return;
      if (!UUID.test(result?.document_id) || !DOCUMENT_STATUSES.includes(result?.status)) throw new PortalError('contract');
      recordedUploads.add(result.document_id);
      questionUploads.delete(questionId);
      feedback(`Upload recorded for this question. Document status: ${docStatus(result.status)}. Refresh to check its status, then select the accepted file before replying. It has not been published or attached to the original submission.`);
    });
  }

  async function downloadDocument(documentId) {
    const documents = [...(view?.submission?.snapshot.documents ?? view?.documents ?? []).filter(item => item.question_id === null),
      ...(view?.questions ?? []).flatMap(question => question.reply?.supplement?.documents ?? [])];
    const item = documents.find(document => document.document_id === documentId && document.status === 'accepted_for_review');
    if (!item || !view.capabilities.document_upload) return;
    await run('Preparing document download', async current => {
      const blob = await client.download(documentId);
      if (current !== epoch || checkExpiry()) return;
      startDownload(blob, 'catalog-document');
      feedback('Download started. The document is not displayed inside this workspace.');
    });
  }

  function startDownload(blob, filename) {
    const url = win.URL.createObjectURL(blob);
    downloadUrls.add(url);
    const link = doc.createElement('a');
    link.href = url;
    // Attachments never render in the workspace; ignore server-provided filenames.
    link.download = filename;
    doc.body.append(link);
    link.click();
    link.remove();
    win.setTimeout(() => { win.URL.revokeObjectURL(url); downloadUrls.delete(url); }, 1000);
  }

  async function exportCase() {
    if (view?.role !== 'owner') return;
    await run('Preparing case export', async current => {
      const blob = await client.exportCase();
      if (current !== epoch || checkExpiry()) return;
      startDownload(blob, 'space-review-export.json');
      feedback('Case export download started. It contains saved portal records, not document files or unsaved entries. Keep this copy private.');
    });
  }

  async function continueInterest() {
    if (view?.role !== 'owner' || busy || needsRefresh || pending || hasStartedUpload() || interest?.acknowledged || checkExpiry()) return;
    interest ??= { request_id: uuid(), acknowledged: false };
    await run('Recording continued interest', async current => {
      const result = await client.continueInterest(interest.request_id);
      if (current !== epoch) return;
      if (result?.recorded !== true || typeof result.created !== 'boolean') throw new PortalError('contract');
      interest.acknowledged = true;
      feedback('Your continued interest has been recorded. The submitted catalog is unchanged.');
    });
  }

  function onInput(event) {
    if (checkExpiry()) return;
    const target = event.target;
    if (target.id === 'recovery-email' && !busy) recoveryEmail = target.value;
    else if ((target.id === 'synthetic-file' && canEdit() && view.capabilities.document_upload && !upload?.started)
      || (target.dataset.uploadQuestion && canStageDocuments(target.dataset.uploadQuestion))) {
      const questionId = target.dataset.uploadQuestion;
      if (documentCount() >= 40) { feedback('The 40-file case limit has been reached. Select existing accepted files instead.', true); render('screen-message'); return; }
      const file = target.files?.[0];
      if (!file) return;
      if (!/\.(pdf|csv|xlsx)$/i.test(file.name) || file.size <= 0 || file.size > 25 * 1024 * 1024 || file.name.length < 5 || file.name.length > 180 || /[\x00-\x1f/\\"]/.test(file.name)) {
        if (questionId) questionUploads.delete(questionId); else upload = null;
        feedback(wording('Choose a synthetic PDF, CSV or XLSX file between 1 byte and 25 MiB, with a plain filename of at most 180 characters.', 'Choose a PDF, CSV or XLSX supporting document between 1 byte and 25 MiB, with a plain filename of at most 180 characters.'), true); render('screen-message'); return;
      }
      const selected = { file, request_id: uuid(), started: false, acknowledged: false };
      if (questionId) questionUploads.set(questionId, selected); else upload = selected;
      consent = false;
      render(questionId ? `question-upload-button-${questionId}` : 'upload-button');
    } else if (target.id === 'request-documents' && view?.role === 'reviewer' && !busy && !pending && !needsRefresh && view.submission && view.capabilities.document_upload) {
      requestDocuments = target.checked;
    } else if (target.dataset.questionDocument && canStageDocuments(target.dataset.documentQuestion)) {
      const questionId = target.dataset.documentQuestion;
      const item = scopedDocuments(questionId).find(item => item.document_id === target.dataset.questionDocument && item.status === 'accepted_for_review');
      if (!item) return;
      const selected = (questionDocuments.get(questionId) ?? []).filter(id => id !== item.document_id);
      if (target.checked) selected.push(item.document_id);
      questionDocuments.set(questionId, selected);
    } else if (target.id === 'consent' && !busy && pending?.kind !== 'submission') {
      consent = target.checked;
      const button = main.querySelector('[data-action="submit"]');
      if (button) button.disabled = !consent || busy || needsRefresh || dirty || !view?.draft || Boolean(pending) || Boolean(upload);
    } else if (target.dataset.questionKey && !busy && !pending && !needsRefresh) {
      questionBodies.set(target.dataset.questionKey, target.value);
    } else if (target.dataset.right !== undefined && canEdit()) {
      const right = draft.rights[Number(target.dataset.right)];
      if (!right || !['title', 'artist', 'ownership', 'share_percent', 'rights_scope', 'obligations'].includes(target.name)) return;
      if (target.name === 'share_percent' && right.ownership !== 'known') return;
      right[target.name] = target.value;
      dirty = true;
      consent = false;
      if (target.name === 'ownership') {
        right.share_percent = right.ownership === 'unknown' ? null : '';
        render(target.id);
      } else {
        doc.getElementById('form-state').textContent = 'Unsaved changes. Save before submitting.';
        const button = main.querySelector('[data-action="submit"]');
        if (button) button.disabled = true;
        const checkbox = doc.getElementById('consent');
        if (checkbox) checkbox.checked = false;
      }
    } else if (target.dataset.document !== undefined && canEdit()) {
      const item = view.documents[Number(target.dataset.document)];
      if (!item || item.question_id !== null || item.status !== 'accepted_for_review') return;
      draft.document_ids = draft.document_ids.filter(id => id !== item.document_id);
      if (target.checked) draft.document_ids.push(item.document_id);
      dirty = true;
      consent = false;
      render();
      main.querySelector(`[data-document="${Number(target.dataset.document)}"]`)?.focus();
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    if (event.target.id === 'draft-form') void save();
    else if (event.target.id === 'access-form') void requestAccess();
    else if (event.target.id === 'upload-form') void uploadDocument();
    else if (event.target.dataset.questionUpload) void uploadQuestionDocument(event.target.dataset.questionUpload);
    else if (event.target.dataset.questionForm) {
      const kind = event.target.dataset.questionForm;
      const questionId = event.target.dataset.questionId;
      const key = kind === 'question' ? 'new' : questionId;
      void mutate(kind, key, questionBodies.get(key) || '', questionId);
    }
  }

  function onClick(event) {
    const download = event.target.closest('[data-download]');
    if (download) {
      event.preventDefault();
      if (!download.disabled && !checkExpiry()) void downloadDocument(download.dataset.download);
      return;
    }
    const button = event.target.closest('button[data-action]');
    if (!button || button.disabled || checkExpiry()) return;
    const action = button.dataset.action;
    if (action === 'logout') { void logout(); return; }
    if (action === 'clear') { clearPrivate('This page has been cleared. No server logout was requested.'); return; }
    if (busy) return;
    if (action === 'open' && invitation) {
      void run('Opening invitation', async current => {
        const result = await client.exchange(invitation);
        if (current !== epoch) return;
        client.setCsrf(result?.csrf);
        invitation = null;
        if (await load(current)) feedback(wording('Workspace opened. Use synthetic information only.', 'Workspace opened. Share only catalog information and documents you are authorized to provide.'));
      });
    } else if (action === 'refresh-reply-status' && view?.role === 'owner' && pending?.kind === 'reply') {
      void refresh();
    } else if (action === 'refresh-question-documents' && view?.role === 'owner' && questionById(button.dataset.questionId)?.request_documents) {
      void refresh();
    } else if (action === 'discard-unresolved-reply' && view?.role === 'owner' && pending?.kind === 'reply'
      && pending.conflict && pending.conflictObserved && view.questions.some(question => question.question_id === pending.questionId && question.reply !== null)) {
      questionBodies.delete(pending.key);
      questionDocuments.delete(pending.key);
      questionUploads.delete(pending.key);
      pending = null;
      feedback('Unresolved reply discarded. It was not confirmed saved. Other unsaved entries have been kept.');
      render('screen-message');
    } else if (action === 'refresh') {
      if (hasUnsaved()) { confirmation = 'refresh'; render('confirmation'); }
      else void refresh();
    } else if (action === 'confirm-refresh' && confirmation === 'refresh') void refresh(true);
    else if (action === 'cancel') {
      const previous = confirmation;
      confirmation = null;
      render();
      main.querySelector(`[data-action="${previous === 'delete' ? 'delete' : 'refresh'}"]`)?.focus();
    } else if (action === 'delete' && view?.role === 'owner') { confirmation = 'delete'; render('confirmation'); }
    else if (action === 'confirm-delete') void deletion();
    else if (action === 'submit') void mutate('submission');
    else if (action === 'export') void exportCase();
    else if (action === 'continue-interest') void continueInterest();
    else if (action === 'clear-file' && !upload?.started) { upload = null; render('synthetic-file'); }
    else if (action === 'clear-question-file' && canStageDocuments(button.dataset.questionId)) {
      questionUploads.delete(button.dataset.questionId); render(`question-file-${button.dataset.questionId}`);
    } else if (action === 'remove-question-documents' && canStageDocuments(button.dataset.questionId)) {
      const id = button.dataset.questionId;
      questionDocuments.set(id, (questionDocuments.get(id) ?? []).filter(documentId => scopedDocuments(id).some(item => item.document_id === documentId && item.status === 'accepted_for_review')));
      render(`body-${id}`);
    } else if (action === 'discard-question-upload' && view?.role === 'owner') {
      const id = button.dataset.questionId;
      const item = questionUploads.get(id);
      if (!item?.conflict || !item.conflictObserved) return;
      questionUploads.delete(id);
      feedback('Unresolved upload discarded. It was not confirmed saved or attached. Other question files and entries have been kept.');
      render('screen-message');
    }
    else if (canEdit() && action === 'add-release' && draft.rights.length < 200) {
      draft.rights.push(newRight(uuid)); dirty = true; consent = false; render(`title-${draft.rights.length - 1}`);
    } else if (canEdit() && action === 'remove-release' && draft.rights.length > 1) {
      draft.rights.splice(Number(button.dataset.index), 1); dirty = true; consent = false; render('title-0');
    } else if (canEdit() && ['remove-document', 'remove-missing-documents'].includes(action)) {
      const item = view.documents[Number(button.dataset.index)];
      draft.document_ids = draft.document_ids.filter(id => action === 'remove-document' ? id !== item?.document_id : view.documents.some(document => document.document_id === id));
      dirty = true; consent = false; render('form-state');
    }
  }

  function onPageHide() { clearPrivate('This page was closed or suspended. Private information has been cleared. Refresh explicitly to reopen a session.'); }
  function onPageShow(event) { if (event.persisted) onPageHide(); else checkExpiry(); }
  const onVisibility = () => checkExpiry();
  main.addEventListener('input', onInput);
  main.addEventListener('submit', onSubmit);
  main.addEventListener('click', onClick);
  doc.addEventListener('visibilitychange', onVisibility);
  win.addEventListener('focus', onVisibility);
  win.addEventListener('pagehide', onPageHide);
  win.addEventListener('pageshow', onPageShow);
  render();
  return {
    destroy() {
      destroyed = true;
      clearPrivate('');
      main.removeEventListener('input', onInput);
      main.removeEventListener('submit', onSubmit);
      main.removeEventListener('click', onClick);
      doc.removeEventListener('visibilitychange', onVisibility);
      win.removeEventListener('focus', onVisibility);
      win.removeEventListener('pagehide', onPageHide);
      win.removeEventListener('pageshow', onPageShow);
    },
  };
}

if (typeof window !== 'undefined' && window.document.querySelector('#content')) createApp();

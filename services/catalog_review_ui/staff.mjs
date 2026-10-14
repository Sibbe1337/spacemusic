const UUID = /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i;
const B64 = /^[A-Za-z0-9_-]+$/;
const PATHS = ['/', '/apply/', '/sell/', '/calculator/', '/guides/music-catalog-valuation-2026/'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value, max = 300) => typeof value === 'string' && value.length <= max;
const timestamp = value => typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

export class StaffError extends Error {
  constructor(kind, status = 0) { super('The staff request could not be completed.'); this.kind = kind; this.status = status; }
}

export function createStaffClient({ fetchImpl = globalThis.fetch, timeoutMs = 12000 } = {}) {
  let csrf = null;
  const requests = new Set();
  function clear() { csrf = null; for (const cancel of requests) cancel(); requests.clear(); }
  async function request(path, method = 'GET', body, { token = csrf, context = false } = {}) {
    if (method !== 'GET' && path !== 'oidc/start' && !token) throw new StaffError('authentication', 401);
    const controller = new AbortController();
    let timer, cancel;
    const interrupted = new Promise((_, reject) => {
      cancel = () => { reject(new StaffError('cancelled')); controller.abort(); };
      timer = setTimeout(() => { reject(new StaffError('timeout')); controller.abort(); }, timeoutMs);
    });
    requests.add(cancel);
    const operation = async () => {
      const response = await fetchImpl(`/api/staff/${path}`, {
        method, credentials: 'same-origin', mode: 'same-origin', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer', signal: controller.signal,
        headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(method !== 'GET' && path !== 'oidc/start' ? { 'X-CSRF-Token': token } : {}) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      // Never read error bodies or expose provider/authentication details.
      if (!response.ok) throw new StaffError('http', response.status);
      if (response.status === 204 && (method === 'DELETE' || context)) return null;
      if (response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json') throw new StaffError('contract');
      try { return await response.json(); } catch { throw new StaffError('contract'); }
    };
    try { return await Promise.race([operation(), interrupted]); }
    catch (error) { throw error instanceof StaffError ? error : new StaffError('network'); }
    finally { clearTimeout(timer); requests.delete(cancel); }
  }
  const id = value => { if (typeof value !== 'string' || !UUID.test(value)) throw new StaffError('contract'); return value; };
  return {
    clear,
    setCsrf(value) { if (!text(value, 512) || !value || /[\r\n]/.test(value)) throw new StaffError('contract'); csrf = value; },
    session: () => request('session'),
    signIn: () => request('oidc/start', 'POST', {}),
    enrollmentOptions: permit => request('enrollment/options', 'POST', { permit }),
    enrollmentVerify: body => request('enrollment/verify', 'POST', body),
    assertionOptions: credential => request('assertion/options', 'POST', credential ? { confirm_credential: credential } : {}),
    assertionVerify: body => request('assertion/verify', 'POST', body),
    intakes: () => request('intakes'),
    workspaces: () => request('workspaces'),
    detail: intakeId => request(`intakes/${id(intakeId)}`),
    approve: (intakeId, body) => request(`intakes/${id(intakeId)}/approve`, 'POST', body),
    manual: body => request('intakes/formspree-receipt', 'POST', body),
    context: workspace => request(`workspaces/${id(workspace)}/context`, 'POST', {}, { context: true }),
    logout() { const token = csrf; clear(); return request('session', 'DELETE', undefined, { token }); },
  };
}

export function validateStaffSession(value) {
  if (!object(value) || !UUID.test(value.principal_id) || !text(value.display_name, 300)
    || !['reviewer', 'operator'].includes(value.role) || !['enrolling', 'active'].includes(value.state)
    || !timestamp(value.expires_at) || !(value.uv_at === null || timestamp(value.uv_at))
    || !text(value.csrf, 512) || !value.csrf || /[\r\n]/.test(value.csrf)) throw new StaffError('contract');
  return { ...value };
}

function listShape(value) {
  if (!object(value) || !Array.isArray(value.intakes) || value.intakes.length > 50
    || !value.intakes.every(item => object(item) && UUID.test(item.intake_id) && text(item.source, 80) && text(item.inquiry_kind, 80)
      && timestamp(item.submitted_at) && timestamp(item.received_at) && (item.workspace_id === null || UUID.test(item.workspace_id)))
    || new Set(value.intakes.map(item => item.intake_id)).size !== value.intakes.length) throw new StaffError('contract');
  return value.intakes;
}

function detailShape(value, id) {
  if (!object(value) || value.intake_id !== id || !text(value.email, 254) || !value.email || !text(value.source, 80)
    || !text(value.form_id, 200) || !text(value.response_id, 200) || !text(value.inquiry_kind, 80)
    || !timestamp(value.submitted_at) || !PATHS.includes(value.landing_path)) throw new StaffError('contract');
  return value;
}

export function googleAuthorizationUrl(value, origin) {
  let url;
  try { url = new URL(value); } catch { throw new StaffError('contract'); }
  if (!text(value, 8192) || url.origin !== 'https://accounts.google.com' || url.pathname !== '/o/oauth2/v2/auth'
    || url.username || url.password || url.hash || url.searchParams.get('redirect_uri') !== `${origin}/api/staff/oidc/callback`
    || url.searchParams.get('response_type') !== 'code' || !url.searchParams.get('state')
    || new Set(url.searchParams.keys()).size !== [...url.searchParams.keys()].length) throw new StaffError('contract');
  return url.href;
}

function decode(value, win) {
  if (!text(value, 65536) || !B64.test(value) || value.length % 4 === 1) throw new StaffError('contract');
  try { return Uint8Array.from(win.atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)), char => char.charCodeAt(0)); }
  catch { throw new StaffError('contract'); }
}

function encode(value, win) {
  if (!value || typeof value.byteLength !== 'number' || value.byteLength > 65536) throw new StaffError('contract');
  return win.btoa(Array.from(new Uint8Array(value.buffer ?? value, value.byteOffset ?? 0, value.byteLength), byte => String.fromCharCode(byte)).join('')).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function credentialOptions(result, kind, win) {
  const options = result?.publicKey;
  if (!object(result) || !UUID.test(result.challenge_id) || !object(options) || !B64.test(options.challenge ?? '')
    || (kind === 'create' ? options.rp?.id !== win.location.hostname || options.authenticatorSelection?.userVerification !== 'required'
      : options.rpId !== win.location.hostname || options.userVerification !== 'required')) throw new StaffError('contract');
  const parse = kind === 'create' ? win.PublicKeyCredential?.parseCreationOptionsFromJSON : win.PublicKeyCredential?.parseRequestOptionsFromJSON;
  try {
    if (parse) return parse.call(win.PublicKeyCredential, options);
    const decoded = { ...options, challenge: decode(options.challenge, win) };
    if (kind === 'create') decoded.user = { ...options.user, id: decode(options.user?.id, win) };
    for (const list of ['excludeCredentials', 'allowCredentials']) if (options[list]) decoded[list] = options[list].map(item => ({ ...item, id: decode(item.id, win) }));
    return decoded;
  } catch { throw new StaffError('contract'); }
}

export function credentialJSON(credential, win) {
  if (!credential || credential.type !== 'public-key' || !text(credential.id, 2048) || !B64.test(credential.id)) throw new StaffError('credential');
  if (typeof credential.toJSON === 'function') return credential.toJSON();
  const response = credential.response;
  const value = { id: credential.id, rawId: encode(credential.rawId, win), type: credential.type,
    response: { clientDataJSON: encode(response?.clientDataJSON, win) }, clientExtensionResults: credential.getClientExtensionResults?.() ?? {} };
  if (response.attestationObject) {
    value.response.attestationObject = encode(response.attestationObject, win);
    if (response.getTransports) value.response.transports = response.getTransports();
  } else {
    value.response.authenticatorData = encode(response.authenticatorData, win);
    value.response.signature = encode(response.signature, win);
    value.response.userHandle = response.userHandle == null ? null : encode(response.userHandle, win);
  }
  if (credential.authenticatorAttachment) value.authenticatorAttachment = credential.authenticatorAttachment;
  return value;
}

export function createStaffApp({ window: win = globalThis.window, client, now = () => Date.now(), uuid, schedule, unschedule,
  navigate = url => win.location.assign(url), autoStart = true } = {}) {
  client ??= createStaffClient({ fetchImpl: win.fetch.bind(win) });
  uuid ??= () => win.crypto.randomUUID();
  schedule ??= (fn, delay) => win.setTimeout(fn, delay);
  unschedule ??= timer => win.clearTimeout(timer);
  const doc = win.document;
  const main = doc.querySelector('#staff-content');
  const rail = doc.querySelector('#staff-progress');
  const announcement = doc.querySelector('#staff-announcement');
  const production = doc.documentElement.dataset.environment === 'production';
  let clean = true;
  try { win.history.replaceState(null, '', '/staff/'); } catch { clean = false; }
  let session = null, intakes = null, workspaces = null, detail = null, pending = null, admission = null, enrollment = null;
  let permit = '', workspaceId = '', authority = false, manualAttested = false;
  let manual = { email: '', submitted_at: '', landing_path: '/apply/' };
  let busy = false, message = '', error = false, epoch = 0, timer = null, destroyed = false, authenticator = null;
  const fresh = () => session?.state === 'active' && session.uv_at !== null && Date.parse(session.uv_at) <= now()
    && now() < Date.parse(session.uv_at) + 300000 && now() < Date.parse(session.expires_at);
  const operator = () => session?.role === 'operator' && fresh();
  const focus = id => doc.getElementById(id)?.focus();
  const feedback = (value, failed = false) => { message = value; error = failed; };

  function scrub() {
    for (const input of main.querySelectorAll('input, textarea')) {
      input.value = ''; input.removeAttribute('value');
      if (input.type === 'checkbox') { input.checked = false; input.removeAttribute('checked'); }
      if (input.tagName === 'TEXTAREA') input.textContent = '';
    }
    main.replaceChildren(); rail.replaceChildren(); announcement.textContent = '';
  }

  function clear(reason, keepClient = false) {
    epoch += 1; unschedule(timer); timer = null;
    authenticator?.abort(); authenticator = null;
    if (!keepClient) client.clear();
    session = null; intakes = null; workspaces = null; detail = null; pending = null; admission = null; enrollment = null;
    permit = ''; workspaceId = ''; authority = false; manualAttested = false;
    manual = { email: '', submitted_at: '', landing_path: '/apply/' };
    busy = false; feedback(reason); scrub(); if (!destroyed) render('staff-message');
  }

  function expiry() {
    if (session && now() >= Date.parse(session.expires_at)) {
      clear('Your staff session expired. Private information, permits and unsaved requests have been cleared. Sign in again and review server records before another action.'); return true;
    }
    if (session?.uv_at && !fresh()) {
      session = { ...session, uv_at: null };
      clearProtected();
      feedback('Passkey verification is no longer fresh. Private intake details have been cleared. Verify again before continuing; nothing is sent automatically.');
      render('staff-message');
    }
    return false;
  }

  function clearProtected() {
    intakes = null; workspaces = null; detail = null; admission = null; authority = false; manualAttested = false; workspaceId = '';
    manual = { email: '', submitted_at: '', landing_path: '/apply/' };
    // Approval retries contain only immutable IDs and an explicit authority flag.
    // Manual receipt retries contain contact PII and cannot outlive fresh UV.
    if (pending?.kind === 'manual') pending = null;
  }

  function arm() {
    unschedule(timer);
    if (!session || expiry()) return;
    const deadline = fresh() ? Math.min(Date.parse(session.expires_at), Date.parse(session.uv_at) + 300000) : Date.parse(session.expires_at);
    timer = schedule(() => { if (!expiry()) arm(); }, Math.max(1, Math.min(deadline - now(), 2147483647)));
  }

  function failure(cause) {
    if ([401, 403, 404].includes(cause?.status)) {
      clear('Staff access could not be confirmed. Private information and pending requests have been cleared. Refresh the session or sign in again, then verify your passkey and assignment.'); return;
    }
    const messages = {
      timeout: 'The request timed out. Its outcome may be unknown. Refresh read-only status; retry an unresolved admission or receipt with its original reference.',
      network: 'The connection failed. Its outcome may be unknown. Nothing retries automatically; keep the original request reference for unresolved admissions or receipts.',
      contract: 'The staff response is incomplete or unsupported. No new authority has been granted in this page. Ask the operator to check the integration.',
      credential: 'Passkey verification was not confirmed. Use a supported browser and an approved single-device passkey.',
      cancelled: 'The passkey operation was cancelled or unavailable. No verification was confirmed. Enrollment options consume a permit; ask your supervisor for a new permit if needed.',
    };
    feedback(cause?.status === 409 ? 'The server reported a conflict. Refresh the intake list before retrying or discarding this unresolved request. Nothing is confirmed saved.'
      : cause?.status === 429 ? 'Too many requests. Wait before trying again. Nothing retries automatically.'
        : cause?.status === 422 ? 'The server could not accept these fields. Check the entries before trying again.'
          : messages[cause?.kind] || 'The staff service could not complete this request. Refresh status before retrying. No internal error details are displayed.', true);
  }

  async function run(label, operation) {
    if (busy || destroyed || !clean || expiry()) return;
    const current = epoch; busy = true; feedback(`${label}...`); render();
    try { await operation(current); }
    catch (cause) { if (current === epoch) failure(cause); }
    finally { if (current === epoch && !destroyed) { busy = false; if (!expiry()) render('staff-message'); } }
  }

  async function loadSession(current) {
    const incoming = validateStaffSession(await client.session());
    if (current !== epoch || destroyed) return false;
    if (Date.parse(incoming.expires_at) <= now()) { clear('Your staff session expired. Private information has been cleared. Sign in again.'); return false; }
    if (session && (session.principal_id !== incoming.principal_id || session.role !== incoming.role)) { clear('Staff identity or role changed. Private information has been cleared. Refresh explicitly to continue.'); return false; }
    session = incoming; client.setCsrf(incoming.csrf);
    if (!fresh()) clearProtected();
    arm(); return true;
  }

  function errorBox() { return `<div id="staff-message" class="screen-message ${error ? 'error' : 'notice'}" role="${error ? 'alert' : 'status'}" tabindex="-1">${escape(message)}</div>`; }
  const disabled = condition => condition ? ' disabled' : '';
  const button = (action, label, blocked = busy, className = 'secondary') => `<button type="button" class="${className}" data-action="${action}"${disabled(blocked)}>${label}</button>`;

  function securitySection() {
    if (!session) return `<section id="staff-security" class="review-section"><h2>Sign in with your approved identity</h2><p class="section-copy">Google sign-in establishes a staff session, not reviewer authority. A server-verified passkey and an active assignment are also required.</p><div class="actions">${button('sign-in', 'Continue with Google', busy || !clean, 'primary')}${button('refresh-session', 'Refresh existing staff session', busy || !clean)}</div></section>`;
    return `<section id="staff-security" class="review-section"><h2>Staff identity &amp; verification</h2><p class="section-copy">${escape(session.display_name)} / ${escape(session.role)}. Session expires ${escape(new Date(session.expires_at).toLocaleString())}.</p><p class="status-tag">${fresh() ? 'Passkey verified by server' : session.state === 'enrolling' ? 'Supervised enrollment required' : 'Verify your passkey'}</p>
      ${session.state === 'enrolling' ? `<p class="section-copy">Register and confirm two distinct single-device passkeys, one permit at a time. Your supervisor determines which slot each permit authorizes. Synced passkeys are not accepted. Registration alone is not possession confirmation.</p>${enrollment ? `<p class="notice">${enrollment.uncertain ? 'Registration outcome is unconfirmed. Try a signed confirmation of this exact key; do not register a replacement blindly.' : 'This key is registered but still needs signed confirmation.'}</p>${button('confirm-key', 'Confirm this passkey with a signed assertion')}` : `<form id="staff-enroll-form" autocomplete="off"><label class="field" for="staff-permit">Supervisor-issued enrollment permit<input id="staff-permit" type="password" autocomplete="off" maxlength="256" value="${escape(permit)}"${disabled(busy)} aria-describedby="permit-help"><small id="permit-help">Single use. Paste only when your supervisor has approved this enrollment. Permits are cleared as soon as the request starts.</small></label><div class="actions"><button class="secondary" type="submit"${disabled(busy)}>Register primary or backup passkey</button></div></form>`}`
        : `<p class="field-hint">Verification lasts at most five minutes. The server rechecks it for protected actions.</p>${button('verify', 'Verify with passkey')}`}
      <div class="actions">${button('refresh-session', 'Refresh staff session')}${button('logout', 'Log out &amp; clear page', false, 'text-button')}</div></section>`;
  }

  function pendingSection() {
    if (!pending) return '';
    return `<section class="notice" aria-labelledby="pending-title"><h3 id="pending-title">Unresolved ${pending.kind === 'approve' ? 'admission' : 'manual receipt'}</h3><p class="field-hint">The original reference and submitted fields are fixed for retries. A visible workspace does not identify this request. Nothing will retry automatically.</p><p class="field-hint">Request reference: ${escape(pending.payload.request_id ?? pending.payload.receipt_id)}</p><div class="actions">${button('retry-mutation', 'Retry exact request', busy || !operator())}${pending.conflictObserved ? button('discard-mutation', 'Discard only this unresolved request', busy, 'text-button') : ''}</div></section>`;
  }

  function intakeSection() {
    if (session?.role !== 'operator') return '';
    const active = operator();
    const admitted = detail && intakes?.find(item => item.intake_id === detail.intake_id)?.workspace_id;
    return `<section id="staff-intakes" class="review-section section-anchor"><h2>Intake review</h2><p class="section-copy">Review the original receipt and the applicant's authority before approving a pilot place. Admission does not establish rights, assign a reviewer or confirm invitation delivery.</p>${button('list', 'Refresh intake list', busy || !active)}
      ${!active ? '<p class="notice">Verify your passkey to view private intake details.</p>' : intakes === null ? '<p class="field-hint">Load the intake list to begin. Nothing is approved automatically.</p>' : intakes.length ? `<ul class="summary-list">${intakes.map(item => `<li><h3>${escape(item.source)} / ${escape(item.inquiry_kind)}</h3><p class="question-date">Received ${escape(new Date(item.received_at).toLocaleString())}</p><p class="field-hint">${item.workspace_id ? 'Admitted to a workspace' : 'Awaiting operator review'}</p><button class="text-button" type="button" data-intake="${item.intake_id}"${disabled(busy)}>Review receipt ${escape(item.intake_id)}</button></li>`).join('')}</ul>` : '<p class="section-copy">No intake receipts are currently available.</p>'}
      ${active && detail ? `<section class="review-section" aria-labelledby="receipt-title"><h3 id="receipt-title">Receipt details</h3><dl class="summary-list"><dt>Applicant email</dt><dd>${escape(detail.email)}</dd><dt>Source / form</dt><dd>${escape(detail.source)} / ${escape(detail.form_id)}</dd><dt>Source reference</dt><dd>${escape(detail.response_id)}</dd><dt>Submitted</dt><dd>${escape(new Date(detail.submitted_at).toLocaleString())}</dd><dt>Inquiry</dt><dd>${escape(detail.inquiry_kind)}</dd><dt>Landing page</dt><dd>${escape(detail.landing_path)}</dd></dl>${admitted ? `<p class="notice">Workspace: ${escape(admitted)}. Reviewer assignment must be confirmed separately.</p>` : detail.inquiry_kind === 'partnership' ? '<p class="notice">Partnership inquiries are not eligible for pilot admission.</p>' : `<label class="check-line"><input id="staff-owner-authority" type="checkbox"${authority ? ' checked' : ''}${disabled(busy || Boolean(pending))}>I have checked the applicant's authority to act for the catalog owner.</label>${button('approve', 'Approve this pilot admission', busy || !authority || Boolean(pending), 'primary')}`}</section>` : ''}
      ${admission ? `<p class="notice">Admission confirmed. Pilot place ${admission.slot}; workspace ${escape(admission.workspace_id)}. This is not confirmation of invitation delivery or reviewer assignment.</p>` : ''}${pendingSection()}
      <details class="review-section"><summary>Record a manual Formspree receipt</summary><p class="field-hint">Optional, operator-attested entry, not a webhook or provider-ID claim. Check the source record for duplicates first. The internal receipt reference stays fixed during an uncertain retry.</p><form id="staff-manual-form" autocomplete="off" novalidate><fieldset${disabled(busy || !active || Boolean(pending))}><legend class="sr-only">Manual intake receipt</legend><label class="field" for="staff-email">Applicant email<input id="staff-email" name="email" type="email" maxlength="254" value="${escape(manual.email)}"></label><label class="field" for="staff-submitted">Original submission time, including UTC or offset<input id="staff-submitted" name="submitted_at" type="text" maxlength="80" value="${escape(manual.submitted_at)}" aria-describedby="submitted-help"><small id="submitted-help">Use YYYY-MM-DDTHH:mm:ssZ or a numeric timezone offset. Do not substitute the time of this entry.</small></label><label class="field" for="staff-landing">Original landing path<select id="staff-landing" name="landing_path">${PATHS.map(path => `<option value="${path}"${manual.landing_path === path ? ' selected' : ''}>${path}</option>`).join('')}</select></label><label class="check-line"><input id="staff-manual-attested" type="checkbox"${manualAttested ? ' checked' : ''}>I checked the original Formspree record for duplicates.</label><div class="actions"><button class="secondary" type="submit">Record manual receipt</button></div></fieldset></form></details></section>`;
  }

  function workspaceSection() {
    if (!session) return '';
    return `<section id="staff-workspace" class="review-section section-anchor"><h2>Assigned workspaces</h2><p class="section-copy">Reviewer assignments are made through the supervised operator process. No assignment-management API is available here. An intake admission alone does not grant reviewer access.</p>${button('workspaces', 'Refresh assigned workspaces', busy || !fresh())}
      ${fresh() && workspaces !== null ? workspaces.length ? `<ul class="summary-list">${workspaces.map(id => `<li><p class="field-hint">Workspace ${id}</p><button class="secondary" type="button" data-workspace="${id}"${disabled(busy)}>Open workspace ${id}</button></li>`).join('')}</ul>` : '<p class="notice">No assigned workspaces are available. Ask the supervised operator to check your assignment; intake approval is not an assignment.</p>' : '<p class="field-hint">Verify your passkey, then load your assigned cases.</p>'}
      <details><summary>Open a workspace by supplied ID</summary><form id="staff-context-form" autocomplete="off" novalidate><label class="field" for="staff-workspace-id">Assigned workspace ID<input id="staff-workspace-id" type="text" maxlength="36" value="${escape(workspaceId)}"${disabled(busy || !fresh())}></label><div class="actions"><button class="secondary" type="submit"${disabled(busy || !fresh())}>Open assigned review workspace</button></div></form></details></section>`;
  }

  function render(focusId) {
    if (destroyed) return;
    scrub();
    doc.getElementById('staff-environment-label').textContent = production ? 'Private pilot' : 'Integration test';
    doc.getElementById('staff-environment-note').textContent = production ? 'Restricted staff access. Review only information you are authorized to handle.' : 'Synthetic information only. Do not enter real customer information.';
    main.innerHTML = `<section class="screen"><p class="eyebrow">SPACE / staff review</p><h1>Review with clear authority.</h1><p class="intro">Sign in, verify your passkey, then review intake or open an assigned catalog workspace.</p>${errorBox()}${!clean ? '<p class="error">The address could not be cleared. Close this page and reopen the staff address. No requests will be sent.</p>' : ''}${securitySection()}${intakeSection()}${workspaceSection()}<section class="privacy-controls"><h2>Private session</h2><p class="section-copy">No browser storage or analytics. Logout, session expiry and page closure clear private entries. Reloading loses unsent entries and unresolved request references; inspect server records before starting a new request.</p>${button('clear', 'Clear this page', false, 'text-button')}</section></section>`;
    main.setAttribute('aria-busy', String(busy));
    const sections = [['staff-security', 'Identity & passkeys'], ...(session?.role === 'operator' ? [['staff-intakes', 'Intake review']] : []), ...(session ? [['staff-workspace', 'Assigned workspaces']] : [])];
    rail.innerHTML = `<p class="rail-kicker">Staff workspace</p><ol>${sections.map(([id, label], index) => `<li><a class="rail-item" href="#${id}"><span class="step-number">${index + 1}</span><span>${escape(label)}</span></a></li>`).join('')}</ol>`;
    announcement.textContent = message; if (focusId) focus(focusId);
  }

  async function refreshSession() { await run('Checking staff session', async current => { if (await loadSession(current)) feedback('Staff session refreshed. Protected actions still require fresh server-verified passkey proof.'); }); }
  async function signIn() {
    await run('Starting Google sign-in', async current => {
      const result = await client.signIn(); if (current !== epoch) return;
      const url = googleAuthorizationUrl(result?.authorization_url, win.location.origin);
      clear('Opening Google sign-in. No reviewer authority has been granted.'); navigate(url);
    });
  }

  async function passkey(kind) {
    if (!session || busy || (kind === 'enroll' ? session.state !== 'enrolling' || enrollment : kind === 'confirm' ? !enrollment : session.state !== 'active')) return;
    if (!win.isSecureContext || !win.navigator.credentials?.create || !win.navigator.credentials?.get) { feedback('Passkeys require a supported browser and a secure HTTPS connection. No fallback MFA checkbox is available.', true); render('staff-message'); return; }
    if (kind === 'enroll' && (!/^[A-Za-z0-9_-]{32,256}$/.test(permit))) { feedback('Enter the single-use permit supplied by your supervisor.', true); render('staff-message'); return; }
    const suppliedPermit = permit; permit = '';
    await run(kind === 'enroll' ? 'Registering supervised passkey' : 'Requesting signed passkey proof', async current => {
      const options = kind === 'enroll' ? await client.enrollmentOptions(suppliedPermit) : await client.assertionOptions(kind === 'confirm' ? enrollment.credential_id : undefined);
      if (current !== epoch || expiry()) return;
      const publicKey = credentialOptions(options, kind === 'enroll' ? 'create' : 'get', win);
      const controller = new win.AbortController(); authenticator = controller;
      let credential;
      try { credential = await win.navigator.credentials[kind === 'enroll' ? 'create' : 'get']({ publicKey, signal: controller.signal }); }
      catch { throw new StaffError('cancelled'); }
      finally { if (authenticator === controller) authenticator = null; }
      if (current !== epoch || expiry()) return;
      const proof = credentialJSON(credential, win);
      if (kind === 'enroll') {
        enrollment = { credential_id: proof.id, uncertain: true };
        const result = await client.enrollmentVerify({ challenge_id: options.challenge_id, credential: proof });
        if (current !== epoch) return;
        if (result?.confirmation_required !== true || result?.credential_id !== proof.id) throw new StaffError('contract');
        enrollment.uncertain = false;
        feedback('Passkey registered. Confirm possession with a signed assertion before enrolling the other key.');
      } else {
        const result = await client.assertionVerify({ challenge_id: options.challenge_id, credential: proof, confirmation: kind === 'confirm' });
        if (current !== epoch) return;
        if (kind === 'confirm' ? result?.confirmed !== true : !timestamp(result?.uv_expires_at)) throw new StaffError('contract');
        if (kind === 'confirm') enrollment = null;
        if (await loadSession(current)) feedback(kind === 'confirm'
          ? session.state === 'active' ? 'Both keys are confirmed. Verify a passkey once more for fresh access to protected actions.' : 'This key is confirmed. Use a new supervised permit to register and confirm the remaining key.'
          : fresh() ? 'Fresh passkey verification confirmed by the server. Protected actions are available for your role.' : 'The verification response was received, but fresh authority is not visible. Refresh the session; no protected action was resumed.');
      }
    });
  }

  async function loadIntakes() {
    if (!operator()) return;
    await run('Loading intake list', async current => {
      const items = listShape(await client.intakes()); if (current !== epoch || expiry() || !operator()) return;
      intakes = items;
      if (detail && !items.some(item => item.intake_id === detail.intake_id)) { detail = null; authority = false; }
      if (pending?.conflict) pending.conflictObserved = true;
      feedback('Intake list refreshed. No admission has been made or retried.');
    });
  }

  async function loadWorkspaces() {
    if (!fresh()) return;
    await run('Loading assigned workspaces', async current => {
      const result = await client.workspaces();
      if (current !== epoch || expiry() || !fresh()) return;
      if (!object(result) || !Array.isArray(result.workspace_ids) || result.workspace_ids.length > 1000
        || !result.workspace_ids.every(id => typeof id === 'string' && UUID.test(id))
        || new Set(result.workspace_ids).size !== result.workspace_ids.length) throw new StaffError('contract');
      workspaces = [...result.workspace_ids];
      feedback('Assigned workspaces refreshed. Select a case to establish its reviewer context.');
    });
  }

  async function loadDetail(id) {
    if (!operator() || !UUID.test(id) || !intakes?.some(item => item.intake_id === id)) return;
    await run('Loading receipt', async current => {
      const item = detailShape(await client.detail(id), id); if (current !== epoch || expiry() || !operator()) return;
      detail = item; authority = false; feedback('Receipt loaded. Confirm owner authority separately before approval.');
    });
  }

  async function mutation(kind, retry = false) {
    if (!operator() || busy || (pending && !retry)) return;
    if (!retry) {
      if (kind === 'approve') {
        if (!detail || !authority || detail.inquiry_kind === 'partnership' || intakes?.some(item => item.intake_id === detail.intake_id && item.workspace_id)) return;
        pending = { kind, intakeId: detail.intake_id, payload: Object.freeze({ request_id: uuid(), owner_authority_confirmed: true }) };
      } else {
        if (!manualAttested || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(manual.email) || manual.email.length > 254 || !timestamp(manual.submitted_at) || !PATHS.includes(manual.landing_path)) {
          feedback('Check the original email, submission time with timezone, landing path and duplicate-check confirmation.', true); render('staff-message'); return;
        }
        pending = { kind, payload: Object.freeze({ receipt_id: uuid(), ...manual }) };
      }
    }
    if (!pending || pending.kind !== kind) return;
    await run(kind === 'approve' ? 'Approving pilot admission' : 'Recording manual receipt', async current => {
      const attempt = pending; let result;
      try { result = kind === 'approve' ? await client.approve(attempt.intakeId, attempt.payload) : await client.manual(attempt.payload); }
      catch (cause) {
        if (current === epoch && cause?.status === 409) { attempt.conflict = true; attempt.conflictObserved = false; }
        if (current === epoch && [400, 422].includes(cause?.status)) pending = null;
        throw cause;
      }
      if (current !== epoch || expiry() || !operator()) return;
      if (kind === 'approve') {
        if (!UUID.test(result?.workspace_id) || typeof result.created !== 'boolean' || !Number.isInteger(result.slot) || result.slot < 1 || result.slot > 5) throw new StaffError('contract');
        admission = result; workspaceId = result.workspace_id; authority = false;
        intakes = intakes?.map(item => item.intake_id === attempt.intakeId ? { ...item, workspace_id: result.workspace_id } : item) ?? null;
        feedback('Pilot admission confirmed. Reviewer assignment and invitation delivery are separate; neither is confirmed by this action.');
      } else {
        if (result?.status !== 'suppressed' && (result?.status !== 'pending_review' || !UUID.test(result.intake_id) || typeof result.created !== 'boolean')) throw new StaffError('contract');
        manual = { email: '', submitted_at: '', landing_path: '/apply/' }; manualAttested = false;
        feedback(result.status === 'suppressed' ? 'The receipt was not added. No pilot admission was made.' : 'Manual receipt recorded. Refresh the list to review it; no pilot admission was made.');
      }
      pending = null;
    });
  }

  async function context() {
    if (!fresh()) return;
    if (!UUID.test(workspaceId)) { feedback('Enter the assigned workspace UUID supplied through the supervised operator process.', true); render('staff-message'); return; }
    const target = workspaceId;
    await run('Checking assigned reviewer context', async current => {
      const result = await client.context(target); if (current !== epoch || expiry() || !fresh()) return;
      if (result?.workspace_id !== undefined && result.workspace_id !== target) throw new StaffError('contract');
      clear('Reviewer context established. Opening the workspace.'); navigate('/workspace/');
    });
  }

  async function logout() {
    clear('Private information cleared. Closing the staff session...', true);
    const current = epoch; busy = true; render('staff-message');
    try { await client.logout(); if (current === epoch) feedback('Logged out. Private information has been cleared.'); }
    catch { if (current === epoch) feedback('This page is cleared, but server logout could not be confirmed. Close this tab; the server session may remain active until expiry.', true); }
    finally { if (current === epoch) { busy = false; render('staff-message'); } }
  }

  function onInput(event) {
    if (busy || expiry()) return;
    const target = event.target;
    if (target.id === 'staff-permit' && session?.state === 'enrolling' && !enrollment) permit = target.value;
    else if (target.id === 'staff-workspace-id' && fresh()) workspaceId = target.value.trim();
    else if (operator() && !pending) {
      if (target.id === 'staff-owner-authority' && detail) {
        authority = target.checked; const approve = main.querySelector('[data-action=approve]'); if (approve) approve.disabled = !authority;
      } else if (target.id === 'staff-manual-attested') manualAttested = target.checked;
      else if (['staff-email', 'staff-submitted', 'staff-landing'].includes(target.id)) manual[target.name] = target.value;
    }
  }
  function onSubmit(event) {
    event.preventDefault();
    if (event.target.id === 'staff-enroll-form') void passkey('enroll');
    else if (event.target.id === 'staff-manual-form') void mutation('manual');
    else if (event.target.id === 'staff-context-form') void context();
  }
  function onClick(event) {
    const target = event.target.closest('button'); if (!target || target.disabled || expiry()) return;
    const action = target.dataset.action;
    if (action === 'clear') { clear('This page was cleared. No server logout was requested.'); return; }
    if (action === 'logout') { void logout(); return; }
    if (busy) return;
    if (target.dataset.intake) void loadDetail(target.dataset.intake);
    else if (target.dataset.workspace && fresh() && workspaces?.includes(target.dataset.workspace)) { workspaceId = target.dataset.workspace; void context(); }
    else if (action === 'sign-in') void signIn();
    else if (action === 'refresh-session') void refreshSession();
    else if (action === 'confirm-key') void passkey('confirm');
    else if (action === 'verify') void passkey('verify');
    else if (action === 'list') void loadIntakes();
    else if (action === 'workspaces') void loadWorkspaces();
    else if (action === 'approve') void mutation('approve');
    else if (action === 'retry-mutation' && pending) void mutation(pending.kind, true);
    else if (action === 'discard-mutation' && pending?.conflictObserved) {
      pending = null; authority = false; feedback('Unresolved request discarded. It was not confirmed saved. Review server records before starting another request.'); render('staff-message');
    }
  }
  const onVisibility = () => expiry();
  const onPageHide = () => clear('This page was closed or suspended. Private information has been cleared. Refresh the staff session explicitly to reopen.');
  const onPageShow = event => { if (event.persisted) onPageHide(); else expiry(); };
  main.addEventListener('input', onInput); main.addEventListener('submit', onSubmit); main.addEventListener('click', onClick);
  doc.addEventListener('visibilitychange', onVisibility); win.addEventListener('focus', onVisibility);
  win.addEventListener('pagehide', onPageHide); win.addEventListener('pageshow', onPageShow);
  render(); if (autoStart) void refreshSession();
  return { destroy() {
    destroyed = true; clear(''); main.removeEventListener('input', onInput); main.removeEventListener('submit', onSubmit); main.removeEventListener('click', onClick);
    doc.removeEventListener('visibilitychange', onVisibility); win.removeEventListener('focus', onVisibility);
    win.removeEventListener('pagehide', onPageHide); win.removeEventListener('pageshow', onPageShow);
  } };
}

if (typeof window !== 'undefined' && window.document.querySelector('#staff-content')) createStaffApp();

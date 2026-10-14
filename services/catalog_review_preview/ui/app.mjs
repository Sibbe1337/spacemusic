import { ACCOUNT, RELEASES, DOCUMENTS, MONTHS, SCENARIOS, REPLIES, summarizeMonths } from '/fixtures.mjs';
import { canVisit, submissionIssues } from '/model.mjs';
import { createSession } from '/storage.mjs';

let browserStorage;
try { browserStorage = window.sessionStorage; } catch { /* Memory-only mode remains usable. */ }
const session = createSession(browserStorage);
const content = document.querySelector('#content');
const progress = document.querySelector('#progress');
const announcement = document.querySelector('#announcement');
const scenarioSelect = document.querySelector('#scenario');
let timer;
let pending = false;
let attemptedSave = false;
let attemptedSubmit = false;
let selectedSource = 'toolost';
let returnFromSettings = 'source';

const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const tag = (label, blue = false) => `<span class="status-tag${blue ? ' blue' : ''}">${escape(label)}</span>`;
const button = (text, action, primary = false) => `<button type="button" class="${primary ? 'primary' : 'text-button'}" data-action="${action}">${text}${primary ? '<span class="action-arrow" aria-hidden="true">&#8594;</span>' : ''}</button>`;
const submit = text => `<button type="submit" class="primary">${text}<span class="action-arrow" aria-hidden="true">&#8594;</span></button>`;
const heading = (kicker, title, intro) => `<div class="eyebrow">${kicker}</div><h1 tabindex="-1">${title}</h1><p class="intro">${intro}</p><div id="screen-error" class="error" role="alert" tabindex="-1"></div>`;
const back = step => `<button type="button" class="text-button" data-step="${step}">Back</button>`;
const money = value => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(Number(value));
const monthLabel = period => new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${period}-01T00:00:00Z`));
const selectedReleases = state => RELEASES.filter(release => state.selected.includes(release.id));
const ownershipLabels = { owned: 'I own the rights', shared: 'Rights are shared', unknown: 'Ownership needs clarification' };
const scopeLabels = { masters: 'Master recording rights', royalties: 'A share of existing royalties', unsure: 'Rights scope needs clarification' };
const obligationsLabels = { yes: 'Existing obligations to discuss', no: 'No obligations declared', unknown: 'Agreement status not yet confirmed' };

function renderProgress(state) {
  const groups = [
    ['Data source', ['invitation', 'source', 'permissions', 'provider', 'account', 'import', 'coverage']],
    ['Your catalog', ['selection']], ['Rights & documents', ['rights', 'documents']], ['Review & send', ['summary', 'status']],
  ];
  const current = groups.findIndex(([, steps]) => steps.includes(state.step));
  progress.innerHTML = `<p class="rail-kicker">Your review</p><nav class="rail" aria-label="Review steps"><ol>${groups.map(([label], index) => `<li><div class="rail-item${index < current ? ' done' : ''}" ${index === current ? 'aria-current="step"' : ''}><span class="step-number">${index < current ? '&#10003;' : `0${index + 1}`}</span><span>${label}</span></div></li>`).join('')}</ol></nav><div class="rail-foot"><strong>Northline Records</strong>DEMO-001<br>Fictional application<br>Free catalog review</div>`;
}

function invitation() {
  return heading('Your application is the starting point', 'Your catalog.<br>A clearer picture.', 'Bring your releases, rights and royalty history together. One place to prepare the information for a free, human-led review.') +
    `<div class="meta-line"><span><i class="dot" aria-hidden="true"></i>Fictional application received</span><span>No commitment to sell</span></div>
    <div class="split"><div><ul class="editorial-list"><li><h3>Start with what you have.</h3><p>Connect a supported distributor or add statements. You do not need a Too Lost account.</p></li><li><h3>You choose the catalog.</h3><p>Select existing releases and explain the rights you can offer. Future music stays outside the review.</p></li><li><h3>Know what happens next.</h3><p>Review the package before sending it. Any questions stay with your application.</p></li></ul><div class="actions">${button('Open demo review', 'start', true)}</div><p class="fine-print">This button simulates an authenticated invitation. It does not sign you in or create an application.</p></div>
    <section class="folio" aria-label="Sample review file"><div class="folio-label">Catalog review / 001</div><h2>Northline<br>Records</h2><dl><div><dt>Prepared for</dt><dd>Alex Morgan<br>alex@example.com</dd></div><div><dt>Review scope</dt><dd>Your selected existing releases</dd></div><div><dt>Next step</dt><dd>Add a source for your catalog</dd></div></dl><small>Fictional example. No real customer data.</small></section></div>`;
}

function source(state) {
  return heading('01 / Data source', 'A simple place<br>to start.', 'Choose the way that works for you. Both routes lead to the same free catalog review.') +
    `<form id="source-form"><fieldset class="source-fieldset"><legend class="sr-only">Choose how to add your catalog</legend>
      <label class="source-choice"><input type="radio" name="source" value="toolost" ${selectedSource === 'toolost' ? 'checked' : ''}><span class="source-copy"><span class="source-top"><h2>Connect Too Lost</h2>${tag('Read-only demo', true)}</span><p>Bring in release information and available royalty history. You choose the releases to include.</p></span></label>
      <label class="source-choice"><input type="radio" name="source" value="manual" ${selectedSource === 'manual' ? 'checked' : ''}><span class="source-copy"><span class="source-top"><h2>Add statements instead</h2></span><p>Use records from your distributor. The preview uses a sample release list and sample documents.</p></span></label>
    </fieldset>${state.source ? '<p class="fine-print">Continuing with a source starts a fresh demo package and clears previous selections and rights answers.</p>' : ''}<div class="actions">${submit('Continue')}${back('invitation')}</div></form>
    <details class="inline-details"><summary>What does connecting a distributor allow?</summary><p>The planned connection reads account identity, release metadata and reported royalties. It does not let SPACE change releases, move distribution or make payments. Available data still needs to be reviewed.</p></details>
    ${state.connection === 'disconnected' && state.source === 'toolost' ? '<p class="fine-print">No active provider connection. You can choose either route.</p>' : ''}`;
}

function permissions() {
  return heading('01 / Connection details', 'Your account.<br>Your control.', 'Before you continue, here is what the planned read-only connection would share and why.') +
    `<ul class="permission-list"><li><strong>Account identity</strong><span>Confirm which provider account belongs with this review. An email match alone is not proof of access.</span></li><li><strong>Release information</strong><span>List existing releases and recordings so you can choose what SPACE reviews.</span></li><li><strong>Reported royalties</strong><span>Bring together available periods and identify missing information. This is not a market valuation.</span></li></ul>
    <div class="notice"><strong>No changes to your music.</strong>SPACE would not upload or remove releases, move your distribution, withdraw funds or include future music automatically.</div>
    <p class="fine-print">In a live service you would authorize on Too Lost, never enter that password on SPACE. The next screen is only a labeled simulation. Live permission, retention and privacy wording still require approval.</p>
    <div class="actions">${button('Try connection demo', 'authorize', true)}${back('source')}</div>`;
}

function provider(state) {
  return heading('Preview / Simulated permission screen', 'No account needed<br>for this demo.', 'A live connection would leave SPACE for Too Lost\'s own authorization page. We do not recreate their login or collect credentials.') +
    `<div class="provider-screen"><h2>SPACE Catalog Review</h2><p>Planned permissions: <code>read:profile</code>, <code>read:releases</code> and <code>read:sales</code>.</p><p>${state.scenario === 'cancelled' ? 'This scenario simulates permission being declined. Try continuing to see the recovery message, or return to the document route.' : 'Continue to a fictional provider account. No OAuth request is made.'}</p>
    <div class="actions">${button('Simulate permission result', 'authorize-result', true)}${button('Cancel connection', 'cancel-authorization')}</div></div>`;
}

function account(state) {
  const wrong = state.scenario === 'wrong-account';
  return heading('01 / Confirm the account', 'The right catalog<br>starts here.', 'Check the account before starting an import. Nothing has been imported at this step.') +
    `<div class="account-line"><div><h2>${wrong ? 'Westbank Audio' : escape(ACCOUNT.name)}</h2><p>${wrong ? 'sam@example.com' : escape(ACCOUNT.email)}</p></div>${tag('Fictional account')}</div>
    ${wrong ? '<div class="notice warm"><strong>A different account is shown.</strong>This is not the Northline Records demo account. Return and use statements instead, or restart the standard demo.</div>' : '<div class="notice"><strong>Access does not prove ownership.</strong>We will still ask which rights you control and whether any agreements affect them.</div>'}
    <div class="actions">${wrong ? button('This is not my account', 'cancel-authorization', true) : button('Use this account & import', 'confirm-account', true)}${wrong ? '' : button('Use a different source', 'cancel-authorization')}</div>`;
}

function importScreen(state) {
  const complete = state.importStatus === 'complete';
  const partial = state.importStatus === 'partial';
  const stages = [
    ['Release information', state.checkpoint > 0 ? `${state.releases.length} fictional releases loaded.` : 'Waiting for the release fixture.'],
    ['Reported history', state.checkpoint > 1 ? partial ? '4 sample months loaded. Remaining history interrupted.' : '8 sample months loaded.' : 'Waiting for the royalty fixture.'],
    ['Coverage check', complete ? 'Missing months remain clearly marked.' : 'No review or valuation is performed.'],
  ];
  const stageFinished = index => state.checkpoint > index && !(partial && index === 1);
  return heading('01 / Synthetic import', complete ? 'Your sample data<br>is ready to review.' : partial ? 'A pause.<br>Not a lost start.' : 'Putting the pieces<br>together.', 'These stages load local fixtures only. A complete import is not a completed rights review.') +
    `<ol class="import-stages">${stages.map(([title, detail], index) => `<li class="${stageFinished(index) ? 'complete' : state.checkpoint === index || partial && index === 1 ? 'active' : ''}"><span class="stage-mark">${stageFinished(index) ? '&#10003;' : partial && index === 1 ? '!' : index + 1}</span><div class="stage-copy"><h3>${title}</h3><p>${detail}</p></div></li>`).join('')}</ol>
    ${partial ? '<div class="notice warm"><strong>Demo interruption after a saved checkpoint.</strong>The releases and completed sample periods are still here. Resume the remaining step or review what is available.</div>' : ''}
    <div class="actions">${complete ? button('Review imported information', 'coverage', true) : partial ? button('Resume sample import', 'retry-import', true) + button('Review partial information', 'coverage') : '<button type="button" class="primary" disabled>Loading sample data&hellip;</button>'}${button('Connection settings', 'settings')}</div>`;
}

function coverage(state) {
  const rows = state.releases.length === 0 ? [] : state.importStatus === 'partial' ? MONTHS.slice(0, 4) : MONTHS;
  const unknown = state.scenario === 'unknown-currency';
  const summary = summarizeMonths(rows, unknown ? null : 'EUR');
  const missingRange = rows.length === 0 ? 'Sep 2025 to Aug 2026' : state.importStatus === 'partial' ? 'Jan to Aug 2026' : 'May to Aug 2026';
  return heading('01 / Check the source', 'Clear about what<br>the data can tell us.', 'Account-level history is a source, not the value of your selected releases. Missing months are not treated as zero.') +
    `<div class="meta-line"><span>Source: fictional Too Lost fixture</span><span>Period: Sep 2025 &ndash; Aug 2026</span></div>
    <dl class="coverage"><div><dt>Reported months</dt><dd>${rows.length} of 12</dd><small>${12 - rows.length} months not confirmed</small></div><div><dt>Sample reported total</dt><dd>${summary.totalMinor === null ? 'Not available' : money(Number(summary.totalMinor) / 100)}</dd><small>${unknown ? 'Currency is not confirmed' : 'EUR declared by this synthetic fixture'}</small></div></dl>
    <div class="notice warm"><strong>${unknown ? 'Currency must be confirmed.' : 'The full 12-month picture is not available.'}</strong>${unknown ? 'No monetary total or valuation is calculated when currency is unknown. Individual source amounts are retained without a currency label.' : `${missingRange} is not confirmed in the sample. No annualized income, available cash or SPACE offer is inferred.`}${state.importStatus === 'partial' ? ' This interrupted import also has incomplete reported history.' : ''}</div>
    <details class="inline-details"><summary>See reported months and source limitations</summary><div class="table-wrap" role="region" aria-label="Reported royalty months" tabindex="0"><table><caption>Sample account overview. Not allocated to your selected releases.</caption><thead><tr><th scope="col">Reporting month</th><th scope="col">Status</th><th scope="col">${unknown ? 'Raw amount' : 'Sample EUR'}</th></tr></thead><tbody>${rows.map(row => `<tr><td>${monthLabel(row.period)}</td><td>Imported sample</td><td class="money">${unknown ? escape(row.amount) : money(row.amount)}</td></tr>`).join('')}<tr><td>${missingRange}</td><td>Not confirmed</td><td>Unknown</td></tr></tbody></table></div><p>The real API's currency and gross/net definitions still need confirmation. These fixture values are not evidence of an API capability. A negative adjustment is retained, not removed.</p></details>
    ${state.releases.length ? `<div class="actions">${button('Choose releases to review', 'selection', true)}${back('import')}</div>` : `<div class="empty-state"><h2>No releases in this sample account.</h2><p>You can continue with a sample document package instead. An empty result does not mean your catalog is ineligible.</p><div class="actions">${button('Use sample documents instead', 'manual-source', true)}</div></div>`}`;
}

function selection(state) {
  return heading('02 / Your catalog', 'Choose the music.<br>Keep the rest.', state.source === 'manual' ? 'A real document route would let you add your release list. This preview uses three fictional releases so no private catalog information is needed.' : 'Select the existing releases you want SPACE to review. A connected account does not put your whole catalog up for sale.') +
    `<form id="selection-form"><fieldset class="source-fieldset"><legend class="sr-only">Existing releases to review</legend><ul class="release-list">${RELEASES.filter(release => state.releases.includes(release.id)).map((release, index) => `<li><label class="release"><input type="checkbox" name="release" value="${release.id}" ${state.selected.includes(release.id) ? 'checked' : ''}><span class="release-info"><span class="release-title">${escape(release.title)}</span><span class="release-meta">${escape(release.artist)} &middot; ${escape(release.genre)}<br>${escape(release.kind)} &middot; Released ${escape(release.date)}</span></span><span class="release-count">${release.tracks} ${release.tracks === 1 ? 'track' : 'tracks'}<br>0${index + 1}</span></label></li>`).join('')}</ul></fieldset>
    <div class="notice"><strong>Future music stays yours.</strong>Only the selected existing releases enter this review. No rights are transferred by submitting information.</div><div class="actions">${submit('Continue with selected releases')}${back(state.source === 'manual' ? 'source' : 'coverage')}</div></form>`;
}

function options(items, value, placeholder = 'Choose an answer') {
  return `<option value="">${placeholder}</option>${Object.entries(items).map(([key, label]) => `<option value="${key}" ${key === value ? 'selected' : ''}>${label}</option>`).join('')}`;
}

function rights(state) {
  const saved = { ...state.rights, ...state.rightsDraft };
  return heading('03 / Rights & documents', 'A little context.<br>No guesswork.', 'Tell us what you know about the selected releases. An uncertain answer becomes a review question, not an automatic rejection.') +
    `<form id="rights-form" novalidate><div class="form-grid"><label class="field">Who controls these rights?<select name="ownership" required>${options(ownershipLabels, saved.ownership)}</select></label>
    <label class="field">Rights you want to discuss<select name="scope" required>${options(scopeLabels, saved.scope)}</select></label>
    <label class="field">Your owned share (%)<input type="number" inputmode="decimal" name="share" min="0.01" max="100" step="0.01" value="${escape(saved.share)}" ${saved.ownership === 'unknown' ? 'disabled' : ''} aria-describedby="share-help"><small id="share-help">Above 0 and up to 100. Leave blank if ownership is not yet confirmed.</small></label>
    <label class="field">Any agreements or obligations?<select name="obligations" required>${options(obligationsLabels, saved.obligations)}</select><small>For example, co-owners, advances, licenses or distribution terms.</small></label></div>
    <div class="notice"><strong>Different terms across releases?</strong>Use &ldquo;Rights are shared&rdquo; or &ldquo;Ownership needs clarification&rdquo; and include supporting documents. The percentage alone cannot establish legal ownership.</div>
    <div class="actions">${submit('Save demo choices & continue')}${back('selection')}</div><p class="fine-print">Demo choices are saved in this browser tab only, not to a customer record.</p></form>`;
}

function documents(state) {
  return heading('03 / Supporting documents', 'The records behind<br>the music.', 'Royalty statements and rights information help a reviewer understand the picture. Add the supplied samples, or flag what is not available yet.') +
    `<div class="notice"><strong>Sample files only in this preview.</strong>Real upload is intentionally disabled. These controls attach fixture references; no file is read, uploaded or security-scanned.</div>
    <div>${DOCUMENTS.map(document => `<div class="document"><span class="document-icon" aria-hidden="true"></span><div class="document-info"><h3>${escape(document.category)}</h3><p>${escape(document.name)}<br>${escape(document.description)}</p>${state.documents.includes(document.id) ? tag('Sample attached; not verified', true) : ''}</div><button type="button" class="text-button" data-document="${document.id}" data-remove="${state.documents.includes(document.id)}">${state.documents.includes(document.id) ? 'Remove sample' : 'Add sample'}</button></div>`).join('')}</div>
    <label class="check-line"><input type="checkbox" id="missing-evidence" ${state.missingEvidence ? 'checked' : ''}><span>Some supporting documents are not available yet.<br><small>Flag the gap for manual follow-up rather than filling it with an assumption.</small></span></label>
    <div class="actions">${button('Review the package', 'summary', true)}${back('rights')}</div>`;
}

function summary(state) {
  const selected = selectedReleases(state);
  const trackCount = selected.reduce((total, release) => total + release.tracks, 0);
  return heading('04 / Before you send', 'Your review.<br>Exactly as selected.', 'Check the scope and known gaps. This request starts a review, not a sale or a binding offer.') +
    `<section class="review-section"><div class="review-heading"><h2>Selected releases</h2><button type="button" class="text-button" data-step="selection">Edit releases</button></div><ul>${selected.map(release => `<li>${escape(release.title)} &middot; ${escape(release.artist)}</li>`).join('')}</ul><p>Future releases excluded. ${trackCount} sample ${trackCount === 1 ? 'track' : 'tracks'} selected.</p></section>
    <section class="review-section"><div class="review-heading"><h2>Rights to discuss</h2><button type="button" class="text-button" data-step="rights">Edit rights</button></div><dl><dt>Scope</dt><dd>${scopeLabels[state.rights.scope]}</dd><dt>Ownership</dt><dd>${ownershipLabels[state.rights.ownership]}</dd><dt>Declared share</dt><dd>${state.rights.share === null ? 'Not yet confirmed' : escape(state.rights.share) + '%'}</dd><dt>Other agreements</dt><dd>${obligationsLabels[state.rights.obligations]}</dd></dl></section>
    <section class="review-section"><div class="review-heading"><h2>Documents & known gaps</h2><button type="button" class="text-button" data-step="documents">Edit documents</button></div><ul>${state.documents.map(id => `<li>${escape(DOCUMENTS.find(doc => doc.id === id).name)} (sample)</li>`).join('') || '<li>No documents attached; flagged for follow-up.</li>'}</ul><p>${state.missingEvidence ? 'Missing documents flagged for the reviewer. ' : ''}${state.source === 'toolost' ? 'History is incomplete. Account totals are not the selected catalog\'s income or value.' : 'Statement figures and ownership still require manual review.'}</p></section>
    <label class="check-line"><input type="checkbox" id="confirm-scope" ${state.consent ? 'checked' : ''}><span>I have checked the demo selection. I understand that future music is excluded and submitting this package does not transfer any rights.</span></label>
    <div class="actions">${button('Submit demo for review', 'submit', true)}${back('documents')}</div><p class="fine-print">No real application, email, payment or review is created. In production, this would save a versioned submission only after server confirmation.</p>`;
}

function status(state) {
  const question = state.status === 'needs_information';
  return heading('04 / Demo submission ' + escape(state.submission.id), question ? 'One question.<br>All in one place.' : 'The next step<br>is a human one.', question ? 'The sample reviewer needs context on the missing reporting months. Your submitted package is unchanged.' : 'Your demo package is locked as version 1. A real review would now check rights, agreements and the supplied income history.') +
    `<div class="meta-line"><span>${tag(question ? 'Information requested (demo)' : state.reply ? 'Under review (demo)' : 'Submitted (demo)', true)}</span><span>Version 1 &middot; ${state.submission.selected.length} releases</span></div>
    <ol class="timeline"><li><span class="step-number">&#10003;</span><div><h3>Package prepared</h3><p>Selected releases, rights answers and document references captured in the demo.</p></div></li><li><span class="step-number">02</span><div><h3>${question ? 'Additional information requested' : 'Human review is next'}</h3><p>No automatic offer, valuation or approval is generated.</p></div></li><li><span class="step-number">03</span><div><h3>Discuss possible next steps</h3><p>A review does not guarantee an offer. You retain the choice whether to proceed.</p></div></li></ol>
    ${question ? `<section class="question"><h2>About the missing months</h2><p>Are statements for May to August 2026 available? If not, please confirm the limitation so it remains visible in the review.</p><form id="reply-form"><label class="field">Sample reply<select name="reply">${options(REPLIES, '')}</select></label><div class="actions">${submit('Save sample reply')}</div></form></section>` : state.reply ? `<div class="notice"><strong>Your sample reply</strong>${escape(REPLIES[state.reply])}<p>The submitted version remains unchanged. No email was sent.</p></div>` : `<div class="actions">${button('Preview a reviewer question', 'request-information', true)}</div>`}
    <details class="inline-details"><summary>View the submitted snapshot</summary><p>${state.submission.selected.map(id => escape(RELEASES.find(release => release.id === id).title)).join(' &middot; ')}</p><p>${escape(scopeLabels[state.submission.rights.scope])}. Declared share: ${state.submission.rights.share === null ? 'unknown' : escape(state.submission.rights.share) + '%'}. ${state.submission.documents.length} sample document references. Future music excluded.</p></details>`;
}

function settings(state) {
  const connected = state.connection === 'connected';
  return heading('Connection & privacy', 'Always your choice.', 'A data connection, a submitted review and a deletion request are different things. Each should have a clear, separate action.') +
    `<div class="account-line"><div><h2>Too Lost</h2><p>${connected ? 'Northline Records (fictional account)' : 'No active demo connection'}</p></div>${tag(connected ? 'Connected (demo)' : 'Disconnected')}</div>
    <ul class="permission-list"><li><strong>Access</strong><span>${connected ? 'Read-only demo: profile, releases and reported royalties.' : 'No provider credentials exist in this preview.'}</span></li><li><strong>Import status</strong><span>${escape(state.importStatus)}. ${state.checkpoint} of 3 local stages completed.</span></li><li><strong>What is retained</strong><span>Only fictional selections in this browser tab. Restarting clears the demo. Production retention terms still require approval.</span></li></ul>
    ${connected ? `<details class="inline-details"><summary>Disconnect the sample account</summary><p>This stops pending demo import stages. Existing sample selections remain available. This is not a provider revocation test.</p>${button('Confirm demo disconnect', 'disconnect')}</details>` : '<p class="fine-print">No remote access has been revoked because no real connection was made.</p>'}
    <section class="danger-zone"><h2>Request deletion</h2><p>A production request would need identity checks and a documented deletion process. Disconnecting alone must not be described as deleting the full review.</p>${state.deletionRequested ? '<div class="notice"><strong>Deletion request simulated.</strong>No real deletion request was sent. Use Restart selected demo to erase the local sample choices now.</div>' : button('Simulate a deletion request', 'request-deletion')}</section>
    <div class="actions">${button('Return to review', 'return', true)}</div>`;
}

function expired() {
  return heading('Session ended / Demo', 'Your place<br>is still here.', 'In the live portal you would verify your identity again before continuing. The demo keeps your choices in this tab.') +
    `<div class="notice"><strong>No email is sent from this preview.</strong>The button below simulates re-authentication. It is not a magic link or a security check.</div><div class="actions">${button('Resume demo session', 'resume-session', true)}</div>`;
}

const screens = { invitation, source, permissions, provider, account, import: importScreen, coverage, selection, rights, documents, summary, status, settings, expired };

function showError(message) {
  const region = content.querySelector('#screen-error');
  if (!region) return;
  region.textContent = message;
  region.focus();
}

function render({ focus = true, route = true } = {}) {
  clearTimeout(timer);
  const focusedDocument = document.activeElement?.dataset.document;
  const state = session.state;
  renderProgress(state);
  content.innerHTML = `<div class="screen">${screens[state.step](state)}</div>`;
  document.querySelector('#save-state').textContent = session.persistent ? 'Demo saved in this tab only' : 'Memory-only demo; reload may lose choices';
  scenarioSelect.value = state.scenario;
  const title = [...content.querySelector('h1').childNodes].map(node => node.nodeName === 'BR' ? ' ' : node.textContent).join('').replace(/\s+/g, ' ');
  document.title = `${title} | SPACE preview`;
  if (route && location.hash !== `#${state.step}`) history.pushState(null, '', `#${state.step}`);
  if (focus) content.querySelector('h1')?.focus({ preventScroll: false });
  else if (focusedDocument) content.querySelector(`[data-document="${focusedDocument}"]`)?.focus({ preventScroll: true });
  if (state.importStatus === 'running' && state.step !== 'expired' && state.connection === 'connected') {
    const run = state.run;
    timer = setTimeout(() => {
      const prior = session.state;
      session.dispatch({ type: 'import-tick', run });
      if (prior === session.state) return;
      announcement.textContent = `Demo import stage ${session.state.checkpoint} of 3. ${session.state.importStatus}.`;
      render({ focus: false });
    }, 800);
  }
}

function dispatch(event, focus = true) {
  if (pending) return;
  try { session.dispatch(event); render({ focus }); }
  catch (error) { showError(error.message); }
}

async function saveWithSimulation(event, kind) {
  if (pending) return;
  if (kind === 'submission' && submissionIssues(session.state).length) return showError(submissionIssues(session.state).join(' '));
  pending = true;
  const before = session.state;
  const controls = [...content.querySelectorAll('button')];
  controls.forEach(control => { control.disabled = true; });
  announcement.textContent = kind === 'rights' ? 'Saving demo choices.' : 'Saving demo submission.';
  await new Promise(resolve => setTimeout(resolve, 350));
  pending = false;
  if (session.state !== before) return render();
  const shouldFail = kind === 'rights' ? before.scenario === 'save-error' && !attemptedSave : before.scenario === 'submission-error' && !attemptedSubmit;
  if (kind === 'rights') attemptedSave = true; else attemptedSubmit = true;
  controls.forEach(control => { control.disabled = false; });
  if (shouldFail) {
    announcement.textContent = 'Simulated save failed. Your choices are still on screen.';
    return showError('Simulated save failure. Nothing was submitted. Your choices are still here; try the same button again.');
  }
  dispatch(event);
  announcement.textContent = session.state.step === 'documents' ? 'Demo choices saved in this tab.' : session.state.step === 'status' ? 'Demo submission saved. Nothing sent to SPACE.' : 'Check the highlighted error. Nothing submitted.';
}

function navigate(step) {
  if (pending) return;
  if (step === 'invitation' && session.state.submission) step = 'status';
  if (step === 'settings') returnFromSettings = session.state.step;
  dispatch({ type: 'navigate', step });
}

content.addEventListener('click', event => {
  const target = event.target.closest('button');
  if (!target || pending) return;
  if (target.dataset.step) return navigate(target.dataset.step);
  if (target.dataset.document) return dispatch({ type: target.dataset.remove === 'true' ? 'remove-document' : 'add-document', id: target.dataset.document }, false);
  const action = target.dataset.action;
  if (!action) return;
  if (['coverage', 'selection', 'summary', 'settings'].includes(action)) return navigate(action);
  if (action === 'manual-source') {
    session.dispatch({ type: 'navigate', step: 'source' });
    return dispatch({ type: 'source', source: 'manual' });
  }
  if (action === 'return') return navigate(session.state.submission ? 'status' : canVisit(session.state, returnFromSettings) ? returnFromSettings : 'source');
  if (action === 'submit') return saveWithSimulation({ type: 'submit' }, 'submission');
  dispatch({ type: action });
});

content.addEventListener('submit', event => {
  event.preventDefault();
  if (pending) return;
  const data = new FormData(event.target);
  switch (event.target.id) {
    case 'source-form': return dispatch({ type: 'source', source: data.get('source') });
    case 'selection-form': return dispatch({ type: 'select', ids: data.getAll('release') });
    case 'rights-form': return saveWithSimulation({ type: 'rights', ownership: data.get('ownership'), scope: data.get('scope'), share: String(data.get('share') || '').trim(), obligations: data.get('obligations') }, 'rights');
    case 'reply-form': return dispatch({ type: 'reply', id: data.get('reply') });
  }
});

content.addEventListener('change', event => {
  if (event.target.name === 'source') selectedSource = event.target.value;
  if (event.target.name === 'ownership') {
    const share = content.querySelector('[name=share]');
    share.disabled = event.target.value === 'unknown';
    if (share.disabled) share.value = '';
  }
  if (event.target.id === 'missing-evidence') {
    session.dispatch({ type: 'missing-evidence', value: event.target.checked });
    announcement.textContent = 'Document availability updated in the demo.';
  }
  if (event.target.id === 'confirm-scope') session.dispatch({ type: 'confirm-scope', value: event.target.checked });
});

content.addEventListener('input', event => {
  if (event.target.closest('#rights-form')) {
    try { session.dispatch({ type: 'edit-rights', field: event.target.name, value: event.target.value }); }
    catch { /* Final validation explains unsupported numeric input without discarding it. */ }
  }
});

document.querySelector('.masthead').addEventListener('click', event => {
  const anchor = event.target.closest('a');
  if (!anchor) return;
  event.preventDefault();
  if (anchor.hash === '#help') {
    document.querySelector('#help').open = true;
    document.querySelector('#help summary').focus();
    return;
  }
  navigate(anchor.hash.slice(1));
});

scenarioSelect.innerHTML = Object.entries(SCENARIOS).map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
document.querySelector('#restart').addEventListener('click', () => {
  if (pending) return;
  clearTimeout(timer);
  session.reset(scenarioSelect.value);
  attemptedSave = false; attemptedSubmit = false; selectedSource = 'toolost'; returnFromSettings = 'source';
  document.querySelector('#preview-controls').open = false;
  render();
  announcement.textContent = 'Demo restarted with fictional data only.';
});
document.querySelector('#expire-session').addEventListener('click', () => {
  dispatch({ type: 'expire' });
  document.querySelector('#preview-controls').open = false;
});
window.addEventListener('popstate', () => {
  if (pending) return;
  const step = location.hash.slice(1);
  if (canVisit(session.state, step)) session.dispatch({ type: 'navigate', step });
  else history.replaceState(null, '', `#${session.state.step}`);
  render({ route: false });
});
history.replaceState(null, '', `#${session.state.step}`);
render({ focus: false, route: false });
if (session.restored) announcement.textContent = 'Your saved demo choices have been restored in this tab.';

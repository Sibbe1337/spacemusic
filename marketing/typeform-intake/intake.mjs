export const FORM_ID = 'xzx5SBJb';
export const FORM_ENDPOINT = 'https://formspree.io/f/mpwdnokz';

export function sourceMetadata(win) {
  const result = {};
  try {
    const candidate = win.spaceFunnel?.sources?.() || {};
    for (const name of ['landing_path', 'apply_source_path']) {
      const value = win.spaceFunnel?.publicPath?.(candidate[name]);
      if (value) result[name] = value;
    }
  } catch { /* Attribution is optional and must never block a request. */ }
  return result;
}

export function embedOptions(win, container, callbacks) {
  return {
    container, domain: 'form.typeform.com', source: 'spacemusic.io', medium: 'space-intake',
    mediumVersion: '20260915-v1', inlineOnMobile: true, autoFocus: false,
    transitiveSearchParams: [], hidden: sourceMetadata(win), tracking: {},
    disableTracking: true, shareGaInstance: false, hubspot: false, noHeading: true,
    redirectTarget: '_self',
    iframeProps: { title: 'SPACE catalog review and partnership inquiry', referrerpolicy: 'no-referrer', allow: '' },
    ...callbacks,
  };
}

export function initialize(win, doc, sdkPath) {
  const start = doc.getElementById('start-intake');
  const container = doc.getElementById('typeform-container');
  const status = doc.getElementById('embed-status');
  const details = doc.getElementById('short-form-details');
  const form = doc.getElementById('short-form');
  const error = doc.getElementById('short-form-error');
  const confirmation = doc.getElementById('intake-confirmation');
  const submit = form.querySelector('button[type="submit"]');
  let loading = false, ready = false, submitting = false, completed = false, mounted = false;
  let startedEvent = false, submittedEvent = false;
  let sdkPromise, widget, readinessTimeout;

  function track(name) {
    try { win.spaceFunnel?.track?.(name); } catch { /* Analytics failure is not a form failure. */ }
  }
  function success(name) {
    if (completed) return;
    completed = true;
    win.clearTimeout(readinessTimeout);
    if (!submittedEvent) { submittedEvent = true; track(name); }
    doc.getElementById('intake-card').hidden = true;
    confirmation.hidden = false;
    confirmation.focus();
    form.reset();
  }
  function failEmbed() {
    status.textContent = 'If the guided form does not load, use the short form below or email hello@spacemusic.io. No request has been confirmed on this page.';
    loading = false;
    start.disabled = false;
    start.textContent = ready ? 'Return to guided form' : 'Try loading the guided form again';
  }
  function watchReadiness() {
    win.clearTimeout(readinessTimeout);
    readinessTimeout = win.setTimeout(() => { if (!ready && !completed) failEmbed(); }, 15000);
  }
  function loadSdk() {
    if (win.embed?.createWidget) return Promise.resolve(win.embed);
    if (sdkPromise) return sdkPromise;
    sdkPromise = new Promise((resolve, reject) => {
      const script = doc.createElement('script');
      script.src = sdkPath; script.async = true;
      const timeout = win.setTimeout(() => { script.remove(); sdkPromise = undefined; reject(new Error('sdk_timeout')); }, 15000);
      script.onload = () => { win.clearTimeout(timeout); if (win.embed?.createWidget) resolve(win.embed); else { sdkPromise = undefined; reject(new Error('sdk_missing')); } };
      script.onerror = () => { win.clearTimeout(timeout); script.remove(); sdkPromise = undefined; reject(new Error('sdk_unavailable')); };
      doc.head.append(script);
    });
    return sdkPromise;
  }

  start.hidden = false;
  start.addEventListener('click', async () => {
    if (loading || submitting || completed) return;
    details.open = false;
    container.hidden = false;
    container.inert = false;
    if (mounted && ready) { container.scrollIntoView?.({ block: 'start' }); container.querySelector('iframe')?.focus({ preventScroll: true }); return; }
    loading = true; start.disabled = true;
    status.textContent = 'Loading the guided form...';
    try {
      if (mounted && widget?.refresh) {
        watchReadiness();
        widget.refresh();
        return;
      }
      const sdk = await loadSdk();
      if (completed) return;
      mounted = true;
      watchReadiness();
      widget = sdk.createWidget(FORM_ID, embedOptions(win, container, {
        onReady: () => {
          win.clearTimeout(readinessTimeout);
          ready = true; loading = false; start.disabled = false; start.textContent = 'Return to guided form';
          status.textContent = 'Your answers are sent only when you finish the form.';
          if (!details.open && !completed) { container.scrollIntoView?.({ block: 'start' }); container.querySelector('iframe')?.focus({ preventScroll: true }); }
        },
        // Mixed owner/representative/partnership flow: do not count these as seller applications.
        onStarted: () => { if (!startedEvent) { startedEvent = true; track('intake_started'); } },
        onSubmit: () => success('intake_submitted'),
      }));
    } catch {
      win.clearTimeout(readinessTimeout);
      if (!ready) { widget?.unmount?.(); container.replaceChildren(); widget = undefined; mounted = false; }
      failEmbed();
    }
  });
  details.addEventListener('toggle', () => {
    if (details.open) { container.hidden = true; container.inert = true; }
  });
  form.addEventListener('change', () => { try { win.spaceFunnel?.once?.('application_started'); } catch {} });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || completed || !form.reportValidity()) return;
    submitting = true; submit.disabled = true; start.disabled = true;
    error.hidden = true; submit.textContent = 'Sending...';
    const data = new win.FormData(form);
    data.set('consentMarketing', data.get('consentMarketing') === 'true' ? 'true' : 'false');
    for (const [name, value] of Object.entries(sourceMetadata(win))) data.set(name, value);
    // Preserve the legacy receiver. Never duplicate a Typeform request here automatically.
    try {
      const result = await win.fetch(FORM_ENDPOINT, { method: 'POST', body: data,
        headers: { Accept: 'application/json' }, signal: win.AbortSignal.timeout(20000) });
      if (!result.ok) throw new Error('not_accepted');
      success('application_submitted');
    } catch {
      error.textContent = 'We could not confirm receipt. Your details are still here. Check for a confirmation before retrying; if unsure, contact hello@spacemusic.io so we can check without a duplicate request.';
      error.hidden = false;
    } finally {
      submitting = false; submit.disabled = completed; start.disabled = completed;
      submit.textContent = 'Request a free catalog review';
    }
  });
}

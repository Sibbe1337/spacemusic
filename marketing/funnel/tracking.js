(function () {
  if (window.spaceFunnel) return;
  const publicPaths = new Set(__PUBLIC_PATHS__);
  const events = new Set(['calculator_used', 'apply_clicked', 'application_started', 'application_submitted']);
  const prefix = 'space.funnel.v1.';
  const memory = {};
  function publicPath(value) {
    if (typeof value !== 'string' || !value.startsWith('/') || /[?#\\]/.test(value)) return '';
    const normalized = value === '/' || /\.[a-z]+$/i.test(value) ? value : value.replace(/\/$/, '') + '/';
    return publicPaths.has(normalized) ? normalized : '';
  }
  function read(key) {
    try { return sessionStorage.getItem(prefix + key) || memory[key] || ''; }
    catch { return memory[key] || ''; }
  }
  function save(key, value) {
    memory[key] = value;
    try { sessionStorage.setItem(prefix + key, value); } catch { /* Storage is optional. */ }
  }
  function sources() {
    const result = {};
    for (const key of ['landing_path', 'apply_source_path']) {
      const value = publicPath(read(key));
      if (value) result[key] = value;
    }
    return result;
  }
  const current = publicPath(location.pathname);
  if (current && !publicPath(read('landing_path'))) save('landing_path', current);
  if (current === '/apply/' && !publicPath(read('apply_source_path'))) {
    try {
      const referrer = new URL(document.referrer);
      if (referrer.origin === location.origin) {
        const source = publicPath(referrer.pathname);
        if (source && source !== '/apply/') save('apply_source_path', source);
      }
    } catch { /* Direct visits have no referring public page. */ }
  }
  function track(name) {
    try {
      if (events.has(name) && publicPath(location.pathname)) window.plausible?.(name, { props: sources() });
    } catch { /* Analytics must never control the application flow. */ }
  }
  function once(name) {
    if (!events.has(name) || read('sent.' + name)) return;
    save('sent.' + name, '1');
    track(name);
  }
  function transformRequest(payload) {
    try {
      if (!['spacemusic.io', 'www.spacemusic.io'].includes(location.hostname)) return null;
      if (!['pageview', 'engagement', ...events].includes(payload.n)) return null;
      const pathname = publicPath(new URL(payload.u).pathname);
      if (!pathname) return null;
      const props = {};
      if (events.has(payload.n)) for (const key of ['landing_path', 'apply_source_path']) {
        const value = publicPath(payload.p?.[key]);
        if (value) props[key] = value;
      }
      let referrer = '';
      if (payload.r) {
        const ref = new URL(payload.r);
        if (/^https?:$/.test(ref.protocol)) referrer = ref.origin;
      }
      // Construct, rather than mutate: no amounts, arbitrary props, query strings or tokens survive.
      return { n: payload.n, u: 'https://spacemusic.io' + pathname, d: 'spacemusic.io', r: referrer,
        p: props, ...(Number.isFinite(payload.sd) ? { sd: payload.sd } : {}),
        ...(Number.isFinite(payload.e) ? { e: payload.e } : {}) };
    } catch { return null; }
  }
  window.spaceFunnel = { track, once, sources, publicPath, transformRequest };
  document.addEventListener('click', function (event) {
    try {
      const anchor = event.target.closest?.('a[href]');
      if (!anchor) return;
      const destination = new URL(anchor.href, location.href);
      if (destination.origin !== location.origin || publicPath(destination.pathname) !== '/apply/') return;
      const source = publicPath(location.pathname);
      if (source && source !== '/apply/') {
        save('apply_source_path', source);
        track('apply_clicked');
      }
    } catch { /* Leave navigation untouched. */ }
  }, true);
  window.plausible = window.plausible || function () { (window.plausible.q = window.plausible.q || []).push(arguments); };
  window.plausible.init = window.plausible.init || function (options) { window.plausible.o = options; };
  window.plausible.init({ transformRequest, formSubmissions: false, outboundLinks: false, fileDownloads: false });
})();

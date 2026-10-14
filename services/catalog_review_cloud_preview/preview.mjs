import { createApp } from './app.mjs';
import { createClient, PortalError } from './client.mjs';

const scenarios = ['draft', 'submitted', 'followup', 'completed', 'reviewer'];
const requested = new URL(location.href).searchParams.get('scenario');
const scenario = scenarios.includes(requested) ? requested : 'draft';
const status = document.getElementById('preview-status');
for (const link of document.querySelectorAll('[data-scenario]')) {
  if (link.dataset.scenario === scenario) link.setAttribute('aria-current', 'page');
}
const client = createClient({ fetchImpl: async (url, options) => {
  if (url !== '/api/portal/workspace' || options.method !== 'GET') throw new PortalError('preview-read-only', 405);
  const response = await fetch(url, { ...options, headers: { ...options.headers, 'X-Preview-Scenario': scenario } });
  status.textContent = response.ok
    ? 'Read-only preview. Example records loaded from the isolated preview API. No customer data, uploads, emails or real login.'
    : 'The preview backend is unavailable. No customer information is involved. Use Refresh below to try again.';
  return response;
} });
const content = document.getElementById('content');
function lockWrites() {
  for (const element of content.querySelectorAll('input, textarea, select, button')) {
    if (element.matches('button[data-action="refresh"]')) continue;
    element.disabled = true;
    element.setAttribute('aria-describedby', 'preview-status');
    element.title = 'Read-only preview. Choose a stage above to explore the next screen.';
  }
}
// Defense in depth: the public preview never forwards writes or file bytes.
content.addEventListener('submit', event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
const observer = new MutationObserver(lockWrites);
observer.observe(content, { childList: true, subtree: true });
createApp({ client });
lockWrites();
content.querySelector('[data-action="refresh"]')?.click();

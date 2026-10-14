import { App } from '@modelcontextprotocol/ext-apps';
import { createDeskState } from './state.mjs';

const content = document.querySelector('#content');
const feedback = document.querySelector('#feedback');
const app = new App({ name: 'SPACE Catalog Desk demo', version: '0.1.0' }, {});
const labels = { provided: 'Supplied / not verified', missing: 'Missing', clarify: 'Needs clarification',
  blocked: 'Blocked', outside_scope: 'Outside scope', potential: 'Potential / not verified' };
function el(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function button(text, action, className = 'text-button') {
  const node = el('button', text, className);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}
function status(value) {
  const node = el('span', labels[value], 'status');
  node.dataset.status = value;
  return node;
}
function report(message, canRetry = false) {
  feedback.replaceChildren(el('span', message));
  if (canRetry) feedback.append(button('Try again', () => state.retry()));
}
function setBusy(value) {
  content.setAttribute('aria-busy', String(value));
  document.querySelectorAll('button').forEach(node => { node.disabled = value; });
}
function openCase(id, view = 'review') {
  return state.run(view === 'review' ? 'space_review_demo_catalog' : 'space_compare_demo_buyers', { case_id: id });
}
function heading(text) {
  const h1 = el('h1', text);
  h1.tabIndex = -1;
  return h1;
}
function overview(data) {
  const intro = el('section', undefined, 'intro');
  intro.append(el('p', 'Catalog intelligence / Demo', 'eyebrow'), heading('A clearer path to a catalog deal.'),
    el('p', 'See what is supplied, what still needs review, and where buyer criteria fit. Start with a fictional catalog below.', 'lede'));
  const sectionHead = el('div', undefined, 'section-head');
  sectionHead.append(el('h2', 'Three catalogs. Different next steps.'), el('span', 'Examples, not live opportunities'));
  const list = el('div', undefined, 'catalog-list');
  for (const [index, item] of data.cases.entries()) {
    const row = el('article', undefined, 'catalog-row');
    const body = el('div');
    body.append(el('h3', item.name), el('p', `${item.rights} / ${item.description}`),
      el('p', item.nextStep, 'next-step'), el('p', `${item.provided} of 6 document categories supplied. Not verified.`));
    const action = button('Open review', () => openCase(item.id), 'row-button');
    action.setAttribute('aria-label', `Open review for ${item.name}`);
    row.append(el('span', String(index + 1).padStart(2, '0'), 'number'), body, action);
    list.append(row);
  }
  content.append(intro, sectionHead, list, el('p', 'All catalogs, figures, document references and buyer profiles are fictional. This is a read-only demonstration, not a valuation service.', 'note'));
}
function review(data) {
  const item = data.selected;
  if (!item) throw new Error('Missing catalog');
  content.append(button('Back to catalogs', () => state.run('space_list_demo_catalogs', {}), 'text-button back'));
  const top = el('div', undefined, 'review-top');
  const title = el('div');
  title.append(el('p', `${item.rights} / Fictional catalog`, 'eyebrow'), heading(item.name), el('p', item.description, 'small'));
  const count = el('div', undefined, 'count');
  count.append(el('strong', `${item.provided} / 6`), el('span', 'categories supplied'));
  top.append(title, count);
  content.append(top, el('p', item.offeredShare, 'scope'), el('p', item.financialContext, 'financial'));
  const nav = el('nav', undefined, 'view-nav');
  nav.setAttribute('aria-label', 'Catalog views');
  for (const [view, name] of [['review', 'Evidence & next steps'], ['buyers', 'Buyer criteria']]) {
    const control = button(name, () => openCase(item.id, view));
    control.setAttribute('aria-pressed', String(data.view === view));
    nav.append(control);
  }
  content.append(nav);
  if (data.view === 'review') {
    content.append(el('p', 'Supplied does not mean verified. A human reviewer must assess each category.', 'small'));
    for (const check of item.checks) {
      const section = el('section', undefined, 'check');
      const row = el('div', undefined, 'row-top');
      row.append(el('h2', check.label), status(check.status));
      section.append(row, el('p', check.finding), el('p', `Next: ${check.nextStep}`, 'action'),
        el('span', `Fixture source: ${check.sourceId}`, 'source-ref'));
      content.append(section);
    }
  } else {
    content.append(el('p', 'These are invented buyer profiles, not real buyers or market benchmarks. No material can be sent from this demo.', 'small'));
    for (const match of data.matches) {
      const section = el('section', undefined, 'buyer');
      const row = el('div', undefined, 'row-top');
      row.append(el('h2', match.name), status(match.status));
      const reasons = el('ul');
      for (const reason of match.reasons) reasons.append(el('li', reason));
      section.append(row, el('p', match.criteria), reasons, el('span', `Fictional criteria source: ${match.sourceId}`, 'source-ref'));
      content.append(section);
    }
  }
  const next = el('section', undefined, 'next-panel');
  next.append(el('p', 'Next review step', 'eyebrow'), el('p', item.nextStep),
    el('p', 'No buyer introduction is authorized. Seller permission must name the recipient and the exact materials.', 'small'));
  const sources = el('details');
  sources.append(el('summary', 'About the fictional sources'));
  const list = el('ul', undefined, 'sources');
  for (const source of item.sources) {
    const row = el('li');
    row.append(el('strong', `${source.id} / ${source.label}`), el('span', source.note));
    list.append(row);
  }
  sources.append(list);
  content.append(next, sources);
}
const state = createDeskState({
  callTool: (name, args) => app.callServerTool({ name, arguments: args }, { timeout: 8000 }),
  clear: () => feedback.replaceChildren(), busy: setBusy, report,
  render(data, focus) {
    content.replaceChildren();
    if (data.view === 'overview') overview(data); else review(data);
    if (focus) content.querySelector('h1')?.focus({ preventScroll: true });
  },
});
function theme(context) {
  if (['light', 'dark'].includes(context?.theme)) document.documentElement.dataset.theme = context.theme;
}
app.ontoolresult = result => state.receive(result);
app.ontoolcancelled = () => state.cancel();
app.onhostcontextchanged = theme;
app.onteardown = async () => { state.cancel(); return {}; };
if (window.parent === window) {
  content.setAttribute('aria-busy', 'false');
  report('Open the local preview homepage or connect this widget through a compatible MCP Apps host. No standalone data fallback is enabled.');
} else {
  try {
    await app.connect(undefined, { timeout: 8000 });
    theme(app.getHostContext());
    setTimeout(() => {
      if (!state.snapshot) { setBusy(false); report('The host has not supplied a demo result. Ask it to open the SPACE demo catalogs.'); }
    }, 10000);
  } catch {
    setBusy(false);
    report('Could not connect to the host. Reload the preview or refresh the ChatGPT connection. No data was accessed.');
  }
}

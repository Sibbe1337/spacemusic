// Shared engine for the authenticity release: applies reviewed text edits
// ({find, replace}) to decoded string literals in active JS modules and to the
// matching text in prerendered HTML (text nodes, meta/title attributes, JSON-LD).
import assert from 'node:assert/strict';
import {readFile, readdir} from 'node:fs/promises';
import path from 'node:path';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from './funnel-support.mjs';

export const SOURCE = 'tmp/motion-preview-v3-20260929';
export const EDITS_DIR = 'marketing/authentic-20260929/edits';

export function stringNodes(code) {
  const out = [];
  (function visit(n) {
    if (!n || typeof n !== 'object') return;
    if (n.type === 'StringLiteral') out.push({start: n.start, end: n.end, value: n.value});
    else if (n.type === 'TemplateLiteral' && n.expressions.length === 0) out.push({start: n.start, end: n.end, value: n.quasis[0].value.cooked});
    else if (n.type === 'TemplateLiteral') out.push({start: n.start, end: n.end, template: true});
    for (const [k, v] of Object.entries(n)) if (k !== 'loc') {
      if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v === 'object') visit(v);
    }
  })(parse(code, {sourceType: 'module'}));
  return out;
}

export async function loadSite(source = SOURCE) {
  const inventory = await files(source);
  const codes = new Map();
  for (const f of inventory.filter(f => /^assets\/.*\.js$/.test(f))) codes.set(path.basename(f), await readFile(path.join(source, f), 'utf8'));
  const home = await readFile(path.join(source, 'index.html'), 'utf8');
  const entry = home.match(/<script type="module"[^>]*src="\/assets\/([^"]+)"/)[1];
  const deps = n => stringNodes(codes.get(n)).filter(x => typeof x.value === "string").map(x => path.basename(x.value)).filter(x => codes.has(x) && x !== n);
  const active = new Set();
  (function v(n) { if (active.has(n)) return; active.add(n); deps(n).forEach(v); })(entry);
  const htmlFiles = inventory.filter(f => f.endsWith('.html'));
  return {source, inventory, codes, entry, active, deps, htmlFiles};
}

export async function loadEdits(dir = EDITS_DIR, only) {
  const names = (await readdir(dir)).filter(f => f.endsWith('.json') && (!only || only.includes(f))).sort();
  const edits = [];
  for (const n of names) {
    const doc = JSON.parse(await readFile(path.join(dir, n), 'utf8'));
    for (const [i, e] of doc.edits.entries()) {
      assert(typeof e.find === 'string' && e.find.length >= 3, `${n}#${i} find`);
      assert(typeof e.replace === 'string', `${n}#${i} replace`);
      edits.push({...e, file: n, index: i});
    }
  }
  return edits;
}

const inModule = (e, name) => !e.modules || e.modules.some(p => name.startsWith(p));
const inPage = (e, file) => !e.pages || !file || e.pages.some(p => file.startsWith(p));
const count = (hay, needle) => { let c = 0, i = 0; while ((i = hay.indexOf(needle, i)) !== -1) { c++; i += needle.length; } return c; };

// Returns per-edit match counts and the rewritten module code.
export function applyToModules(site, edits) {
  const stats = edits.map(() => ({js: 0, modules: new Set()}));
  const changed = new Map();
  for (const name of site.active) {
    let code = site.codes.get(name);
    // Code edits: exact source replacement, only in the modules they name.
    edits.forEach((e, i) => {
      if (!e.code) return;
      assert(e.modules, `code edit needs modules: ${e.file}#${e.index}`);
      if (!inModule(e, name)) return;
      const c = count(code, e.find);
      if (c) { stats[i].js += c; stats[i].modules.add(name); code = code.split(e.find).join(e.replace); }
    });
    if (code !== site.codes.get(name)) { parse(code, {sourceType: 'module'}); changed.set(name, code); }
    const nodes = stringNodes(code);
    const rewrites = [];
    for (const node of nodes) {
      if (node.template) {
        // Template literal with expressions: edits marked `template: true` match
        // the literal's source text, e.g. "an independent ${a} producer".
        let raw = code.slice(node.start, node.end), touched = false;
        edits.forEach((e, i) => {
          if (!e.template || e.code || !inModule(e, name)) return;
          const c = count(raw, e.find);
          if (c) { stats[i].js += c; stats[i].modules.add(name); raw = raw.split(e.find).join(e.replace.replace(/`/g, '\\`')); touched = true; }
        });
        if (touched) rewrites.push({...node, text: raw});
        continue;
      }
      let value = node.value, touched = false;
      edits.forEach((e, i) => {
        if (e.code || e.jsonLd) return;
        if (e.href) { if (value === e.find && inModule(e, name)) { stats[i].js++; stats[i].modules.add(name); value = e.replace; touched = true; } return; }
        if (e.template || e.htmlOnly || !inModule(e, name)) return;
        const c = count(value, e.find);
        if (c) { stats[i].js += c; stats[i].modules.add(name); value = value.split(e.find).join(e.replace); touched = true; }
      });
      if (touched) rewrites.push({...node, text: JSON.stringify(value)});
    }
    if (rewrites.length) {
      let next = code;
      for (const r of rewrites.sort((a, b) => b.start - a.start)) next = next.slice(0, r.start) + r.text + next.slice(r.end);
      parse(next, {sourceType: 'module'});
      changed.set(name, next);
    }
  }
  return {stats, changed};
}

// Applies edits to one HTML document. Returns {html, counts}.
export function applyToHtml(html, edits, file) {
  const dom = new JSDOM(html);
  const d = dom.window.document;
  const counts = edits.map(() => 0);
  const swap = s => { edits.forEach((e, i) => { if (e.template || e.href || e.code || e.jsonLd || !inPage(e, file)) return; const c = count(s, e.find); if (c) { counts[i] += c; s = s.split(e.find).join(e.replace); } }); return s; };
  const walker = d.createTreeWalker(d.documentElement, dom.window.NodeFilter.SHOW_TEXT);
  const texts = []; while (walker.nextNode()) texts.push(walker.currentNode);
  for (const t of texts) {
    const p = t.parentNode?.nodeName;
    if (p === 'STYLE' || (p === 'SCRIPT' && t.parentNode.type !== 'application/ld+json')) continue;
    if (p === 'SCRIPT') {
      // JSON-LD: edit decoded strings, keep the JSON valid.
      const json = JSON.parse(t.data);
      const exact = v => { edits.forEach((e, i) => { if (e.jsonLd && inPage(e, file) && v === e.find) { counts[i]++; v = e.replace; } }); return v; };
      const deep = v => typeof v === 'string' ? swap(exact(v)) : Array.isArray(v) ? v.map(deep) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, deep(x)])) : v;
      const before = JSON.stringify(json), next = deep(json);
      if (JSON.stringify(next) !== before) t.data = JSON.stringify(next);
      continue;
    }
    const next = swap(t.data);
    if (next !== t.data) t.data = next;
  }
  for (const a of d.querySelectorAll('a[href]')) {
    edits.forEach((e, i) => {
      if (!inPage(e, file)) return;
      const h = a.getAttribute('href');
      if (e.href && h === e.find) { a.setAttribute('href', e.replace); counts[i]++; }
      // Plain edits of a URL string also change the prerendered link, as the client does.
      else if (!e.href && !e.code && !e.template && !e.jsonLd && /^https?:\/\//.test(e.find) && h === e.find) { a.setAttribute('href', e.replace); counts[i]++; }
    });
  }
  for (const el of d.querySelectorAll('meta[content],[alt],[title],[aria-label]')) {
    for (const a of ['content', 'alt', 'title', 'aria-label']) {
      const v = el.getAttribute(a); if (v == null) continue;
      const next = swap(v); if (next !== v) el.setAttribute(a, next);
    }
  }
  return {html: counts.some(Boolean) ? dom.serialize() : html, counts};
}

// Replaces the prerendered #root content of the given pages with what the browser
// renders from the built modules, so server HTML matches the changed components.
export async function rerender(output, pages, {serve, playwrightModule}, {head = false} = {}) {
  const {chromium} = await import(playwrightModule);
  const server = await serve(output);
  const browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? {channel: process.env.PLAYWRIGHT_CHANNEL} : {});
  const {readFile: rf, writeFile: wf} = await import('node:fs/promises');
  for (const f of pages) {
    const page = await browser.newPage({locale: 'en-US'});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(server.origin + '/' + f.replace(/index\.html$/, ''), {waitUntil: 'networkidle'});
    assert.equal(errors.length, 0, `render errors on ${f}: ${errors.join(' | ')}`);
    const inner = await page.evaluate(() => document.getElementById('root').innerHTML);
    const headTags = head ? await page.evaluate(() => ({title: document.title, tags: [...document.head.querySelectorAll('[data-rh]')].map(n => n.outerHTML)})) : null;
    await page.close();
    const file = path.join(output, f);
    const html = await rf(file, 'utf8');
    const dom = new JSDOM(html); const root = dom.window.document.getElementById('root');
    assert(root, `no #root in ${f}`);
    root.innerHTML = inner;
    if (headTags) {
      const h = dom.window.document.head;
      h.querySelectorAll('[data-rh]').forEach(n => n.remove());
      dom.window.document.title = headTags.title;
      const anchor = h.querySelector('link[rel="stylesheet"]');
      for (const t of headTags.tags) anchor ? anchor.insertAdjacentHTML('afterend', t) : h.insertAdjacentHTML('beforeend', t);
    }
    await wf(file, dom.serialize());
  }
  await browser.close(); server.close();
}

export async function loadInjects(dir = EDITS_DIR, only) {
  const names = (await readdir(dir)).filter(f => f.endsWith('.json') && (!only || only.includes(f))).sort();
  const out = [];
  for (const n of names) { const doc = JSON.parse(await readFile(path.join(dir, n), 'utf8')); if (doc.inject) out.push({...doc.inject, file: n}); }
  return out;
}

// Renders each page in the browser and copies the element matching `selector` into
// the prerendered HTML (as the first child of `parent`), so crawlers see it too.
export async function injectRendered(output, pages, inject, {serve, playwrightModule}) {
  const {chromium} = await import(playwrightModule);
  const server = await serve(output);
  const browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? {channel: process.env.PLAYWRIGHT_CHANNEL} : {});
  const {readFile: rf, writeFile: wf} = await import('node:fs/promises');
  const done = [];
  let next = 0;
  await Promise.all(Array.from({length: 4}, async () => {
    const ctx = await browser.newContext({locale: 'en-US'});
    while (next < pages.length) {
      const f = pages[next++];
      const page = await ctx.newPage();
      await page.goto(server.origin + '/' + f.replace(/index\.html$/, ''), {waitUntil: 'networkidle'});
      const html = await page.evaluate(sel => document.querySelector(sel)?.outerHTML ?? null, inject.selector);
      await page.close();
      if (!html) continue;
      const file = path.join(output, f);
      const dom = new JSDOM(await rf(file, 'utf8'));
      const parent = dom.window.document.querySelector(inject.parent);
      if (!parent || dom.window.document.querySelector(inject.selector)) continue;
      parent.insertAdjacentHTML(inject.position || 'afterbegin', html);
      await wf(file, dom.serialize());
      done.push(f);
    }
    await ctx.close();
  }));
  await browser.close(); server.close();
  return done.sort();
}

export async function loadDocs(dir = EDITS_DIR, only) {
  const names = (await readdir(dir)).filter(f => f.endsWith('.json') && (!only || only.includes(f))).sort();
  const out = {files: {}, newPages: [], fileEdits: []};
  for (const n of names) {
    const doc = JSON.parse(await readFile(path.join(dir, n), 'utf8'));
    Object.assign(out.files, doc.files ?? {});
    out.newPages.push(...(doc.newPages ?? []));
    out.fileEdits.push(...(doc.fileEdits ?? []).map(e => ({...e, from: n})));
  }
  return out;
}
export function applyFileEdit(text, e) {
  if (e.append) return text + e.append;
  assert(text.split(e.find).length === 2, `file edit must match once: ${e.file}`);
  return text.replace(e.find, e.replace);
}

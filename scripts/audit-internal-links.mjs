import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from './funnel-support.mjs';

export async function auditLinks(root) {
  const inventory = await files(root);
  const sitemap = [...(await readFile(path.join(root, 'sitemap.xml'), 'utf8')).matchAll(/<loc>(.*?)<\/loc>/g)].map(m => new URL(m[1]).pathname);
  const pages = new Map();
  for (const f of inventory.filter(f => f.endsWith('/index.html') || f === 'index.html')) {
    const route = '/' + f.replace(/index\.html$/, '');
    pages.set(route, new JSDOM(await readFile(path.join(root, f), 'utf8')).window.document);
  }
  const links = [], issues = [], inbound = new Map([...pages.keys()].map(k => [k, new Set()]));
  for (const [route, doc] of pages) for (const a of doc.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href');
    const label = (a.textContent || a.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    const zone = a.closest('footer') ? 'footer' : a.closest('main') ? 'main' : 'navigation';
    const item = {page:route, href, label, zone};
    if (!href || href === '#') { issues.push({...item, type:'placeholder'}); continue; }
    let url;
    try { url = new URL(href, 'https://spacemusic.io' + route); } catch { issues.push({...item, type:'invalid'}); continue; }
    if (!['spacemusic.io', 'www.spacemusic.io'].includes(url.hostname)) continue;
    const dest = url.pathname;
    const canonical = pages.has(dest) ? dest : pages.has(dest + '/') ? dest + '/' : inventory.includes(dest.slice(1)) ? dest : null;
    links.push({...item, path:canonical, hash:url.hash});
    if (!canonical) { issues.push({...item, type:'missing-page'}); continue; }
    if (canonical !== dest || url.protocol !== 'https:' || url.hostname !== 'spacemusic.io') issues.push({...item, type:'noncanonical', expected:canonical + url.search + url.hash});
    if (url.hash && pages.has(canonical)) {
      const target = decodeURIComponent(url.hash.slice(1));
      const targetDoc = pages.get(canonical);
      if (!targetDoc.getElementById(target) && ![...targetDoc.querySelectorAll('a[name]')].some(n => n.name === target)) issues.push({...item, type:'missing-fragment'});
    }
    if (canonical !== route) inbound.get(canonical)?.add(route);
  }
  const depth = {'/':0}, queue = ['/'];
  while (queue.length) {
    const from = queue.shift();
    for (const l of links.filter(l => l.page === from && l.path && pages.has(l.path))) if (depth[l.path] === undefined) { depth[l.path] = depth[from] + 1; queue.push(l.path); }
  }
  const graph = [...pages.keys()].map(route => ({route, title:pages.get(route).querySelector('h1')?.textContent || pages.get(route).title, inbound:inbound.get(route).size, depth:depth[route] ?? null, inSitemap:sitemap.includes(route)}));
  const summary = {pages:pages.size,sitemap:sitemap.length,internalLinks:links.length,issues:issues.reduce((a,x)=>(a[x.type]=(a[x.type]||0)+1,a),{}),orphans:graph.filter(x=>x.inSitemap&&x.route!=='/'&&!x.inbound).map(x=>x.route),unreachable:graph.filter(x=>x.inSitemap&&x.depth===null).map(x=>x.route),maxDepth:Math.max(...Object.values(depth))};
  return {root, summary, graph, issues, links};
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [root, output] = process.argv.slice(2);
  const report = await auditLinks(root);
  if (output) await writeFile(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({...report.summary, missing:[...new Set(report.issues.filter(x=>x.type==='missing-page').map(x=>x.href))], fragments:report.issues.filter(x=>x.type==='missing-fragment')},null,2));
}

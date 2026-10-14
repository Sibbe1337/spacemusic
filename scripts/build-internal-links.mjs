import assert from 'node:assert/strict';
import {cp, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';
import {primary, explore, learn, aliases, topics, resourceTitle, resourceDescription, resourceGroups, createLinkResolver} from '../marketing/internal-links-20260916/navigation.mjs';

const [source, output, manifestPath] = process.argv.slice(2);
assert(source && output && manifestPath, 'Usage: VERIFIED_SOURCE FRESH_OUTPUT MANIFEST');
assert(!path.resolve(output).startsWith(path.resolve(source)), 'Use a separate fresh output');
const hash = s => createHash('sha256').update(s).digest('hex');
const inventory = await files(source);
const read = f => readFile(path.join(source, f), 'utf8');
const home = await read('index.html');
const entry = home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry, 'index-article-360c41838159-quietseo-fd17485db4c3-intent-50f4feb4050e.js', 'Build from verified production, not a design or article preview');
const sitemap = await read('sitemap.xml');
const publicPaths = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map(m => new URL(m[1]).pathname);
assert.equal(publicPaths.length, 140);
assert(!publicPaths.includes('/blog/'));
publicPaths.push('/blog/');
const resolveLink = createLinkResolver(publicPaths);
const css = await readFile('marketing/internal-links-20260916/navigation.css', 'utf8');
const revision = hash(await readFile(import.meta.filename) + await readFile('marketing/internal-links-20260916/navigation.mjs', 'utf8') + css).slice(0,12);
const linkName = `InternalLinks-${revision}.js`, resourcesName = `Resources-${revision}.js`, cssName = `navigation-${revision}.css`;
const codes = new Map();
for (const f of inventory.filter(f => /^assets\/.*\.js$/.test(f))) codes.set(path.basename(f), await read(f));
const deps = name => literals(codes.get(name)).map(n => path.basename(n.value)).filter(n => codes.has(n));
const reachable = new Set();
function visit(name) { if (reachable.has(name)) return; reachable.add(name); deps(name).forEach(visit); }
visit(entry);
const moduleName = prefix => { const matches=[...reachable].filter(n=>n.startsWith(prefix)); assert.equal(matches.length,1,prefix); return matches[0]; };
const navbar = moduleName('Navbar-'), footer = moduleName('Footer-'), related = moduleName('RelatedContent-');
const changed = new Set();
function once(code, from, to) { assert.equal(code.split(from).length, 2, `Unique patch: ${from.slice(0,80)}`); return code.replace(from,to); }
function walk(node, fn) {
  if (!node || typeof node !== 'object') return;
  if (typeof node.type === 'string') fn(node);
  for (const [key,value] of Object.entries(node)) if (!['loc','start','end','extra'].includes(key)) {
    if (Array.isArray(value)) value.forEach(n=>walk(n,fn)); else if (value && typeof value==='object') walk(value,fn);
  }
}
function edit(code, edits) {
  edits.sort((a,b)=>b.start-a.start);
  let limit=code.length;
  for (const p of edits) { assert(p.end<=limit,'Overlapping patches'); code=code.slice(0,p.start)+p.value+code.slice(p.end); limit=p.start; }
  return code;
}
function setArray(code, name, value) {
  let match;
  walk(parse(code,{sourceType:'module'}), n=>{if(n.type==='VariableDeclarator'&&n.id.name===name&&n.init?.type==='ArrayExpression') {assert(!match,`Ambiguous ${name}`);match=n.init;}});
  assert(match,`Array ${name}`);
  return edit(code,[{...match,value:JSON.stringify(value)}]);
}
let code=codes.get(navbar);
code=setArray(code,'x',primary);
code=once(code,'const r=w[i];','i=i.replace(/[/]$/,"");const r=w[i];');
code=once(code,'const l=i.pathname;return l===t||l.startsWith(`${t}/`)','const l=i.pathname.replace(/[/]$/,"");t=t.replace(/[/]$/,"");return l===t||l.startsWith(`${t}/`)');
code=once(code,'e.jsxs("nav",{className:`fixed','e.jsxs("nav",{"aria-label":"Main navigation",className:`space-site-nav fixed');
// The legacy app replaces its static HTML while lazy routes load. Restore the
// requested anchor after the real page mounts, not against the loading screen.
code=once(code,'return d.useEffect(()=>{const t=()=>h(window.scrollY>20);','return d.useEffect(()=>{if(!i.hash)return;let id;try{id=decodeURIComponent(i.hash.slice(1))}catch{return}const frame=requestAnimationFrame(()=>document.getElementById(id)?.scrollIntoView({block:"start",behavior:"instant"}));return()=>cancelAnimationFrame(frame)},[i.pathname,i.hash]),d.useEffect(()=>{const t=()=>h(window.scrollY>20);');
code=once(code,'d.useEffect(()=>(document.body.style.overflow=r?', 'd.useEffect(()=>{if(!r)return;const close=t=>{if(t.key==="Escape"){s(!1);document.querySelector("[aria-controls=space-mobile-menu]")?.focus()}};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close)},[r]),d.useEffect(()=>(document.body.style.overflow=r?');
codes.set(navbar,code); changed.add(navbar);
code=setArray(setArray(codes.get(footer),'p',explore),'h',learn).replaceAll('s==="/apply"','s==="/apply/"');
code=once(code,'e.jsxs("nav",{className:"flex flex-col gap-4 md:col-span-3"','e.jsxs("nav",{"aria-label":"Explore",className:"flex flex-col gap-4 md:col-span-3"');
code=once(code,'e.jsxs("nav",{className:"flex flex-col gap-4 md:col-span-4"','e.jsxs("nav",{"aria-label":"Learn",className:"flex flex-col gap-4 md:col-span-4"');
// Do not present unconfigured social accounts as working links.
code=code.replaceAll('e.jsx("a",{href:"#","aria-label":','e.jsx("span",{"aria-hidden":"true","data-unconfigured-social":');
codes.set(footer,code); changed.add(footer);
code=codes.get(related);
code=once(code,'function R(e){const t=z(e);','function R(e){const t=z(__spaceResolve(e));');
codes.set(related,code); changed.add(related);

const legacyBlog=moduleName('BlogPost-G1IBKFnh-');
code=codes.get(legacyBlog);
const backMatch=code.match(/([A-Za-z_$][\w$]*)\.jsxs\(([A-Za-z_$][\w$]*),\{to:"\/",className:"inline-flex items-center",children:\[([^\]]+),"Back to all articles"\]\}\)/);
assert(backMatch,'Legacy back link');
code=code.replace(backMatch[0],backMatch[0].replace('to:"/"','to:"/blog/#articles"'));
codes.set(legacyBlog,code);changed.add(legacyBlog);

// Normalize actual anchors and React Router Links, never route definitions.
for (const name of reachable) {
  if (name.startsWith('vendor-') || name.startsWith('preload-helper-')) continue;
  let current=codes.get(name), patches=[], needsResolver=name===related;
  const ast=parse(current,{sourceType:'module'});
  for (const node of ast.program.body) if (node.type==='ImportDeclaration' && node.source.value.includes('vendor-router-')) {
    const link=node.specifiers.find(n=>n.imported?.name==='L');
    if (!link) continue;
    const others=node.specifiers.filter(n=>n!==link);
    const retained=others.length?`import{${others.map(n=>`${n.imported.name} as ${n.local.name}`).join(',')}}from${JSON.stringify(node.source.value)};`:'';
    patches.push({...node,value:retained+`import{Link as ${link.local.name}}from"./${linkName}";`});
  }
  walk(ast,n=>{
    if(n.type!=='CallExpression'||!['jsx','jsxs'].includes(n.callee.property?.name)||n.arguments[0]?.value!=='a'||n.arguments[1]?.type!=='ObjectExpression')return;
    const href=n.arguments[1].properties.find(p=>p.key?.name==='href');
    if(!href)return;
    if(href.value.type==='StringLiteral') {
      const next=resolveLink(href.value.value);
      if(next!==href.value.value)patches.push({...href.value,value:JSON.stringify(next)});
    } else {patches.push({...href.value,value:`__spaceResolve(${current.slice(href.value.start,href.value.end)})`});needsResolver=true;}
  });
  current=edit(current,patches);
  patches=[];
  for(const node of literals(current)) if(node.value.includes('<')&&/href=["']/.test(node.value)) {
    const next=node.value.replace(/href=(["'])(.*?)\1/g,(_,q,href)=>`href=${q}${resolveLink(href)}${q}`);
    if(next!==node.value)patches.push({...node,value:JSON.stringify(next)});
  }
  current=edit(current,patches);
  if(needsResolver)current=`import{resolveLink as __spaceResolve}from"./${linkName}";`+current;
  if(current!==codes.get(name)){codes.set(name,current);changed.add(name);}
}

const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const documents=new Map();
for(const f of inventory.filter(f=>f==='index.html'||f.endsWith('/index.html'))) documents.set('/'+f.replace(/index\.html$/,''),new JSDOM(await read(f)).window.document);
const headerTemplate=documents.get('/').getElementById('space-mobile-menu').closest('nav').cloneNode(true);
const headerExceptions=new Set(['/apply/','/data/conversion-intelligence/','/data/space-market-index/']);
function title(route){const d=documents.get(route);assert(d,route);return d.querySelector('h1').textContent.trim();}
const groups=resourceGroups.map(g=>({...g,items:g.items|| (g.paths||publicPaths.filter(p=>p.startsWith(g.prefix))).map(p=>[p,title(p)])}));
for(const g of groups)for(const [url] of g.items)assert(publicPaths.includes(new URL(url,'https://spacemusic.io').pathname),url);
const resourceBody=`<header class="space-library-intro"><p class="space-library-eyebrow">SPACE resources</p><h1>${escape(resourceTitle)}</h1><p>Find a clear next step for your catalog. Start with a guide, prepare for a review, or compare your options.</p><nav aria-label="On this page" class="space-library-jump">${groups.map(g=>`<a href="#${g.id}">${escape(g.title)}</a>`).join('')}</nav></header>`+groups.map(g=>`<section id="${g.id}" aria-labelledby="${g.id}-title" class="space-library-section"><h2 id="${g.id}-title">${escape(g.title)}</h2><p>${escape(g.intro)}</p><ul class="space-library-list">${g.items.map(([url,label])=>`<li><a href="${escape(url)}"><span>${escape(label)}</span><span aria-hidden="true">&#8599;</span></a></li>`).join('')}</ul></section>`).join('');
const schema={'@context':'https://schema.org','@type':'CollectionPage',name:resourceTitle,description:resourceDescription,url:'https://spacemusic.io/blog/'};
const breadcrumb={'@context':'https://schema.org','@type':'BreadcrumbList',itemListElement:[{'@type':'ListItem',position:1,name:'Home',item:'https://spacemusic.io/'},{'@type':'ListItem',position:2,name:'Resources',item:'https://spacemusic.io/blog/'}]};
const resourcesCode=`import{e}from"./vendor-DhPEFgb5.js";import{N}from"./${navbar}";import{F}from"./${footer}";import{S}from"./SEOHead-C4J8_WVH.js";export default function Resources(){return e.jsxs("div",{children:[e.jsx(S,{title:${JSON.stringify(resourceTitle+' | SPACE')},description:${JSON.stringify(resourceDescription)},canonical:"/blog/",type:"website",schema:${JSON.stringify([schema,breadcrumb])}}),e.jsx(N,{}),e.jsx("main",{id:"space-resource-library",className:"space-library",dangerouslySetInnerHTML:{__html:${JSON.stringify(resourceBody)}}}),e.jsx(F,{})]})}`;
codes.set(resourcesName,resourcesCode);
code=codes.get(entry);
code=once(code,'e.jsx(t,{path:"/blog/:slug",',`e.jsx(t,{path:"/blog",element:e.jsx(__spaceResources,{})}),e.jsx(t,{path:"/blog/:slug",`);
code=`const __spaceResources=s.lazy(()=>import("./${resourcesName}"));`+code;
codes.set(entry,code);changed.add(entry);

let growing=true;
while(growing){growing=false;for(const n of reachable)if(!changed.has(n)&&deps(n).some(d=>changed.has(d))){changed.add(n);growing=true;}}
const mapping=new Map([...changed].map(n=>[n,n.replace(/\.js$/,`-links-${revision}.js`)]));
const rewrite=s=>{for(const [from,to]of mapping)s=s.replaceAll(from,to);return s;};
await mkdir(output);await cp(source,output,{recursive:true});
for(const n of changed){const text=rewrite(codes.get(n));parse(text,{sourceType:'module'});await writeFile(path.join(output,'assets',mapping.get(n)),text);}
const linkCode=`import{r as React,e}from"./vendor-DhPEFgb5.js";import{L as RouterLink}from"./vendor-router-D1jo5eb_.js";
const aliases=${JSON.stringify(aliases)},topics=${JSON.stringify(topics)};
${createLinkResolver.toString()}
export const resolveLink=createLinkResolver(${JSON.stringify(publicPaths)});
export const Link=React.forwardRef(function InternalLink({to,reloadDocument,...props},ref){
 let next=to;
 if(typeof to==="string")next=resolveLink(to);
 else if(to?.pathname?.startsWith("/")){const resolved=new URL(resolveLink(to.pathname+(to.search||"")+(to.hash||"")),"https://spacemusic.io");next={...to,pathname:resolved.pathname,search:resolved.search,hash:resolved.hash};}
 const pathname=typeof next==="string"?next.split(/[?#]/)[0]:next?.pathname;
 const fragment=typeof next==="string"?next.includes("#"):!!next?.hash;
 return e.jsx(RouterLink,{...props,to:next,ref,reloadDocument:reloadDocument||fragment||pathname==="/apply/"||/\\.(md|txt)$/.test(pathname||"")});
});`;
parse(linkCode,{sourceType:'module'});
await writeFile(path.join(output,'assets',linkName),linkCode);
await writeFile(path.join(output,'assets',resourcesName),rewrite(resourcesCode));
await writeFile(path.join(output,'assets',cssName),css);

function replaceList(container,items,tag='a'){
  const template=container.querySelector(tag);assert(template);
  const className=template.className;
  container.innerHTML=items.map(({to,label})=>tag==='li'?`<li><a class="${escape(template.querySelector('a').className)}" href="${to}">${escape(label)}</a></li>`:`<a class="${escape(className)}" href="${to}">${escape(label)}</a>`).join('');
}
function updateChrome(d,route){
  const legacyHeader=d.querySelector('nav.fixed');
  if(legacyHeader&&!d.getElementById('space-mobile-menu'))legacyHeader.replaceWith(d.importNode(headerTemplate,true));
  const mobile=d.getElementById('space-mobile-menu');
  assert(mobile||headerExceptions.has(route),`Every public marketing page needs the shared header: ${route}`);
  if(mobile){
    const nav=mobile.closest('nav');nav.classList.add('space-site-nav');nav.setAttribute('aria-label','Main navigation');
    for(const container of [nav.querySelector('.hidden.md\\:flex'),mobile.querySelector('.flex.flex-col')]){
      const oldLinks=[...container.children].filter(n=>n.tagName==='A'&&n.getAttribute('href')!=='/apply/');
      assert.equal(oldLinks.length,3,`Primary navigation: ${route}`);
      const template=oldLinks[0];
      for(const item of primary){
        const a=template.cloneNode(false),active=route===item.to||route.startsWith(item.to);
        a.textContent=item.label;a.setAttribute('href',item.to);a.removeAttribute('aria-current');
        a.classList.remove('font-medium','font-normal','text-ink','text-ink-muted','hover:text-ink');
        a.classList.add(active?'font-medium':'font-normal',active?'text-ink':'text-ink-muted');
        if(active)a.setAttribute('aria-current','page');else a.classList.add('hover:text-ink');
        container.insertBefore(a,template);
      }
      oldLinks.forEach(a=>a.remove());
    }
  }
  const foot=d.querySelector('footer');
  if(foot)for(const [heading,items]of [['Explore',explore],['Learn',learn]]){
    const nav=[...foot.querySelectorAll('nav')].find(n=>n.querySelector('span')?.textContent===heading);assert(nav,`${route} ${heading}`);nav.setAttribute('aria-label',heading);replaceList(nav.querySelector('ul'),items,'li');
  }
  for(const a of d.querySelectorAll('a[href]')){
    const href=a.getAttribute('href');
    if(href==='#'&&a.closest('footer')){const span=d.createElement('span');span.innerHTML=a.innerHTML;span.className=a.className;span.setAttribute('aria-hidden','true');span.setAttribute('data-unconfigured-social',a.getAttribute('aria-label')||'');a.replaceWith(span);continue;}
    a.setAttribute('href',a.textContent.trim()==='Back to all articles'?'/blog/#articles':resolveLink(href));
  }
  if(route==='/guides/how-to-sell-music-rights/'){
    const h=[...d.querySelectorAll('h3')].find(n=>n.textContent==='Spoke pages');assert(h);
    const list=h.nextElementSibling, template=list.querySelector('a');
    const label=[...d.querySelectorAll('p')].find(n=>n.textContent==='Related guides');assert(label);
    for(const a of label.nextElementSibling.querySelectorAll('a')){
      const text=a.querySelector('h3')?.textContent||a.textContent.trim();
      if([...list.querySelectorAll('a')].some(n=>n.getAttribute('href')===a.getAttribute('href')))continue;
      const next=template.cloneNode(false);next.textContent=text;next.setAttribute('href',a.getAttribute('href'));list.append(next);
    }
  }
  const style=d.createElement('link');style.rel='stylesheet';style.href='/assets/'+cssName;d.head.append(style);
  const funnel=d.querySelector('script[data-space-funnel="v1"]');
  if(funnel){assert(funnel.textContent.includes('const f=new Set(['),'Funnel allowlist');funnel.textContent=funnel.textContent.replace('const f=new Set([','const f=new Set(["/blog/",');}
}
for(const [route,d]of documents){updateChrome(d,route);await writeFile(path.join(output,route.slice(1),'index.html'),rewrite(d.documentElement.outerHTML.replace(/^/,'<!DOCTYPE html>')));}
const resourceDom=new JSDOM(await read('about/index.html')),d=resourceDom.window.document;
const root=d.getElementById('root');assert(root);
const header=root.querySelector('nav'),foot=root.querySelector('footer');assert(header&&foot);
root.replaceChildren(header,foot);
const main=d.createElement('main');main.id='space-resource-library';main.className='space-library';main.innerHTML=resourceBody;root.insertBefore(main,foot);
d.title=resourceTitle+' | SPACE';
for(const sel of ['meta[name="description"]','meta[property="og:description"]','meta[name="twitter:description"]']){const n=d.querySelector(sel);if(n)n.content=resourceDescription;}
for(const sel of ['meta[property="og:title"]','meta[name="twitter:title"]']){const n=d.querySelector(sel);if(n)n.content=d.title;}
d.querySelector('link[rel="canonical"]').href='https://spacemusic.io/blog/';
for(const sel of ['meta[property="og:url"]','meta[name="twitter:url"]']){const n=d.querySelector(sel);if(n)n.content='https://spacemusic.io/blog/';}
d.querySelector('meta[property="og:type"]').content='website';
d.querySelectorAll('script[type="application/ld+json"]').forEach(n=>n.remove());
for(const [index,data] of [schema,breadcrumb].entries()){const script=d.createElement('script');script.type='application/ld+json';script.id=`seo-schema-${index}`;script.setAttribute('data-rh','true');script.textContent=JSON.stringify(data);d.head.append(script);}
updateChrome(d,'/blog/');
await mkdir(path.join(output,'blog'),{recursive:true});
await writeFile(path.join(output,'blog/index.html'),rewrite(resourceDom.serialize()));
await writeFile(path.join(output,'sitemap.xml'),sitemap.replace('</urlset>','  <url><loc>https://spacemusic.io/blog/</loc></url>\n</urlset>'));
const redirects=(await read('_redirects')).trimEnd()+'\n'+Object.entries(aliases).flatMap(([from,to])=>[`${from} ${to} 301`,`${from}/ ${to} 301`]).join('\n')+'\n';
await writeFile(path.join(output,'_redirects'),redirects);
const sourceHashes={};for(const f of inventory)sourceHashes[f]=hash(await readFile(path.join(source,f)));
const manifest={source,output,revision,entry:mapping.get(entry),modules:[...mapping],newModules:[linkName,resourcesName],cssName,publicPaths,groups,sourceHashes,status:'PREVIEW ONLY; production unchanged'};
await writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({output,revision,changedModules:changed.size,sitemap:publicPaths.length,status:manifest.status},null,2));

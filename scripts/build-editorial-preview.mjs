import assert from 'node:assert/strict';
import {cp,mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {parse} from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {files} from './funnel-support.mjs';
import {literals} from './journey-support.mjs';

const [output,manifestPath]=process.argv.slice(2);
assert(output&&manifestPath,'Usage: FRESH_OUTPUT MANIFEST');
const source='tmp/wordmark-preview-v1-20260916';
assert(!path.resolve(output).startsWith(path.resolve(source)),'Keep verified production immutable');
const hash=s=>createHash('sha256').update(s).digest('hex');
const css=await readFile('marketing/editorial-20260916/editorial.css','utf8');
const revision=hash(css+await readFile(import.meta.filename)).slice(0,12);
const cssName=`editorial-${revision}.css`;
const inventory=await files(source),read=f=>readFile(path.join(source,f),'utf8');
const home=await read('index.html');
const entry=home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert(entry.endsWith('-brand-ba3115eb02ed.js'),'Build on the approved logo/link release');
const codes=new Map();
for(const f of inventory.filter(f=>/^assets\/.*\.js$/.test(f)))codes.set(path.basename(f),await read(f));
const dependencies=n=>literals(codes.get(n)).map(x=>path.basename(x.value)).filter(n=>codes.has(n));
const active=new Set();
function visit(n){if(active.has(n))return;active.add(n);dependencies(n).forEach(visit);}
visit(entry);
function walk(n,fn,ancestors=[]){if(!n||typeof n!=='object')return;if(n.type)fn(n,ancestors);for(const[k,v]of Object.entries(n))if(!['loc','extra'].includes(k)){if(Array.isArray(v))v.forEach(c=>walk(c,fn,[...ancestors,n]));else if(v&&typeof v==='object')walk(v,fn,[...ancestors,n]);}}
const jsx=n=>n.type==='CallExpression'&&['jsx','jsxs'].includes(n.callee.property?.name)&&n.arguments[1]?.type==='ObjectExpression';
const prop=(n,key)=>n.arguments[1].properties.find(p=>p.key?.name===key||p.key?.value===key);
function edit(code,patches){let limit=code.length;for(const p of patches.sort((a,b)=>b.start-a.start)){assert(p.end<=limit,'Overlapping edits');code=code.slice(0,p.start)+p.value+code.slice(p.end);limit=p.start;}return code;}
function patch(code,fn){const changes=[];walk(parse(code,{sourceType:'module'}),(n,a)=>fn(n,a,changes));return edit(code,changes);}
const note='Legacy article. Original contributor details have not been verified.';
const authorLabel='Original contributor information (unverified)';
const newsletterNote='Newsletter sign-ups are currently unavailable here. No email address will be submitted.';
const classes={
  'flex-grow pt-24':'space-editorial space-editorial-legacy',
  'container mx-auto px-4 py-8':'editorial-shell',
  'flex flex-col lg:flex-row gap-8':'editorial-layout',
  'lg:w-2/3':'editorial-body',
  'prose prose-lg max-w-none mb-8':'editorial-prose',
  'flex items-center text-sm text-gray-500 mb-6':'editorial-meta',
  'flex flex-wrap gap-2 mb-4':'editorial-categories',
  'flex justify-between items-center my-8 py-4 border-t border-b':'editorial-share',
  'grid grid-cols-1 md:grid-cols-3 gap-6':'editorial-related-list',
  'mt-12':'editorial-related',
};
const changed=new Set();
const legacy=[...active].filter(n=>n.startsWith('BlogPost-G1IBKFnh-'));
assert.equal(legacy.length,1);
let code=codes.get(legacy[0]);
code=patch(code,(n,a,p)=>{
  if(n.type==='ObjectProperty'&&n.key.name==='className'&&classes[n.value.value])p.push({...n.value,value:JSON.stringify(classes[n.value.value])});
});
// Remove image-only wrappers, including their otherwise empty duplicate links.
let imageComponents=0;
code=patch(code,(n,anc,p)=>{
  if(!jsx(n)||n.arguments[0].value!=='img')return;
  const parents=anc.filter(jsx).reverse();
  let target=parents[0];assert.equal(target.arguments[0].value,'div');
  if(parents[1]?.arguments[0].name==='o'&&prop(parents[1],'children')?.value===target)target=parents[1];
  p.push({...target,value:'null'});imageComponents++;
});
assert.equal(imageComponents,4,'Hero, author, related and popular-post image templates');
code=patch(code,(n,a,p)=>{
  if(n.type==='VariableDeclarator'&&n.id.name==='L')p.push({...n.init,value:'({headings:a})=>a.length===0?null:e.jsxs("details",{className:"editorial-toc-panel",open:true,children:[e.jsx("summary",{children:"Table of Contents"}),e.jsx("nav",{"aria-label":"In this article",children:e.jsx("ul",{children:a.map((s,t)=>e.jsx("li",{children:e.jsx("a",{href:__spaceResolve(`#${s.id}`),className:s.level>2?"pl-4":"",children:s.text})},t))})})]})'});
  if(!jsx(n))return;
  const cl=prop(n,'className')?.value.value;
  if(cl==='editorial-layout'){
    const children=prop(n,'children').value;assert.equal(children.elements.length,2);
    p.push({...children,value:`[e.jsx("aside",{className:"editorial-toc",children:e.jsx(L,{headings:i.tableOfContents})}),${code.slice(children.elements[0].start,children.elements[0].end)},e.jsx("section",{className:"editorial-extras","aria-label":"More resources",children:e.jsx(B,{})})]`});
  }
  if(cl==='mb-8'&&n.arguments[0].value==='div'){
    const children=prop(n,'children')?.value;
    assert(children?.elements?.some(c=>jsx(c)&&c.arguments[0].value==='h1'));
    p.push({...prop(n,'className').value,value:'"editorial-header"'});
    p.push({start:children.end-1,end:children.end-1,value:`,e.jsx("p",{className:"editorial-note",children:${JSON.stringify(note)}})`});
  }
  if(cl==='bg-gray-50 border-none mt-8'){
    const child=prop(n,'children').value;
    p.push({...n,value:`e.jsxs("details",{className:"editorial-author",children:[e.jsx("summary",{children:${JSON.stringify(authorLabel)}}),${code.slice(child.start,child.end)}]})`});
  }
  if(n.arguments[0].value==='form'){
    assert(!prop(n,'action')&&!prop(n,'onSubmit'),'Do not disable a real form integration');
    p.push({...n,value:`e.jsxs("div",{children:[e.jsx("p",{className:"editorial-newsletter-note",children:${JSON.stringify(newsletterNote)}}),e.jsxs("fieldset",{disabled:true,"aria-label":"Newsletter unavailable",className:"space-y-3",children:${code.slice(prop(n,'children').value.start,prop(n,'children').value.end)}})]})`});
  }
});
assert(code.includes('localStorage.getItem("cookiesAccepted")||n(!0),window.scrollTo(0,0)'));
code=code.replace('localStorage.getItem("cookiesAccepted")||n(!0),window.scrollTo(0,0)','(()=>{try{localStorage.getItem("cookiesAccepted")||n(!0)}catch{n(!0)}if(!window.location.hash)window.scrollTo(0,0)})()');
code=code.replace('localStorage.setItem("cookiesAccepted","true"),n(!1)','(()=>{try{localStorage.setItem("cookiesAccepted","true")}catch{}n(!1)})()');
codes.set(legacy[0],code);changed.add(legacy[0]);

let authored=0;
for(const n of active)if(n.startsWith('BlogPost-')){
  let code=codes.get(n);if(!code.includes('className: "space-blog-article"'))continue;
  authored++;
  code=patch(code,(node,a,p)=>{
    if(!jsx(node))return;
    const cl=prop(node,'className')?.value.value;
    if(cl==='space-blog-article')p.push({...prop(node,'className').value,value:'"space-blog-article space-editorial"'});
    if(cl==='space-blog-toc'){
      p.push({...node.arguments[0],value:'"details"'});
      p.push({start:node.arguments[1].start+1,end:node.arguments[1].start+1,value:'open:true,'});
      const label=prop(node,'children').value.elements[0];assert.equal(label.arguments[0].value,'p');
      p.push({...label.arguments[0],value:'"summary"'});
    }
    if(cl==='space-blog-header'){
      const children=prop(node,'children').value;
      p.push({start:children.start+1,end:children.start+1,value:'jsx.jsx("a",{href:"/blog/#articles",className:"editorial-back",children:"Back to all articles"}),'});
    }
  });
  codes.set(n,code);changed.add(n);
}
assert.equal(authored,8,'All authored article wrappers');

function libraryBody(main){
  for(const [i,section] of [...main.querySelectorAll('.space-library-section')].entries()){
    const d=main.ownerDocument,heading=d.createElement('header');heading.className='editorial-section-heading';
    const num=d.createElement('span');num.className='editorial-section-number';num.setAttribute('aria-hidden','true');num.textContent=String(i+1).padStart(2,'0');
    heading.append(num,section.querySelector('h2'),section.querySelector('p'));section.prepend(heading);
  }
}
const resources=[...active].find(n=>n.startsWith('Resources-'));assert(resources);
code=codes.get(resources);
const body=literals(code).find(n=>n.value.startsWith('<header class="space-library-intro"'));assert(body);
const frag=new JSDOM(body.value);libraryBody(frag.window.document.body);
code=edit(code,[{...body,value:JSON.stringify(frag.window.document.body.innerHTML)}]);
code=code.replace('className:"space-library"','className:"space-library space-editorial"');
codes.set(resources,code);changed.add(resources);

let grow=true;while(grow){grow=false;for(const n of active)if(!changed.has(n)&&dependencies(n).some(d=>changed.has(d))){changed.add(n);grow=true;}}
const mapping=new Map([...changed].map(n=>[n,n.replace(/\.js$/,`-editorial-${revision}.js`)]));
const rewrite=s=>{for(const[a,b]of mapping)s=s.replaceAll(a,b);return s;};
await mkdir(output);await cp(source,output,{recursive:true});
for(const n of changed){const code=rewrite(codes.get(n));parse(code,{sourceType:'module'});await writeFile(path.join(output,'assets',mapping.get(n)),code);}
await writeFile(path.join(output,'assets',cssName),css);
let articles=0,removedImages=0;
for(const f of inventory.filter(f=>f.endsWith('.html'))){
  const original=await read(f),dom=new JSDOM(original),d=dom.window.document,main=d.querySelector('main');
  if(f==='blog/index.html'){main.classList.add('space-editorial');libraryBody(main);}
  else if(f.startsWith('blog/')){
    articles++;
    if(main.classList.contains('space-blog-article')){
      main.classList.add('space-editorial');
      const old=main.querySelector('.space-blog-toc'),details=d.createElement('details');
      for(const a of old.attributes)details.setAttribute(a.name,a.value);details.open=true;
      details.innerHTML=old.innerHTML;const label=details.querySelector('p'),summary=d.createElement('summary');summary.textContent=label.textContent;label.replaceWith(summary);old.replaceWith(details);
      const a=d.createElement('a');a.href='/blog/#articles';a.className='editorial-back';a.textContent='Back to all articles';main.querySelector('header').prepend(a);
    }else{
      main.className='space-editorial space-editorial-legacy';
      for(const img of [...main.querySelectorAll('img')]){
        removedImages++;let target=img.parentElement;
        assert.equal(target.children.length,1);if(target.parentElement.tagName==='A'&&target.parentElement.children.length===1)target=target.parentElement;target.remove();
      }
      for(const n of main.querySelectorAll('[class]'))if(classes[n.className])n.className=classes[n.className];
      const shell=main.firstElementChild,header=shell.firstElementChild;header.className='editorial-header';
      const warning=d.createElement('p');warning.className='editorial-note';warning.textContent=note;header.append(warning);
      const layout=shell.lastElementChild,body=layout.firstElementChild,sidebar=layout.lastElementChild;
      const panel=sidebar.firstElementChild.firstElementChild,widgets=sidebar.firstElementChild.lastElementChild;
      const aside=d.createElement('aside');aside.className='editorial-toc';const details=d.createElement('details');details.className='editorial-toc-panel';details.open=true;
      const summary=d.createElement('summary');summary.textContent=panel.querySelector('h3').textContent;const nav=panel.querySelector('nav');nav.setAttribute('aria-label','In this article');
      nav.querySelector('ul').removeAttribute('class');
      for(const a of nav.querySelectorAll('a'))a.className=a.classList.contains('pl-4')?'pl-4':'';
      details.append(summary,nav);aside.append(details);
      const extras=d.createElement('section');extras.className='editorial-extras';extras.setAttribute('aria-label','More resources');extras.append(widgets);
      layout.replaceChildren(aside,body,extras);
      const author=body.querySelector('.bg-gray-50'),authorDetails=d.createElement('details');assert(author);
      authorDetails.className='editorial-author';const label=d.createElement('summary');label.textContent=authorLabel;authorDetails.append(label,...author.childNodes);author.replaceWith(authorDetails);
      const form=extras.querySelector('form');assert(form&&!form.hasAttribute('action'));
      const group=d.createElement('div'),message=d.createElement('p'),fieldset=d.createElement('fieldset');message.className='editorial-newsletter-note';message.textContent=newsletterNote;
      fieldset.disabled=true;fieldset.setAttribute('aria-label','Newsletter unavailable');fieldset.className=form.className;fieldset.append(...form.childNodes);group.append(message,fieldset);form.replaceWith(group);
    }
  }
  // Global stylesheet is scoped; it also supports client navigation from non-blog routes.
  const link=d.createElement('link');link.rel='stylesheet';link.href='/assets/'+cssName;d.head.append(link);
  await writeFile(path.join(output,f),rewrite(dom.serialize()));dom.window.close();
}
assert.equal(articles,14);assert.equal(removedImages,57);
const sourceHashes={};for(const f of inventory)sourceHashes[f]=hash(await readFile(path.join(source,f)));
await writeFile(manifestPath,JSON.stringify({source,output,revision,cssName,entry:mapping.get(entry),modules:[...mapping],articles,removedImages,sourceHashes,status:'PREVIEW ONLY; production unchanged',notes:{note,authorLabel,newsletterNote}},null,2)+'\n');
console.log(JSON.stringify({output,articles,removedImages,modules:changed.size,revision},null,2));

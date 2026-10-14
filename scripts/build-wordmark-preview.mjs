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
const linkManifest=JSON.parse(await readFile('marketing/internal-links-20260916/manifest.json','utf8'));
const source=linkManifest.output;
assert(!path.resolve(output).startsWith(path.resolve(source)),'Separate fresh preview required');
const hash=s=>createHash('sha256').update(s).digest('hex');
const svg=await readFile('marketing/identity-20260916/space-wordmark.svg','utf8');
const css=await readFile('marketing/identity-20260916/wordmark.css','utf8');
const revision=hash(svg+css+await readFile(import.meta.filename)).slice(0,12);
const component=`SpaceWordmark-${revision}.js`,cssName=`space-wordmark-${revision}.css`,svgName=`space-wordmark-${revision}.svg`;
const doc=new JSDOM(svg,{contentType:'image/svg+xml'}).window.document;
const mark=doc.documentElement;
assert.equal(mark.getAttribute('viewBox'),'0 0 218 44');
assert.equal(mark.querySelectorAll('path').length,5);
mark.removeAttribute('role');mark.removeAttribute('aria-label');
mark.setAttribute('aria-hidden','true');mark.setAttribute('focusable','false');mark.setAttribute('class','space-wordmark');
mark.setAttribute('width','218');mark.setAttribute('height','44');mark.setAttribute('data-space-wordmark','cut-a-v1');
const brandHtml=mark.outerHTML+'<span class="space-wordmark-text">SPACE</span>';
const props={xmlns:'http://www.w3.org/2000/svg',viewBox:'0 0 218 44',width:218,height:44,fill:'currentColor',className:'space-wordmark','aria-hidden':'true',focusable:'false','data-space-wordmark':'cut-a-v1'};
const paths=[...mark.querySelectorAll('path')].map(p=>Object.fromEntries([...p.attributes].map(a=>[a.name==='fill-rule'?'fillRule':a.name,a.value])));
const componentCode=`import{e}from"./vendor-DhPEFgb5.js";function W(){return e.jsxs("svg",{...${JSON.stringify(props)},children:[${paths.map(p=>`e.jsx("path",${JSON.stringify(p)})`).join(',')}]})}export{W};`;
const inventory=await files(source),codes=new Map();
for(const f of inventory.filter(f=>/^assets\/.*\.js$/.test(f)))codes.set(path.basename(f),await readFile(path.join(source,f),'utf8'));
const entry=linkManifest.entry;
const dependencies=n=>literals(codes.get(n)).map(n=>path.basename(n.value)).filter(n=>codes.has(n));
const reachable=new Set();
function visit(n){if(reachable.has(n))return;reachable.add(n);dependencies(n).forEach(visit);}
visit(entry);
const changed=new Set();
function walk(n,fn){if(!n||typeof n!=='object')return;if(n.type)fn(n);for(const[k,v]of Object.entries(n))if(!['loc','extra'].includes(k)){if(Array.isArray(v))v.forEach(c=>walk(c,fn));else if(v&&typeof v==='object')walk(v,fn);}}
for(const prefix of ['Navbar-','Footer-']){
  const found=[...reachable].filter(n=>n.startsWith(prefix));assert.equal(found.length,1);
  const name=found[0];let code=codes.get(name),target;
  walk(parse(code,{sourceType:'module'}),n=>{
    if(n.type!=='CallExpression'||!['jsx','jsxs'].includes(n.callee.property?.name)||n.arguments[1]?.type!=='ObjectExpression')return;
    const p=n.arguments[1].properties;
    if(p.some(p=>p.key?.name==='to'&&p.value.value==='/')&&p.some(p=>p.key?.name==='className'&&p.value.value?.includes(prefix==='Navbar-'?'gap-2.5 group':'font-display'))){assert(!target);target=n.arguments[1];}
  });
  assert(target,`${prefix} home brand link`);
  const replacements=target.properties.filter(p=>['className','children'].includes(p.key?.name)).map(p=>({...p.value,value:p.key.name==='className'?JSON.stringify('space-wordmark-link'):'[e.jsx(__SpaceWordmark,{}),e.jsx("span",{className:"space-wordmark-text",children:"SPACE"})]'}));
  assert.equal(replacements.length,2);
  for(const p of replacements.sort((a,b)=>b.start-a.start))code=code.slice(0,p.start)+p.value+code.slice(p.end);
  // jsxs is the correct JSX-runtime entry when the brand now has two children.
  if(prefix==='Footer-')code=code.replace('e.jsx(i,{to:"/",className:"space-wordmark-link"','e.jsxs(i,{to:"/",className:"space-wordmark-link"');
  code=`import{W as __SpaceWordmark}from"./${component}";`+code;
  codes.set(name,code);changed.add(name);
}
let grow=true;
while(grow){grow=false;for(const n of reachable)if(!changed.has(n)&&dependencies(n).some(d=>changed.has(d))){changed.add(n);grow=true;}}
const mapping=new Map([...changed].map(n=>[n,n.replace(/\.js$/,`-brand-${revision}.js`)]));
const rewrite=s=>{for(const [from,to]of mapping)s=s.replaceAll(from,to);return s;};
await mkdir(output);await cp(source,output,{recursive:true});
for(const n of changed){const text=rewrite(codes.get(n));parse(text,{sourceType:'module'});await writeFile(path.join(output,'assets',mapping.get(n)),text);}
await writeFile(path.join(output,'assets',component),componentCode);
await writeFile(path.join(output,'assets',cssName),css);
await writeFile(path.join(output,'assets',svgName),svg);
let headers=0,footers=0,applications=0;
for(const f of inventory.filter(f=>f.endsWith('.html'))){
  const dom=new JSDOM(await readFile(path.join(source,f),'utf8')),d=dom.window.document;
  const header=d.querySelector('.space-site-nav a[aria-label][href="/"]');
  const footer=[...d.querySelectorAll('footer a[href="/"]')].find(a=>a.textContent==='SPACE');
  const apply=d.querySelector('.masthead a.wordmark[href="/"]');
  if(header)headers++;if(footer)footers++;if(apply)applications++;
  for(const anchor of [header,footer,apply].filter(Boolean)){
    anchor.className=anchor===apply?'wordmark space-wordmark-link':'space-wordmark-link';
    anchor.innerHTML=brandHtml;
  }
  const style=d.createElement('link');style.rel='stylesheet';style.href='/assets/'+cssName;d.head.append(style);
  await writeFile(path.join(output,f),rewrite(dom.serialize()));
  dom.window.close();
}
assert.equal(headers,136);assert.equal(footers,138);assert.equal(applications,1);
const sourceHashes={};for(const f of inventory)sourceHashes[f]=hash(await readFile(path.join(source,f)));
const manifest={source,output,revision,entry:mapping.get(entry),modules:[...mapping],component,cssName,svgName,brandHtml,paths,headers,footers,applications,sourceHashes,status:'PREVIEW ONLY; includes the pending internal-link fixes; production unchanged'};
await writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({output,revision,headers,footers,applications,modules:changed.size},null,2));

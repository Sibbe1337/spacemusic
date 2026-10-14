import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parse } from '../services/seller_ui/node_modules/@babel/parser/lib/index.js';

export const copy = JSON.parse(await readFile(new URL('../marketing/journey/copy.json', import.meta.url), 'utf8'));
export const sourceModules = {
  'Index-og-type-32d4337373ff.js': copy.home,
  'HowItWorksPage-Br1vbw7A.js': copy.process,
  'GenreIndex-nzzjt_go.js': copy.genres,
};
export function literals(code) {
  const result = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'StringLiteral') result.push(node);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === 'object') visit(value);
    }
  }
  visit(parse(code, { sourceType: 'module' }));
  return result;
}
export function replaceLiterals(code, replacements, required = false) {
  const map = new Map(replacements), seen = new Set();
  const edits = literals(code).filter(node => map.has(node.value)).map(node => {
    seen.add(node.value);
    return { start: node.start, end: node.end, text: JSON.stringify(map.get(node.value)) };
  });
  if (required) for (const key of map.keys()) assert(seen.has(key), `Missing reviewed source text: ${key}`);
  for (const edit of edits.sort((a,b) => b.start-a.start)) code = code.slice(0,edit.start)+edit.text+code.slice(edit.end);
  return code;
}
export function directApplicationLinks(code) {
  const edits=[];
  const tree=parse(code,{sourceType:'module'});
  const links=new Set(tree.program.body.filter(node=>node.type==='ImportDeclaration' && node.source.value.startsWith('./vendor-router-')).flatMap(node=>node.specifiers.filter(s=>s.type==='ImportSpecifier' && s.imported.name==='L').map(s=>s.local.name)));
  function visit(node) {
    if(!node || typeof node!=='object')return;
    if(node.type==='CallExpression' && node.callee?.type==='MemberExpression' && ['jsx','jsxs'].includes(node.callee.property?.name) && node.arguments[0]?.type==='Identifier' && links.has(node.arguments[0].name) && node.arguments[1]?.type==='ObjectExpression') {
      const to=node.arguments[1].properties.find(p=>p.type==='ObjectProperty' && (p.key.name||p.key.value)==='to' && p.value.type==='StringLiteral' && ['/apply','/apply/'].includes(p.value.value));
      if(to) edits.push({start:node.arguments[0].start,end:node.arguments[0].end,text:'"a"'},{start:to.key.start,end:to.key.end,text:'href'},{start:to.value.start,end:to.value.end,text:'"/apply/"'});
    }
    for(const value of Object.values(node)) {
      if(Array.isArray(value))value.forEach(visit);
      else if(value && typeof value==='object')visit(value);
    }
  }
  visit(tree);
  for(const edit of edits.sort((a,b)=>b.start-a.start))code=code.slice(0,edit.start)+edit.text+code.slice(edit.end);
  return code;
}
export function updateSharedDocument(document) {
  let count = 0;
  for (const anchor of document.querySelectorAll('a[href="/apply/"],a[href="/apply"]')) {
    const walker = document.createTreeWalker(anchor, 4);
    while (walker.nextNode()) {
      const node = walker.currentNode, text = node.nodeValue.trim();
      if (copy.ctaAliases.includes(text)) {
        node.nodeValue = node.nodeValue.replace(text, copy.cta);
        count++;
      }
    }
  }
  for (const node of document.querySelectorAll('footer p')) {
    if (node.textContent === copy.footer[0]) node.textContent = copy.footer[1];
  }
  return count;
}

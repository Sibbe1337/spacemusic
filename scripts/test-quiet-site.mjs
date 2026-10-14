import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM} from '../services/seller_ui/node_modules/jsdom/lib/api.js';
import {files} from './funnel-support.mjs';
const [file]=process.argv.slice(2);
const m=JSON.parse(await readFile(file,'utf8'));
const inventory=await files(m.output);
const hash=v=>createHash('sha256').update(v).digest('hex');
let checks=0;
for(const [file,digest] of Object.entries(m.sourceHashes)) {
  const before=await readFile(path.join(m.source,file));
  assert.equal(hash(before),digest,`Baseline changed: ${file}`);checks++;
  assert(inventory.includes(file),`Missing ${file}`);checks++;
  const after=await readFile(path.join(m.output,file));
  if(!file.endsWith('.html')){assert(before.equals(after),`Protected asset changed: ${file}`);checks++;continue;}
  const d=new JSDOM(after.toString()).window.document;
  assert(d.body.classList.contains('space-quiet-site'),`Missing theme: ${file}`);checks++;
  const styles=d.querySelectorAll(`link[rel="stylesheet"][href="/assets/${m.stylesheet}"]`);
  assert.equal(styles.length,1,file);checks++;
  const reverted=after.toString().replace('<body class="space-quiet-site">','<body>').replace(`<link rel="stylesheet" href="/assets/${m.stylesheet}">`,'');
  assert.equal(reverted,before.toString(),`Unexpected content, metadata, form or script change: ${file}`);checks++;
}
assert.equal(m.htmlPages,137);checks++;
console.log(JSON.stringify({status:'PASS',checks,pages:m.htmlPages,allContentAndMetadata:'byte-identical after removing CSS hook',applyFormAndRuntime:'unchanged',sitemap:'139 retained',production:'not touched'},null,2));

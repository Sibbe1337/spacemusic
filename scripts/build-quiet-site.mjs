import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,cp} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {files} from './funnel-support.mjs';

const [source,output,manifestPath] = process.argv.slice(2);
assert(source && output && manifestPath,'Usage: VERIFIED_SOURCE FRESH_OUTPUT MANIFEST');
assert(path.resolve(source)!==path.resolve(output) && !path.resolve(output).startsWith(path.resolve(source)+path.sep),'Preserve source snapshot');
const digest=v=>createHash('sha256').update(v).digest('hex');
const inventory=await files(source);
const stylesheet=await readFile('marketing/quiet-site-20260916/site.css','utf8');
const fontCSS=await readFile('marketing/design/fonts/fonts.css','utf8');
const css=fontCSS+'\n'+stylesheet;
const styleName=`quiet-site-${digest(css).slice(0,12)}.css`;
const sourceHashes={};
for(const file of inventory) sourceHashes[file]=digest(await readFile(path.join(source,file)));
await mkdir(output);
await cp(source,output,{recursive:true});
await writeFile(path.join(output,'assets',styleName),css);
for(const file of inventory.filter(f=>f.endsWith('.html'))) {
  let html=await readFile(path.join(source,file),'utf8');
  assert(!html.includes('space-quiet-site'),'Do not stack duplicate site layers');
  assert(html.includes('<body>'),'Unexpected body attributes: '+file);
  html=html.replace('<body>','<body class="space-quiet-site">').replace('</head>',`<link rel="stylesheet" href="/assets/${styleName}"></head>`);
  await writeFile(path.join(output,file),html);
}
await mkdir(path.dirname(manifestPath),{recursive:true});
await writeFile(manifestPath,JSON.stringify({source,output,stylesheet:styleName,sourceHashes,htmlPages:inventory.filter(f=>f.endsWith('.html')).length,scope:'Presentation only on all marketing HTML, including Apply shell. No content or behavior changes.',production:'unchanged'},null,2)+'\n');
console.log(JSON.stringify({output,styleName,htmlPages:inventory.filter(f=>f.endsWith('.html')).length,status:'preview only'}));

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { files } from './funnel-support.mjs';
const [sourceArg, outputArg] = process.argv.slice(2);
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep));
const inventory = await files(source);
const home = await readFile(path.join(source,'index.html'),'utf8');
assert(home.includes('data-space-funnel="v1"') && !home.includes('data-space-design'));
const entryPath = home.match(/<script type="module" crossorigin(?:="")? src="\/([^"]+)"/)[1];
const entry = await readFile(path.join(source,entryPath),'utf8');
const guideName = entry.match(/assets\/(ValuationGuidePage-[\w-]+\.js)/)[1];
const oldGuide = await readFile(path.join(source,'assets',guideName),'utf8');
const data = JSON.parse(await readFile('marketing/funnel/valuation-guide.json','utf8'));
const supplements = [
  ['music-catalog-sale-documents-checklist','Music Catalog Sale Documents: A Seller\'s Checklist'],
  ['music-catalog-offer-checklist','Music Catalog Offer Checklist: Questions Before You Sign']
].filter(([slug]) => inventory.includes(`blog/${slug}/index.html`));
if (supplements.length) data.sections.push({heading:'Practical Seller Checklists', content:supplements.map(([slug,label])=>`<a href="/blog/${slug}/">${label}</a>`).join('<br/><br/>')});
const serialized = JSON.stringify(data);
assert(!/<script|\bon\w+=|javascript:/i.test(serialized));
let next = oldGuide.replace(/const p=\{[\s\S]*?\},P=\(\)=>/, `const p=${serialized},P=()=>`);
assert.notEqual(next,oldGuide);
next = next.replace(/title:"(?:Music Catalog Valuation \(2026\) — Multiples, Factors, Offer Range|Music Catalog Valuation: Method, Example & Review)"/, 'title:"Music Catalog Valuation: Method, Example & Review"');
next = next.replace(/description:"(?:Learn how catalog valuation works, what multiples mean, and estimate a realistic offer range\. Free calculator\.|Understand music catalog valuation, calculate a hypothetical sale from net income, and prepare the documents for an individual catalog review\.)"/, `description:${JSON.stringify(data.metaDescription)}`);
next = next.replace('children:a.content','dangerouslySetInnerHTML:{__html:a.content}');
next = next.replace('url:`https://spacemusic.io/guides/${t.slug}`','url:`https://spacemusic.io/guides/${t.slug}/`').replace('canonical:`/guides/${t.slug}`','canonical:`/guides/${t.slug}/`');
next = next.replace('children:"Revenue Multiples by Genre"','children:"Genre Evidence to Review"').replace('children:"Multiple Range"','children:"Pricing basis"');
next = next.replace('children:"Find out what your catalog is worth"','children:"Explore a scenario or request an individual review"').replace('children:"Free instant estimate. No obligation."','children:"The calculator is hypothetical. A catalog review is free and carries no obligation."').replace('children:"Try the Calculator"','children:"Build a Sale Scenario"').replace('children:"Apply for a Full Valuation"','children:"Request a Free Catalog Review"');
const schemaAddition = 'dateModified:"2026-09-07",author:{"@type":"Organization",name:"SPACE",url:"https://spacemusic.io/about/"},citation:t.citations.map(a=>a.url),';
if (!next.includes(schemaAddition)) next = next.replace('publisher:{"@type":"Organization"',schemaAddition+'publisher:{"@type":"Organization"');
if (!next.includes('Reviewed September 7, 2026')) next = next.replace('e.jsx("h1",{', 'e.jsx("p",{className:"text-sm text-muted-foreground mb-4",children:"By SPACE. Reviewed September 7, 2026. Educational guide; not an independent appraisal."}),e.jsx("h1",{');
const hash = value => createHash('sha256').update(value).digest('hex').slice(0,12);
const nextGuideName = `ValuationGuidePage-reviewed-${hash(next)}.js`;
const nextEntry = entry.replaceAll(guideName,nextGuideName);
const nextEntryPath = `assets/index-guide-${hash(nextEntry)}.js`;
assert(nextEntry.includes('CanonicalApplication-3b3108140369.js'));
await mkdir(output); await cp(source,output,{recursive:true});
await writeFile(path.join(output,'assets',nextGuideName),next);
await writeFile(path.join(output,nextEntryPath),nextEntry);
for (const file of inventory.filter(file=>file.endsWith('.html'))) {
  const before = await readFile(path.join(source,file),'utf8');
  const after = before.replaceAll('/'+entryPath,'/'+nextEntryPath);
  if (before !== after) await writeFile(path.join(output,file),after);
}
const sitemap = await readFile(path.join(source,'sitemap.xml'),'utf8');
const record = [...sitemap.matchAll(/<url>[\s\S]*?<\/url>/g)].find(([record])=>record.includes('<loc>https://spacemusic.io/guides/music-catalog-valuation-2026/</loc>'))[0];
const updatedRecord = record.replace(/<lastmod>[^<]+<\/lastmod>/,'<lastmod>2026-09-07</lastmod>');
await writeFile(path.join(output,'sitemap.xml'),sitemap.replace(record,updatedRecord));
console.log(JSON.stringify({output,nextGuideName,nextEntryPath,supplements:supplements.map(([slug])=>slug),requiresPrerender:true}));

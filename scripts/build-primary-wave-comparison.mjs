import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const [sourceArg, outputArg] = process.argv.slice(2);
assert(sourceArg && outputArg, "Usage: node scripts/build-primary-wave-comparison.mjs SOURCE OUTPUT");
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep), "Use a separate output directory");
const data = JSON.parse(await readFile(path.join(projectRoot, "marketing/comparisons/space-vs-primary-wave.json"), "utf8"));
assert.equal(data.slug, "space-vs-primary-wave");
const targetRelative = `compare/${data.slug}/index.html`;
const oldHtml = await readFile(path.join(source, targetRelative), "utf8");
assert(oldHtml.includes(`<title>${data.title}</title>`), "Do not change the existing title");
assert(oldHtml.includes(`content="${data.metaDescription}"`), "Do not change the existing description");
assert(oldHtml.includes(`href="https://spacemusic.io/compare/${data.slug}/"`));
const oldEntryName = oldHtml.match(/<script type="module" crossorigin src="\/assets\/([^\"]+)"/)[1];
const oldEntry = await readFile(path.join(source, "assets", oldEntryName), "utf8");
const oldPageName = "CompetitorComparisonPage-nqD8Tapv.js";
const oldDataName = "competitorComparisonsExpanded-D0DJzCdV.js";
assert(oldEntry.includes(oldPageName), "Unsupported baseline: review the current comparison entry");
const oldPage = await readFile(path.join(source, "assets", oldPageName), "utf8");
const oldData = await readFile(path.join(source, "assets", oldDataName), "utf8");

// The legacy module contains literal data only. Parse it as JSON, never execute it.
const arrays = oldData.match(/^const e=(\[.*\]),i=(\[.*\]);export\{e as c,i as e\};\s*$/s);
assert(arrays, "Unexpected comparison data format");
const parseLiteral = (text) => JSON.parse(text.replace(/"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`|([a-zA-Z_$][\w$]*)(?=\s*:)/g, (match, key) => {
  if (key) return JSON.stringify(key);
  if (!match.startsWith("`")) return match;
  assert(!match.includes("${") && !match.includes("\\"), "Only literal, unescaped template strings are supported");
  return JSON.stringify(match.slice(1, -1));
}));
const records = [...parseLiteral(arrays[1]), ...parseLiteral(arrays[2])];
assert.equal(records.filter((record) => record.slug === data.slug).length, 1);
const previous = records.find((record) => record.slug === data.slug);
for (const key of ["slug", "title", "metaDescription", "primaryKeyword"]) assert.equal(data[key], previous[key]);
assert.equal(data.competitorProfile.name, previous.competitorProfile.name);
assert(data.faq.length >= previous.faq.length);
assert.equal(new Set(data.faq.map((faq) => faq.question)).size, data.faq.length);

const digest = (content) => createHash("sha256").update(content).digest("hex").slice(0, 12);
// Only the renderer reads descriptions; the unchanged RelatedContent module reads slugs.
// Retain the original module for cached clients and add a small, explicit data overlay.
const nextData = `import{c as original,e as expanded}from"./${oldDataName}";\nconst updated=${JSON.stringify(data)};\nconst replace=row=>row.slug===updated.slug?updated:row;\nconst c=original.map(replace),e=expanded.map(replace);\nexport{c,e};\n`;
const dataName = `competitorComparisons-primary-wave-${digest(nextData)}.js`;
const extraSections = `s.sections?.map(section=>e.jsx("section",{className:"bg-white py-12 border-t border-black/10",children:e.jsxs("div",{className:"max-w-5xl mx-auto px-4",children:[e.jsx("h2",{className:"text-2xl md:text-3xl font-semibold tracking-tight mb-6",children:section.title}),section.paragraphs.map(text=>e.jsx("p",{className:"text-muted-foreground leading-relaxed max-w-3xl mb-6",children:text},text)),section.blocks?.map(block=>e.jsxs("div",{className:"mb-8 max-w-3xl",children:[e.jsx("h3",{className:"text-lg font-semibold mb-3",children:block.title}),e.jsx("p",{className:"text-muted-foreground leading-relaxed mb-3",children:block.text}),block.link&&comparisonLink(block.link)]},block.title)),section.items&&e.jsx("ul",{className:"list-disc pl-6 space-y-3 max-w-3xl text-muted-foreground leading-relaxed mb-6",children:section.items.map(text=>e.jsx("li",{children:text},text))}),section.links&&e.jsx("div",{className:"flex flex-col gap-3",children:section.links.map(comparisonLink)})]})},section.title)),`;
const linkHelper = `function comparisonLink(link){const props={className:"text-brand underline underline-offset-2",children:link.label};return link.url.startsWith("/")?e.jsx(i,{...props,to:link.url},link.url):e.jsx("a",{...props,href:link.url,target:"_blank",rel:"noopener noreferrer"},link.url)}\n`;
const faqAnchor = 'e.jsx(b,{type:"single",collapsible:!0,className:"w-full",children:s.faq.map((t,a)=>e.jsxs(w,{value:`faq-${a}`,className:"border-b border-black/10",children:[e.jsx(k,{className:"text-base font-medium py-5 hover:no-underline text-left",children:t.question}),e.jsx(y,{className:"text-muted-foreground pb-5 leading-relaxed",children:t.answer})]},a))})';
const nativeFaq = `s.sections?e.jsx("div",{className:"w-full",children:s.faq.map(t=>e.jsxs("details",{className:"border-b border-black/10",children:[e.jsx("summary",{className:"text-base font-medium py-5 text-left cursor-pointer",children:t.question}),e.jsx("p",{className:"text-muted-foreground pb-5 leading-relaxed",children:t.answer})]},t.question))}):${faqAnchor}`;
const sectionAnchor = 'e.jsx("section",{className:"bg-cream py-16",children:e.jsxs("div",{className:"max-w-3xl mx-auto px-4",children:[e.jsx("p",{className:"text-xs font-medium text-ink-muted uppercase tracking-widest mb-6",children:"Common questions"})';
const tableAnchor = 'e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-sm",children:[';
const nextTable = 'e.jsx("div",{className:"overflow-x-auto",tabIndex:s.sections?0:void 0,role:s.sections?"region":void 0,"aria-label":s.sections?"Scrollable buyer comparison":void 0,children:e.jsxs("table",{className:"w-full text-sm",style:s.sections?{minWidth:"640px"}:void 0,children:[s.sections&&e.jsx("caption",{className:"text-left text-sm text-ink-muted pb-4",children:"Compare the same rights and term. On small screens, scroll across to see both buyers."}),';
for (const anchor of [faqAnchor, sectionAnchor, tableAnchor, "const l=[...f,...N]"]) assert.equal(oldPage.split(anchor).length, 2, "Comparison template changed; review before patching");
const nextPage = oldPage.replaceAll(oldDataName, dataName)
  .replace("const l=[...f,...N]", linkHelper + "const l=[...f,...N]")
  .replace(faqAnchor, nativeFaq).replace(sectionAnchor, extraSections + sectionAnchor).replace(tableAnchor, nextTable);
const pageName = `CompetitorComparisonPage-primary-wave-${digest(nextPage)}.js`;
const nextEntry = oldEntry.replaceAll(oldPageName, pageName).replaceAll(oldDataName, dataName);
const entryName = `index-primary-wave-${digest(nextEntry)}.js`;
await mkdir(output);
await cp(source, output, { recursive: true });
for (const [name, content] of [[dataName, nextData], [pageName, nextPage], [entryName, nextEntry]]) {
  await writeFile(path.join(output, "assets", name), content);
}

let htmlCount = 0;
for (const relative of await readdir(source, { recursive: true })) {
  if (!relative.endsWith(".html")) continue;
  const original = await readFile(path.join(source, relative), "utf8");
  const next = original.replaceAll(`/assets/${oldEntryName}`, `/assets/${entryName}`);
  assert.equal(next.replaceAll(`/assets/${entryName}`, `/assets/${oldEntryName}`), original);
  assert.equal(next.split(/<body[^>]*>/i)[1], original.split(/<body[^>]*>/i)[1]);
  if (next !== original) await writeFile(path.join(output, relative), next);
  htmlCount++;
}
console.log(JSON.stringify({ output, targetRelative, htmlCount, originalRecords: records.length, newAssets: [dataName, pageName, entryName], nextStep: "Prerender and test the target. Sitemap, robots, GEO files and all old assets are unchanged." }, null, 2));

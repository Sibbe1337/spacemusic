import assert from "node:assert/strict";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";

const [sourceArg, outputArg, slug] = process.argv.slice(2);
assert(sourceArg && outputArg && /^[a-z0-9-]+$/.test(slug), "Usage: node scripts/check-blog-update.mjs SOURCE OUTPUT SLUG");
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
const target = `blog/${slug}/index.html`;
const entryPath = (html) => html.match(/<script type="module" crossorigin src="\/([^\"]+)"/)[1];
const beforeEntry = entryPath(await readFile(path.join(source, "index.html"), "utf8"));
const afterEntry = entryPath(await readFile(path.join(output, "index.html"), "utf8"));

async function articleChain(root, entry) {
  const text = await readFile(path.join(root, entry), "utf8");
  let file = text.match(/assets\/BlogPost-[\w-]+\.js/)[0];
  const records = [], visited = new Set();
  while (true) {
    assert(!visited.has(file), "Cycle in article chain"); visited.add(file);
    const module = await readFile(path.join(root, file), "utf8");
    const match = module.match(/^const article = (.+);$/m);
    if (!match) return { records, legacy: file };
    records.push(JSON.parse(match[1]));
    const fallback = module.match(/const LegacyBlogPost = React.lazy\(\(\) => import\("\.\/([^\"]+)"\)\);/)?.[1];
    assert(fallback && /^BlogPost-[\w-]+\.js$/.test(fallback));
    file = "assets/" + fallback;
  }
}

const beforeChain = await articleChain(source, beforeEntry);
const afterChain = await articleChain(output, afterEntry);
assert.deepEqual(afterChain.records.map((article) => article.slug), beforeChain.records.map((article) => article.slug));
assert.equal(afterChain.legacy, beforeChain.legacy);
assert.equal(new Set(afterChain.records.map((article) => article.slug)).size, afterChain.records.length);
const beforeArticle = beforeChain.records.find((article) => article.slug === slug);
const afterArticle = afterChain.records.find((article) => article.slug === slug);
assert(beforeArticle && afterArticle);
assert.deepEqual(afterChain.records.filter((article) => article.slug !== slug), beforeChain.records.filter((article) => article.slug !== slug));
for (const key of ["title", "seoTitle", "description", "url", "datePublished", "dateModified", "author", "category", "image", "imageAlt", "introduction"]) {
  assert.equal(afterArticle[key], beforeArticle[key], `Changed article identity or introduction: ${key}`);
}
for (const heading of beforeArticle.headings) assert(afterArticle.headings.some((item) => item.id === heading.id && item.text === heading.text), `Existing anchor lost: ${heading.id}`);

let preservedHtml = 0, preservedOther = 0;
for (const file of await readdir(source, { recursive: true })) {
  if (!(await stat(path.join(source, file))).isFile() || file === target) continue;
  const before = await readFile(path.join(source, file));
  const after = await readFile(path.join(output, file));
  if (file.endsWith(".html")) {
    assert.equal(after.toString().replaceAll(`/${afterEntry}`, `/${beforeEntry}`), before.toString(), `Unrelated page changed: ${file}`);
    preservedHtml++;
  } else {
    assert(before.equals(after), `Unrelated file changed: ${file}`);
    preservedOther++;
  }
}

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ channel: "chrome", headless: true });
let result;
try {
  const page = await browser.newPage();
  result = await page.evaluate(({ beforeArticle, afterArticle, beforeHtml, afterHtml }) => {
    const parse = (html) => new DOMParser().parseFromString(html, "text/html");
    const oldBody = parse(beforeArticle.body), nextBody = parse(afterArticle.body);
    const previousBlocks = [...oldBody.body.children].map((node) => node.outerHTML);
    const nextBlocks = [...nextBody.body.children].map((node) => node.outerHTML);
    let cursor = 0;
    const missingBlocks = [];
    for (const block of previousBlocks) {
      const next = nextBlocks.indexOf(block, cursor);
      if (next === -1) missingBlocks.push(block);
      else cursor = next + 1;
    }
    const metadata = (html) => {
      const doc = parse(html);
      return {
        title: doc.title,
        h1: [...doc.querySelectorAll("h1")].map((node) => node.textContent),
        canonical: [...doc.querySelectorAll('link[rel="canonical"]')].map((node) => node.getAttribute("href")),
        tags: [...doc.querySelectorAll("meta[name],meta[property]")].map((node) => ({ name: node.name || node.getAttribute("property"), content: node.content })).sort((a, b) => a.name.localeCompare(b.name)),
      };
    };
    const doc = parse(afterHtml);
    const moneyTable = [...doc.querySelectorAll("table")].find((table) => table.textContent.includes("Months covered"));
    return {
      missingBlocks, preservedContentBlocks: previousBlocks.length,
      beforeMetadata: metadata(beforeHtml), afterMetadata: metadata(afterHtml),
      links: [...new Set([...doc.querySelectorAll("a[href],script[src],link[href]")].map((node) => node.getAttribute("href") || node.getAttribute("src")))],
      budgetRows: moneyTable ? [...moneyTable.querySelectorAll("tbody tr")].map((row) => [...row.querySelectorAll("td")].map((cell) => cell.textContent)) : [],
      schema: [...doc.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent)).find((schema) => schema["@type"] === "BlogPosting"),
    };
  }, { beforeArticle, afterArticle, beforeHtml: await readFile(path.join(source, target), "utf8"), afterHtml: await readFile(path.join(output, target), "utf8") });
} finally { await browser.close(); }
assert.deepEqual(result.missingBlocks, [], "Existing article content was removed or changed");
assert.deepEqual(result.afterMetadata, result.beforeMetadata, "Existing article SEO or sharing metadata changed");
assert.equal(result.schema.wordCount, afterArticle.wordCount);
assert.equal(afterArticle.readingTime, Math.ceil(afterArticle.wordCount / 220));
assert.deepEqual(result.schema, afterArticle.schema.find((schema) => schema["@type"] === "BlogPosting"));
assert.deepEqual(result.budgetRows, [
  ["$750", "$24,000 / $750", "32 months"],
  ["$1,000", "$24,000 / $1,000", "24 months"],
  ["$1,500", "$24,000 / $1,500", "16 months"],
]);
for (const row of result.budgetRows) assert.equal(24000 / Number(row[0].replace(/[$,]/g, "")), Number(row[2].split(" ")[0]));
let checkedLinks = 0;
for (const href of result.links) {
  const url = new URL(href, beforeArticle.url);
  if (url.origin !== "https://spacemusic.io") continue;
  let file = path.join(output, decodeURIComponent(url.pathname));
  const info = await stat(file);
  if (info.isDirectory()) file = path.join(file, "index.html");
  await readFile(file);
  checkedLinks++;
}
const summary = {
  url: afterArticle.url, articleMetadata: "identical", preservedOtherHtml: preservedHtml,
  preservedOtherFiles: preservedOther, preservedContentBlocks: result.preservedContentBlocks,
  articleWords: afterArticle.wordCount, previousWords: beforeArticle.wordCount,
  authoredArticles: afterChain.records.length, unchangedOtherArticles: afterChain.records.length - 1,
  duplicateWrappers: false, checkedInternalDestinations: checkedLinks, budgetArithmetic: "passed",
  sitemapUrls: (await readFile(path.join(output, "sitemap.xml"), "utf8")).match(/<loc>/g).length,
};
console.log(JSON.stringify(summary, null, 2));

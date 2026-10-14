import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "../services/seller_ui/node_modules/jsdom/lib/api.js";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const [sourceArg, outputArg, slug = "what-is-a-blanket-license", mode] = process.argv.slice(2);
assert(sourceArg && outputArg, "Usage: node scripts/build-blog-post.mjs SOURCE OUTPUT [SLUG] [--update]");
assert(mode === undefined || mode === "--update", "Unknown build mode");
const updating = mode === "--update";
assert(/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug), "Invalid article slug");
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep), "Use a separate output directory");
const { marked } = await import(process.env.MARKED_MODULE || "marked");
const contentRoot = path.join(projectRoot, "marketing/blog");
const article = JSON.parse(await readFile(path.join(contentRoot, `${slug}.json`), "utf8"));
assert.equal(article.slug, slug);
assert(/^\/glossary\/[a-z0-9-]+\/$/.test(article.relatedGlossary), "A canonical glossary route is required");
const glossarySlug = article.relatedGlossary.split("/")[2];
const markdown = await readFile(path.join(contentRoot, `${article.slug}.md`), "utf8");
assert(markdown.startsWith(`# ${article.title}\n`), "Article title and metadata differ");
const plain = (text) => JSDOM.fragment(text).textContent;
const headings = [];
const ids = new Set();
let html = marked.parse(markdown).replace(/^<h1>[\s\S]*?<\/h1>\s*/, "");
html = html.replace(/<h([23])>(.*?)<\/h\1>/g, (_, level, text) => {
  const label = plain(text);
  const id = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  assert(!ids.has(id), `Duplicate heading: ${id}`); ids.add(id);
  if (level === "2") headings.push({ id, text: label });
  return `<h${level} id="${id}">${text}</h${level}>`;
});
html = html.replace(/<table>([\s\S]*?)<\/table>/g, '<div class="space-blog-table" role="region" aria-label="Article comparison table" tabindex="0"><table>$1</table></div>');
assert(!/<script\b|\bon\w+=|javascript:/i.test(html), "Unexpected active content in article");
const firstSection = html.indexOf("<h2 ");
assert(firstSection >= 0, "Article needs at least one section heading");
article.introduction = html.slice(0, firstSection);
article.body = html.slice(firstSection);
article.headings = headings;
article.url = `https://spacemusic.io/blog/${article.slug}/`;
article.wordCount = plain(html).split(/\s+/).filter(Boolean).length;
article.readingTime = Math.ceil(article.wordCount / 220);
article.displayDate = new Date(`${article.datePublished}T00:00:00Z`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
article.schema = [{
  "@context": "https://schema.org", "@type": "BlogPosting",
  "@id": `${article.url}#article`, headline: article.title,
  description: article.description, url: article.url,
  mainEntityOfPage: { "@type": "WebPage", "@id": article.url },
  author: { "@type": "Organization", name: article.author, url: "https://spacemusic.io/about/" },
  publisher: { "@type": "Organization", name: "SPACE", url: "https://spacemusic.io/" },
  datePublished: article.datePublished, dateModified: article.dateModified,
  inLanguage: "en-US", articleSection: article.category, wordCount: article.wordCount,
  image: { "@type": "ImageObject", url: article.image, width: 1730, height: 909 },
  citation: [...new Set([...html.matchAll(/href="(https:\/\/[^\"]+)"/g)].map((match) => match[1]))],
}, {
  "@context": "https://schema.org", "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://spacemusic.io/" },
    { "@type": "ListItem", position: 2, name: article.title, item: article.url },
  ],
}];

const homepage = await readFile(path.join(source, "index.html"), "utf8");
const oldEntryPath = homepage.match(/<script type="module" crossorigin(?:="")? src="\/([^\"]+)"/)?.[1];
assert(oldEntryPath, "Expected the current versioned module entry");
const entry = await readFile(path.join(source, oldEntryPath), "utf8");
const oldBlogPath = entry.match(/assets\/BlogPost-[\w-]+\.js/)[0];
const oldGlossaryPath = entry.match(/assets\/GlossaryTerm-[\w-]+\.js/)[0];
let legacyBlogModule = path.basename(oldBlogPath);
const parentBlogModules = [];
if (updating) {
  const visited = new Set();
  let currentName = legacyBlogModule;
  while (true) {
    assert(!visited.has(currentName), "Cycle in the existing blog route chain");
    visited.add(currentName);
    const currentModule = await readFile(path.join(source, "assets", currentName), "utf8");
    const previousArticleMatch = currentModule.match(/^const article = (.+);$/m);
    assert(previousArticleMatch, `Authored article ${slug} was not found; do not shadow a legacy route`);
    const previousArticle = JSON.parse(previousArticleMatch[1]);
    const fallbackName = currentModule.match(/const LegacyBlogPost = React.lazy\(\(\) => import\("\.\/([^\"]+)"\)\);/)?.[1];
    assert(fallbackName && /^BlogPost-[\w-]+\.js$/.test(fallbackName), "Unexpected legacy blog import");
    if (previousArticle.slug === slug) {
      for (const key of ["url", "title", "seoTitle", "description", "datePublished", "author", "category", "image", "imageAlt"]) {
        assert.equal(article[key], previousArticle[key], `Preserve existing ${key} during a content-only update`);
      }
      assert(article.dateModified >= previousArticle.dateModified, "Modification date must not move backwards");
      legacyBlogModule = fallbackName;
      await readFile(path.join(source, "assets", fallbackName));
      break;
    }
    parentBlogModules.push({ name: currentName, text: currentModule, fallbackName });
    currentName = fallbackName;
  }
}
const digest = (text) => createHash("sha256").update(text).digest("hex").slice(0, 12);
let pageTemplate = await readFile(path.join(contentRoot, "blanket-license-page.mjs"), "utf8");
// Keep the current navigation/form-link fixes when extending a versioned release.
const activeBlogSource = await readFile(path.join(source, oldBlogPath), "utf8");
for (const component of ["Navbar", "Footer", "SEOHead"]) {
  const pattern = new RegExp(`\\./${component}-[\\w-]+\\.js`);
  const currentImport = activeBlogSource.match(pattern)?.[0];
  assert(currentImport, `Current article must expose its ${component} import`);
  pageTemplate = pageTemplate.replace(pattern, currentImport);
}
const styles = await readFile(path.join(contentRoot, "article.css"), "utf8");
const pageModule = pageTemplate.replace("__ARTICLE__", JSON.stringify(article))
  .replace("__ARTICLE_STYLES__", JSON.stringify(styles))
  .replace("__LEGACY_BLOG_MODULE__", legacyBlogModule);
const blogPath = `assets/BlogPost-article-${digest(pageModule)}.js`;
const blogAssets = [[blogPath, pageModule]];
let activeBlogPath = blogPath;
// Re-version the existing parents without adding duplicate route wrappers.
for (const parent of parentBlogModules.toReversed()) {
  const oldImport = `const LegacyBlogPost = React.lazy(() => import("./${parent.fallbackName}"));`;
  const nextImport = `const LegacyBlogPost = React.lazy(() => import("./${path.basename(activeBlogPath)}"));`;
  assert.equal(parent.text.split(oldImport).length, 2, "Expected a single fallback import");
  const nextParent = parent.text.replace(oldImport, nextImport);
  activeBlogPath = `assets/BlogPost-article-${digest(nextParent)}.js`;
  blogAssets.push([activeBlogPath, nextParent]);
}

const oldGlossary = await readFile(path.join(source, oldGlossaryPath), "utf8");
const glossaryAnchor = 'e.jsx(j,{title:"Related content"';
assert.equal(oldGlossary.split(glossaryAnchor).length, 2, "Unexpected glossary component; review current build");
const guideLabel = article.relatedLinkLabel || "Blanket licenses: ASCAP, BMI and SESAC for musicians";
assert(!/[<>&"]/.test(guideLabel), "Use a plain-text glossary label");
assert.equal(oldGlossary.includes(`/blog/${article.slug}/`), updating, "Unexpected existing glossary link for build mode");
const relatedAside = `s.slug===${JSON.stringify(glossarySlug)}?e.jsxs("aside",{className:"mb-8 border-t border-black/10 pt-8",children:[e.jsx("p",{className:"text-sm font-medium mb-3",children:"Full guide"}),e.jsx(o,{to:"/blog/${article.slug}/",className:"text-brand underline underline-offset-4",children:${JSON.stringify(guideLabel)}})]}):null,`;
const nextGlossary = updating ? oldGlossary : oldGlossary.replace(glossaryAnchor, relatedAside + glossaryAnchor);
const glossaryPath = updating ? oldGlossaryPath : `assets/GlossaryTerm-article-${digest(nextGlossary)}.js`;
const nextEntry = entry.replaceAll(path.basename(oldBlogPath), path.basename(activeBlogPath))
  .replaceAll(path.basename(oldGlossaryPath), path.basename(glossaryPath));
const entryPath = `assets/index-article-${digest(nextEntry)}.js`;

const sitemap = await readFile(path.join(source, "sitemap.xml"), "utf8");
const articleLoc = `<loc>${article.url}</loc>`;
assert.equal(sitemap.split(articleLoc).length - 1, updating ? 1 : 0, "Unexpected sitemap entry for build mode");
let nextSitemap;
if (updating) {
  const record = [...sitemap.matchAll(/<url>[\s\S]*?<\/url>/g)].find(([text]) => text.includes(articleLoc))?.[0];
  assert(record && /<lastmod>[^<]+<\/lastmod>/.test(record), "Article sitemap record needs a modification date");
  nextSitemap = sitemap.replace(record, record.replace(/<lastmod>[^<]+<\/lastmod>/, `<lastmod>${article.dateModified}</lastmod>`));
} else {
  nextSitemap = sitemap.replace("</urlset>", `  <url><loc>${article.url}</loc><lastmod>${article.dateModified}</lastmod></url>\n</urlset>`);
}
const outputAssets = [...blogAssets, [entryPath, nextEntry]];
if (!updating) outputAssets.push([glossaryPath, nextGlossary]);
await mkdir(output);
await cp(source, output, { recursive: true });
for (const [relative, text] of outputAssets) {
  await writeFile(path.join(output, relative), text);
}
async function htmlFiles(dir) {
  const files = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await htmlFiles(file));
    else if (entry.name.endsWith(".html")) files.push(file);
  }
  return files;
}
for (const file of await htmlFiles(output)) {
  const before = await readFile(file, "utf8");
  const after = before.replaceAll(`/${oldEntryPath}`, `/${entryPath}`);
  if (before !== after) await writeFile(file, after);
}

const glossaryFile = path.join(output, "glossary", glossarySlug, "index.html");
const glossaryHTML = await readFile(glossaryFile, "utf8");
const relatedAnchor = '<section class="bg-white py-12 border-t border-black/10">';
assert.equal(glossaryHTML.split(relatedAnchor).length, 2, "Unexpected glossary HTML");
const staticAside = `<aside class="mb-8 border-t border-black/10 pt-8"><p class="text-sm font-medium mb-3">Full guide</p><a class="text-brand underline underline-offset-4" href="/blog/${article.slug}/">${guideLabel}</a></aside>`;
if (updating) assert.equal(glossaryHTML.split(staticAside).length, 2, "Existing glossary link must remain unique");
else await writeFile(glossaryFile, glossaryHTML.replace(relatedAnchor, staticAside + relatedAnchor));
await writeFile(path.join(output, "sitemap.xml"), nextSitemap);

// This shell must be prerendered before deployment so crawlers receive the full article.
const baseHead = homepage.slice(0, homepage.indexOf('<meta data-rh="true" name="description"'));
const normalizer = homepage.match(/<script data-space-seo-links="true">[\s\S]*?<\/script>/)?.[0] || "";
const shell = baseHead.replaceAll(`/${oldEntryPath}`, `/${entryPath}`) + `</head><body><div id="root"></div>${normalizer}</body></html>`;
const routeFile = path.join(output, "blog", article.slug, "index.html");
await mkdir(path.dirname(routeFile), { recursive: true });
await writeFile(routeFile, shell);
console.log(JSON.stringify({ output, mode: updating ? "update" : "create", routeFile, url: article.url, wordCount: article.wordCount, readingTime: article.readingTime, assets: outputAssets.map(([file]) => file), sitemapUrls: [...nextSitemap.matchAll(/<loc>/g)].length, requiresPrerender: true }, null, 2));

import assert from "node:assert/strict";
import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const [sourceArg, outputArg, extra] = process.argv.slice(2);
assert(sourceArg && outputArg && !extra, "Usage: node scripts/build-llms-release.mjs SOURCE OUTPUT");
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep) && !source.startsWith(output + path.sep), "Use a separate output directory");
const next = await readFile(path.join(projectRoot, "marketing/ai/llms.txt"), "utf8");
const previous = await readFile(path.join(source, "llms.txt"), "utf8");
assert.notEqual(next, previous, "The source already contains this llms.txt revision");
assert(next.startsWith("# SPACE\n\n> "), "Expected a site title followed by a summary");
assert.equal((next.match(/^# /gm) || []).length, 1, "Use one Markdown H1");
assert(!/<\/?[a-z][^>]*>|^```/im.test(next), "Keep llms.txt as plain Markdown, not an HTML page");
assert(/^Last updated: \d{4}-\d{2}-\d{2}$/m.test(next), "Include a revision date");
const sections = next.split(/^## /m).slice(1);
assert(sections.length > 0 && sections.at(-1).startsWith("Optional\n"), "Keep secondary links in the final Optional section");
const links = [];
for (const section of sections) {
  const [, ...lines] = section.trim().split("\n");
  for (const line of lines.filter((line) => line.trim())) {
    const match = line.match(/^- \[([^\]]+)\]\((https:\/\/[^)]+)\): (.+)$/);
    assert(match, `Expected a described link: ${line}`);
    links.push(match[2]);
  }
}
assert.equal(new Set(links).size, links.length, "Avoid duplicate URLs");
const oldLinks = [...previous.matchAll(/\]\((https:\/\/[^)]+)\)/g)].map((match) => match[1]);
for (const url of oldLinks) assert(links.includes(url), `Retain the existing key resource: ${url}`);
const sitemap = await readFile(path.join(source, "sitemap.xml"), "utf8");
assert(sitemap.includes("<loc>https://spacemusic.io/llms.txt</loc>"), "Use the existing sitemap record");
for (const href of links) {
  const url = new URL(href);
  assert.equal(url.origin, "https://spacemusic.io", "Use the production origin");
  assert(!url.search && !url.hash && !url.username && !url.password, "Use clean resource URLs");
  assert(url.pathname.endsWith("/") || url.pathname === "/pricing.md", "Use canonical page paths");
  const file = path.join(source, url.pathname.endsWith("/") ? url.pathname + "index.html" : url.pathname);
  const content = await readFile(file, "utf8");
  if (file.endsWith(".html")) {
    const tags = content.match(/<link\b[^>]*rel="canonical"[^>]*>/g) || [];
    assert.equal(tags.length, 1, `Expected one canonical: ${href}`);
    assert.equal(tags[0].match(/href="([^"]+)"/)?.[1], href, "Reject fallback pages and noncanonical destinations");
    assert(/<h1\b/i.test(content), `Expected page content: ${href}`);
    assert(!/<meta\b[^>]*name="robots"[^>]*content="[^"]*noindex/i.test(content), `Do not promote noindex pages: ${href}`);
  }
}

await mkdir(output);
await cp(source, output, { recursive: true });
await writeFile(path.join(output, "llms.txt"), next);

async function files(root, relative = "") {
  const result = [];
  for (const entry of await readdir(path.join(root, relative), { withFileTypes: true })) {
    const name = path.join(relative, entry.name);
    result.push(...(entry.isDirectory() ? await files(root, name) : [name]));
  }
  return result.sort();
}
const originalFiles = await files(source), releaseFiles = await files(output);
assert.deepEqual(releaseFiles, originalFiles, "Do not add or remove any public file");
for (const file of originalFiles) {
  if (file === "llms.txt") continue;
  assert((await readFile(path.join(source, file))).equals(await readFile(path.join(output, file))), `Unexpected change: ${file}`);
}
console.log(JSON.stringify({ output, changedFiles: ["llms.txt"], preservedFiles: originalFiles.length - 1, totalFiles: releaseFiles.length, validatedLinks: links.length, sitemap: "byte-identical", markup: "plain Markdown" }, null, 2));

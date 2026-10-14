import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { build, transform } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { files } from './funnel-support.mjs';
const [sourceArg, outputArg, applyBuildArg] = process.argv.slice(2);
assert(sourceArg && outputArg && applyBuildArg, 'Usage: SOURCE FRESH_OUTPUT APPLY_BUILD');
const source = path.resolve(sourceArg), output = path.resolve(outputArg), applyBuild = path.resolve(applyBuildArg);
assert(source !== output && !output.startsWith(source + path.sep));
const inventory = await files(source);
const home = await readFile(path.join(source, 'index.html'), 'utf8');
assert(!home.includes('data-space-design') && !home.includes('data-space-funnel'));
const oldEntryPath = home.match(/<script type="module" crossorigin src="\/([^"]+)"/)[1];
const entry = await readFile(path.join(source, oldEntryPath), 'utf8');
assert(entry.includes('CanonicalApplication-3b3108140369.js'), 'Preserve the latest Apply navigation fix');
const oldCalculator = 'Calculator-LQUD5H9x.js';
assert.equal(entry.split(oldCalculator).length, 3);
const compiled = await build({ entryPoints: ['marketing/funnel/Calculator.jsx'], bundle: true, format: 'esm', write: false, minify: true, jsxFactory: 'React.createElement', jsxFragment: 'React.Fragment', external: ['./vendor-*.js', './Navbar-*.js', './Footer-*.js', './SEOHead-*.js'] });
const calculator = compiled.outputFiles[0].text;
const hash = data => createHash('sha256').update(data).digest('hex').slice(0,12);
const calculatorPath = `assets/Calculator-scenario-${hash(calculator)}.js`;
const nextEntry = entry.replaceAll(oldCalculator, path.basename(calculatorPath));
const nextEntryPath = `assets/index-funnel-${hash(nextEntry)}.js`;
assert.equal(nextEntry.replaceAll(path.basename(calculatorPath), oldCalculator), entry);
const sitemap = await readFile(path.join(source, 'sitemap.xml'), 'utf8');
const paths = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => new URL(match[1]).pathname);
assert.equal(paths.length, 137);
// Future article paths are explicitly known, not wildcard matches or user input.
paths.push('/blog/music-catalog-sale-documents-checklist/', '/blog/music-catalog-offer-checklist/');
const tracking = (await transform((await readFile('marketing/funnel/tracking.js','utf8')).replace('__PUBLIC_PATHS__', JSON.stringify(paths)), { minify: true })).code;
assert(!tracking.includes('</script'));
const snippet = `<script data-space-funnel="v1">${tracking}</script>\n<script async src="https://plausible.io/js/pa-SkcIQImRmi7Ocm0b--b1D.js"></script>`;
const analyticsPattern = /<script async(?:="")? src="https:\/\/plausible\.io\/js\/pa-SkcIQImRmi7Ocm0b--b1D\.js"><\/script>\s*<script>\s*window\.plausible=[\s\S]*?plausible\.init\(\)\s*<\/script>/;
const applyHtml = await readFile(path.join(applyBuild, 'index.html'), 'utf8');
const applyEntry = applyHtml.match(/src="\/apply\/([^" ]+\.js)"/)[1];
const applyJs = await readFile(path.join(applyBuild, applyEntry), 'utf8');
assert(applyJs.includes('https://formspree.io/f/mpwdnokz'));
assert(applyJs.includes('application_submitted'));
const applyCss = applyHtml.match(/href="\/apply\/([^" ]+\.css)"/)[1];
assert((await readFile(path.join(applyBuild, applyCss))).equals(await readFile(path.join(source, 'apply/assets/index-B__1VwK8.css'))), 'Application CSS changed; design must remain paused');
await mkdir(output);
await cp(source, output, { recursive: true });
await writeFile(path.join(output, calculatorPath), calculator);
await writeFile(path.join(output, nextEntryPath), nextEntry);
await cp(path.join(applyBuild, applyEntry), path.join(output, 'apply', applyEntry));
for (const relative of inventory.filter(name => name.endsWith('.html'))) {
  const original = await readFile(path.join(source, relative), 'utf8');
  let updated = original;
  if (relative === 'apply/index.html') {
    assert(updated.includes('/apply/assets/index-1Mu13qxd.js'));
    updated = updated.replace('/apply/assets/index-1Mu13qxd.js', '/apply/' + applyEntry).replace('</head>', snippet + '\n</head>');
  } else {
    assert(analyticsPattern.test(updated), `${relative}: analytics snippet changed`);
    updated = updated.replace(analyticsPattern, snippet).replaceAll('/' + oldEntryPath, '/' + nextEntryPath);
  }
  assert.equal(updated.split(/<body\b[^>]*>/)[1], original.split(/<body\b[^>]*>/)[1], `${relative}: preserve existing body until targeted prerender`);
  await writeFile(path.join(output, relative), updated);
}
for (const relative of inventory.filter(name => !name.endsWith('.html'))) {
  assert((await readFile(path.join(source,relative))).equals(await readFile(path.join(output,relative))), `${relative} modified`);
}
console.log(JSON.stringify({ output, calculatorPath, nextEntryPath, applyEntry, sitemapUrls: paths.length - 2, oldAssetsPreserved: true, applyCssUnchanged: true }));

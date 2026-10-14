import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { files } from './funnel-support.mjs';
import { transform } from '../marketing/typeform-intake/notification-worker/node_modules/esbuild/lib/main.js';

const [sourceArg, outputArg] = process.argv.slice(2);
assert(sourceArg && outputArg, 'Usage: node scripts/build-typeform-intake-release.mjs VERIFIED_SOURCE FRESH_OUTPUT');
const source = path.resolve(sourceArg), output = path.resolve(outputArg);
assert(source !== output && !output.startsWith(source + path.sep));
const inventory = await files(source);
assert.equal(inventory.length, 335, 'Review baseline before changing release');
const originalApply = await readFile(path.join(source, 'apply/index.html'), 'utf8');
assert.ok(originalApply.includes('/apply/assets/index-B1pNjteW.js'));
const hash = value => createHash('sha256').update(value).digest('hex').slice(0, 12);
const readDraft = relative => readFile(new URL('../marketing/typeform-intake/' + relative, import.meta.url), 'utf8');
const sdk = await readDraft('notification-worker/node_modules/@typeform/embed/build/index.js');
const sdkAsset = `apply/assets/typeform-sdk-6.0.0-${hash(sdk)}.js`;
const widgetCss = await readDraft('notification-worker/node_modules/@typeform/embed/build/css/widget.css');
const css = widgetCss + '\n' + await readDraft('intake.css');
const cssAsset = `apply/assets/intake-${hash(css)}.css`;
const runtimeSource = await readDraft('intake.mjs') + `\ninitialize(window, document, ${JSON.stringify('/' + sdkAsset)});\n`;
const runtime = (await transform(runtimeSource, { format: 'esm', target: 'es2020', minify: true })).code;
const runtimeAsset = `apply/assets/intake-${hash(runtime)}.js`;
let nextApply = originalApply.replace('/apply/assets/index-B1pNjteW.js', '/' + runtimeAsset)
  .replace('</head>', `<meta name="referrer" content="no-referrer">\n<link rel="stylesheet" href="/${cssAsset}">\n</head>`)
  .replace(/<body>[\s\S]*<\/body>/, '<body>\n' + await readDraft('apply-body.html') + '\n</body>');
const eventList = '"calculator_used","apply_clicked","application_started","application_submitted"';
assert.equal(nextApply.split(eventList).length, 2, 'Expected one tracker event allowlist');
nextApply = nextApply.replace(eventList, eventList + ',"intake_started","intake_submitted"');
assert.ok(!nextApply.includes('noindex'));

const privacyRelative = 'assets/PrivacyPage-nphbg5_k-journey-396b323aebc9-review-51e10d24b4de.js';
const privacy = await readFile(path.join(source, privacyRelative), 'utf8');
const edits = JSON.parse(await readDraft('privacy-changes.json'));
let nextPrivacy = privacy;
for (const edit of edits) {
  assert.equal(nextPrivacy.split(edit.from).length, 2, 'Privacy source mismatch');
  nextPrivacy = nextPrivacy.replace(edit.from, edit.to);
}
const privacyAsset = `assets/PrivacyPage-typeform-${hash(nextPrivacy)}.js`;
const entryRelative = 'assets/index-guide-e66c64405e6c-journey-396b323aebc9-review-51e10d24b4de.js';
const entry = await readFile(path.join(source, entryRelative), 'utf8');
assert.ok(entry.includes(path.basename(privacyRelative)));
const nextEntry = entry.replaceAll(path.basename(privacyRelative), path.basename(privacyAsset));
const entryAsset = `assets/index-typeform-${hash(nextEntry)}.js`;
const newAssets = { [sdkAsset]: sdk, [cssAsset]: css, [runtimeAsset]: runtime, [privacyAsset]: nextPrivacy, [entryAsset]: nextEntry };
await mkdir(output);
await cp(source, output, { recursive: true });
for (const [relative, text] of Object.entries(newAssets)) await writeFile(path.join(output, relative), text);
let entryReferences = 0;
for (const relative of inventory.filter(file => file.endsWith('.html'))) {
  const original = await readFile(path.join(source, relative), 'utf8');
  let next = original.replaceAll('/' + entryRelative, '/' + entryAsset);
  if (next !== original) entryReferences++;
  if (relative === 'apply/index.html') next = nextApply;
  if (relative === 'privacy/index.html') {
    for (const edit of edits) {
      assert.equal(next.split(edit.from).length, 2, 'Privacy SSR mismatch');
      next = next.replace(edit.from, edit.to);
    }
  }
  if (next !== original) await writeFile(path.join(output, relative), next);
}
for (const relative of inventory) {
  const originalBytes = await readFile(path.join(source, relative));
  const nextBytes = await readFile(path.join(output, relative));
  if (!relative.endsWith('.html')) {
    assert.deepEqual(nextBytes, originalBytes, `Unexpected binary/config change: ${relative}`);
    continue;
  }
  const original = originalBytes.toString('utf8');
  const next = nextBytes.toString('utf8');
  if (relative === 'apply/index.html') {
    const head = text => text.match(/<head>[\s\S]*?<\/head>/)?.[0];
    const restoredHead = head(next)
      .replace('/' + runtimeAsset, '/apply/assets/index-B1pNjteW.js')
      .replace(`<meta name="referrer" content="no-referrer">\n<link rel="stylesheet" href="/${cssAsset}">\n`, '')
      .replace(eventList + ',"intake_started","intake_submitted"', eventList);
    assert.equal(restoredHead, head(original), 'Unexpected Apply head/metadata/schema change');
  } else if (relative === 'privacy/index.html') {
    let restored = next.replaceAll('/' + entryAsset, '/' + entryRelative);
    for (const edit of edits) restored = restored.replace(edit.to, edit.from);
    assert.equal(restored, original, 'Unexpected privacy changes');
  } else assert.equal(next.replaceAll('/' + entryAsset, '/' + entryRelative), original, `Unexpected change: ${relative}`);
}
assert.equal((await readFile(path.join(output, 'sitemap.xml'), 'utf8')).match(/<loc>/g).length, 139);
assert.deepEqual((await files(output)).sort(), [...inventory, ...Object.keys(newAssets)].sort());
console.log(JSON.stringify({ output, baseline: source, existingFilesPreserved: inventory.length,
  sitemapUrls: 139, entryReferences, newAssets: Object.keys(newAssets),
  contentChangesOnly: ['apply/index.html', 'privacy/index.html'],
  hostingRules: 'unchanged', formerAssets: 'retained for rollback and cached pages' }, null, 2));

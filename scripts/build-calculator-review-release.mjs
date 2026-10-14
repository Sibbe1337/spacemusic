import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { build } from '../services/seller_ui/node_modules/esbuild/lib/main.js';
import { files } from './funnel-support.mjs';
import { literals, replaceLiterals } from './journey-support.mjs';

const [source, output, manifestFile] = process.argv.slice(2);
assert(source && output && manifestFile, 'Usage: BASELINE FRESH_OUTPUT MANIFEST');
assert(path.resolve(source) !== path.resolve(output));
assert(!path.resolve(output).startsWith(path.resolve(source) + path.sep));
const hash = value => createHash('sha256').update(value).digest('hex').slice(0, 12);
const inventory = await files(source);
const home = await readFile(path.join(source, 'index.html'), 'utf8');
const entry = home.match(/<script type="module" crossorigin(?:="")? src="\/assets\/([^" ]+)"/)[1];
assert.equal(entry, 'index-guide-e66c64405e6c-journey-396b323aebc9.js', 'Use the verified September 8 journey release');
assert.equal([...((await readFile(path.join(source, 'sitemap.xml'), 'utf8')).matchAll(/<loc>/g))].length, 139);

const originals = new Map();
for (const file of inventory.filter(file => file.startsWith('assets/') && file.endsWith('.js'))) {
  originals.set(path.basename(file), await readFile(path.join(source, file), 'utf8'));
}
const codes = new Map(originals);
const dependencies = name => new Set(literals(codes.get(name)).map(node => path.basename(node.value)).filter(name => codes.has(name)));
const reachable = new Set();
function visit(name) {
  if (reachable.has(name)) return;
  reachable.add(name);
  for (const child of dependencies(name)) visit(child);
}
visit(entry);
const calculators = [...reachable].filter(name => name.startsWith('Calculator-scenario-'));
assert.equal(calculators.length, 1);
const oldCalculator = calculators[0];
assert(!reachable.has('ApplicationForm-DRjdd2L1.js'));
const compiled = await build({
  entryPoints: ['marketing/funnel/Calculator.jsx'], bundle: true, format: 'esm', write: false,
  minify: true, jsxFactory: 'React.createElement', jsxFragment: 'React.Fragment',
  external: ['./vendor-*.js', './Navbar-*.js', './Footer-*.js', './SEOHead-*.js'],
});
// Keep the current shared components, not the superseded imports in the original JSX source.
const currentImports = literals(originals.get(oldCalculator)).map(node => node.value).filter(value => /^\.\/(vendor|Navbar|Footer|SEOHead)-.*\.js$/.test(value));
assert.equal(currentImports.length, 4);
let calculator = compiled.outputFiles[0].text;
for (const current of currentImports) {
  const family = current.match(/^\.\/([^-]+)-/)[1];
  const matches = literals(calculator).map(node => node.value).filter(value => value.startsWith(`./${family}-`) && value.endsWith('.js'));
  assert.equal(matches.length, 1);
  calculator = replaceLiterals(calculator, [[matches[0], current]], true);
}
assert(calculator.includes('How much could your music catalog sell for?'));
codes.set(oldCalculator, calculator);
const changed = new Set([oldCalculator]);
let growing = true;
while (growing) {
  growing = false;
  for (const name of reachable) if (!changed.has(name) && [...dependencies(name)].some(child => changed.has(child))) {
    changed.add(name); growing = true;
  }
}
// One fingerprint supports the existing cyclic import graph while retaining every cached asset.
const revision = hash([...changed].sort().map(name => name + codes.get(name)).join('\n'));
const renamed = new Map([...changed].map(name => [name, `${name.slice(0, -3)}-review-${revision}.js`]));
await mkdir(output);
await cp(source, output, { recursive: true });
for (const name of changed) {
  const replacements = literals(codes.get(name)).filter(node => renamed.has(path.basename(node.value))).map(node => [node.value, node.value.slice(0, -path.basename(node.value).length) + renamed.get(path.basename(node.value))]);
  await writeFile(path.join(output, 'assets', renamed.get(name)), replaceLiterals(codes.get(name), replacements));
}
for (const file of inventory.filter(file => file.endsWith('.html'))) {
  const original = await readFile(path.join(source, file), 'utf8');
  let updated = original;
  for (const [oldName, newName] of renamed) updated = updated.replaceAll(`/assets/${oldName}`, `/assets/${newName}`);
  if (updated !== original) await writeFile(path.join(output, file), updated);
}
for (const file of inventory.filter(file => !file.endsWith('.html') || file.startsWith('apply/'))) {
  assert((await readFile(path.join(source, file))).equals(await readFile(path.join(output, file))), `Unapproved change: ${file}`);
}
await mkdir(path.dirname(manifestFile), { recursive: true });
await writeFile(manifestFile, JSON.stringify({ source, output, revision, entry: renamed.get(entry), oldCalculator, calculator: renamed.get(oldCalculator), changed: [...renamed], sourceHashes: Object.fromEntries(await Promise.all(inventory.map(async file => [file, hash(await readFile(path.join(source, file)))]))) }, null, 2));
console.log(JSON.stringify({ output, revision, newModules: changed.size, apply: 'byte-identical', existingAssets: 'preserved', nextStep: 'prerender calculator only, then verify' }));

import { build } from 'esbuild';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const dist = new URL('dist/', root);
await mkdir(dist, { recursive: true });
const bundle = await build({
  entryPoints: [new URL('web/widget.mjs', root).pathname], bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', minify: true, write: false,
});
const css = await readFile(new URL('web/widget.css', root), 'utf8');
const font = await readFile(new URL('assets/inter.woff2', root));
const wordmark = await readFile(new URL('assets/space-wordmark.svg', root), 'utf8');
const template = await readFile(new URL('web/widget.html', root), 'utf8');
const html = template.replace('/* SPACE_STYLES */', css.replace('SPACE_FONT_DATA', font.toString('base64')))
  .replace('<!-- SPACE_WORDMARK -->', wordmark)
  .replace('/* SPACE_SCRIPT */', () => bundle.outputFiles[0].text.replace(/<\/script/gi, '<\\/script'));
await writeFile(new URL('widget.html', dist), html);
await build({
  entryPoints: [new URL('web/preview.mjs', root).pathname], bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', minify: true,
  outfile: new URL('preview.js', dist).pathname,
});
await writeFile(new URL('preview.html', dist), await readFile(new URL('web/preview.html', root)));
console.log('Built self-contained widget and local preview host. No remote assets or customer data.');

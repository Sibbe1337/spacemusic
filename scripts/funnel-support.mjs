import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
export async function files(root, prefix = '') {
  const result = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    assert(!entry.isSymbolicLink());
    const name = path.join(prefix, entry.name);
    if (entry.isDirectory()) result.push(...await files(path.join(root, entry.name), name));
    else result.push(name);
  }
  return result.sort();
}
export async function serve(directory) {
  const root = path.resolve(directory);
  const mime = { '.html': 'text/html', '.js': 'application/javascript', '.mjs': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.xml': 'application/xml' };
  const server = http.createServer(async (req, res) => {
    try {
      let file = path.resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
      assert(file === root || file.startsWith(root + path.sep));
      if ((await stat(file)).isDirectory()) file = path.join(file, 'index.html');
      res.setHeader('Content-Type', mime[path.extname(file)] || 'text/plain');
      res.end(await readFile(file));
    } catch { res.writeHead(404); res.end('Not found'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { origin: `http://127.0.0.1:${server.address().port}`, close: () => server.close() };
}
export const playwrightModule = process.env.PLAYWRIGHT_MODULE || '/Users/emilsoujeh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';

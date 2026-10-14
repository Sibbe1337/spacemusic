import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const base = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(base, '../..');
const assets = new Map([
  ['/', ['ui/index.html', 'text/html; charset=utf-8']],
  ['/app.mjs', ['ui/app.mjs', 'text/javascript; charset=utf-8']],
  ['/review.css', ['ui/review.css', 'text/css; charset=utf-8']],
  ['/model.mjs', ['model.mjs', 'text/javascript; charset=utf-8']],
  ['/fixtures.mjs', ['fixtures.mjs', 'text/javascript; charset=utf-8']],
  ['/storage.mjs', ['storage.mjs', 'text/javascript; charset=utf-8']],
]);
const shared = new Map([
  ['/space-wordmark.svg', ['marketing/identity-20260916/space-wordmark.svg', 'image/svg+xml']],
  ['/inter.woff2', ['marketing/design/fonts/inter-latin-c940764593d0.woff2', 'font/woff2']],
]);

export function createPreviewServer() {
  return http.createServer(async (req, res) => {
    const port = req.socket.localPort;
    const headers = {
      'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow, noarchive',
      'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
      'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
      'Cross-Origin-Resource-Policy': 'same-origin',
    };
    function finish(status, body, type = 'text/plain; charset=utf-8') {
      res.writeHead(status, { ...headers, 'Content-Type': type });
      res.end(req.method === 'HEAD' ? undefined : body);
    }
    if (req.headers.host !== `127.0.0.1:${port}`) return finish(403, 'Local preview host required.');
    if (!['GET', 'HEAD'].includes(req.method)) return finish(405, 'Read-only design preview.');
    const asset = assets.get(req.url) || shared.get(req.url);
    if (!asset) return finish(404, 'Not part of this preview.');
    const fetchSite = req.headers['sec-fetch-site'];
    if (fetchSite === 'cross-site' && !(req.url === '/' && req.headers['sec-fetch-mode'] === 'navigate' && req.headers['sec-fetch-dest'] === 'document')) return finish(403, 'Cross-site request denied.');
    try {
      const location = shared.has(req.url) ? root : base;
      finish(200, await readFile(path.join(location, asset[0])), asset[1]);
    } catch { finish(503, 'Preview asset unavailable.'); }
  });
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  const raw = process.argv[2] || '4197';
  if (!/^\d+$/.test(raw) || Number(raw) < 1024 || Number(raw) > 65535) throw new Error('Use an unprivileged local port.');
  const server = createPreviewServer();
  server.listen(Number(raw), '127.0.0.1', () => console.log(`Synthetic-only catalog review preview: http://127.0.0.1:${raw}/`));
}

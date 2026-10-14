import http from 'node:http';
import { pathToFileURL } from 'node:url';
import { SCENARIOS, workspaceFor } from './scenarios.mjs';

export function createServer() {
  const server = http.createServer({ maxHeaderSize: 8192 }, (req, res) => {
    const send = (status, value) => {
      res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
        'X-Robots-Tag': 'noindex, nofollow, noarchive', 'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'",
        Connection: 'close',
      });
      res.end(req.method === 'HEAD' ? undefined : JSON.stringify(value));
    };
    // No body reader, persistence, authentication bypass or customer-data API.
    if (!['GET', 'HEAD'].includes(req.method) || req.headers['transfer-encoding'] || Number(req.headers['content-length'] || 0) !== 0) {
      return send(405, { error: 'Read-only synthetic preview. No uploads or writes.' });
    }
    if (req.url === '/healthz') return send(200, { status: 'ok', mode: 'synthetic-read-only-preview' });
    const match = /^\/preview\/(draft|submitted|followup|completed|reviewer)$/.exec(req.url || '');
    if (!match || !SCENARIOS.includes(match[1])) return send(404, { error: 'Not a preview endpoint' });
    send(200, workspaceFor(match[1]));
  });
  server.requestTimeout = 5000;
  server.headersTimeout = 5000;
  server.keepAliveTimeout = 1000;
  server.maxRequestsPerSocket = 10;
  return server;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const port = Number(process.env.PORT || 4318);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port');
  const server = createServer();
  server.listen(port, '0.0.0.0', () => console.log('Synthetic read-only preview started'));
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => server.close(() => process.exit(0)));
}

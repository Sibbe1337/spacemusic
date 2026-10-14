import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createMcpServer } from './mcp.mjs';

const MAX_BODY = 16 * 1024;
const dist = new URL('../dist/', import.meta.url);
function publicOrigin(value) {
  if (!value) return null;
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('PUBLIC_MCP_ORIGIN must be an exact HTTPS origin, without credentials or a path.');
  }
  return url.origin;
}

export function createHttpServer({ origin = null } = {}) {
  const externalOrigin = publicOrigin(origin);
  const widgetHtml = readFileSync(new URL('widget.html', dist), 'utf8');
  const inlineScript = widgetHtml.match(/<script type="module">([\s\S]*?)<\/script>/)?.[1];
  if (!inlineScript) throw new Error('Build the widget before starting the server.');
  const scriptHash = createHash('sha256').update(inlineScript).digest('base64');
  const assets = new Map([
    ['/', { type: 'text/html; charset=utf-8', data: readFileSync(new URL('preview.html', dist)) }],
    ['/preview.js', { type: 'text/javascript; charset=utf-8', data: readFileSync(new URL('preview.js', dist)) }],
    ['/widget.html', { type: 'text/html; charset=utf-8', data: widgetHtml }],
  ]);
  const server = createServer(async (req, res) => {
    const port = server.address().port;
    const origins = new Set([`http://127.0.0.1:${port}`, `http://localhost:${port}`]);
    if (externalOrigin) origins.add(externalOrigin);
    const hosts = new Set([...origins].map(value => new URL(value).host));
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
    res.setHeader('Referrer-Policy', 'no-referrer');
    const fail = (status, message) => {
      req.resume();
      if (!res.headersSent) res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' }).end(message);
    };
    if (!hosts.has(req.headers.host)) return fail(403, 'Host not allowed');
    if (req.headers.origin && !origins.has(req.headers.origin)) return fail(403, 'Origin not allowed');
    if (req.headers['sec-fetch-site'] === 'cross-site') return fail(403, 'Cross-site request denied');
    let url;
    try { url = new URL(req.url, `http://${req.headers.host}`); }
    catch { return fail(400, 'Invalid URL'); }
    if (url.search) return fail(400, 'Query parameters are not supported');
    if (req.method === 'GET' && url.pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ status: 'ok', mode: 'synthetic-only' }));
      return;
    }
    if (req.method === 'GET' && assets.has(url.pathname)) {
      const asset = assets.get(url.pathname);
      const csp = url.pathname === '/widget.html'
        ? `default-src 'none'; script-src 'sha256-${scriptHash}'; style-src 'unsafe-inline'; font-src data:; img-src data:; connect-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'`
        : "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
      res.writeHead(200, { 'Content-Type': asset.type, 'Content-Security-Policy': csp }).end(asset.data);
      return;
    }
    if (url.pathname !== '/mcp') return fail(404, 'Not found');
    if (req.method === 'OPTIONS') {
      res.setHeader('Allow', 'POST, GET, DELETE, OPTIONS');
      if (req.headers.origin) {
        res.setHeader('Access-Control-Allow-Origin', req.headers.origin);
        res.setHeader('Vary', 'Origin');
        res.setHeader('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'content-type, mcp-protocol-version, mcp-session-id');
      }
      res.writeHead(204).end();
      return;
    }
    if (!['POST', 'GET', 'DELETE'].includes(req.method)) return fail(405, 'Method not allowed');
    let body;
    if (req.method === 'POST') {
      if (!/^application\/json(?:\s*;|$)/i.test(req.headers['content-type'] ?? '')) return fail(415, 'JSON required');
      if (req.headers['content-encoding']) return fail(415, 'Encoded bodies are not supported');
      if (Number(req.headers['content-length']) > MAX_BODY) return fail(413, 'Request too large');
      try {
        let length = 0;
        const chunks = [];
        for await (const chunk of req) {
          length += chunk.length;
          if (length > MAX_BODY) return fail(413, 'Request too large');
          chunks.push(chunk);
        }
        body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (!body || typeof body !== 'object' || Array.isArray(body)) return fail(400, 'Expected one JSON-RPC object');
      } catch { return fail(400, 'Invalid JSON'); }
    }
    const mcp = createMcpServer(widgetHtml);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.once('close', () => { void mcp.close().catch(() => {}); });
    try {
      await mcp.connect(transport);
      await transport.handleRequest(req, res, body);
    } catch {
      // Do not log request bodies, supplied arguments or credentials.
      fail(500, 'MCP request failed');
    }
  });
  server.requestTimeout = 10000;
  server.headersTimeout = 10000;
  server.keepAliveTimeout = 5000;
  server.maxRequestsPerSocket = 100;
  return server;
}

export function stopHttpServer(server) {
  return new Promise(resolve => {
    server.close(resolve);
    // Persistent MCP event streams must not keep a local restart alive indefinitely.
    server.closeAllConnections();
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.PORT ?? 4210);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('PORT must be 1024-65535');
  const server = createHttpServer({ origin: process.env.PUBLIC_MCP_ORIGIN });
  server.listen(port, '127.0.0.1', () => {
    console.log(`SPACE synthetic-only preview: http://127.0.0.1:${port}/`);
    console.log(`MCP endpoint: http://127.0.0.1:${port}/mcp`);
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => { void stopHttpServer(server); });
}

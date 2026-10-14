const scenarios = new Set(['draft', 'submitted', 'followup', 'completed', 'reviewer']);

export async function proxyWorkspace(req, res, { backend = process.env.REVIEW_PREVIEW_BACKEND_URL, fetchImpl = fetch } = {}) {
  const send = (status, body) => {
    res.statusCode = status;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.end(JSON.stringify(body));
  };
  if (req.method !== 'GET' || req.headers['transfer-encoding'] || Number(req.headers['content-length'] || 0) !== 0) return send(405, { error: 'Read-only preview' });
  if (req.url?.includes('?')) return send(400, { error: 'Query parameters are not accepted' });
  const scenario = req.headers['x-preview-scenario'] || 'draft';
  if (!scenarios.has(scenario)) return send(400, { error: 'Unknown preview scenario' });
  // The URL is server configuration, never a browser-supplied proxy target.
  let origin;
  try {
    const url = new URL(backend);
    if (url.protocol !== 'https:' || !/^[a-z0-9-]+\.up\.railway\.app$/.test(url.hostname)
      || url.port || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error();
    origin = url.origin;
  } catch { return send(503, { error: 'Preview backend is not connected yet' }); }
  try {
    const response = await fetchImpl(`${origin}/preview/${scenario}`, {
      method: 'GET', headers: { Accept: 'application/json' }, redirect: 'error',
      signal: AbortSignal.timeout(8000),
    });
    if (response.status !== 200 || !response.headers.get('content-type')?.startsWith('application/json')) throw new Error();
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) { await reader.cancel(); throw new Error(); }
      chunks.push(value);
    }
    const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (value.environment !== 'test' || value.workspace_id !== '10000000-0000-4000-8000-000000000001'
      || value.csrf !== 'public-preview-not-a-real-session') throw new Error();
    return send(200, value);
  } catch { return send(502, { error: 'Preview backend unavailable. Please try again later.' }); }
}

export default function handler(req, res) { return proxyWorkspace(req, res); }

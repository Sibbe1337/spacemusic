// Typeform is the response store. This worker retains no answers or raw payloads.
export const FORM_ID = 'xzx5SBJb';
// Webhook field IDs differ from the editor's UUID refs.
export const EMAIL_FIELD_ID = 'oY3yxQa3CAD3';
export const NAME_FIELD_ID = 'cIEzRJe4jZWW';
export const INBOX = 'hello@spacemusic.io';
export const RESULTS = `https://admin.typeform.com/form/${FORM_ID}/results#responses`;
const VERSION = '20260916-v2';
const MAX_BODY = 128 * 1024;
const DAY = 86400000;
const RETRY_WINDOW = 20 * 3600000; // Less than Resend's 24-hour idempotency retention.
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });

function response(status, message) {
  return new Response(message, { status, headers: {
    'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow',
    'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'",
  } });
}

export async function boundedBody(body, limit = MAX_BODY) {
  if (!body) return new Uint8Array();
  const reader = body.getReader();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > limit) { await reader.cancel(); throw new Error('body_limit'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}

export async function verifySignature(bytes, signature, secret) {
  if (typeof secret !== 'string' || secret.length < 32 || !/^sha256=[A-Za-z0-9+/]{43}=$/.test(signature || '')) return false;
  const received = Uint8Array.from(atob(signature.slice(7)), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
  return crypto.subtle.verify('HMAC', key, received, bytes);
}

async function identifier(token) {
  const bytes = await crypto.subtle.digest('SHA-256', encoder.encode(`${FORM_ID}:${token}`));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
}

export function safeEmail(value) {
  return typeof value === 'string' && value.length <= 254 && /^[^\s<>(),;:"\\\x00-\x1f\x7f@]+@[^\s<>(),;:"\\\x00-\x1f\x7f@]+\.[^\s<>(),;:"\\\x00-\x1f\x7f@]+$/u.test(value);
}

async function encryptionKey(secret) {
  if (!/^[a-f0-9]{64}$/.test(secret || '')) throw new Error('encryption_config');
  const bytes = Uint8Array.from(secret.match(/../g), x => parseInt(x, 16));
  return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
}

export async function encryptEmail(email, id, secret) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: encoder.encode(id) }, await encryptionKey(secret), encoder.encode(email)));
  return btoa(String.fromCharCode(...iv, ...encrypted));
}

export async function decryptEmail(value, id, secret) {
  const bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0));
  const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes.slice(0, 12), additionalData: encoder.encode(id) }, await encryptionKey(secret), bytes.slice(12));
  const email = decoder.decode(decrypted);
  if (!safeEmail(email)) throw new Error('reply_invalid');
  return email;
}

export async function parseNotification(payload, now) {
  const form = payload?.form_response;
  if (payload?.event_type !== 'form_response' || form?.form_id !== FORM_ID) return null;
  if (form.response_type && form.response_type !== 'completed') return null;
  if (typeof form.token !== 'string' || !/^[a-zA-Z0-9_-]{8,128}$/.test(form.token)) throw new Error('response_reference');
  const submitted = Date.parse(form.submitted_at);
  if (!Number.isFinite(submitted) || submitted > now + 300000 || submitted < now - 7 * DAY) throw new Error('response_date');
  if (!Array.isArray(form.answers) || form.answers.length > 100) throw new Error('response_answers');
  const emails = form.answers.filter(answer => answer?.field?.id === EMAIL_FIELD_ID && answer.type === 'email');
  if (emails.length !== 1 || !safeEmail(emails[0].email)) throw new Error('response_email');
  const testName = form.answers.find(answer => answer?.field?.id === NAME_FIELD_ID && answer.type === 'text')?.text;
  const is_test = emails[0].email === INBOX && typeof testName === 'string' && testName.startsWith('TEST ONLY - SPACE QA ');
  return { id: await identifier(form.token), email: emails[0].email, submitted_at: new Date(submitted).toISOString(), is_test: Number(is_test) };
}

export function notificationMessage(row, replyTo) {
  return {
    from: 'SPACE intake <hello@spacemusic.io>', to: [INBOX], reply_to: replyTo,
    subject: (row.is_test ? '[TEST ONLY] ' : '') + 'SPACE: New intake received',
    text: `A new SPACE intake has been completed.\n\nReceived: ${row.submitted_at}\nNotification reference: ${row.id.slice(0, 12)}\n\nSign in to Typeform to review the complete response before replying:\n${RESULTS}\n\nThis inbox includes owners, representatives and partnership inquiries. A request is not a qualified lead, valuation or offer. No automatic reply has been sent to the respondent.\n\nUse Reply to contact the address supplied in the form after reviewing the record. Do not reply to records marked TEST ONLY.\n\nSPACE\nhttps://spacemusic.io/`,
    tags: [{ name: 'source', value: 'space_typeform_intake' }],
  };
}

async function markFailed(env, id, code) {
  await env.DB.prepare("UPDATE notifications SET status='failed', reply_cipher=NULL, lease_token=NULL, lease_until=0, error_code=? WHERE id=? AND status='pending'").bind(code, id).run();
  console.error('space_intake_notification_requires_review');
}

export async function deliver(id, env, fetcher = fetch, now = Date.now()) {
  if (env.SEND_ENABLED !== 'true') return;
  const lease = crypto.randomUUID();
  // Single conditional SQL mutation arbitrates webhook/cron/concurrent retries.
  const row = await env.DB.prepare(`UPDATE notifications SET lease_token=?, lease_until=?,
    attempts=attempts+1, first_attempt=COALESCE(first_attempt,?)
    WHERE id=? AND status='pending' AND next_attempt<=? AND lease_until<=?
    RETURNING *`).bind(lease, now + 60000, now, id, now, now).first();
  if (!row) return;
  if (now - row.first_attempt >= RETRY_WINDOW || now - row.created_at >= 2 * DAY) {
    await markFailed(env, id, 'retry_window_expired'); return;
  }
  let code = 'sender_config';
  try {
    if (!env.RESEND_API_KEY) throw new Error('sender_config');
    code = 'reply_decrypt';
    const replyTo = await decryptEmail(row.reply_cipher, id, env.REPLY_ENCRYPTION_KEY);
    code = 'provider_fetch';
    const result = await fetcher('https://api.resend.com/emails', {
      method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(10000),
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json',
        'Idempotency-Key': `space-intake-v1-${id}` },
      body: JSON.stringify(notificationMessage(row, replyTo)),
    });
    code = `provider_http_${result.status}`;
    const bytes = await boundedBody(result.body, 16384);
    if (result.ok) {
      const receipt = JSON.parse(decoder.decode(bytes));
      if (typeof receipt.id !== 'string' || !/^[a-f0-9-]{36}$/.test(receipt.id)) throw new Error('provider_receipt');
      await env.DB.prepare(`UPDATE notifications SET status='accepted', provider_id=?,
        reply_cipher=NULL, lease_token=NULL, lease_until=0, error_code=NULL
        WHERE id=? AND lease_token=? AND status='pending'`).bind(receipt.id, id, lease).run();
      return;
    }
  } catch (error) {
    // Bounded stage/type only: retain actionable diagnostics without provider bodies or secrets.
    const type = ['TypeError', 'OperationError', 'AbortError', 'TimeoutError'].includes(error?.name) ? error.name : 'Error';
    code += '_' + type;
  }
  const delay = Math.min(3600000, 60000 * 2 ** Math.min(row.attempts - 1, 6));
  await env.DB.prepare(`UPDATE notifications SET lease_token=NULL, lease_until=0,
    next_attempt=?, error_code=? WHERE id=? AND lease_token=? AND status='pending'`)
    .bind(now + delay, code, id, lease).run();
  console.error('space_intake_notification_retry_pending');
}

export async function receive(request, env, ctx, now = Date.now()) {
  const url = new URL(request.url);
  if (url.search) return response(400, 'Unexpected query');
  if (url.pathname === '/health' && request.method === 'GET') {
    await env.DB.prepare('SELECT 1 AS healthy').first();
    return response(200, `SPACE intake notifications ${VERSION}`);
  }
  if (url.pathname !== '/typeform') return response(404, 'Not found');
  if (request.method !== 'POST') return response(405, 'POST required');
  if (!env.TYPEFORM_WEBHOOK_SECRET || !env.REPLY_ENCRYPTION_KEY) return response(503, 'Not configured');
  if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') || '')) return response(415, 'JSON required');
  if (Number(request.headers.get('content-length')) > MAX_BODY) return response(413, 'Too large');
  let bytes;
  try { bytes = await boundedBody(request.body); } catch { return response(413, 'Too large'); }
  if (!await verifySignature(bytes, request.headers.get('typeform-signature'), env.TYPEFORM_WEBHOOK_SECRET)) return response(401, 'Invalid signature');
  let item;
  try { item = await parseNotification(JSON.parse(decoder.decode(bytes)), now); }
  catch { console.error('space_intake_payload_requires_review'); return response(422, 'Invalid completed response'); }
  if (!item) return response(204, null);
  const cipher = await encryptEmail(item.email, item.id, env.REPLY_ENCRYPTION_KEY);
  await env.DB.prepare(`INSERT INTO notifications
    (id,submitted_at,created_at,reply_cipher,is_test,status,next_attempt) VALUES (?,?,?,?,?,'pending',?)
    ON CONFLICT(id) DO NOTHING`).bind(item.id, item.submitted_at, now, cipher, item.is_test, now).run();
  // Acknowledge only after durable storage. Cron is the recovery path if waitUntil is interrupted.
  ctx.waitUntil(deliver(item.id, env));
  return response(202, 'Notification queued; completed response remains in Typeform');
}

export async function retryDue(env, now = Date.now()) {
  // Ciphertext is removed on acceptance or terminal failure; operational hashes expire after 30 days.
  await env.DB.prepare("UPDATE notifications SET status='failed', reply_cipher=NULL, error_code='queue_expired', lease_token=NULL, lease_until=0 WHERE status='pending' AND created_at<?").bind(now - 2 * DAY).run();
  await env.DB.prepare('DELETE FROM notifications WHERE created_at<?').bind(now - 30 * DAY).run();
  const due = await env.DB.prepare("SELECT id FROM notifications WHERE status='pending' AND next_attempt<=? AND lease_until<=? ORDER BY next_attempt LIMIT 20").bind(now, now).all();
  for (const row of due.results) await deliver(row.id, env, fetch, now);
  const attention = await env.DB.prepare("SELECT COUNT(*) AS total FROM notifications WHERE status='failed'").first();
  if (attention.total) console.error('space_intake_failed_notifications_check_typeform');
}

export default {
  async fetch(request, env, ctx) {
    try { return await receive(request, env, ctx); }
    catch { console.error('space_intake_receiver_unavailable'); return response(503, 'Temporarily unavailable'); }
  },
  async scheduled(_event, env) { await retryDue(env); },
};

const BASE = '/api/portal/';
const UUID = /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i;

export class PortalError extends Error {
  constructor(kind, status = 0) {
    super('The workspace request could not be completed.');
    this.name = 'PortalError';
    this.kind = kind;
    this.status = status;
  }
}

export function errorMessage(error) {
  if (error?.status === 401) return 'Your session or invitation has expired. Private information has been cleared. Open a new invitation or explicitly refresh an existing session.';
  if (error?.status === 403) return 'This session does not have permission for that action. Private information has been cleared. Ask for the correct workspace access.';
  if (error?.status === 409) return 'The workspace changed or is already submitted. Your entries have not been overwritten. Refresh and review the server version before continuing.';
  if (error?.status === 429) return 'Too many requests. Wait a moment, then try again. Nothing will retry automatically.';
  if (error?.status === 422) return 'The server could not accept these fields. Check your entries. They are still here.';
  if (error?.kind === 'timeout') return 'The request timed out. Its outcome may be unknown. Refresh to check; use the same retry action if needed.';
  if (error?.kind === 'network') return 'The connection is unavailable. Check whether you are offline, then retry or refresh. The outcome of a sent request may be unknown.';
  if (error?.kind === 'contract') return 'The workspace response is incomplete or unsupported. No new information has been applied. Ask the integration maintainer to check the contract.';
  return 'The service could not complete this request. No server error details are displayed. Refresh to check its outcome before trying again.';
}

export function createClient({ fetchImpl = globalThis.fetch, timeoutMs = 12000 } = {}) {
  let csrf = null;
  let logoutRequest = null;
  const requests = new Set();

  function clear() {
    csrf = null;
    for (const cancel of requests) cancel();
    requests.clear();
  }

  async function request(path, method = 'GET', body, csrfToken = csrf, upload, downloadType = null, keepalive = false) {
    const controller = new AbortController();
    let timer;
    let cancel;
    const interruption = new Promise((_, reject) => {
      cancel = () => {
        reject(new PortalError('cancelled'));
        controller.abort();
      };
      timer = setTimeout(() => {
        reject(new PortalError('timeout'));
        controller.abort();
      }, timeoutMs);
    });
    // Session revocation must survive private-view cleanup and page navigation.
    if (!keepalive) requests.add(cancel);
    const headers = { Accept: downloadType || 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (upload) {
      headers['Content-Type'] = 'application/octet-stream';
      headers['X-Document-Name'] = encodeURIComponent(upload.file.name);
      headers['X-Upload-Id'] = upload.request_id;
    }
    if (method !== 'GET' && !['session', 'access-request'].includes(path)) {
      if (!csrfToken) {
        clearTimeout(timer);
        requests.delete(cancel);
        throw new PortalError('authentication', 401);
      }
      headers['X-CSRF-Token'] = csrfToken;
    } else if (method === 'DELETE' && csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
    const operation = async () => {
      const response = await fetchImpl(`${BASE}${path}`, {
        method, headers, credentials: 'same-origin', mode: 'same-origin',
        cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        signal: controller.signal,
        ...(keepalive ? { keepalive: true } : {}),
        ...(upload ? { body: upload.file } : body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      // Never read or expose error bodies, even when they claim to contain JSON.
      if (!response.ok) throw new PortalError('http', response.status);
      if (response.status === 204 && method === 'DELETE') return null;
      const type = response.headers.get('content-type')?.split(';')[0].trim().toLowerCase();
      if (downloadType) {
        if (type !== downloadType || !/^attachment(?:;|$)/i.test(response.headers.get('content-disposition') || '')) throw new PortalError('response');
        return response.blob();
      }
      if (type !== 'application/json') throw new PortalError('response');
      try { return await response.json(); }
      catch { throw new PortalError('response'); }
    };
    try {
      return await Promise.race([operation(), interruption]);
    } catch (error) {
      if (error instanceof PortalError) throw error;
      throw new PortalError('network');
    } finally {
      clearTimeout(timer);
      requests.delete(cancel);
    }
  }

  return {
    clear,
    setCsrf(value) {
      if (typeof value !== 'string' || !value || value.length > 512 || /[\r\n]/.test(value)) throw new PortalError('contract');
      csrf = value;
    },
    exchange: token => request('session', 'POST', { token }),
    access: (workspaceId, email) => request('access-request', 'POST', { workspace_id: workspaceId, email }),
    workspace: () => request('workspace'),
    dealflow: () => request('dealflow'),
    dealflowSave: body => request('dealflow/reviews', 'POST', body),
    dealflowPrepare: body => request('dealflow/packages', 'POST', body),
    dealflowDecide(body, packageId) {
      if (!UUID.test(packageId)) return Promise.reject(new PortalError('contract'));
      return request(`dealflow/packages/${packageId}/decision`, 'POST', body);
    },
    save: (revision, draft) => request('draft', 'PUT', { revision, draft }),
    submit: body => request('submission', 'POST', body),
    question: body => request('questions', 'POST', { request_documents: false, ...body }),
    reply(questionId, body) {
      if (!UUID.test(questionId)) return Promise.reject(new PortalError('contract'));
      return request(`questions/${questionId}/reply`, 'POST', { document_ids: [], ...body });
    },
    deletion: () => request('deletion-request', 'POST'),
    exportCase: () => request('export', 'GET', undefined, csrf, undefined, 'application/json'),
    continueInterest(requestId) {
      if (!UUID.test(requestId)) return Promise.reject(new PortalError('contract'));
      return request('continue-interest', 'POST', { request_id: requestId });
    },
    upload(file, requestId) {
      if (!UUID.test(requestId)) return Promise.reject(new PortalError('contract'));
      return request('documents', 'POST', undefined, csrf, { file, request_id: requestId });
    },
    uploadQuestion(questionId, file, requestId) {
      if (!UUID.test(questionId) || !UUID.test(requestId)) return Promise.reject(new PortalError('contract'));
      return request(`questions/${questionId}/documents`, 'POST', undefined, csrf, { file, request_id: requestId });
    },
    download(documentId) {
      if (!UUID.test(documentId)) return Promise.reject(new PortalError('contract'));
      return request(`documents/${documentId}`, 'GET', undefined, csrf, undefined, 'application/octet-stream');
    },
    logout() {
      if (logoutRequest) return logoutRequest;
      const previous = csrf;
      clear();
      if (!previous) return Promise.reject(new PortalError('authentication', 401));
      logoutRequest = request('session', 'DELETE', undefined, previous, undefined, null, true)
        .finally(() => { logoutRequest = null; });
      return logoutRequest;
    },
  };
}

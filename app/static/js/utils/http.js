/* app/static/js/utils/http.js
 * SIIAP.api — the one HTTP client of the frontend.
 *
 *   SIIAP.api.request(method, url, {json, body, headers, signal, flash, onUnauthorized})
 *     -> Promise<{ok, status, data, meta, error, flash, body, contentType}>  (body = raw JSON)
 *   SIIAP.api.get(url, opts) / post(url, json, opts) / put / patch / delete
 *   SIIAP.api.csrfToken()  -> current token (read live from the meta tag)
 *
 * Contract:
 *   - Resolves for ANY HTTP status whose body is the API envelope
 *     {data, error, meta, flash}; it never throws on 4xx/5xx. It rejects only
 *     on network failures (or aborted requests).
 *   - Non-JSON bodies (HTML error pages) resolve with ok=false and a synthetic
 *     error {code: 'HTTP_ERROR' | 'INVALID_RESPONSE', message}.
 *   - X-CSRFToken is read on every call (the token rotates on login), plus
 *     Accept and X-Requested-With. Caller headers are merged on top.
 *   - opts.flash (default true) shows the envelope's flash messages through
 *     the canonical toast (js/flash.js listens to the 'flash' window event).
 *   - 401 with code SESSION_EXPIRED / UNAUTHORIZED sends the user to the login
 *     page (opts.onUnauthorized === false opts out).
 */
(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});

  function csrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') || '' : '';
  }

  function loginUrl() {
    return (typeof global.loginPageUrl !== 'undefined' && global.loginPageUrl)
      ? global.loginPageUrl
      : '/login';
  }

  function emitFlash(items) {
    if (!Array.isArray(items)) return;
    items.forEach((f) => {
      if (f && f.message) {
        global.dispatchEvent(new CustomEvent('flash', { detail: f }));
      }
    });
  }

  function redirectToLogin() {
    const target = loginUrl();
    if (global.location.pathname === new URL(target, global.location.origin).pathname) return;
    global.location.replace(target);
  }

  async function request(method, url, opts) {
    const o = opts || {};
    const verb = String(method || 'GET').toUpperCase();
    const headers = {
      'Accept': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': csrfToken(),
    };

    let body;
    if (o.body !== undefined && o.body !== null) {
      body = o.body; // FormData / string: the browser sets the Content-Type
    } else if (o.json !== undefined && o.json !== null) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(o.json);
    }
    Object.assign(headers, o.headers || {});

    const res = await fetch(url, {
      method: verb,
      credentials: 'same-origin',
      headers,
      body: verb === 'GET' || verb === 'HEAD' ? undefined : body,
      signal: o.signal,
    });

    let payload = null;
    let parsed = true;
    try {
      payload = await res.json();
    } catch (_) {
      parsed = false;
    }
    const env = payload && typeof payload === 'object' ? payload : {};

    let error = env.error || null;
    if (!error && !res.ok) {
      error = {
        code: parsed ? 'HTTP_ERROR' : 'INVALID_RESPONSE',
        message: res.statusText || ('Error HTTP ' + res.status),
      };
    }
    const result = {
      ok: res.ok && !error,
      status: res.status,
      body: payload,
      contentType: res.headers.get('content-type') || '',
      data: 'data' in env ? env.data : null,
      meta: env.meta || {},
      error,
      flash: Array.isArray(env.flash) ? env.flash : [],
    };

    if (o.flash !== false) emitFlash(result.flash);

    if (res.status === 401 && o.onUnauthorized !== false && error &&
        (error.code === 'SESSION_EXPIRED' || error.code === 'UNAUTHORIZED')) {
      redirectToLogin();
    }
    return result;
  }

  const api = {
    request,
    csrfToken,
    get: (url, opts) => request('GET', url, opts),
    post: (url, json, opts) => request('POST', url, Object.assign({ json }, opts)),
    put: (url, json, opts) => request('PUT', url, Object.assign({ json }, opts)),
    patch: (url, json, opts) => request('PATCH', url, Object.assign({ json }, opts)),
    delete: (url, opts) => request('DELETE', url, opts),
  };

  SIIAP.api = api;
})(window);

// app/static/js/api/http.js
// ES-module adapter over SIIAP.api (js/utils/http.js, must be loaded first).
// Resolves with the envelope's data; throws the envelope's error object.
export function getCsrf() {
  return window.SIIAP.api.csrfToken();
}

export async function api(path, { method = 'GET', headers = {}, body } = {}) {
  const opts = { headers, onUnauthorized: false };
  if (typeof body === 'string') {
    opts.body = body;
    opts.headers = { 'Content-Type': 'application/json', ...headers };
  } else if (body !== undefined && body !== null) {
    opts.json = body;
  }
  const res = await window.SIIAP.api.request(method, `/api/v1${path}`, opts);
  if (!res.ok) throw res.error || { code: 'HTTP_ERROR', message: 'Error de red' };
  return res.data;
}

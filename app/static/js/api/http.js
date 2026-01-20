// app/static/js/api/http.js
export function getCsrf() {
  const el = document.querySelector('meta[name="csrf-token"]');
  return el ? el.getAttribute('content') : '';
}

export async function api(path, { method = 'GET', headers = {}, body } = {}) {
  const opts = {
    method,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
      ...headers
    }
  };
  if (body && typeof body !== 'string') opts.body = JSON.stringify(body);
  else if (body) opts.body = body;

  const res = await fetch(`/api/v1${path}`, opts);
  const json = await res.json().catch(() => ({}));
  if (json.flash) {
    json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
  }
  if (!res.ok) throw json.error || { code: 'HTTP_ERROR', message: res.statusText };
  return json.data;
}

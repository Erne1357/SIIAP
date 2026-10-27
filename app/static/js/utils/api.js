// app/static/js/utils/api.js

/**
 * Compatibility wrapper (window.apiClient) over SIIAP.api (utils/http.js).
 * Resolves a Response-like object: { ok, status, json() } so existing callers
 * keep reading `res.ok` / `await res.json()`. New code should call SIIAP.api.
 * Flash messages and the login redirect stay with the caller, as before.
 */

class ApiClient {
    constructor() {
        this.baseUrl = `${window.location.protocol}//${window.location.host}`;
    }

    /** Builds an absolute URL from a relative path (e.g. '/api/v1/notifications'). */
    url(path) {
        const cleanPath = path.startsWith('/') ? path.slice(1) : path;
        return `${this.baseUrl}/${cleanPath}`;
    }

    /** Current CSRF token. */
    getCsrf() {
        return window.SIIAP.api.csrfToken();
    }

    /** Default headers (kept for old callers). */
    getDefaultHeaders() {
        return {
            'X-CSRFToken': this.getCsrf(),
            'X-Requested-With': 'XMLHttpRequest'
        };
    }

    async _send(method, path, data, options = {}) {
        const opts = { flash: false, onUnauthorized: false, headers: options.headers, signal: options.signal };
        if (data instanceof FormData) opts.body = data;
        else if (data !== null && data !== undefined) opts.json = data;
        const r = await window.SIIAP.api.request(method, this.url(path), opts);
        return {
            ok: r.ok,
            status: r.status,
            json: async () => (r.body === null ? {} : r.body)
        };
    }

    get(path, options = {}) { return this._send('GET', path, null, options); }
    post(path, data = null, options = {}) { return this._send('POST', path, data, options); }
    patch(path, data = null, options = {}) { return this._send('PATCH', path, data, options); }
    delete(path, options = {}) { return this._send('DELETE', path, null, options); }
}

// Global instance
window.apiClient = new ApiClient();

// Legacy helpers
window.getApiUrl = (path) => window.apiClient.url(path);
window.getCsrfToken = () => window.apiClient.getCsrf();

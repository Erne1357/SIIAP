/* Shared helpers for admin/events module. Exposed under window.EventsCommon. */
(() => {
    const API = "/api/v1";

    function flash(message, level = "success") {
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level: level, message: message }
        }));
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    /**
     * Pulls a readable Spanish message out of ANY body this API may answer.
     *
     * The standard envelope carries `error` as an object `{code, message}`,
     * while a few legacy endpoints still answer with a bare string. Reading
     * `data.error` straight into `new Error()` stringifies the object, so a
     * coordinator who touched an event outside their scope would get the toast
     * «Error: [object Object]» instead of the reason.
     *
     * Shapes handled, in order of preference:
     *   {error: {code, message}}       -> message   (standard envelope)
     *   {error: "texto"}               -> texto     (legacy endpoints)
     *   {message: "texto"}             -> texto
     *   {flash: [{level, message}]}    -> message   (flash array)
     *   {flash: [["texto", "level"]]}  -> texto     (tuple form used by Flask)
     *
     * @param {*} data Parsed response body (or anything).
     * @param {string} fallback Message to use when the body says nothing useful.
     * @returns {string} Always a non-empty string.
     */
    function errorMessage(data, fallback = 'Ocurrió un error inesperado') {
        const text = (value) => (typeof value === 'string' && value.trim()) ? value.trim() : null;

        if (text(data)) return text(data);
        if (!data || typeof data !== 'object') return fallback;

        const err = data.error;
        if (text(err)) return text(err);
        if (err && typeof err === 'object' && text(err.message)) return text(err.message);

        if (text(data.message)) return text(data.message);

        const flash = Array.isArray(data.flash) ? data.flash : [];
        for (const entry of flash) {
            if (text(entry)) return text(entry);
            if (Array.isArray(entry) && text(entry[0])) return text(entry[0]);
            if (entry && typeof entry === 'object' && text(entry.message)) return text(entry.message);
        }

        return fallback;
    }

    /**
     * Fetches `url` and returns `{response, body}` with the parsed JSON body.
     * Throws on HTML answers (permission redirects) and unparseable bodies;
     * judging the status / `error` is left to the caller.
     */
    async function fetchJson(url, options = {}) {
        const defaultOptions = {
            credentials: "same-origin",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                ...options.headers
            }
        };
        const finalOptions = { ...defaultOptions, ...options };
        const response = await fetch(url, finalOptions);
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
            throw new Error('No tienes permisos para realizar esta acción');
        }
        let body;
        try {
            body = await response.json();
        } catch (jsonError) {
            throw new Error('Error al procesar la respuesta del servidor');
        }
        return { response, body };
    }

    /**
     * Raw request: resolves with `{response, data}` where `data` is the whole
     * parsed body. Use it for endpoints whose callers read the body as-is
     * (e.g. `data.data.students`); use `apiData` for the standard envelope.
     */
    async function apiRequest(url, options = {}) {
        try {
            const { response, body: data } = await fetchJson(url, options);
            if (!response.ok) {
                throw new Error(errorMessage(data, `Error HTTP ${response.status}`));
            }
            if (data.ok === false || (data.error && typeof data.error === 'object')) {
                throw new Error(errorMessage(data, 'Operación fallida'));
            }
            return { response, data };
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    /**
     * Envelope-aware request for the standard `{data, error, meta, flash}`
     * body. Resolves with `{response, data, meta, flash}` where `data` is the
     * envelope's `data` (never null: `{}` when the server sent none), so
     * callers read `data.<key>` directly. Throws `Error(error.message)` on any
     * failure.
     *
     * The one 4xx that resolves: a 409 whose `data.requires_force` is true
     * (deleting an event / window / slot that still has booked appointments).
     * The caller shows `data.message` in a confirmation and repeats the call
     * with `?force=true`.
     */
    async function apiData(url, options = {}) {
        try {
            const { response, body } = await fetchJson(url, options);
            const payload = (body && typeof body === 'object' && 'data' in body) ? body.data : null;
            if (!response.ok) {
                if (payload && payload.requires_force) {
                    return { response, data: payload, meta: body.meta || {}, flash: body.flash || [] };
                }
                throw new Error(errorMessage(body, `Error HTTP ${response.status}`));
            }
            if (body && body.error) {
                throw new Error(errorMessage(body, 'Operación fallida'));
            }
            return { response, data: payload || {}, meta: body.meta || {}, flash: body.flash || [] };
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    const TYPE_LABEL = {
        interview: 'Entrevista',
        defense: 'Defensa',
        workshop: 'Taller',
        seminar: 'Seminario',
        conference: 'Conferencia',
        info_session: 'Sesión Informativa',
        other: 'Otro'
    };

    const TYPE_ICON = {
        interview: 'bi-person-lines-fill',
        defense: 'bi-mortarboard',
        workshop: 'bi-tools',
        seminar: 'bi-easel2',
        conference: 'bi-megaphone',
        info_session: 'bi-info-circle',
        other: 'bi-calendar-event'
    };

    const TYPE_BADGE_CLASS = {
        interview: 'bg-primary',
        defense: 'bg-danger',
        workshop: 'bg-success',
        seminar: 'bg-info text-dark',
        conference: 'bg-warning text-dark',
        info_session: 'bg-secondary',
        other: 'bg-secondary'
    };

    const STATUS_LABEL = {
        draft: 'Borrador',
        published: 'Publicado',
        ongoing: 'En curso',
        completed: 'Concluido',
        cancelled: 'Cancelado',
        archived: 'Archivado'
    };

    const STATUS_BADGE_CLASS = {
        draft: 'bg-secondary',
        published: 'bg-success',
        ongoing: 'bg-info text-dark',
        completed: 'bg-dark',
        cancelled: 'bg-danger',
        archived: 'bg-warning text-dark'
    };

    const CAPACITY_LABEL = {
        single: 'Individual (1:1)',
        multiple: 'Cupo limitado',
        unlimited: 'Sin límite'
    };

    function formatDateTime(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleString('es-MX', {
                day: '2-digit', month: 'short', year: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (e) { return iso; }
    }

    function formatDate(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString('es-MX', {
                day: '2-digit', month: 'short', year: 'numeric'
            });
        } catch (e) { return iso; }
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    window.EventsCommon = {
        API,
        flash,
        getCsrfToken,
        apiRequest,
        apiData,
        errorMessage,
        TYPE_LABEL,
        TYPE_ICON,
        TYPE_BADGE_CLASS,
        STATUS_LABEL,
        STATUS_BADGE_CLASS,
        CAPACITY_LABEL,
        formatDateTime,
        formatDate,
        escapeHtml
    };
})();

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

    async function apiRequest(url, options = {}) {
        const defaultOptions = {
            credentials: "same-origin",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                ...options.headers
            }
        };
        const finalOptions = { ...defaultOptions, ...options };
        try {
            const response = await fetch(url, finalOptions);
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('text/html')) {
                throw new Error('No tienes permisos para realizar esta acción');
            }
            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                throw new Error('Error al procesar la respuesta del servidor');
            }
            if (!response.ok) {
                throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
            }
            if (data.ok === false) {
                throw new Error(data.error || 'Operación fallida');
            }
            return { response, data };
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

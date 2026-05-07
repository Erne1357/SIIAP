// app/static/js/events/promo-toast.js
/**
 * Notificación de eventos nuevos (promoción).
 *
 * Al cargar cualquier página (excepto /events*), consulta si hay eventos
 * nuevos desde la última visita del usuario. Si los hay, muestra un flash
 * informativo una sola vez por sesión de navegador.
 *
 * Depende de:
 *   - flash.js (escucha CustomEvent 'flash' — cargado antes en base.html)
 *   - GET /api/v1/events/new-count  → { data: { count: N }, error: null, meta: {} }
 *
 * El flag 'eventsPromoShown' en sessionStorage evita mostrar el toast más de
 * una vez por sesión. list.js lo elimina cuando el usuario visita /events,
 * de modo que la próxima sesión comienza limpia.
 */
(() => {
    'use strict';

    const SESSION_KEY = 'eventsPromoShown';
    const ENDPOINT    = '/api/v1/events/new-count';

    /**
     * Devuelve true si la URL actual corresponde a la sección de eventos.
     * @returns {boolean}
     */
    function isOnEventsPage() {
        return /^\/events(\/|$)/.test(window.location.pathname);
    }

    /**
     * Consulta el conteo de eventos nuevos y, si hay alguno, despacha un
     * CustomEvent 'flash' para que flash.js lo muestre.
     */
    async function checkAndPromote() {
        if (isOnEventsPage()) return;
        if (sessionStorage.getItem(SESSION_KEY) === '1') return;

        try {
            const res = await fetch(ENDPOINT, { credentials: 'same-origin' });
            if (!res.ok) return;
            const body = await res.json();
            const count = Number(body?.data?.count || 0);
            if (count <= 0) return;

            const message = count === 1
                ? 'Hay 1 evento nuevo disponible. Revísalo en la sección Eventos.'
                : `Hay ${count} eventos nuevos disponibles. Revísalos en la sección Eventos.`;

            window.dispatchEvent(new CustomEvent('flash', {
                detail: { level: 'info', message }
            }));
            sessionStorage.setItem(SESSION_KEY, '1');
        } catch (err) {
            console.warn('[promo-toast] fallo:', err);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkAndPromote);
    } else {
        checkAndPromote();
    }
})();

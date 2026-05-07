// app/static/js/events/invitations-badge.js
/**
 * Gestiona el badge de invitaciones pendientes en el sidebar (desktop y móvil).
 *
 * - Carga inicial: GET /api/v1/invitations/my-invitations → muestra total en badge.
 * - Tiempo real: escucha CustomEvent 'siiap:invitations:count_changed' (re-emitido
 *   por socket-client.js desde el evento socket 'invitations:count_changed').
 *
 * Usa [data-role="invitations-badge"] en lugar de ID porque el macro sidebar_nav
 * se renderiza dos veces (prefix='' desktop, prefix='m-' móvil).
 */
(() => {
    'use strict';

    const ENDPOINT = '/api/v1/invitations/my-invitations';

    /**
     * Actualiza el texto y visibilidad de TODOS los badges en la página.
     * @param {number} count
     */
    function setBadge(count) {
        const badges = document.querySelectorAll('[data-role="invitations-badge"]');
        badges.forEach(b => {
            if (count > 0) {
                b.textContent = count > 9 ? '9+' : String(count);
                b.classList.remove('d-none');
            } else {
                b.textContent = '';
                b.classList.add('d-none');
            }
        });
    }

    /**
     * Llama al endpoint de invitaciones y actualiza el badge con el total.
     */
    async function loadInitialCount() {
        try {
            const res = await fetch(ENDPOINT, { credentials: 'same-origin' });
            if (!res.ok) return;
            const data = await res.json();
            const count = Number(data.total || 0);
            setBadge(count);
        } catch (err) {
            console.warn('[invitations-badge] fallo carga inicial:', err);
        }
    }

    // Actualización en tiempo real vía socket
    window.addEventListener('siiap:invitations:count_changed', (event) => {
        const count = Number(event.detail?.count ?? 0);
        setBadge(count);
    });

    // Iniciar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadInitialCount);
    } else {
        loadInitialCount();
    }
})();

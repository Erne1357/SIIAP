/**
 * socket-client.js
 * Gestor global de la conexión Socket.IO para SIIAP.
 *
 * Se carga en base.html DESPUÉS de socket.io.min.js y ANTES de notifications.js.
 * Expone `window.siiapSocket` para que los módulos de página escuchen eventos.
 *
 * Eventos que emite al window (custom events):
 *   siiap:notification:new     → { notification: {...} }
 *   siiap:deliberation:updated → { user_id, user_name, program_id, status }
 *   siiap:email:queue_update   → { pending, failed }
 */

(function () {
    'use strict';

    // Solo conectar si el usuario está autenticado (el badge de notificaciones existe)
    const isBellPresent = !!document.getElementById('notificationBell');
    if (!isBellPresent) return;

    // ─── Conectar ────────────────────────────────────────────────────────────
    const socket = io({
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 2000,
        reconnectionDelayMax: 30000,
    });

    window.siiapSocket = socket;

    // ─── Gestión de conexión ─────────────────────────────────────────────────
    socket.on('connect', () => {
        console.debug('[WS] Conectado al servidor Socket.IO');
    });

    socket.on('disconnect', (reason) => {
        console.debug('[WS] Desconectado:', reason);
    });

    socket.on('connect_error', (err) => {
        console.warn('[WS] Error de conexión:', err.message);
    });

    // ─── Eventos del servidor → re-emit como CustomEvents del window ─────────

    /**
     * notification:new
     * Emitido por el servidor cada vez que se crea una notificación para el usuario.
     * Payload: { notification: { id, type, title, message, action_url, ... } }
     */
    socket.on('notification:new', (data) => {
        window.dispatchEvent(new CustomEvent('siiap:notification:new', { detail: data }));
    });

    /**
     * deliberation:updated
     * Emitido cuando un coordinador acepta/rechaza a un aspirante.
     * Payload: { user_id, user_name, program_id, status }
     */
    socket.on('deliberation:updated', (data) => {
        window.dispatchEvent(new CustomEvent('siiap:deliberation:updated', { detail: data }));
    });

    /**
     * email:queue_update
     * Emitido cuando cambia el estado de la cola de correos.
     * Payload: { pending, failed }
     */
    socket.on('email:queue_update', (data) => {
        window.dispatchEvent(new CustomEvent('siiap:email:queue_update', { detail: data }));
    });

})();

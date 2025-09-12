// Session timeout con API (sesión Flask + CSRF), advertencia 1 min antes del corte
(() => {
    'use strict';

    // Solo corre si hay sesión
    if (typeof userLoggedIn === 'undefined' || userLoggedIn !== 'true') {
        console.log('[session] sin usuario, no se inicia temporizador.');
        return;
    }

    // Utilidades
    const getCsrf = () => {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    };
    const csrf = getCsrf();
    const toLogin = () => {
        // usa variable inyectada; si no existe, cae a /login
        const url = (typeof loginPageUrl !== 'undefined' && loginPageUrl) ? loginPageUrl : '/login';
        window.location.href = url;
    };

    // Importante: tu backend expira a los 15 min de inactividad (before_request).
    // Mostramos el modal a los 14 min para dar 1 min al usuario.
    const WARNING_MS = 14 * 60 * 1000; // 14 min
    const AUTO_LOGOUT_MS = 1 * 60 * 1000; // +1 min -> 15 min total
    let warningTimer = null;
    let autoLogoutTimer = null;

    const modal = document.getElementById('sessionModal');
    const continueBtn = document.getElementById('continueBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    function clearTimers() {
        if (warningTimer) { clearTimeout(warningTimer); warningTimer = null; }
        if (autoLogoutTimer) { clearTimeout(autoLogoutTimer); autoLogoutTimer = null; }
    }

    function showSessionModal() {
        if (!modal) return;
        modal.style.display = 'flex';
        // Programar auto-logout si no responde
        autoLogoutTimer = setTimeout(doApiLogout, AUTO_LOGOUT_MS);
    }

    function hideSessionModal() {
        if (!modal) return;
        modal.style.display = 'none';
        if (autoLogoutTimer) { clearTimeout(autoLogoutTimer); autoLogoutTimer = null; }
    }

    async function doApiLogout() {
        try {
            await fetch(sessionLogoutUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRF-Token': csrf }
            });
            const json = await res.json().catch(() => ({}));
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }
        } catch (e) {
            console.warn('[session] fallo logout API, redirigiendo igual.');
        } finally {
            toLogin();
        }
    }

    async function doKeepalive() {
        try {
            const res = await fetch(sessionKeepaliveUrl, {
                method: 'GET', // keepalive es GET en la API
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrf // no es requerido para GET, pero no estorba
                }
            });
            const json = await res.json().catch(() => ({}));
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }
            if (!res.ok) throw new Error('keepalive no OK');
            // No recargues; basta con reiniciar timers
            resetInactivityTimers(true);
            return true;
        } catch (err) {
            console.error('[session] error keepalive:', err);
            // Si el servidor ya expiró, redirige a login
            toLogin();
            return false;
        }
    }

    function scheduleWarning() {
        // Programa la aparición del modal
        warningTimer = setTimeout(showSessionModal, WARNING_MS);
    }

    // Reset al detectar actividad del usuario
    let activityArm = true;
    function onActivity() {
        // Throttle sencillo para no resetear en exceso (cada 2s máx.)
        if (!activityArm) return;
        activityArm = false;
        setTimeout(() => (activityArm = true), 2000);
        // Si el modal está visible, lo escondemos (el usuario volvió)
        if (modal && modal.style.display === 'flex') {
            hideSessionModal();
        }
        resetInactivityTimers(false);
    }

    function resetInactivityTimers(fromKeepalive) {
        clearTimers();
        // Si esto viene del botón "Continuar", ya hicimos keepalive; si no, solo reprograma
        if (!fromKeepalive) {
            // No hagas keepalive cada tecla, solo reprograma la advertencia
        }
        scheduleWarning();
    }

    // Wire de botones del modal
    if (continueBtn) {
        continueBtn.addEventListener('click', async () => {
            hideSessionModal();
            await doKeepalive(); // si falla, doKeepalive redirige a login
        });
    }
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            hideSessionModal();
            doApiLogout();
        });
    }

    // Listeners de actividad del usuario
    const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'];
    ACTIVITY_EVENTS.forEach(evt => window.addEventListener(evt, onActivity, { passive: true }));

    // Reinicia temporizadores al recuperar foco de la pestaña (opcional)
    window.addEventListener('focus', onActivity);

    // Inicio
    console.log('[session] usuario autenticado, temporizador iniciado.');
    scheduleWarning();
})();

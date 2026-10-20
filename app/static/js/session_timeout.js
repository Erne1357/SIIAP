// Session timeout con API (sesion Flask + CSRF), advertencia 1 min antes del corte.
//
// La fuente de verdad de la inactividad es el SERVIDOR (session['last_activity']);
// este script solo decide cuando preguntar. Reglas:
//   - La actividad se comparte entre pestanas (localStorage 'siiap:last-activity'
//     + evento 'storage'): una pestana olvidada en segundo plano nunca cierra la
//     sesion mientras el usuario trabaja en otra.
//   - Antes de mostrar el aviso y antes del cierre automatico se consulta
//     /api/v1/auth/session-status (solo lectura, no extiende la sesion).
//   - Un cierre de sesion se difunde ('siiap:logout') para que las demas pestanas
//     vayan al login en vez de seguir con una sesion muerta.
(() => {
  'use strict';

  if (typeof userLoggedIn === 'undefined' || userLoggedIn !== 'true') {
    return;
  }

  const ACTIVITY_KEY = 'siiap:last-activity';
  const LOGOUT_KEY = 'siiap:logout';
  const STATUS_URL = '/api/v1/auth/session-status';
  const AUTO_LOGOUT_MS = 1 * 60 * 1000; // +1 min after the warning
  const WARNING_LEAD_S = 60; // the modal appears when this many seconds remain
  const RECHECK_MS = 30 * 1000; // retry after a network failure
  const DEFAULT_WARNING_MS = 14 * 60 * 1000; // 14 min

  let warningMs = DEFAULT_WARNING_MS;
  let warningTimer = null;
  let autoLogoutTimer = null;
  let leaving = false; // a logout / redirect is already under way

  const getLoginUrl = () => {
    return (typeof loginPageUrl !== 'undefined' && loginPageUrl) ? loginPageUrl : '/login';
  };
  const toLogin = () => {
    window.location.href = getLoginUrl();
  };

  function lsSet(key, value) {
    try { localStorage.setItem(key, String(value)); } catch (_) { /* storage unavailable */ }
  }
  function lsRemove(key) {
    try { localStorage.removeItem(key); } catch (_) { /* storage unavailable */ }
  }

  const modalEl = document.getElementById('sessionModal');
  const continueBtn = document.getElementById('continueBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  let bsModal = null;

  function getBsModal() {
    if (!modalEl) return null;
    if (!bsModal && window.bootstrap && window.bootstrap.Modal) {
      bsModal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    }
    return bsModal;
  }

  function isModalShown() {
    return modalEl && modalEl.classList.contains('show');
  }

  function clearTimers() {
    if (warningTimer) { clearTimeout(warningTimer); warningTimer = null; }
    if (autoLogoutTimer) { clearTimeout(autoLogoutTimer); autoLogoutTimer = null; }
  }

  /**
   * Ask the server how much idle time is left.
   * Resolves { state: 'ok', remaining } | { state: 'expired' } | { state: 'error' }.
   * Also adopts the server's idle limit for the warning delay.
   */
  async function fetchStatus() {
    try {
      const res = await window.SIIAP.api.get(STATUS_URL, { flash: false, onUnauthorized: false });
      if (res.status === 401) return { state: 'expired' };
      if (!res.ok || !res.data || typeof res.data.remaining_seconds !== 'number') {
        return { state: 'error' };
      }
      const limit = Number(res.data.idle_limit_seconds);
      if (limit > WARNING_LEAD_S) warningMs = (limit - WARNING_LEAD_S) * 1000;
      return { state: 'ok', remaining: res.data.remaining_seconds };
    } catch (_) {
      return { state: 'error' };
    }
  }

  function cleanClientState() {
    try { sessionStorage.clear(); } catch (_) {}
    // htmx snapshots rendered pages under this key; never leave them behind.
    lsRemove('htmx-history-cache');
  }

  /** The session is already dead on the server: no POST, just leave. */
  function leaveToLogin() {
    if (leaving) return;
    leaving = true;
    clearTimers();
    cleanClientState();
    lsSet(LOGOUT_KEY, Date.now());
    window.location.replace(getLoginUrl());
  }

  function showSessionModal() {
    const m = getBsModal();
    if (!m) return;
    m.show();
    // El dialogo aparece sin que el usuario lo pida: se anuncia por la region
    // viva unica para que un lector de pantalla no lo pase por alto.
    if (window.SIIAP && typeof window.SIIAP.announce === 'function') {
      window.SIIAP.announce('Tu sesión expirará en 1 minuto por inactividad.');
    }
    if (autoLogoutTimer) clearTimeout(autoLogoutTimer);
    autoLogoutTimer = setTimeout(onAutoLogout, AUTO_LOGOUT_MS);
  }

  function hideSessionModal() {
    const m = getBsModal();
    if (!m) return;
    m.hide();
    if (autoLogoutTimer) { clearTimeout(autoLogoutTimer); autoLogoutTimer = null; }
  }

  /** Warning timer fired: warn only if the server also considers the user idle. */
  async function onWarningDue() {
    warningTimer = null;
    const st = await fetchStatus();
    if (leaving) return;
    if (st.state === 'expired') { leaveToLogin(); return; }
    if (st.state === 'ok' && st.remaining > WARNING_LEAD_S) {
      // Another tab (or request) kept the session alive: warn later.
      scheduleWarning((st.remaining - WARNING_LEAD_S) * 1000);
      return;
    }
    showSessionModal();
  }

  /** Auto-logout timer fired: log out only if the server agrees the user is idle. */
  async function onAutoLogout() {
    autoLogoutTimer = null;
    const st = await fetchStatus();
    if (leaving) return;
    if (st.state === 'expired') { leaveToLogin(); return; }
    if (st.state === 'ok' && st.remaining > 0) {
      // Still alive on the server (activity elsewhere): close the dialog, warn again later.
      hideSessionModal();
      scheduleWarning(Math.max(st.remaining - WARNING_LEAD_S, 0) * 1000);
      return;
    }
    if (st.state === 'error') {
      // Cannot confirm (offline): never kick the user out blindly, retry shortly.
      autoLogoutTimer = setTimeout(onAutoLogout, RECHECK_MS);
      return;
    }
    doApiLogout();
  }

  async function doApiLogout() {
    if (leaving) return;
    leaving = true;
    clearTimers();
    try {
      await window.SIIAP.api.post(sessionLogoutUrl, null, { flash: false, onUnauthorized: false });
      // NO mostrar flash aqui - dejamos que el backend maneje los mensajes
    } catch (e) {
      console.warn('[session] fallo logout API, redirigiendo igual.', e);
    } finally {
      // IMPORTANTE: limpiar cualquier storage y forzar recarga completa
      cleanClientState();
      lsSet(LOGOUT_KEY, Date.now()); // tell the other tabs
      // replace() fuerza recarga completa sin cache
      window.location.replace(getLoginUrl());
    }
  }

  async function doKeepalive() {
    try {
      const res = await window.SIIAP.api.get(sessionKeepaliveUrl, { onUnauthorized: false });
      if (!res.ok) throw new Error('keepalive no OK');
      markActivity();
      resetInactivityTimers();
      return true;
    } catch (err) {
      console.error('[session] error keepalive:', err);
      toLogin();
      return false;
    }
  }

  function scheduleWarning(delayMs) {
    if (warningTimer) clearTimeout(warningTimer);
    warningTimer = setTimeout(onWarningDue, delayMs === undefined ? warningMs : delayMs);
  }

  function resetInactivityTimers() {
    clearTimers();
    scheduleWarning();
  }

  /** Publish "the user is active" so every other tab resets its timers. */
  function markActivity() {
    lsSet(ACTIVITY_KEY, Date.now());
  }

  let activityArm = true;
  // Mouse and keyboard activity never reaches the server on its own: a user
  // reading one page for 15 minutes would be idle for the server. While the
  // user is really active, touch the server at most every 5 minutes (shared
  // across tabs, so only one tab pings).
  const SERVER_TOUCH_KEY = 'siiap:last-server-touch';
  const SERVER_TOUCH_EVERY_MS = 5 * 60 * 1000;
  let touching = false;

  function maybeTouchServer() {
    if (touching || leaving || !sessionKeepaliveUrl) return;
    const now = Date.now();
    let last = 0;
    try { last = parseInt(localStorage.getItem(SERVER_TOUCH_KEY) || '0', 10) || 0; } catch (_) {}
    if (now - last < SERVER_TOUCH_EVERY_MS) return;
    try { localStorage.setItem(SERVER_TOUCH_KEY, String(now)); } catch (_) {}
    touching = true;
    window.SIIAP.api.get(sessionKeepaliveUrl, { flash: false, onUnauthorized: false })
      .catch(() => {})
      .finally(() => { touching = false; });
  }

  function onActivity() {
    if (!activityArm || leaving) return;
    activityArm = false;
    setTimeout(() => (activityArm = true), 2000);
    if (isModalShown()) hideSessionModal();
    markActivity();
    resetInactivityTimers();
    maybeTouchServer();
  }

  // Other tabs: activity resets this tab's timers; a logout sends it to the login.
  window.addEventListener('storage', (e) => {
    if (leaving) return;
    if (e.key === LOGOUT_KEY && e.newValue) {
      leaving = true;
      clearTimers();
      cleanClientState();
      window.location.replace(getLoginUrl());
    } else if (e.key === ACTIVITY_KEY && e.newValue) {
      if (isModalShown()) hideSessionModal();
      resetInactivityTimers();
    }
  });

  if (continueBtn) {
    continueBtn.addEventListener('click', async () => {
      hideSessionModal();
      await doKeepalive();
    });
  }
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      hideSessionModal();
      doApiLogout();
    });
  }

  const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'];
  ACTIVITY_EVENTS.forEach(evt => window.addEventListener(evt, onActivity, { passive: true }));
  window.addEventListener('focus', onActivity);

  // A stale logout marker from a previous session must not eject a fresh login.
  lsRemove(LOGOUT_KEY);
  scheduleWarning();
})();

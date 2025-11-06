// Session timeout con API (sesión Flask + CSRF), advertencia 1 min antes del corte
(() => {
  'use strict';

  if (typeof userLoggedIn === 'undefined' || userLoggedIn !== 'true') {
    
    return;
  }

  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();
  const toLogin = () => {
    const url = (typeof loginPageUrl !== 'undefined' && loginPageUrl) ? loginPageUrl : '/login';
    window.location.href = url;
  };

  const WARNING_MS = 14 * 60 * 1000; // 14 min
  const AUTO_LOGOUT_MS = 1 * 60 * 1000; // +1 min
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
    autoLogoutTimer = setTimeout(doApiLogout, AUTO_LOGOUT_MS);
  }

  function hideSessionModal() {
    if (!modal) return;
    modal.style.display = 'none';
    if (autoLogoutTimer) { clearTimeout(autoLogoutTimer); autoLogoutTimer = null; }
  }

  async function doApiLogout() {
    try {
      const res = await fetch(sessionLogoutUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': csrf }
      });
      let json = null;
      try { json = await res.json(); } catch (_) {}
      if (json && json.flash) {
        json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
      }
    } catch (e) {
      console.warn('[session] fallo logout API, redirigiendo igual.', e);
    } finally {
      toLogin();
    }
  }

  async function doKeepalive() {
    try {
      const res = await fetch(sessionKeepaliveUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRF-Token': csrf
        }
      });
      const json = await res.json().catch(() => ({}));
      if (json && json.flash) {
        json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
      }
      if (!res.ok) throw new Error('keepalive no OK');
      resetInactivityTimers(true);
      return true;
    } catch (err) {
      console.error('[session] error keepalive:', err);
      toLogin();
      return false;
    }
  }

  function scheduleWarning() {
    warningTimer = setTimeout(showSessionModal, WARNING_MS);
  }

  let activityArm = true;
  function onActivity() {
    if (!activityArm) return;
    activityArm = false;
    setTimeout(() => (activityArm = true), 2000);
    if (modal && modal.style.display === 'flex') hideSessionModal();
    resetInactivityTimers(false);
  }

  function resetInactivityTimers(fromKeepalive) {
    clearTimers();
    scheduleWarning();
  }

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

  
  scheduleWarning();
})();

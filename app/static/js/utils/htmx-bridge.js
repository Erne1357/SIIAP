/* app/static/js/utils/htmx-bridge.js
 * The one place where htmx meets the rest of the SIIAP frontend.
 *
 * Loaded by base.html AFTER htmx + the morph extension and AFTER SIIAP.api,
 * flash.js, dialogs.js, data-table.js and reveal.js; BEFORE page scripts.
 * Rules and conventions: .claude/rules/htmx-fragments.md
 *
 * What it does:
 *   - Config: no history cache, no eval (hx-on, js: in hx-vals and trigger
 *     filters are disabled), no <script> in swapped HTML, no injected <style>.
 *   - CSRF: htmx:configRequest copies the LIVE token (SIIAP.api.csrfToken())
 *     into X-CSRFToken; a static hx-headers would go stale when the token
 *     rotates on login / password change.
 *   - hx-confirm: htmx:confirm opens siiapConfirm (the accessible dialog)
 *     instead of window.confirm. Optional attributes on the element:
 *     data-confirm-title, data-confirm-type, data-confirm-label.
 *   - Messages: the server sends HX-Trigger {"siiap:flash": {level, message}};
 *     it is shown with SIIAP.flash. htmx 2 does not swap 4xx/5xx, so
 *     htmx:responseError / sendError / timeout show a Spanish fallback unless
 *     the response already carried its own flash.
 *   - htmx:load: idempotent re-init of tooltips, data tables and reveal on the
 *     swapped subtree.
 *   - Socket.IO stays: socket-client.js re-emits domain events on window as
 *     `siiap:<event>`; screens listen with hx-trigger="siiap:<event> from:window".
 *     No ws/sse extension.
 */
(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});
  const htmx = global.htmx;
  if (!htmx || SIIAP.htmxBridge) return;
  SIIAP.htmxBridge = true;

  // ── Config ──────────────────────────────────────────────────────────────
  // 0 also makes htmx drop the 'htmx-history-cache' localStorage key: DOM
  // snapshots of student records must not sit in a shared computer's browser.
  htmx.config.historyCacheSize = 0;
  htmx.config.defaultSwapStyle = 'innerHTML';   // explicit; morph is opt-in per element
  htmx.config.allowEval = false;                // blocks hx-on:*, js: in hx-vals, trigger filters
  htmx.config.allowScriptTags = false;          // a fragment never carries executable <script>
  htmx.config.selfRequestsOnly = true;          // same origin only (htmx default, pinned)
  htmx.config.includeIndicatorStyles = false;   // css/components/_htmx.css owns .htmx-indicator

  const FLASH_EVENT = 'siiap:flash';
  const FALLBACK_BY_STATUS = {
    400: 'La solicitud no es válida.',
    403: 'No tienes permiso para realizar esta acción.',
    404: 'El recurso solicitado ya no existe.',
    409: 'La acción entra en conflicto con el estado actual.',
    413: 'El archivo excede el tamaño máximo permitido.',
  };

  function flash(level, message) {
    if (message && typeof SIIAP.flash === 'function') SIIAP.flash(level || 'info', message);
  }

  // ── CSRF ────────────────────────────────────────────────────────────────
  document.addEventListener('htmx:configRequest', (evt) => {
    const token = SIIAP.api && SIIAP.api.csrfToken ? SIIAP.api.csrfToken() : '';
    if (token) evt.detail.headers['X-CSRFToken'] = token;
  });

  // ── hx-confirm → siiapConfirm ───────────────────────────────────────────
  document.addEventListener('htmx:confirm', (evt) => {
    const question = evt.detail.question;
    if (!question) return;                       // nothing to confirm: let htmx proceed
    if (typeof global.siiapConfirm !== 'function') return;  // fall back to window.confirm
    evt.preventDefault();
    const el = evt.detail.elt || {};
    const data = el.dataset || {};
    global.siiapConfirm({
      message: question,
      title: data.confirmTitle || '¿Estás seguro?',
      type: data.confirmType || 'warning',
      confirmLabel: data.confirmLabel || 'Aceptar',
    }).then((ok) => {
      if (ok) evt.detail.issueRequest(true);     // true = skip htmx's own confirm()
    });
  });

  // ── Messages from the server (HX-Trigger) ───────────────────────────────
  // htmx dispatches the event on the triggering element and it bubbles.
  document.addEventListener(FLASH_EVENT, (evt) => {
    const d = evt.detail || {};
    if (Array.isArray(d.flash)) {
      d.flash.forEach((f) => f && flash(f.level, f.message));
    } else {
      flash(d.level, d.message);
    }
  });

  function carriesFlash(xhr) {
    try {
      const header = xhr && xhr.getResponseHeader && xhr.getResponseHeader('HX-Trigger');
      return !!header && header.indexOf(FLASH_EVENT) !== -1;
    } catch (_) {
      return false;
    }
  }

  // ── Failures htmx does not swap ─────────────────────────────────────────
  document.addEventListener('htmx:responseError', (evt) => {
    const xhr = evt.detail.xhr;
    if (carriesFlash(xhr)) return;               // the server already said why
    const status = xhr ? xhr.status : 0;
    flash('danger', FALLBACK_BY_STATUS[status] ||
      (status >= 500
        ? 'Ocurrió un error interno. Intenta de nuevo más tarde.'
        : 'No se pudo completar la acción.'));
  });

  document.addEventListener('htmx:sendError', () => {
    flash('danger', 'No se pudo conectar con el servidor. Revisa tu conexión.');
  });

  document.addEventListener('htmx:timeout', () => {
    flash('warning', 'La solicitud tardó demasiado. Intenta de nuevo.');
  });

  // ── Re-init on every swap (htmx:load fires for the initial page too) ────
  function within(root, selector) {
    const out = Array.from(root.querySelectorAll(selector));
    if (root.matches && root.matches(selector)) out.unshift(root);
    return out;
  }

  function initTooltips(root) {
    if (!global.bootstrap || !global.bootstrap.Tooltip) return;
    within(root, '[data-bs-toggle="tooltip"]').forEach((el) => {
      global.bootstrap.Tooltip.getOrCreateInstance(el);
    });
  }

  function initDataTables(root) {
    if (typeof SIIAP.initDataTable !== 'function') return;
    within(root, '.siiap-table-wrapper').forEach(SIIAP.initDataTable);  // guarded by a WeakSet
  }

  document.addEventListener('htmx:load', (evt) => {
    const root = evt.detail && evt.detail.elt;
    if (!root || !root.querySelectorAll) return;
    initTooltips(root);
    initDataTables(root);
    if (typeof SIIAP.initReveal === 'function') SIIAP.initReveal(root);
  });

  // A removed element must not leave its tooltip popper floating around.
  document.addEventListener('htmx:beforeCleanupElement', (evt) => {
    const el = evt.target;
    if (!global.bootstrap || !global.bootstrap.Tooltip || !el || !el.matches) return;
    if (el.matches('[data-bs-toggle="tooltip"]')) {
      const tip = global.bootstrap.Tooltip.getInstance(el);
      if (tip) tip.dispose();
    }
  });
})(window);

/* app/static/js/teaching/acta.js
 * Acta of a group (Mis grupos → grupo). The fragment lives in #actaRoot and
 * every mutation swaps it, the correction modals included.
 *
 * A modal left inside the page content sits under its own stacking context,
 * so the backdrop could cover it (the 6B1 "Carga académica" bug). On show,
 * the modal moves to <body>; its hx-* attributes keep targeting #actaRoot by
 * id. Before a real swap of the root, every moved modal is disposed and
 * removed, so no backdrop, body lock or duplicate id survives. Idempotent.
 */
(function () {
  'use strict';

  if (window.SIIAP && window.SIIAP.actaInit) return;
  window.SIIAP = window.SIIAP || {};
  window.SIIAP.actaInit = true;

  const PORTAL_ATTR = 'data-acta-portal';

  document.addEventListener('show.bs.modal', function (evt) {
    const modal = evt.target;
    if (!modal || !modal.closest || !modal.closest('#actaRoot')) return;
    modal.setAttribute(PORTAL_ATTR, '');
    document.body.appendChild(modal);
  });

  document.addEventListener('htmx:beforeSwap', function (evt) {
    const target = evt.detail && evt.detail.target;
    if (!target || target.id !== 'actaRoot' || !evt.detail.shouldSwap) return;

    document.querySelectorAll('[' + PORTAL_ATTR + ']').forEach(function (modal) {
      const instance = window.bootstrap && window.bootstrap.Modal.getInstance(modal);
      if (instance) instance.dispose();
      modal.remove();
    });
    document.querySelectorAll('.modal-backdrop').forEach(function (el) { el.remove(); });
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  });
})();

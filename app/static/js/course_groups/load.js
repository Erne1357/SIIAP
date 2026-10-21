/* app/static/js/course_groups/load.js
 * "Carga académica" tab (Permanencia). The fragment lives in #courseLoadRoot and
 * every mutation swaps the whole root, modals included.
 *
 * A modal left inside the tab pane sits under its own stacking context, so the
 * backdrop covered it and swallowed every click. On show, the modal moves to
 * <body> (Bootstrap's own advice); its hx-* attributes keep targeting
 * #courseLoadRoot by id. Before the root is swapped, every moved modal is
 * disposed and removed, so no backdrop, body lock or duplicate id survives.
 * Idempotent: loaded once, listens on document.
 */
(function () {
  'use strict';

  if (window.SIIAP && window.SIIAP.courseLoadInit) return;
  window.SIIAP = window.SIIAP || {};
  window.SIIAP.courseLoadInit = true;

  const PORTAL_ATTR = 'data-course-load-portal';

  document.addEventListener('show.bs.modal', function (evt) {
    const modal = evt.target;
    if (!modal || !modal.closest || !modal.closest('#courseLoadRoot')) return;
    modal.setAttribute(PORTAL_ATTR, '');
    document.body.appendChild(modal);
  });

  document.addEventListener('htmx:beforeSwap', function (evt) {
    const target = evt.detail && evt.detail.target;
    if (!target || target.id !== 'courseLoadRoot' || !evt.detail.shouldSwap) return;

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

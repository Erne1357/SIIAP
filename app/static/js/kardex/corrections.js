/* app/static/js/kardex/corrections.js
 * "Solicitar corrección" modal of the student record's Kardex tab.
 * One shared modal lives inside #recordKardex, which is swapped by htmx. A modal
 * left there is covered by its own backdrop, so on show it moves to <body>;
 * before #recordKardex is swapped every moved modal is disposed and removed.
 * Idempotent: loaded once, listens on document.
 */
(function () {
  'use strict';

  if (window.SIIAP && window.SIIAP.kardexCorrectionsInit) return;
  window.SIIAP = window.SIIAP || {};
  window.SIIAP.kardexCorrectionsInit = true;

  const MODAL_ID = 'kardexCorrectionModal';
  const PORTAL_ATTR = 'data-kardex-portal';

  function fill(trigger) {
    const set = function (id, text) {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    const enrollment = document.getElementById('kardexCorrectionEnrollment');
    if (enrollment) enrollment.value = trigger.getAttribute('data-enrollment-id') || '';
    set('kardexCorrectionSubject', trigger.getAttribute('data-subject') || '');
    set('kardexCorrectionCurrent', trigger.getAttribute('data-current') || '');
    const value = document.getElementById('kardexCorrectionValue');
    const reason = document.getElementById('kardexCorrectionReason');
    if (value) value.value = '';
    if (reason) reason.value = '';
  }

  document.addEventListener('show.bs.modal', function (evt) {
    const modal = evt.target;
    if (!modal || modal.id !== MODAL_ID) return;
    if (modal.closest('#recordKardex')) {
      // A copy left in <body> by an earlier fragment would shadow this one.
      document.querySelectorAll('body > [' + PORTAL_ATTR + ']').forEach(function (stale) {
        if (stale !== modal) stale.remove();
      });
      modal.setAttribute(PORTAL_ATTR, '');
      document.body.appendChild(modal);
    }
    if (evt.relatedTarget) fill(evt.relatedTarget);
  });

  document.addEventListener('htmx:beforeSwap', function (evt) {
    const target = evt.detail && evt.detail.target;
    if (!target || !evt.detail.shouldSwap) return;
    if (target.id !== 'recordKardex' && !target.querySelector('#recordKardex')) return;

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

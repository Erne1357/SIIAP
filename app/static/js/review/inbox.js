/* app/static/js/review/inbox.js
 * "Por revisar" inbox. The decision modal is fetched into #reviewModalHost; a modal
 * left inside the page sits under its own stacking context, so on load it moves to
 * <body>, opens, and is removed when it closes. After a successful decision the server
 * sends `siiap:review-count` (HX-Trigger) and the sidebar badge is updated here.
 * Idempotent `init(root)`, run on htmx:load; guarded by a WeakSet.
 */
(function () {
  'use strict';

  if (window.SIIAP && window.SIIAP.reviewInboxInit) return;
  window.SIIAP = window.SIIAP || {};
  window.SIIAP.reviewInboxInit = true;

  var seen = new WeakSet();

  function removeModal(modal) {
    var instance = window.bootstrap && window.bootstrap.Modal.getInstance(modal);
    if (instance) instance.dispose();
    modal.remove();
    document.querySelectorAll('.modal-backdrop').forEach(function (el) { el.remove(); });
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  }

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.id === 'reviewDecideModal' ? scope : scope.querySelector('#reviewDecideModal');
    if (!modal || seen.has(modal)) return;
    seen.add(modal);
    document.body.appendChild(modal);
    modal.addEventListener('hidden.bs.modal', function () { removeModal(modal); });
    window.bootstrap.Modal.getOrCreateInstance(modal).show();
  }

  function setBadge(count) {
    document.querySelectorAll('[data-role="review-badge"]').forEach(function (badge) {
      badge.textContent = String(count);
      badge.classList.toggle('d-none', !count);
    });
  }

  document.addEventListener('htmx:load', function (evt) { init(evt.detail && evt.detail.elt); });

  // A successful decision swaps #reviewBody: close the modal that sent it.
  document.addEventListener('htmx:afterRequest', function (evt) {
    var elt = evt.detail && evt.detail.elt;
    if (!elt || !evt.detail.successful || !elt.closest) return;
    var modal = elt.closest('#reviewDecideModal');
    if (!modal || elt.tagName !== 'FORM') return;
    var instance = window.bootstrap.Modal.getInstance(modal);
    if (instance) instance.hide();
  });

  window.addEventListener('siiap:review-count', function (evt) {
    var detail = evt.detail || {};
    if (typeof detail.count === 'number') setBadge(detail.count);
  });
  document.body.addEventListener('siiap:review-count', function (evt) {
    var detail = evt.detail || {};
    if (typeof detail.count === 'number') setBadge(detail.count);
  });
})();

/*
 * SIIAP — Helper para feedback visual en botones asincronos.
 *
 * Patron de uso:
 *   <button class="btn btn-primary" id="confirmBtn">
 *     <span class="btn-label">Confirmar</span>
 *   </button>
 *
 *   btn.addEventListener('click', async () => {
 *     SIIAP.setButtonLoading(btn, true);
 *     try { await api(...); }
 *     finally { SIIAP.setButtonLoading(btn, false); }
 *   });
 *
 * Si el boton no tiene .btn-label, el helper usa innerHTML completo y lo
 * restaura al terminar (compatibilidad con codigo existente).
 */

(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});

  SIIAP.setButtonLoading = function (btn, loading, loadingText) {
    if (!btn) return;
    btn.disabled = !!loading;

    const label = btn.querySelector('.btn-label');
    let spinner = btn.querySelector('.btn-spinner');

    if (label) {
      // Patron nuevo: separamos label y spinner
      if (!spinner) {
        spinner = document.createElement('span');
        spinner.className = 'btn-spinner spinner-border spinner-border-sm ms-2 d-none';
        spinner.setAttribute('role', 'status');
        spinner.setAttribute('aria-hidden', 'true');
        btn.appendChild(spinner);
      }
      label.classList.toggle('d-none', !!loading);
      spinner.classList.toggle('d-none', !loading);
      if (loading && loadingText) {
        if (!btn.dataset.originalLabel) btn.dataset.originalLabel = label.textContent;
        label.textContent = loadingText;
        label.classList.remove('d-none');
      } else if (!loading && btn.dataset.originalLabel) {
        label.textContent = btn.dataset.originalLabel;
        delete btn.dataset.originalLabel;
      }
      return;
    }

    // Patron retro-compatible: reemplazar innerHTML completo
    if (loading) {
      if (!btn.dataset.originalHtml) {
        btn.dataset.originalHtml = btn.innerHTML;
      }
      const text = loadingText || 'Procesando...';
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' + text;
    } else if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
      delete btn.dataset.originalHtml;
    }
  };

})(window);

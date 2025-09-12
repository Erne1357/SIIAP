// app/static/js/flash.js
(function () {
  'use strict';

  function ensureContainer() {
    let ctn = document.getElementById('flash-container');
    if (!ctn) {
      ctn = document.createElement('div');
      ctn.id = 'flash-container';
      document.body.appendChild(ctn);
    }
    return ctn;
  }

  function wireAutoRemove(toastEl) {
    toastEl.addEventListener('animationend', (e) => {
      if (e.animationName === 'slideOutRight') toastEl.remove();
    });
  }

  function spawnToast(level, message) {
    const ctn = ensureContainer();
    const div = document.createElement('div');
    div.className = `flash-toast alert alert-${level || 'info'} shadow-sm`;
    div.setAttribute('role', 'alert');
    div.textContent = message || '';
    ctn.appendChild(div);
    wireAutoRemove(div);
  }

  function popPersistedFlashes() {
    const raw = sessionStorage.getItem('flashQueue');
    if (!raw) return;
    sessionStorage.removeItem('flashQueue');
    try {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        arr.forEach(f => spawnToast(f.level || 'info', f.message || ''));
      }
    } catch (e) { /* noop */ }
  }

  // Flashes SSR ya presentes (Jinja) + pop persistidos
  document.addEventListener('DOMContentLoaded', () => {
    const ctn = ensureContainer();
    ctn.querySelectorAll('.flash-toast').forEach(wireAutoRemove);
    popPersistedFlashes();
  });

  // Si usas Swup y hay navegación sin recarga, vuelve a mostrar persistidos
  window.addEventListener('swup:contentReplaced', () => {
    ensureContainer();
    popPersistedFlashes();
  });

  // FlashBridge para JSON de API
  window.addEventListener('flash', (e) => {
    const { level, message } = e.detail || {};
    spawnToast(level, message);
  });
})();

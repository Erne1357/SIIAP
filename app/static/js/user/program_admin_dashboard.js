/* app/static/js/user/program_admin_dashboard.js
 * Dashboard del administrador de programa: selector de programa que recarga
 * la página con el query param correspondiente + listeners de tiempo real para
 * refrescar KPIs cuando cambian datos del programa.
 */
(function () {
  'use strict';

  function onProgramChange(e) {
    const url = new URL(window.location);
    url.searchParams.set('program_id', e.target.value);
    window.location.href = url.toString();
  }

  function toast(level, message) {
    window.SIIAP.flash(level, message);
  }

  // Estrategia: toast + refresco in situ del cuerpo del dashboard (htmx sobre
  // #dashboard-content; hx-sync deduplica ráfagas y el morph conserva scroll y
  // foco). Eventos a escuchar son los que llegan a role:coordinator (nuevas
  // submissions, aceptación, deliberación).
  function scheduleReload(msg) {
    toast('info', msg);
    const el = document.getElementById('dashboard-content');
    if (el && window.htmx) window.htmx.trigger(el, 'siiap:dashboard:refresh');
  }

  function init() {
    const sel = document.getElementById('programSelector');
    if (sel) sel.addEventListener('change', onProgramChange);

    window.addEventListener('siiap:submission:new', (e) => {
      const d = e.detail || {};
      scheduleReload(`Nuevo documento (${d.archive_name || 'doc'}). Actualizando KPIs...`);
    });
    window.addEventListener('siiap:acceptance:updated',   () => scheduleReload('Cambio en aceptación. Actualizando...'));
    window.addEventListener('siiap:deliberation:updated', () => scheduleReload('Cambio en deliberación. Actualizando...'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

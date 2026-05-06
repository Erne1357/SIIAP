/* app/static/js/user/postgraduate_admin_dashboard.js
 * Dashboard del administrador de posgrado: recordatorios (estado de correo +
 * documentos pendientes) al abrir la pestaña.
 *
 * Depende de window.SIIAP_POSTGRAD_DASH = { emailConfigUrl, pendingReviews }.
 */
(function () {
  'use strict';

  const CFG = window.SIIAP_POSTGRAD_DASH || {};
  const EMAIL_CONFIG_URL = CFG.emailConfigUrl || '#';
  const PENDING_REVIEWS = Number(CFG.pendingReviews || 0);

  const ALERT_CLASSES = {
    success: 'alert-success',
    warning: 'alert-warning',
    info: 'alert-info',
    danger: 'alert-danger',
  };

  function renderReminders(list, reminders) {
    if (!reminders.length) {
      list.innerHTML = `
        <div class="text-center py-4">
          <i class="bi bi-check-circle text-success icon-3xl"></i>
          <h5 class="mt-3 text-success">¡Todo en orden!</h5>
          <p class="text-muted mb-0">No hay recordatorios pendientes</p>
        </div>`;
      return;
    }

    const html = reminders.map(r => {
      const cls = ALERT_CLASSES[r.type] || 'alert-secondary';
      const btnType = r.type === 'warning' ? 'warning' : r.type;
      const action = r.action
        ? `<a href="${r.action.url}" class="btn btn-sm btn-${btnType} mt-2">
             ${r.action.text} <i class="bi bi-arrow-right ms-1"></i>
           </a>`
        : '';
      return `
        <div class="alert ${cls} d-flex align-items-start mb-3">
          <div class="flex-shrink-0 me-3">
            <i class="bi ${r.icon} icon-2xl"></i>
          </div>
          <div class="flex-grow-1">
            <h6 class="alert-heading mb-1">${r.title}</h6>
            <p class="mb-0">${r.message}</p>
            ${action}
          </div>
        </div>`;
    }).join('');

    list.innerHTML = html;
  }

  async function checkEmailConfiguration() {
    const list = document.getElementById('reminders-list');
    const loading = document.getElementById('loading-reminders');
    if (!list) return;

    try {
      const response = await fetch('/api/v1/emails/status');
      const data = await response.json();
      const reminders = [];

      if (!data.data?.connected || !data.data?.account) {
        reminders.push({
          type: 'warning',
          icon: 'bi-envelope-x',
          title: 'Correo no configurado',
          message: 'No hay una cuenta de correo configurada. Los correos no se enviarán hasta que configures Microsoft Graph.',
          action: { text: 'Configurar ahora', url: EMAIL_CONFIG_URL },
        });
      } else {
        reminders.push({
          type: 'success',
          icon: 'bi-envelope-check',
          title: 'Correo configurado exitosamente',
          message: `Cuenta activa: ${data.data.account.username || 'No disponible'}`,
          action: null,
        });
      }

      if (PENDING_REVIEWS > 0) {
        reminders.push({
          type: 'info',
          icon: 'bi-hourglass-split',
          title: 'Documentos pendientes de revisión',
          message: `Hay ${PENDING_REVIEWS} documentos esperando revisión en todos los programas.`,
          action: null,
        });
      }

      renderReminders(list, reminders);
    } catch (error) {
      console.error('Error al verificar configuración:', error);
      list.innerHTML = `
        <div class="alert alert-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>
          Error al cargar recordatorios. Por favor, recarga la página.
        </div>`;
    } finally {
      if (loading) loading.classList.add('d-none');
      if (list) list.classList.remove('d-none');
    }
  }

  function init() {
    const tab = document.getElementById('reminders-tab');
    if (tab) tab.addEventListener('click', checkEmailConfiguration);

    // ==================== TIEMPO REAL ====================
    // Reload tras toast (delay 3s) cuando suceden eventos que afectan los KPIs.
    // Eventos que llegan a este rol:
    //   - submission:new (role:coordinator — postgrad también tiene coordinator.page.view)
    //   - acceptance:updated, deliberation:updated (idem)
    //   - email:queue_update (role:postgraduate_admin) → refresca recordatorios
    let reloadScheduled = false;
    const scheduleReload = (msg) => {
      if (reloadScheduled) return;
      reloadScheduled = true;
      if (typeof showFlash === 'function') showFlash('info', msg);
      setTimeout(() => { window.location.reload(); }, 3000);
    };

    window.addEventListener('siiap:submission:new',       () => scheduleReload('Nuevo documento pendiente de revisión. Actualizando...'));
    window.addEventListener('siiap:acceptance:updated',   () => scheduleReload('Cambio en aceptación. Actualizando...'));
    window.addEventListener('siiap:deliberation:updated', () => scheduleReload('Cambio en deliberación. Actualizando...'));

    // email:queue_update: no reload, sólo refresca recordatorios si la tab está visible
    window.addEventListener('siiap:email:queue_update', () => {
      const list = document.getElementById('reminders-list');
      if (list && !list.classList.contains('d-none')) {
        checkEmailConfiguration();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

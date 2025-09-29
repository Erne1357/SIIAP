// app/static/js/flash.js

/**
 * Muestra un mensaje flash dinámico
 * @param {string} level - Nivel del mensaje (success, danger, warning, info)
 * @param {string} message - Mensaje a mostrar
 */
function showFlash(level, message) {
  const container = document.getElementById('flash-container');
  if (!container) return;

  const alertTypes = {
    'success': 'success',
    'error': 'danger',
    'danger': 'danger',
    'warning': 'warning',
    'info': 'info'
  };

  const iconTypes = {
    'success': 'fa-check-circle',
    'danger': 'fa-exclamation-circle',
    'warning': 'fa-exclamation-triangle',
    'info': 'fa-info-circle'
  };

  const alertType = alertTypes[level] || 'info';
  const iconClass = iconTypes[alertType] || 'fa-info-circle';

  const alertEl = document.createElement('div');
  alertEl.className = `alert alert-${alertType} alert-dismissible fade show`;
  alertEl.setAttribute('role', 'alert');
  alertEl.innerHTML = `
    <strong><i class="fas ${iconClass} me-1"></i></strong>
    ${escapeHtml(message)}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>
  `;

  container.appendChild(alertEl);

  // Auto-remover después de 5 segundos
  setTimeout(() => {
    alertEl.classList.add('fade-out');
    setTimeout(() => {
      if (alertEl.parentElement) {
        alertEl.remove();
      }
    }, 500);
  }, 5000);
}

/**
 * Escapa HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} - Texto escapado
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Escucha eventos de flash personalizados
 */
window.addEventListener('flash', (event) => {
  const { level, message } = event.detail;
  if (message) {
    showFlash(level, message);
  }
});

/**
 * Auto-cerrar alertas después de 5 segundos
 */
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.classList.add('fade-out');
      setTimeout(() => {
        if (alert.parentElement) {
          alert.remove();
        }
      }, 500);
    }, 5000);
  });
});

/**
 * Limpiar mensajes flash al cambiar de página con Swup
 */
if (typeof swup !== 'undefined') {
  swup.on('willReplaceContent', () => {
    const container = document.getElementById('flash-container');
    if (container) {
      container.innerHTML = '';
    }
  });
}
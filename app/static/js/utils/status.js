/*
 * SIIAP — Helper compartido para renderizar StatusBadge desde JS.
 * Mantener sincronizado con _STATUS_META en app/templates/_macros.html.
 */

(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});

  const STATUS_META = {
    in_progress:         { icon: 'arrow-repeat',         label: 'En proceso' },
    interview_completed: { icon: 'mic-fill',             label: 'Entrevista completada' },
    deliberation:        { icon: 'hourglass-split',      label: 'En deliberación' },
    accepted:            { icon: 'check-circle-fill',    label: 'Aceptado' },
    approved:            { icon: 'check-circle-fill',    label: 'Aprobado' },
    rejected:            { icon: 'x-circle-fill',        label: 'Rechazado' },
    deferred:            { icon: 'arrow-right-circle',   label: 'Diferido' },
    enrolled:            { icon: 'mortarboard-fill',     label: 'Inscrito' },
    pending:             { icon: 'clock',                label: 'Pendiente' },
  };

  SIIAP.STATUS_META = STATUS_META;

  /**
   * Genera el HTML de un status-badge.
   * @param {string} status - Codigo del estado (e.g. 'accepted')
   * @param {string} [label] - Etiqueta personalizada (opcional)
   * @param {string} [size] - 'sm' | 'lg' | '' (opcional)
   * @returns {string} HTML del badge
   */
  SIIAP.statusBadge = function (status, label, size) {
    const meta = STATUS_META[status] || { icon: 'circle', label: status };
    const cls = 'status-badge--' + String(status).replace(/_/g, '-');
    const sizeCls = size ? ('status-badge--' + size) : '';
    const text = label || meta.label;
    return (
      '<span class="status-badge ' + cls + ' ' + sizeCls + '">' +
        '<i class="bi bi-' + meta.icon + '" aria-hidden="true"></i>' +
        '<span>' + text + '</span>' +
      '</span>'
    );
  };

})(window);

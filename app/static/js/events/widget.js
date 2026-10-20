// app/static/js/events/widget.js
// Maneja botones aceptar/rechazar del widget de eventos en dashboards.
(() => {
  'use strict';

  // The shell #eventsWidgetRegion is always rendered, but a dashboard refresh may
  // replace it: delegate from the document and resolve it at the point of use.
  if (!document.getElementById('eventsWidgetRegion')) return;

  function flash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }

  async function respond(invitationId, accept) {
    try {
      const res = await window.SIIAP.api.post(`/api/v1/invitations/${invitationId}/respond`, { accept }, { flash: false });
      const body = res.body || {};
      if (!res.ok || body.error) {
        flash('danger', body.error?.message || 'No se pudo registrar tu respuesta.');
        return;
      }
      flash('success', accept ? 'Invitación aceptada.' : 'Invitación rechazada.');
      // Only the widget changes: re-render it from the server (invitation moves
      // to "Estás inscrito" or disappears) instead of reloading the dashboard.
      const url = document.getElementById('eventsWidgetRegion')?.dataset.refreshUrl;
      if (url && window.htmx) {
        await window.htmx.ajax('GET', url, { target: '#eventsWidgetRegion', swap: 'innerHTML' });
        if (window.SIIAP?.announce) window.SIIAP.announce('Eventos actualizados.');
      }
    } catch (err) {
      console.error('[events-widget] respond error', err);
      flash('danger', 'Error de red al responder la invitación.');
    }
  }

  document.addEventListener('click', (event) => {
    const btn = event.target.closest('#eventsWidgetRegion .events-widget-respond');
    if (!btn) return;
    event.preventDefault();
    const invitationId = btn.dataset.invitationId;
    const accept = btn.dataset.accept === 'true';
    if (!invitationId) return;
    btn.disabled = true;
    respond(invitationId, accept).finally(() => { btn.disabled = false; });
  });
})();

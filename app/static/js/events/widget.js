// app/static/js/events/widget.js
// Maneja botones aceptar/rechazar del widget de eventos en dashboards.
(() => {
  'use strict';

  const widget = document.getElementById('eventsWidget');
  if (!widget) return;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function flash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }

  async function respond(invitationId, accept) {
    try {
      const res = await fetch(`/api/v1/invitations/${invitationId}/respond`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ accept }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || body.ok === false) {
        flash('danger', body.error || 'No se pudo registrar tu respuesta.');
        return;
      }
      flash('success', accept ? 'Invitación aceptada.' : 'Invitación rechazada.');
      setTimeout(() => window.location.reload(), 600);
    } catch (err) {
      console.error('[events-widget] respond error', err);
      flash('danger', 'Error de red al responder la invitación.');
    }
  }

  widget.addEventListener('click', (event) => {
    const btn = event.target.closest('.events-widget-respond');
    if (!btn) return;
    event.preventDefault();
    const invitationId = btn.dataset.invitationId;
    const accept = btn.dataset.accept === 'true';
    if (!invitationId) return;
    btn.disabled = true;
    respond(invitationId, accept).finally(() => { btn.disabled = false; });
  });
})();

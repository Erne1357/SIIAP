// static/js/admin/admin_review.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-review-form="true"]');
  if (!form) return;

  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();

  function emitFlash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }
  function persistFlashes(flashes) {
    try { sessionStorage.setItem('flashQueue', JSON.stringify(flashes || [])); } catch (_) {}
  }

  let pendingAction = null;

  // Captura qué botón se pulsó (approve/reject)
  form.querySelectorAll('button[type="submit"][data-action]').forEach(btn => {
    btn.addEventListener('click', () => { pendingAction = btn.getAttribute('data-action'); });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const subId = form.getAttribute('data-sub-id');
    const nextUrl = form.getAttribute('data-next-url') || window.location.href;
    const comment = form.comment?.value?.trim() || '';

    if (!pendingAction) return;

    if (pendingAction === 'reject') {
      const ok = confirm('¿Estás seguro de rechazar este documento?');
      if (!ok) return;
    }

    try {
      const res = await fetch(`/api/v1/admin/review/submissions/${subId}/decision`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify({ action: pendingAction, comment })
      });
      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg = json?.error?.message || 'No se pudo aplicar la acción.';
        if (Array.isArray(json.flash) && json.flash.length) {
          json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
        } else {
          emitFlash('danger', msg);
        }
        return;
      }

      const flashes = Array.isArray(json.flash) && json.flash.length
        ? json.flash
        : [{ level: 'success', message: 'Acción realizada correctamente.' }];

      persistFlashes(flashes);
      window.location.href = nextUrl;

    } catch (err) {
      console.error('review decision error:', err);
      emitFlash('danger', 'Error de red. Intenta de nuevo.');
    }
  });
});

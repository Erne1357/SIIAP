// app/static/js/user/profile.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form[data-profile-update="true"]');
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
    try {
      sessionStorage.setItem('flashQueue', JSON.stringify(flashes || []));
    } catch (_) {}
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
      first_name: form.first_name.value.trim(),
      last_name: form.last_name.value.trim(),
      mother_last_name: form.mother_last_name.value.trim()
    };

    try {
      const res = await fetch('/api/v1/users/me', {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify(payload)
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg = json?.error?.message || 'No se pudo actualizar el perfil.';
        if (Array.isArray(json.flash) && json.flash.length) {
          json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
        } else {
          emitFlash('danger', msg);
        }
        return;
      }

      // Cierra modal
      const modalEl = document.getElementById('editProfileModal');
      if (modalEl) {
        let inst = bootstrap.Modal.getInstance(modalEl);
        if (!inst) inst = new bootstrap.Modal(modalEl);
        inst.hide();
      }

      const flashes = Array.isArray(json.flash) && json.flash.length
        ? json.flash
        : [{ level: 'success', message: 'Perfil actualizado correctamente.' }];

      // Persistimos y recargamos para refrescar nombres/badges en toda la vista
      persistFlashes(flashes);
      window.location.reload();

    } catch (err) {
      console.error('profile update error:', err);
      emitFlash('danger', 'Error de red al actualizar el perfil.');
    }
  });
});

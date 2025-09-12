// static/js/program/admission.js
document.addEventListener('DOMContentLoaded', () => {
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
      const arr = Array.isArray(flashes) ? flashes : [];
      sessionStorage.setItem('flashQueue', JSON.stringify(arr));
    } catch (_) {}
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    let inst = bootstrap.Modal.getInstance(modalEl);
    if (!inst) inst = new bootstrap.Modal(modalEl);
    inst.hide();
  }

  const uploadModal = document.getElementById('uploadModal');
  let currentStepForHash = null;

  if (uploadModal) {
    uploadModal.addEventListener('show.bs.modal', event => {
      const btn = event.relatedTarget;
      const archId = btn?.getAttribute('data-archive');
      const stepId = btn?.getAttribute('data-step');
      const inputArchive = uploadModal.querySelector('[name="archive_id"]');
      if (inputArchive) inputArchive.value = archId || '';
      currentStepForHash = stepId || null;
    });

    uploadModal.addEventListener('hidden.bs.modal', () => {
      const fileInput = uploadModal.querySelector('input[type="file"]');
      if (fileInput) fileInput.value = '';
    });
  }

  const hash = window.location.hash;
  if (hash.startsWith('#pane-')) {
    const btn = document.querySelector(`button[data-bs-target="${hash}"]`);
    if (btn) new bootstrap.Tab(btn).show();
  }

  // SUBIR
  document.querySelectorAll('form[data-admission-upload="true"]').forEach(form => {
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const archiveId = fd.get('archive_id');
      const file = fd.get('file');

      if (!archiveId || !file || (file instanceof File && !file.name)) {
        emitFlash('danger', 'Selecciona un archivo válido.');
        return;
      }

      try {
        const res = await fetch('/api/v1/submissions', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': csrf },
          body: fd
        });
        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          // errores: muestra inmediatamente (no persistimos)
          const msg = json?.error?.message || 'No se pudo subir el documento.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        closeModal(uploadModal);

        // éxito: persistimos y recargamos
        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Documento enviado correctamente.' }];

        if (currentStepForHash) window.location.hash = `#pane-${currentStepForHash}`;
        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('Upload error:', err);
        emitFlash('danger', 'Error de red al subir.');
      }
    });
  });

  // ELIMINAR
  document.querySelectorAll('[data-delete-submission]').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      ev.preventDefault();
      const subId = btn.getAttribute('data-delete-submission');
      const stepId = btn.getAttribute('data-step');
      if (!subId) return;
      if (!confirm('¿Eliminar este archivo?')) return;

      try {
        const res = await fetch(`/api/v1/submissions/${subId}`, {
          method: 'DELETE',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': csrf }
        });
        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          const msg = json?.error?.message || 'No se pudo eliminar.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Archivo eliminado.' }];

        if (stepId) window.location.hash = `#pane-${stepId}`;
        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('Delete error:', err);
        emitFlash('danger', 'Error de red al eliminar.');
      }
    });
  });
});

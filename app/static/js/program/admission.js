// static/js/program/admission.js - FASE 1
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

  // ==================== MODAL DE SUBIDA MEJORADO ====================
  if (uploadModal) {
    uploadModal.addEventListener('show.bs.modal', event => {
      const btn = event.relatedTarget;
      const archId = btn?.getAttribute('data-archive');
      const stepId = btn?.getAttribute('data-step');
      const archiveName = btn?.getAttribute('data-archive-name');
      const hasExisting = btn?.getAttribute('data-has-existing') === 'true';
      const existingFilename = btn?.getAttribute('data-existing-filename');
      const existingDate = btn?.getAttribute('data-existing-date');

      // Llenar inputs hidden
      const inputArchive = uploadModal.querySelector('[name="archive_id"]');
      if (inputArchive) inputArchive.value = archId || '';
      currentStepForHash = stepId || null;

      // Mostrar/ocultar información de archivo existente
      const existingInfo = document.getElementById('existingFileInfo');
      const uploadBtnText = document.getElementById('uploadBtnText');
      const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');

      if (hasExisting && existingFilename) {
        document.getElementById('existingArchiveName').textContent = archiveName || '';
        document.getElementById('existingFilename').textContent = existingFilename || '';
        document.getElementById('existingDate').textContent = existingDate || '';
        existingInfo.classList.remove('d-none');
        uploadBtnText.textContent = 'Reemplazar';
        uploadSubmitBtn.className = 'btn btn-warning';
      } else {
        existingInfo.classList.add('d-none');
        uploadBtnText.textContent = 'Subir';
        uploadSubmitBtn.className = 'btn btn-primary';
      }
    });

    uploadModal.addEventListener('hidden.bs.modal', () => {
      const fileInput = uploadModal.querySelector('input[type="file"]');
      if (fileInput) fileInput.value = '';
      // Limpiar info
      document.getElementById('existingFileInfo').classList.add('d-none');
    });
  }

  // Restaurar pestaña activa desde hash
  const hash = window.location.hash;
  if (hash.startsWith('#pane-')) {
    const btn = document.querySelector(`button[data-bs-target="${hash}"]`);
    if (btn) new bootstrap.Tab(btn).show();
  }

  // ==================== SUBIR ARCHIVOS CON VALIDACIONES ====================
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

      // VALIDACIÓN: Tamaño máximo 3MB
      if (file.size > 3 * 1024 * 1024) {
        emitFlash('danger', 'El archivo no puede superar los 3MB.');
        return;
      }

      // VALIDACIÓN: Solo PDF
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        emitFlash('danger', 'Solo se permiten archivos PDF.');
        return;
      }

      // Mostrar loading en el botón
      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
      submitBtn.disabled = true;

      try {
        const res = await fetch('/api/v1/submissions', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': csrf },
          body: fd
        });
        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          const msg = json?.error?.message || 'No se pudo subir el documento.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        closeModal(uploadModal);

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Documento subido correctamente.' }];

        if (currentStepForHash) window.location.hash = `#pane-${currentStepForHash}`;
        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('Upload error:', err);
        emitFlash('danger', 'Error de red al subir.');
      } finally {
        // Restaurar botón
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
      }
    });
  });

  // ==================== ELIMINAR ARCHIVOS ====================
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

  // ==================== MOSTRAR TAMAÑO DE ARCHIVO SELECCIONADO ====================
  document.querySelectorAll('input[type="file"]').forEach(input => {
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      let feedbackEl = e.target.parentNode.querySelector('.file-feedback');
      
      if (!feedbackEl) {
        feedbackEl = document.createElement('div');
        feedbackEl.className = 'file-feedback small mt-1';
        e.target.parentNode.appendChild(feedbackEl);
      }

      if (file.size > 3 * 1024 * 1024) {
        feedbackEl.className = 'file-feedback small mt-1 text-danger';
        feedbackEl.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Archivo: ${file.name} (${sizeMB} MB) - EXCEDE EL LÍMITE`;
      } else if (!file.name.toLowerCase().endsWith('.pdf')) {
        feedbackEl.className = 'file-feedback small mt-1 text-danger';
        feedbackEl.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Solo se permiten archivos PDF`;
      } else {
        feedbackEl.className = 'file-feedback small mt-1 text-success';
        feedbackEl.innerHTML = `<i class="fas fa-check"></i> Archivo: ${file.name} (${sizeMB} MB)`;
      }
    });
  });
});
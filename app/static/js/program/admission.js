// static/js/program/admission.js - Versión mejorada con prórroga y citas
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
  const extensionModal = document.getElementById('extensionModal');
  let currentStepForHash = null;

  // ==================== INICIALIZAR TOOLTIPS ====================
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

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
      document.getElementById('existingFileInfo').classList.add('d-none');
    });
  }

  // ==================== MODAL DE PRÓRROGA ====================
  if (extensionModal) {
    // Configurar fecha mínima (mañana)
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowString = tomorrow.toISOString().split('T')[0];
    document.getElementById('extensionRequestedUntil').min = tomorrowString;
  }

  // ==================== SOLICITAR PRÓRROGA ====================
  document.addEventListener('click', (e) => {
    if (e.target.closest('.btn-request-extension')) {
      const button = e.target.closest('.btn-request-extension');
      const archiveId = button.getAttribute('data-archive-id');
      const archiveName = button.getAttribute('data-archive-name');
      
      if (archiveId && archiveName) {
        document.getElementById('extensionArchiveId').value = archiveId;
        document.getElementById('extensionArchiveName').textContent = archiveName;
        
        // Limpiar formulario
        document.getElementById('extensionRequestedUntil').value = '';
        document.getElementById('extensionReason').value = '';
        
        const modal = new bootstrap.Modal(extensionModal);
        modal.show();
      }
    }
  });

  // ==================== ENVIAR SOLICITUD DE PRÓRROGA ====================
  document.getElementById('extensionForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const archiveId = document.getElementById('extensionArchiveId').value;
    const requestedUntil = document.getElementById('extensionRequestedUntil').value;
    const reason = document.getElementById('extensionReason').value.trim();
    
    if (!archiveId || !requestedUntil || !reason) {
      emitFlash('warning', 'Completa todos los campos requeridos.');
      return;
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
    submitBtn.disabled = true;
    
    try {
      const payload = {
        archive_id: parseInt(archiveId),
        requested_until: requestedUntil,
        reason: reason
      };
      
      const res = await fetch('/api/v1/extensions/requests', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify(payload)
      });
      
      const json = await res.json().catch(() => ({}));
      
      if (!res.ok) {
        const msg = json?.error || 'No se pudo enviar la solicitud de prórroga.';
        emitFlash('danger', msg);
        return;
      }
      
      emitFlash('success', 'Solicitud de prórroga enviada correctamente. Recibirás una respuesta pronto.');
      closeModal(extensionModal);
      
      // Opcional: recargar página para mostrar estado actualizado
      setTimeout(() => window.location.reload(), 1500);
      
    } catch (err) {
      console.error('Extension request error:', err);
      emitFlash('danger', 'Error de red al enviar la solicitud.');
    } finally {
      submitBtn.innerHTML = originalText;
      submitBtn.disabled = false;
    }
  });

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

  // ==================== VALIDACIÓN DE ARCHIVOS EN TIEMPO REAL ====================
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

  // ==================== CARGAR INFORMACIÓN DE CITA ASIGNADA ====================
  loadInterviewInfo();

  async function loadInterviewInfo() {
    try {
      const res = await fetch('/api/v1/appointments/mine/active', {
        credentials: 'same-origin'
      });
      
      if (!res.ok) return;
      
      const json = await res.json();
      if (json.ok && json.appointments && json.appointments.length > 0) {
        // Mostrar todas las citas activas
        json.appointments.forEach(appt => showInterviewCard(appt));
      }
      
    } catch (err) {
      console.log('No se pudo cargar información de citas');
    }
  }

  function showInterviewCard(appointment) {
    // Crear card de cita asignada
    const interviewCard = document.createElement('div');
    interviewCard.className = 'alert alert-success shadow-sm mb-4';
    interviewCard.id = `interviewCard-${appointment.id}`;
    
    // Formatear fecha y hora
    const startDate = new Date(appointment.starts_at);
    const endDate = new Date(appointment.ends_at);
    const dateStr = startDate.toLocaleDateString('es-MX', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
    const timeStr = `${startDate.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${endDate.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;
    
    interviewCard.innerHTML = `
      <div class="row align-items-center">
        <div class="col-12 col-md-8">
          <h5 class="mb-2">
            <i class="fas fa-calendar-check me-2"></i>
            ${appointment.event_title}
          </h5>
          <p class="mb-2">
            <strong><i class="fas fa-clock me-1"></i> Fecha y hora:</strong> ${dateStr}<br>
            <strong><i class="fas fa-hourglass-half me-1"></i> Horario:</strong> ${timeStr}<br>
            <strong><i class="fas fa-map-marker-alt me-1"></i> Lugar:</strong> ${appointment.location || 'Por confirmar'}
          </p>
          ${appointment.notes ? `
            <div class="alert alert-info py-2 mb-0">
              <small><strong>Notas:</strong> ${appointment.notes}</small>
            </div>
          ` : ''}
        </div>
        <div class="col-12 col-md-4 text-md-end mt-3 mt-md-0">
          <button class="btn btn-outline-warning btn-sm w-100 w-md-auto btn-request-change" data-appointment-id="${appointment.id}">
            <i class="fas fa-exchange-alt me-1"></i>
            Solicitar Cambio
          </button>
        </div>
      </div>
    `;
    
    // Insertar después del alert de proceso de admisión
    const processAlert = document.querySelector('.alert-info');
    if (processAlert) {
      processAlert.parentNode.insertBefore(interviewCard, processAlert.nextSibling);
    }
  }

  // ==================== SOLICITAR CAMBIO DE CITA ====================
  document.addEventListener('click', (e) => {
    if (e.target.closest('.btn-request-change')) {
      const button = e.target.closest('.btn-request-change');
      const appointmentId = button.getAttribute('data-appointment-id');
      
      if (appointmentId) {
        openChangeRequestModal(appointmentId);
      }
    }
  });

  function openChangeRequestModal(appointmentId) {
    // Por ahora mostrar un prompt simple
    const reason = prompt('Motivo del cambio de horario:');
    if (!reason || !reason.trim()) return;
    
    const suggestions = prompt('Sugerencias de horario (opcional):');
    
    requestAppointmentChange(appointmentId, reason.trim(), suggestions?.trim());
  }

  async function requestAppointmentChange(appointmentId, reason, suggestions) {
    try {
      const payload = { reason };
      if (suggestions) payload.suggestions = suggestions;
      
      const res = await fetch(`/api/v1/appointments/${appointmentId}/change-requests`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify(payload)
      });
      
      const json = await res.json();
      
      if (!res.ok || !json.ok) {
        emitFlash('danger', json.error || 'No se pudo enviar la solicitud');
        return;
      }
      
      emitFlash('success', 'Solicitud de cambio enviada. El coordinador la revisará pronto.');
      
    } catch (err) {
      console.error('Change request error:', err);
      emitFlash('danger', 'Error al enviar la solicitud de cambio');
    }
  }
});
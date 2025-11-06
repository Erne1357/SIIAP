// static/js/program/admission.js - Flash corregido
document.addEventListener('DOMContentLoaded', () => {

  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();

  // FUNCIÓN FLASH CORRECTA
  function flash(message, level = 'success') {
    window.dispatchEvent(new CustomEvent('flash', {
      detail: { level: level, message: message }
    }));
  }

  function persistFlashes(flashes) {
    try {
      const arr = Array.isArray(flashes) ? flashes : [];
      sessionStorage.setItem('flashQueue', JSON.stringify(arr));
    } catch (_) { }
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

      const inputArchive = uploadModal.querySelector('[name="archive_id"]');
      if (inputArchive) inputArchive.value = archId || '';
      currentStepForHash = stepId || null;

      const existingInfo = document.getElementById('existingFileInfo');
      const uploadBtnText = document.getElementById('uploadBtnText');
      const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');

      // SIEMPRE empezar ocultando la información de archivo existente
      existingInfo.style.display = 'none';

      // DEBUG: Mostrar todos los valores para diagnosticar
      
      
      
      
      

      // Solo mostrar información de archivo existente si realmente hay uno Y tiene datos válidos
      const shouldShow = hasExisting === true 
        && existingFilename 
        && typeof existingFilename === 'string' 
        && existingFilename.trim() !== '' 
        && existingDate 
        && typeof existingDate === 'string' 
        && existingDate.trim() !== '';
      
      
      
      if (shouldShow) {
        
        document.getElementById('existingArchiveName').textContent = archiveName || '';
        document.getElementById('existingFilename').textContent = existingFilename;
        document.getElementById('existingDate').textContent = existingDate;
        // Mostrar el contenedor
        existingInfo.style.display = 'block';
        existingInfo.classList.remove('d-none');
        uploadBtnText.textContent = 'Reemplazar';
        uploadSubmitBtn.className = 'btn btn-warning';
      } else {
        
        existingInfo.style.display = 'none';
        existingInfo.classList.add('d-none');
        uploadBtnText.textContent = 'Subir';
        uploadSubmitBtn.className = 'btn btn-primary';
      }
    });

    uploadModal.addEventListener('hidden.bs.modal', () => {
      const fileInput = uploadModal.querySelector('input[type="file"]');
      
      if (fileInput) fileInput.value = '';
      
      // Siempre ocultar la información de archivo existente al cerrar
      const existingInfo = document.getElementById('existingFileInfo');
      existingInfo.style.display = 'none';
      existingInfo.classList.add('d-none');
      
      // Limpiar contenido para evitar que se muestre información residual
      document.getElementById('existingArchiveName').textContent = '';
      document.getElementById('existingFilename').textContent = '';
      document.getElementById('existingDate').textContent = '';
    });
  }

  // ==================== MODAL DE PRÓRROGA ====================
  if (extensionModal) {
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
      flash('Completa todos los campos requeridos', 'warning');
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
        flash(msg, 'danger');
        return;
      }

      flash('Solicitud de prórroga enviada correctamente. Recibirás una respuesta pronto', 'success');
      closeModal(extensionModal);

      setTimeout(() => window.location.reload(), 1500);

    } catch (err) {
      console.error('Extension request error:', err);
      flash('Error de red al enviar la solicitud', 'danger');
    } finally {
      submitBtn.innerHTML = originalText;
      submitBtn.disabled = false;
    }
  });

  // Restaurar pestaña activa desde hash
  const hash = window.location.hash;
  if (hash && hash.startsWith('#pane-')) {
    const btn = document.querySelector(`button[data-bs-target="${hash}"]`);
    if (btn) new bootstrap.Tab(btn).show();
  }

  // Actualizar hash cuando cambie de tab
  document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(btn => {
    btn.addEventListener('shown.bs.tab', (e) => {
      const target = e.target.getAttribute('data-bs-target');
      if (target) {
        window.location.hash = target;
      }
    });
  });

  // ==================== SUBIR ARCHIVOS CON VALIDACIONES ====================
  document.querySelectorAll('form[data-admission-upload="true"]').forEach(form => {
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const archiveId = fd.get('archive_id');
      const file = fd.get('file');

      if (!archiveId || !file || (file instanceof File && !file.name)) {
        flash('Selecciona un archivo válido', 'danger');
        return;
      }

      if (file.size > 3 * 1024 * 1024) {
        flash('El archivo no puede superar los 3MB', 'danger');
        return;
      }

      if (!file.name.toLowerCase().endsWith('.pdf')) {
        flash('Solo se permiten archivos PDF', 'danger');
        return;
      }

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
            json.flash.forEach(f => flash(f.message || msg, f.level || 'danger'));
          } else {
            flash(msg, 'danger');
          }
          return;
        }

        closeModal(uploadModal);

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Documento subido correctamente.' }];

        if (currentStepForHash) {
          // Buscar si este step está en un tab combinado
          const combinedTab = document.querySelector(`[data-bs-target*="pane-combined-"][data-bs-target*="${currentStepForHash}"]`);
          if (combinedTab) {
            const target = combinedTab.getAttribute('data-bs-target');
            window.location.hash = target;
          } else {
            window.location.hash = `#pane-${currentStepForHash}`;
          }
        }
        persistFlashes(flashes);
        window.location.reload();

      } catch (err) {
        console.error('Upload error:', err);
        flash('Error de red al subir', 'danger');
      } finally {
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

      // TODO Fase 3: Reemplazar con modal de confirmación
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
            json.flash.forEach(f => flash(f.message || msg, f.level || 'danger'));
          } else {
            flash(msg, 'danger');
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
        flash('Error de red al eliminar', 'danger');
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
        json.appointments.forEach(appt => showInterviewCard(appt));
      } else if (json.ok && !json.appointments.length) {
        // Verificar si ya completo su perfil, si no, mostrar alerta de que debe completar perfil, si no, mostrar que es elegible para entrevista
        const res = await fetch('/api/v1/users/me', {
          credentials: 'same-origin'
        });
        const userInfo = await res.json();
        if (res.ok && !userInfo.data.user.profile_completed) {
          const processAlert = document.querySelector('.interview-info');
          if (processAlert) {
            processAlert.className = 'alert alert-warning interview-info';
            processAlert.innerHTML = `
              <i class="fas fa-user-edit me-2"></i>
              Completa tu perfil para ser elegible para entrevista.
              <a href="/user/profile" class="alert-link">Ir a mi perfil</a>
            `;
          }
        } else {
          const processAlert = document.querySelector('.interview-info');
          if (processAlert) {
            processAlert.className = 'alert alert-info interview-info';
            processAlert.innerHTML = `
              <i class="fas fa-info-circle me-2"></i>
              Eres elegible para entrevista. Pronto recibirás una notificación con la fecha y hora asignada.
            `;
          }
        }
      }
    } catch (err) {
      
    }
  }

  function showInterviewCard(appointment) {
    const interviewCard = document.createElement('div');
    interviewCard.className = 'alert alert-success shadow-sm mb-4';
    interviewCard.id = `interviewCard-${appointment.id}`;

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

    const processAlert = document.querySelector('.interview-info');
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
        // TODO Fase 3: Reemplazar con modal
        openChangeRequestModal(appointmentId);
      }
    }
  });

  function openChangeRequestModal(appointmentId) {
    // TODO Fase 3: Modal en lugar de prompt
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
        flash(json.error || 'No se pudo enviar la solicitud', 'danger');
        return;
      }

      flash('Solicitud de cambio enviada. El coordinador la revisará pronto', 'success');

    } catch (err) {
      console.error('Change request error:', err);
      flash('Error al enviar la solicitud de cambio', 'danger');
    }
  }
});
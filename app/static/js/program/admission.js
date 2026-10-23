// static/js/program/admission.js
// Documents are uploaded / replaced / deleted through htmx fragments (see
// routes/pages/admission_pages.py and templates/programs/admission/_partials/):
// no full reload and no sessionStorage flash queue. What is left
// here is what htmx cannot do declaratively: modal wiring, client pre-checks,
// the extra request parameters, and re-applying client-only state after a morph.
document.addEventListener('DOMContentLoaded', () => {

  // FUNCIÓN FLASH CORRECTA
  function flash(message, level = 'success') {
    window.dispatchEvent(new CustomEvent('flash', {
      detail: { level: level, message: message }
    }));
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    let inst = bootstrap.Modal.getInstance(modalEl);
    if (!inst) inst = new bootstrap.Modal(modalEl);
    inst.hide();
  }

  const uploadModal = document.getElementById('uploadModal');
  const extensionModal = document.getElementById('extensionModal');

  // Ask the server for a fresh body (status banner / tabs). The element declares
  // hx-get and the trigger list in the template.
  function refreshPanel() {
    const el = document.getElementById('admission-refresh');
    if (el && window.htmx) window.htmx.trigger(el, 'siiap:admission-refresh');
  }

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
      const archiveName = btn?.getAttribute('data-archive-name');
      const hasExisting = btn?.getAttribute('data-has-existing') === 'true';
      const existingFilename = btn?.getAttribute('data-existing-filename');
      const existingDate = btn?.getAttribute('data-existing-date');

      const inputArchive = uploadModal.querySelector('[name="archive_id"]');
      if (inputArchive) inputArchive.value = archId || '';

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
    submitBtn.innerHTML = '<i class="bi bi-arrow-repeat bi-spin" aria-hidden="true"></i> Enviando...';
    submitBtn.disabled = true;

    try {
      const payload = {
        // Identificador público del archivo (UUID): cadena, no entero.
        archive_id: archiveId,
        requested_until: requestedUntil,
        reason: reason
      };

      const res = await window.SIIAP.api.post('/api/v1/extensions/requests', payload, { flash: false });

      if (!res.ok) {
        const msg = res.body?.error?.message || 'No se pudo enviar la solicitud de prórroga.';
        flash(msg, 'danger');
        return;
      }

      flash('Solicitud de prórroga enviada exitosamente. Recibirás una respuesta pronto', 'success');
      closeModal(extensionModal);
      refreshPanel();

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

  // ==================== HTMX: SUBIR / ELIMINAR (sin recarga) ====================
  // The form (#uploadForm) and the delete buttons declare hx-post / hx-delete.
  // The server answers with the pane that changed (HX-Retarget), the tabs and
  // the stepper out of band, and the flash in HX-Trigger.
  const MAX_UPLOAD_BYTES = 3 * 1024 * 1024;
  let openCollapseIds = [];
  let focusFallbackId = null;

  // Pre-checks that save a round trip; the server validates again, identically.
  document.addEventListener('htmx:beforeRequest', (evt) => {
    const elt = evt.detail.elt;
    if (!elt || !elt.matches || !elt.matches('[data-admission-ctx]')) return;

    if (elt.id === 'uploadForm') {
      const fd = new FormData(elt);
      const file = fd.get('file');
      if (!fd.get('archive_id') || !file || (file instanceof File && !file.name)) {
        evt.preventDefault();
        flash('Selecciona un archivo válido', 'danger');
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        evt.preventDefault();
        flash('El archivo no puede superar los 3MB', 'danger');
        return;
      }
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        evt.preventDefault();
        flash('Solo se permiten archivos PDF', 'danger');
        return;
      }
    }

    // A morph resets attributes the server does not know about: remember the
    // description rows the user opened, and where focus should go if the
    // pressed button disappears (delete).
    openCollapseIds = Array.from(document.querySelectorAll('#admission-body .archive-table .collapse.show'))
      .map(el => el.id).filter(Boolean);
    focusFallbackId = elt.getAttribute('data-focus-fallback');
  });

  // The server cannot know which tab is open nor which tabs the browser shows
  // locked; tell it, so it marks the right tab active and only re-sends the
  // panes whose lock changed.
  document.addEventListener('htmx:configRequest', (evt) => {
    const elt = evt.detail.elt;
    if (!elt || !elt.matches || !elt.matches('[data-admission-ctx]')) return;
    const paneOf = (btn) => (btn.getAttribute('data-bs-target') || '').replace(/^#/, '');
    const activeTab = document.querySelector('#stepTab .nav-link.active');
    if (activeTab) evt.detail.parameters['active'] = paneOf(activeTab);
    evt.detail.parameters['locked'] = Array.from(document.querySelectorAll('#stepTab .nav-link.disabled'))
      .map(paneOf).filter(Boolean).join(',');
  });

  // Success closes the modal; a refusal keeps it open (the flash says why).
  document.addEventListener('htmx:afterRequest', (evt) => {
    const elt = evt.detail.elt;
    if (elt && elt.id === 'uploadForm' && evt.detail.successful) closeModal(uploadModal);
  });

  function restoreOpenCollapses() {
    openCollapseIds.forEach((id) => {
      const row = document.getElementById(id);
      if (!row || !row.classList.contains('collapse')) return;
      row.classList.add('show');
      const toggler = document.querySelector(`[href="#${id}"][data-bs-toggle="collapse"]`);
      if (toggler) toggler.setAttribute('aria-expanded', 'true');
    });
    openCollapseIds = [];
  }

  function restoreFocus() {
    if (!focusFallbackId) return;
    const target = document.getElementById(focusFallbackId);
    const lost = !document.activeElement || document.activeElement === document.body;
    if (target && lost) target.focus();
  }

  document.addEventListener('htmx:afterSwap', (evt) => {
    if (!document.getElementById('admission-body')) return;
    restoreOpenCollapses();

    // The interview panel is filled by JS: a morph puts back the server's skeleton.
    if (document.querySelector('.interview-info[aria-busy="true"]')) loadInterviewInfo();

    const target = evt.detail.target;
    if (target && target.id === 'admission-body' && window.SIIAP && SIIAP.announce) {
      SIIAP.announce('Se actualizó el estado de tus documentos.');
    }

    restoreFocus();
    if (focusFallbackId) {
      // The confirm dialog hands focus back after its own fade.
      setTimeout(() => { restoreFocus(); focusFallbackId = null; }, 400);
    }
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

      const fileName = SIIAP.escapeHtml(file.name);

      if (file.size > 3 * 1024 * 1024) {
        feedbackEl.className = 'file-feedback small mt-1 text-danger';
        feedbackEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill" aria-hidden="true"></i> Archivo: ${fileName} (${sizeMB} MB) - EXCEDE EL LÍMITE`;
      } else if (!file.name.toLowerCase().endsWith('.pdf')) {
        feedbackEl.className = 'file-feedback small mt-1 text-danger';
        feedbackEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill" aria-hidden="true"></i> Solo se permiten archivos PDF`;
      } else {
        feedbackEl.className = 'file-feedback small mt-1 text-success';
        feedbackEl.innerHTML = `<i class="bi bi-check-lg" aria-hidden="true"></i> Archivo: ${fileName} (${sizeMB} MB)`;
      }
    });
  });

  // ==================== CARGAR INFORMACIÓN DE CITA ASIGNADA ====================
  loadInterviewInfo();

  // Pinta el panel de entrevista conservando role/aria-live y apagando aria-busy.
  // Antes se reasignaba className a secas y el panel se quedaba en blanco
  // (y anunciándose como "cargando") en cuanto la petición fallaba.
  function renderInterviewPanel(extraClass, html) {
    const panel = document.querySelector('.interview-info');
    if (!panel) return null;
    panel.className = `interview-info ${extraClass}`.trim();
    panel.setAttribute('aria-busy', 'false');
    panel.innerHTML = html;
    return panel;
  }

  async function loadInterviewInfo() {
    const panel = document.querySelector('.interview-info');
    if (!panel) return;

    try {
      const res = await window.SIIAP.api.get('/api/v1/appointments/mine/active', { flash: false });

      if (!res.ok) throw new Error('appointments-request-failed');

      const json = res.body;
      const appointments = json.data?.appointments || [];
      if (!json.error && appointments.length > 0) {
        renderInterviewPanel('', '');
        appointments.forEach(appt => showInterviewCard(appt));
      } else if (!json.error && !appointments.length) {
        // Sin cita asignada: informar si falta completar el perfil.
        const meRes = await window.SIIAP.api.get('/api/v1/users/me', { flash: false });
        const userInfo = meRes.body;

        if (meRes.ok && !userInfo.data.user.profile_completed) {
          renderInterviewPanel('alert alert-warning', `
            <i class="bi bi-person-fill-gear me-2" aria-hidden="true"></i>
            Completa tu perfil para ser elegible para entrevista.
            <a href="/user/profile" class="alert-link">Ir a mi perfil</a>
          `);
        } else {
          renderInterviewPanel('alert alert-info', `
            <i class="bi bi-info-circle-fill me-2" aria-hidden="true"></i>
            Eres elegible para entrevista. Pronto recibirás una notificación con la fecha y hora asignada.
          `);
        }
      } else {
        throw new Error('unexpected-payload');
      }
    } catch (err) {
      console.error('Interview info error:', err);
      renderInterviewPanel('alert alert-danger', `
        <i class="bi bi-exclamation-triangle-fill me-2" aria-hidden="true"></i>
        No pudimos cargar la información de tu entrevista.
        <button type="button" class="btn btn-sm btn-outline-danger ms-2" id="retryInterviewInfo">
          Reintentar
        </button>
      `);
      document.getElementById('retryInterviewInfo')?.addEventListener('click', () => {
        const p = document.querySelector('.interview-info');
        if (p) {
          p.className = 'interview-info';
          p.setAttribute('aria-busy', 'true');
          p.innerHTML = '<div class="skeleton skeleton-card skeleton-card--sm"></div>';
        }
        loadInterviewInfo();
      });
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
          <h3 class="h5 mb-2">
            <i class="bi bi-calendar-check me-2" aria-hidden="true"></i>
            ${SIIAP.escapeHtml(appointment.event_title)}
          </h3>
          <p class="mb-2">
            <strong><i class="bi bi-clock me-1" aria-hidden="true"></i> Fecha y hora:</strong> ${SIIAP.escapeHtml(dateStr)}<br>
            <strong><i class="bi bi-hourglass-split me-1" aria-hidden="true"></i> Horario:</strong> ${SIIAP.escapeHtml(timeStr)}<br>
            <strong><i class="bi bi-geo-alt-fill me-1" aria-hidden="true"></i> Lugar:</strong> ${SIIAP.escapeHtml(appointment.location || 'Por confirmar')}
          </p>
          ${appointment.notes ? `
            <div class="alert alert-info py-2 mb-0">
              <small><strong>Notas:</strong> ${SIIAP.escapeHtml(appointment.notes)}</small>
            </div>
          ` : ''}
        </div>
        <div class="col-12 col-md-4 text-md-end mt-3 mt-md-0">
          ${appointment.pending_change_request ? `
            <div class="alert alert-warning py-2 mb-2 text-start">
              <small><i class="bi bi-clock me-1" aria-hidden="true"></i><strong>Solicitud en revisión</strong><br>
              Tu solicitud de cambio está pendiente de respuesta.</small>
            </div>
            <button class="btn btn-outline-secondary btn-sm w-100 w-md-auto btn-request-change"
                    data-appointment-id="${SIIAP.escapeAttr(appointment.id)}"
                    data-pending-reason="${SIIAP.escapeAttr(appointment.pending_change_request.reason || '')}"
                    data-pending-suggestions="${SIIAP.escapeAttr(appointment.pending_change_request.suggestions || '')}">
              <i class="bi bi-pencil-square me-1" aria-hidden="true"></i>
              Editar Solicitud
            </button>
          ` : `
            <button class="btn btn-outline-warning btn-sm w-100 w-md-auto btn-request-change"
                    data-appointment-id="${SIIAP.escapeAttr(appointment.id)}">
              <i class="bi bi-arrow-left-right me-1" aria-hidden="true"></i>
              Solicitar Cambio
            </button>
          `}
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
      const pendingReason = button.getAttribute('data-pending-reason') || '';
      const pendingSuggestions = button.getAttribute('data-pending-suggestions') || '';

      if (appointmentId) {
        openChangeRequestModal(appointmentId, pendingReason, pendingSuggestions);
      }
    }
  });

  const changeRequestModalEl = document.getElementById('changeRequestModal');
  const changeRequestModal = changeRequestModalEl ? new bootstrap.Modal(changeRequestModalEl) : null;
  const changeRequestForm = document.getElementById('changeRequestForm');

  changeRequestForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const appointmentId = document.getElementById('changeReqAppointmentId').value;
    const reason = document.getElementById('changeReqReason').value.trim();
    const suggestions = document.getElementById('changeReqSuggestions').value.trim();

    await requestAppointmentChange(appointmentId, reason, suggestions || null);
    changeRequestModal?.hide();
    changeRequestForm.reset();
  });

  function openChangeRequestModal(appointmentId, pendingReason = '', pendingSuggestions = '') {
    document.getElementById('changeReqAppointmentId').value = appointmentId;
    document.getElementById('changeReqReason').value = pendingReason;
    document.getElementById('changeReqSuggestions').value = pendingSuggestions;

    if (changeRequestModal) {
      changeRequestModal.show();
    }
  }

  async function requestAppointmentChange(appointmentId, reason, suggestions) {
    try {
      const payload = { reason };
      if (suggestions) payload.suggestions = suggestions;

      const res = await window.SIIAP.api.post(`/api/v1/appointments/${appointmentId}/change-requests`, payload, { flash: false });

      if (!res.ok) {
        flash(res.body?.error?.message || 'No se pudo enviar la solicitud', 'danger');
        return;
      }

      flash('Solicitud de cambio enviada. El coordinador la revisará pronto', 'success');

    } catch (err) {
      console.error('Change request error:', err);
      flash('Error al enviar la solicitud de cambio', 'danger');
    }
  }

  // ==================== TIEMPO REAL ====================
  // The body refreshes itself: #admission-refresh declares hx-get and listens
  // to these same window events (hx-trigger "... from:window"). Here only the
  // user-facing message remains.
  window.addEventListener('siiap:submission:reviewed', (e) => {
    const data = e.detail;
    if (!data) return;
    const newStatus = data.status; // 'approved' o 'rejected'
    if (newStatus !== 'approved' && newStatus !== 'rejected') return;
    const action = newStatus === 'approved' ? 'aprobado' : 'rechazado';
    flash(`Un documento ha sido ${action}.`, newStatus === 'approved' ? 'success' : 'warning');
  });

  // ==================== TIEMPO REAL: DECISIÓN DE PRÓRROGA ====================
  window.addEventListener('siiap:extension:decided', (e) => {
    const data = e.detail || {};
    const messages = {
      granted:   { text: 'Tu solicitud de prórroga fue aprobada.', level: 'success' },
      rejected:  { text: 'Tu solicitud de prórroga fue rechazada.', level: 'warning' },
      cancelled: { text: 'Tu solicitud de prórroga fue cancelada.', level: 'info' },
    };
    const m = messages[data.status];
    if (!m) return;
    flash(m.text, m.level);
  });

  // ==================== TIEMPO REAL: CAMBIO DE ESTADO DE ADMISIÓN ====================
  window.addEventListener('siiap:admission:status_changed', (e) => {
    const data = e.detail;
    if (!data) return;

    const ctx = window.SIIAP_ADMISSION || {};
    if (ctx.programId && data.program_id && ctx.programId !== data.program_id) return;

    const messages = {
      interview_completed: { text: 'Tu entrevista fue marcada como completada.', level: 'info' },
      deliberation:        { text: 'Tu expediente entró en deliberación.',        level: 'warning' },
      accepted:            { text: '¡Has sido aceptado al programa!',             level: 'success' },
      rejected:            { text: 'Se actualizó el estado de tu admisión.',      level: 'warning' },
      in_progress:         { text: 'Tu expediente fue reabierto para correcciones.', level: 'info' },
    };

    const m = messages[data.new_status];
    if (!m) return;

    flash(m.text, m.level);
  });

  // ── Subida de carta de asignación de número de control ────────────────────
  // Delegated: the button lives in the refreshable body, so it can be replaced.
  document.addEventListener('click', (e) => {
    if (window.SIIAP_ADMISSION && e.target.closest('#receiptUploadBtn')) submitEnrollmentReceipt();
  });

  function submitEnrollmentReceipt() {
    const cfg = window.SIIAP_ADMISSION || {};
    const fileInput = document.getElementById('receiptFileInput');
    const statusDiv = document.getElementById('receiptUploadStatus');
    const btn = document.getElementById('receiptUploadBtn');
    if (!cfg.userId || !cfg.programId) {
      statusDiv.innerHTML = '<div class="alert alert-danger py-1 small">Configuración inválida — recarga la página.</div>';
      return;
    }
    if (!fileInput.files.length) {
      statusDiv.innerHTML = '<div class="alert alert-warning py-1 small">Selecciona un archivo primero.</div>';
      return;
    }
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.innerHTML = '<i class="bi bi-arrow-repeat bi-spin me-1" aria-hidden="true"></i>Subiendo…';
    statusDiv.innerHTML = '<p class="small mb-0">Subiendo la carta de asignación…</p>';

    const restoreButton = () => {
      btn.disabled = false;
      btn.setAttribute('aria-busy', 'false');
      btn.innerHTML = '<i class="bi bi-upload me-1" aria-hidden="true"></i>Subir carta';
    };

    window.SIIAP.api.request('POST', `/api/v1/acceptance/user/${cfg.userId}/program/${cfg.programId}/submit-receipt`, { body: formData, flash: false })
      .then(res => {
        if (res.error) {
          statusDiv.innerHTML = '<div class="alert alert-danger py-1 small mb-0">' + SIIAP.escapeHtml(res.error.message || 'No se pudo subir el archivo.') + '</div>';
          restoreButton();
        } else {
          statusDiv.innerHTML = '<div class="alert alert-success py-1 small mb-0">Documento subido. El coordinador lo revisará pronto.</div>';
          flash('Documento subido. El coordinador lo revisará pronto.', 'success');
          refreshPanel();
        }
      })
      .catch(() => {
        statusDiv.innerHTML = '<div class="alert alert-danger py-1 small mb-0">Error de red. Intenta de nuevo.</div>';
        restoreButton();
      });
  }
});
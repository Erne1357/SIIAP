/* app/static/js/user/applicant_dashboard.js
 * Lógica del dashboard de aspirante (carta de aceptación en diferimiento +
 * flujo completo de aceptación: carta, tira de materias, boleta).
 *
 * Depende de window.SIIAP_APPLICANT_DASH = {
 *   userId, userProgramId, admissionStatus, programId
 * }.
 */
(function () {
  'use strict';

  const CFG = window.SIIAP_APPLICANT_DASH || {};
  const userId = CFG.userId;
  const userProgramId = CFG.userProgramId;
  if (!userId || !userProgramId) return;

  // ── Helpers ──────────────────────────────────────────────────────────────
  function buildDownloadUrl(filePath) {
    if (!filePath) return '#';
    const parts = filePath.split('/');
    return '/files/doc/' + parts[0] + '/' + parts[1] + '/' + parts.slice(2).join('/');
  }

  function getCsrf() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
  }

  // ── Carta de aceptación en estado diferido ───────────────────────────────
  async function loadDeferralLetter() {
    const container = document.getElementById('deferralAcceptanceLetterSection');
    if (!container) return;
    try {
      const resp = await fetch(`/api/v1/acceptance/user/${userId}/program/${userProgramId}/status`);
      const result = await resp.json();
      if (result.error) {
        container.innerHTML = '';
        return;
      }
      const letter = result.data?.acceptance_letter;
      if (letter && letter.file_path) {
        const url = buildDownloadUrl(letter.file_path);
        container.innerHTML = `
          <a href="${url}" target="_blank" class="btn btn-outline-success btn-sm">
            <i class="bi bi-download me-1"></i>Descargar Carta de Aceptación
          </a>`;
      } else {
        container.innerHTML = '';
      }
    } catch (e) {
      container.innerHTML = '';
    }
  }

  // ── Flujo de aceptación (aspirante aceptado) ─────────────────────────────
  async function loadAcceptanceDocs() {
    const container = document.getElementById('acceptanceDocsContent');
    if (!container) return;
    try {
      const resp = await fetch(`/api/v1/acceptance/user/${userId}/program/${userProgramId}/status`);
      const result = await resp.json();

      if (result.error) {
        container.innerHTML = '<p class="text-danger">Error al cargar documentos.</p>';
        return;
      }

      const docs = result.data;
      const letter = docs.acceptance_letter;
      const schedule = docs.course_schedule;
      const receipt = docs.enrollment_receipt;

      const hasLetter   = letter   && letter.file_path;
      const hasSchedule = schedule && schedule.file_path;
      const receiptApproved = receipt && receipt.status === 'approved';
      const receiptRejected = receipt && receipt.status === 'rejected';
      const receiptUploaded = receipt && receipt.status === 'uploaded';

      const letterCard = buildDocCard(
        'Carta de Aceptación', 'bi-file-earmark-text',
        hasLetter, 'Para formalizar tu admisión al programa',
        hasLetter ? buildDownloadBtn(buildDownloadUrl(letter.file_path)) : ''
      );

      const scheduleCard = buildDocCard(
        'Tira de Materias', 'bi-list-check',
        hasSchedule, 'Materias que cursarás este semestre',
        hasSchedule ? buildDownloadBtn(buildDownloadUrl(schedule.file_path)) : ''
      );

      let receiptAction = '';
      let receiptStatus = 'pending';
      let receiptNote = 'Pendiente de subir';

      if (receiptApproved) {
        receiptStatus = 'approved';
        receiptNote = 'Aprobada por el coordinador';
        receiptAction = '<span class="badge bg-success fs-6"><i class="bi bi-check-circle me-1"></i>Aprobada</span>';
      } else if (receiptUploaded) {
        receiptStatus = 'uploaded';
        receiptNote = 'Subida, en revisión por el coordinador';
        receiptAction = '<span class="badge bg-info fs-6">En revisión</span>';
      } else if (receiptRejected) {
        receiptStatus = 'rejected';
        receiptNote = 'Rechazada: ' + (receipt.review_notes || 'Sin especificar');
        if (hasLetter && hasSchedule) {
          receiptAction = '<button class="btn btn-danger btn-sm" id="uploadReceiptBtn"><i class="bi bi-upload me-1"></i>Volver a Subir</button>';
        }
      } else if (hasLetter && hasSchedule) {
        receiptAction = '<button class="btn btn-primary btn-sm" id="uploadReceiptBtn"><i class="bi bi-upload me-1"></i>Subir Boleta</button>';
      } else {
        receiptAction = '<small class="text-muted">Disponible cuando el coordinador suba la carta y tira</small>';
      }

      const receiptCard = buildReceiptCard(receiptStatus, receiptNote, receiptAction);
      container.innerHTML = '<div class="row g-3">' + letterCard + scheduleCard + receiptCard + '</div>';

      const btn = document.getElementById('uploadReceiptBtn');
      if (btn) btn.addEventListener('click', triggerReceiptUpload);

    } catch (err) {
      console.error('Error loading acceptance docs:', err);
      container.innerHTML = '<p class="text-danger">Error al cargar documentos.</p>';
    }
  }

  function buildDocCard(title, icon, isAvailable, subtitle, actionHtml) {
    const borderClass = isAvailable ? 'border-success' : 'border-secondary';
    const iconClass = isAvailable ? 'text-success' : 'text-secondary';
    const statusBadge = isAvailable ? '' : '<span class="badge bg-secondary mb-2">Pendiente</span>';
    return `
      <div class="col-md-4">
        <div class="card h-100 border ${borderClass}">
          <div class="card-body text-center py-3">
            <i class="bi ${icon} ${iconClass} icon-2xl"></i>
            <h6 class="fw-bold mt-2 mb-1">${title}</h6>
            <p class="text-muted small mb-2">${subtitle}</p>
            ${statusBadge}
            ${actionHtml}
          </div>
        </div>
      </div>`;
  }

  function buildReceiptCard(status, note, actionHtml) {
    const borders = {
      approved: 'border-success', uploaded: 'border-info',
      rejected: 'border-danger', pending: 'border-warning',
    };
    const icons = {
      approved: 'text-success', uploaded: 'text-info',
      rejected: 'text-danger', pending: 'text-warning',
    };
    const bc = borders[status] || 'border-secondary';
    const ic = icons[status] || 'text-secondary';
    return `
      <div class="col-md-4">
        <div class="card h-100 border ${bc}">
          <div class="card-body text-center py-3">
            <i class="bi bi-receipt ${ic} icon-2xl"></i>
            <h6 class="fw-bold mt-2 mb-1">Boleta de Inscripción</h6>
            <p class="text-muted small mb-2">${note}</p>
            ${actionHtml}
          </div>
        </div>
      </div>`;
  }

  function buildDownloadBtn(url) {
    return `<a href="${url}" target="_blank" class="btn btn-success btn-sm">
      <i class="bi bi-download me-1"></i>Descargar
    </a>`;
  }

  function triggerReceiptUpload() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.doc,.docx';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      const btn = document.getElementById('uploadReceiptBtn');
      if (btn) { btn.disabled = true; btn.textContent = 'Subiendo...'; }

      try {
        const resp = await fetch(
          `/api/v1/acceptance/user/${userId}/program/${userProgramId}/submit-receipt`,
          {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf() },
            body: formData,
          }
        );
        const result = await resp.json();
        if (result.flash) result.flash.forEach(f => showSimpleToast(f.message, f.level));
        if (!result.error) loadAcceptanceDocs();
      } catch (err) {
        showSimpleToast('Error al subir la boleta', 'danger');
        if (btn) { btn.disabled = false; btn.textContent = 'Subir Boleta'; }
      }
    };
    input.click();
  }

  // ── Toast ad-hoc (se conserva del inline original) ───────────────────────
  function showSimpleToast(message, level) {
    let cont = document.getElementById('toast-container');
    if (!cont) {
      cont = document.createElement('div');
      cont.id = 'toast-container';
      cont.className = 'toast-container position-fixed top-0 end-0 p-3 siiap-toast-stack';
      document.body.appendChild(cont);
    }
    const id = 'toast-' + Date.now();
    cont.insertAdjacentHTML('beforeend', `
      <div id="${id}" class="toast align-items-center text-bg-${level} border-0" role="alert">
        <div class="d-flex">
          <div class="toast-body">${message}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>`);
    const el = document.getElementById(id);
    new bootstrap.Toast(el, { autohide: true, delay: 4000 }).show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
  }

  // ── Init ─────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    loadDeferralLetter();   // sólo actúa si existe #deferralAcceptanceLetterSection
    loadAcceptanceDocs();   // sólo actúa si existe #acceptanceDocsContent
  });

  // Tiempo real: recargar documentos de aceptación cuando hay cambios
  window.addEventListener('siiap:acceptance:updated', () => {
    loadAcceptanceDocs();
  });

  const DASH_CTX = window.SIIAP_APPLICANT_DASH || {};

  // Tiempo real: documento revisado → progreso y contadores cambian
  window.addEventListener('siiap:submission:reviewed', (e) => {
    const data = e.detail || {};
    const action = data.status === 'approved' ? 'aprobado' : 'rechazado';
    showSimpleToast(`Un documento ha sido ${action}. Actualizando...`, data.status === 'approved' ? 'success' : 'warning');
    setTimeout(() => { window.location.reload(); }, 2000);
  });

  // Tiempo real: decisión de prórroga
  window.addEventListener('siiap:extension:decided', (e) => {
    const data = e.detail || {};
    const messages = {
      granted:   { text: 'Tu solicitud de prórroga fue aprobada.', type: 'success' },
      rejected:  { text: 'Tu solicitud de prórroga fue rechazada.', type: 'warning' },
      cancelled: { text: 'Tu solicitud de prórroga fue cancelada.', type: 'info' },
    };
    const m = messages[data.status];
    if (!m) return;
    showSimpleToast(`${m.text} Actualizando...`, m.type);
    setTimeout(() => { window.location.reload(); }, 2000);
  });

  // Tiempo real: cambio de estado de admisión → banners y timeline cambian
  window.addEventListener('siiap:admission:status_changed', (e) => {
    const data = e.detail || {};
    if (DASH_CTX.programId && data.program_id && DASH_CTX.programId !== data.program_id) return;
    const messages = {
      interview_completed: { text: 'Tu entrevista fue marcada como completada.', type: 'info' },
      deliberation:        { text: 'Tu expediente entró en deliberación.',        type: 'warning' },
      accepted:            { text: '¡Has sido aceptado al programa!',             type: 'success' },
      rejected:            { text: 'Se actualizó el estado de tu admisión.',      type: 'warning' },
      in_progress:         { text: 'Tu expediente fue reabierto para correcciones.', type: 'info' },
    };
    const m = messages[data.new_status];
    if (!m) return;
    showSimpleToast(`${m.text} Actualizando...`, m.type);
    setTimeout(() => { window.location.reload(); }, 2500);
  });
})();

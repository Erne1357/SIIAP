/* app/static/js/user/student_dashboard.js
 * Lógica del dashboard de estudiante (módulos Permanencia, Referencia Bancaria,
 * Documentos del Semestre, Solicitud de Baja Temporal).
 *
 * Depende de window.SIIAP_STUDENT_DASH = { upId: <int> } inyectado en la plantilla.
 */
(function () {
  'use strict';

  const CFG = window.SIIAP_STUDENT_DASH || {};
  const UP_ID = CFG.upId;
  if (!UP_ID) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  // ── Utils ────────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function flashMsg(level, message) {
    if (typeof showFlash === 'function') showFlash(level, message);
  }

  // ── Documentos del semestre ──────────────────────────────────────────────
  async function loadStudentDocs() {
    const container = document.getElementById('studentDocsContainer');
    if (!container) return;
    try {
      const res = await fetch(`/api/v1/permanence/user-program/${UP_ID}/documents`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderStudentDocs(json.data || []);
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger m-3 small">Error al cargar documentos: ${e.message}</div>`;
    }
  }

  function renderStudentDocs(docs) {
    const container = document.getElementById('studentDocsContainer');
    if (!docs.length) {
      container.innerHTML = `
        <div class="text-center py-4 text-muted">
          <i class="bi bi-folder-x fs-2 d-block mb-2"></i>
          No hay documentos solicitados para este periodo.
        </div>`;
      return;
    }

    const rows = docs.map(d => {
      const dl = d.deadline;
      const sub = d.submission;
      const archive = d.archive;

      const closesAt = dl.closes_at
        ? `<span class="small text-muted">Cierra: ${new Date(dl.closes_at).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })}</span>`
        : '';

      let statusHtml = '';
      let actionHtml = '';

      if (!sub) {
        if (dl.is_currently_open) {
          statusHtml = '<span class="badge bg-warning text-dark">Pendiente</span>';
          actionHtml = buildUploadForm(UP_ID, dl.id, dl.label);
        } else {
          statusHtml = '<span class="badge bg-secondary">Ventana cerrada</span>';
        }
      } else if (sub.status === 'review') {
        statusHtml = '<span class="badge bg-info text-dark"><i class="bi bi-hourglass-split me-1"></i>En revisión</span>';
      } else if (sub.status === 'approved') {
        statusHtml = '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Aprobado</span>';
        if (sub.file_path) {
          actionHtml = `<a href="/files/doc/${sub.file_path}" target="_blank" class="btn btn-sm btn-outline-success">
            <i class="bi bi-eye me-1"></i>Ver documento
          </a>`;
        }
      } else if (sub.status === 'rejected') {
        statusHtml = '<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>Rechazado</span>';
        if (sub.reviewer_comment) {
          statusHtml += `<div class="small text-danger mt-1">Motivo: ${escHtml(sub.reviewer_comment)}</div>`;
        }
        if (dl.is_currently_open) {
          actionHtml = buildUploadForm(UP_ID, dl.id, dl.label);
        }
      }

      return `
        <div class="border-bottom px-3 py-3">
          <div class="d-flex align-items-start gap-3 flex-wrap">
            <div class="flex-grow-1">
              <div class="fw-semibold">${escHtml(dl.label)}</div>
              <div class="small text-muted">${escHtml(archive.name)} ${closesAt}</div>
              <div class="mt-1">${statusHtml}</div>
            </div>
            ${actionHtml ? `<div class="flex-shrink-0">${actionHtml}</div>` : ''}
          </div>
        </div>`;
    }).join('');

    container.innerHTML = rows;

    container.querySelectorAll('.doc-upload-form').forEach(form => {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const upId = form.dataset.upId;
        const dlId = form.dataset.dlId;
        const fileInput = form.querySelector('input[type=file]');
        if (!fileInput.files.length) return;
        const btn = form.querySelector('button[type=submit]');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        const fd = new FormData();
        fd.append('file', fileInput.files[0]);
        try {
          const res = await fetch(`/api/v1/permanence/user-program/${upId}/documents/${dlId}`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: fd,
          });
          const json = await res.json();
          if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
          if (res.ok && !json.error) loadStudentDocs();
          else btn.disabled = false;
        } catch (err) {
          btn.disabled = false;
          flashMsg('danger', 'Error al subir el documento.');
        }
      });
    });
  }

  function buildUploadForm(upId, dlId, label) {
    return `
      <form class="doc-upload-form d-flex align-items-center gap-2" data-up-id="${upId}" data-dl-id="${dlId}">
        <input type="file" class="form-control form-control-sm doc-upload-input"
               accept=".pdf,.doc,.docx,.jpg,.png" required>
        <button type="submit" class="btn btn-sm btn-primary text-nowrap">
          <i class="bi bi-upload me-1"></i>Subir
        </button>
      </form>`;
  }

  // ── Referencia Bancaria ──────────────────────────────────────────────────
  async function loadPaymentReference() {
    const container = document.getElementById('paymentRefContainer');
    if (!container) return;
    try {
      const res = await fetch(`/api/v1/permanence/user-program/${UP_ID}/payment-reference`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      const d = json.data;

      if (!d.configured) {
        container.innerHTML = `
          <div class="alert alert-secondary d-flex gap-2 align-items-center mb-0 py-2 small">
            <i class="bi bi-info-circle-fill fs-5"></i>
            <span>${escHtml(d.error || 'La referencia bancaria no está configurada para tu programa.')}</span>
          </div>`;
        return;
      }

      if (d.file_url) {
        container.innerHTML = `
          <div class="d-flex align-items-center gap-3">
            <i class="bi bi-file-earmark-pdf text-danger fs-3"></i>
            <div>
              <div class="fw-semibold">Tu referencia bancaria está lista</div>
              <div class="small text-muted mb-2">${escHtml(d.template_name || '')}</div>
              <a href="${d.file_url}" target="_blank" class="btn btn-sm btn-success">
                <i class="bi bi-download me-1"></i>Descargar referencia
              </a>
            </div>
          </div>`;
      } else {
        container.innerHTML = `
          <div class="alert alert-info d-flex gap-2 align-items-center mb-0 py-2 small">
            <i class="bi bi-hourglass-split fs-5"></i>
            <span>${escHtml(d.error || 'La generación de referencias estará disponible próximamente.')}</span>
          </div>`;
      }
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger small mb-0">Error al cargar la referencia: ${e.message}</div>`;
    }
  }

  // ── Solicitud de Baja Temporal ───────────────────────────────────────────
  async function loadLeaveRequest() {
    const container = document.getElementById('leaveRequestContainer');
    if (!container) return;
    try {
      const res = await fetch(`/api/v1/permanence/user-program/${UP_ID}/leave-request`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderLeaveRequest(json.data);
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger small">Error al cargar solicitud: ${e.message}</div>`;
    }
  }

  function renderLeaveRequest(data) {
    const container = document.getElementById('leaveRequestContainer');
    if (!container) return;

    if (!data.archive_available) {
      container.innerHTML = `
        <p class="text-muted small mb-0">
          <i class="bi bi-info-circle me-1"></i>
          La solicitud de baja temporal no está disponible para tu programa actualmente.
        </p>`;
      return;
    }

    const sub = data.submission;

    if (!sub) {
      container.innerHTML = `
        <p class="text-muted small mb-2">
          Puedes solicitar una baja temporal subiendo el formulario firmado por tu director de tesis.
        </p>
        ${buildLeaveUploadForm()}`;
      bindLeaveUploadForm();
      return;
    }

    if (sub.status === 'review') {
      container.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-info text-dark"><i class="bi bi-hourglass-split me-1"></i>En revisión</span>
          <span class="small text-muted">Tu solicitud está siendo revisada por el coordinador.</span>
        </div>`;
      return;
    }

    if (sub.status === 'approved') {
      container.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Aprobada</span>
          <span class="small text-muted">Tu solicitud de baja temporal fue aprobada.</span>
        </div>`;
      return;
    }

    if (sub.status === 'rejected') {
      const motivo = sub.reviewer_comment
        ? `<div class="small text-danger mt-1">Motivo: ${escHtml(sub.reviewer_comment)}</div>`
        : '';
      container.innerHTML = `
        <div class="mb-3">
          <span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>Rechazada</span>
          ${motivo}
        </div>
        <p class="text-muted small mb-2">Puedes volver a subir la solicitud corregida.</p>
        ${buildLeaveUploadForm()}`;
      bindLeaveUploadForm();
    }
  }

  function buildLeaveUploadForm() {
    return `
      <form id="leaveUploadForm" class="d-flex align-items-center gap-2 flex-wrap">
        <input type="file" class="form-control form-control-sm leave-upload-input" id="leaveFile"
               accept=".pdf,.doc,.docx,.jpg,.png" required>
        <button type="submit" class="btn btn-sm btn-outline-secondary text-nowrap">
          <i class="bi bi-upload me-1"></i>Enviar solicitud
        </button>
      </form>`;
  }

  function bindLeaveUploadForm() {
    const form = document.getElementById('leaveUploadForm');
    if (!form) return;
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const file = document.getElementById('leaveFile')?.files[0];
      if (!file) return;
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await fetch(`/api/v1/permanence/user-program/${UP_ID}/leave-request`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: fd,
        });
        const json = await res.json();
        if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
        if (res.ok && !json.error) loadLeaveRequest();
        else btn.disabled = false;
      } catch (err) {
        btn.disabled = false;
        flashMsg('danger', 'Error al enviar la solicitud.');
      }
    });
  }

  // ── Init ─────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    loadPaymentReference();
    loadStudentDocs();
    loadLeaveRequest();
  });

  // ── Tiempo real ──────────────────────────────────────────────────────────
  function toast(level, message) {
    if (typeof showFlash === 'function') showFlash(level, message);
  }

  window.addEventListener('siiap:permanence:status_changed', (e) => {
    const data = e.detail || {};
    const messages = {
      semester_confirmed: { text: `Tu inscripción del semestre ${data.semester_number || ''} fue confirmada.`, level: 'success' },
      doc_reviewed:       { text: data.status === 'approved'
                               ? `Documento "${data.document_label || ''}" aprobado.`
                               : `Documento "${data.document_label || ''}" rechazado.`,
                            level: data.status === 'approved' ? 'success' : 'warning' },
      leave_decided:      { text: data.approved
                               ? 'Tu solicitud de baja temporal fue aprobada.'
                               : 'Tu solicitud de baja temporal fue rechazada.',
                            level: data.approved ? 'success' : 'warning' },
    };
    const m = messages[data.action];
    if (!m) return;
    toast(m.level, `${m.text} Actualizando...`);
    setTimeout(() => { window.location.reload(); }, 2000);
  });

  window.addEventListener('siiap:submission:reviewed', (e) => {
    const data = e.detail || {};
    const action = data.status === 'approved' ? 'aprobado' : 'rechazado';
    toast(data.status === 'approved' ? 'success' : 'warning', `Un documento ha sido ${action}. Actualizando...`);
    setTimeout(() => { window.location.reload(); }, 2000);
  });

  window.addEventListener('siiap:extension:decided', (e) => {
    const data = e.detail || {};
    const messages = {
      granted:   { text: 'Tu solicitud de prórroga fue aprobada.', level: 'success' },
      rejected:  { text: 'Tu solicitud de prórroga fue rechazada.', level: 'warning' },
      cancelled: { text: 'Tu solicitud de prórroga fue cancelada.', level: 'info' },
    };
    const m = messages[data.status];
    if (!m) return;
    toast(m.level, `${m.text} Actualizando...`);
    setTimeout(() => { window.location.reload(); }, 2000);
  });
})();

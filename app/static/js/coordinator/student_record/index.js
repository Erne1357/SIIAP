/* Student Record (Expediente) page logic. */
(function () {
  'use strict';

  const CFG = window.SIIAP_RECORD || {};
  const USER_ID = CFG.userId;
  if (!USER_ID) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  let RECORD = null;

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtDate(iso, opts) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-MX', opts || { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function fmtDateOnly(iso) {
    if (!iso) return '—';
    const d = new Date(iso + (iso.length <= 10 ? 'T00:00:00' : ''));
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  function flashMsg(level, msg) {
    if (typeof showFlash === 'function') showFlash(level, msg);
  }

  // ── Loaders ──────────────────────────────────────────────────────────────
  async function loadRecord() {
    try {
      const res = await fetch(`/api/v1/students/${USER_ID}/record`);
      const json = await res.json();
      if (!res.ok || json.error) {
        if (res.status === 403) {
          flashMsg('danger', 'No tienes permiso para ver este expediente.');
        }
        throw new Error(json.error?.message || 'Error');
      }
      RECORD = json.data;
      renderHeader();
      renderInfo();
      renderAcademic();
      renderDocuments();
      renderAcceptance();
      renderSemesters();
      renderInterview();
      renderEvents();
      renderDeferrals();
      renderHistory();
    } catch (e) {
      flashMsg('danger', `Error al cargar expediente: ${e.message}`);
    }
  }

  // ── Header ──────────────────────────────────────────────────────────────
  function renderHeader() {
    const u = RECORD.user;
    const programs = RECORD.programs || [];
    const headerName = document.getElementById('recordHeaderName');
    const headerMeta = document.getElementById('recordHeaderMeta');
    if (headerName) {
      headerName.textContent = `${u.first_name} ${u.last_name} ${u.mother_last_name || ''}`.trim();
    }
    if (headerMeta) {
      const parts = [];
      parts.push(u.email);
      if (u.control_number) parts.push(`N° Control: ${u.control_number}`);
      if (programs.length) parts.push(programs.map(p => p.program_name).join(', '));
      headerMeta.textContent = parts.join(' · ');
    }
  }

  // ── Info tab ────────────────────────────────────────────────────────────
  function renderInfo() {
    const u = RECORD.user;
    document.getElementById('recordAvatar').src = u.avatar_url + '?t=' + Date.now();
    document.getElementById('recordFullName').textContent =
      `${u.first_name} ${u.last_name} ${u.mother_last_name || ''}`.trim();
    document.getElementById('recordRole').textContent = u.role || '—';

    const fields = [
      ['Teléfono', u.phone], ['Celular', u.mobile_phone],
      ['Correo', u.email], ['Usuario', u.username],
      ['CURP', u.curp], ['RFC', u.rfc],
      ['NSS', u.nss], ['Cédula profesional', u.cedula_profesional],
      ['Fecha de nacimiento', u.birth_date ? fmtDateOnly(u.birth_date) : null],
      ['Lugar de nacimiento', u.birth_place],
      ['Dirección', u.address],
      ['Contacto emergencia', u.emergency_contact_name],
      ['Tel. emergencia', u.emergency_contact_phone],
      ['Parentesco', u.emergency_contact_relationship],
      ['Registro', fmtDate(u.registration_date)],
      ['Último acceso', fmtDate(u.last_login)],
    ];

    const grid = `
      <div class="info-grid">
        ${fields.map(([l, v]) => `
          <div class="info-cell">
            <span class="label">${escHtml(l)}</span>
            <div class="value">${escHtml(v || '—')}</div>
          </div>`).join('')}
      </div>
      <div class="mt-3 small text-muted">
        Estado del perfil:
        <span class="status-badge status-badge--${u.profile_completed ? 'approved' : 'pending'}">
          ${u.profile_completed ? 'Completo' : 'Incompleto'}
        </span>
      </div>`;

    document.getElementById('recordPersonalInfo').innerHTML = grid;

    // Photo actions
    const photoActionsEl = document.getElementById('recordPhotoActions');
    let photoHtml = '';
    if (u.photo_change_requested_at && !u.photo_change_allowed) {
      photoHtml += `
        <div class="alert alert-warning small mb-2 py-2">
          <i class="bi bi-clock-history me-1"></i>
          Solicitud pendiente desde ${escHtml(fmtDate(u.photo_change_requested_at))}.
        </div>
        <button type="button" class="btn btn-sm btn-success me-1" data-photo-action="approve">
          <i class="bi bi-check-lg me-1"></i>Habilitar cambio
        </button>
        <button type="button" class="btn btn-sm btn-outline-danger" data-photo-action="reject">
          <i class="bi bi-x-lg me-1"></i>Rechazar
        </button>`;
    }
    photoHtml += `
      <button type="button" class="btn btn-sm btn-outline-primary mt-1" data-photo-action="upload">
        <i class="bi bi-upload me-1"></i>Subir foto por el estudiante
      </button>`;
    photoActionsEl.innerHTML = photoHtml;
    photoActionsEl.querySelectorAll('[data-photo-action]').forEach(btn => {
      btn.addEventListener('click', () => handlePhotoAction(btn.dataset.photoAction));
    });

    // Edit button
    const editBtn = document.getElementById('btnEditPersonalInfo');
    if (editBtn) {
      editBtn.classList.remove('d-none');
      editBtn.addEventListener('click', openEditModal, { once: true });
    }
  }

  async function handlePhotoAction(action) {
    if (action === 'upload') {
      new bootstrap.Modal(document.getElementById('coordUploadPhotoModal')).show();
      return;
    }
    const approve = action === 'approve';
    const reason = approve ? null : (prompt('Motivo del rechazo (opcional):') || null);

    try {
      const res = await fetch(`/api/v1/users/${USER_ID}/photo/enable-change`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ approve, reason }),
      });
      const json = await res.json();
      if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
      if (res.ok && !json.error) await loadRecord();
    } catch (e) {
      flashMsg('danger', 'Error al procesar la solicitud.');
    }
  }

  // ── Edit modal ──────────────────────────────────────────────────────────
  function openEditModal() {
    const form = document.getElementById('editPersonalInfoForm');
    const u = RECORD.user;
    Array.from(form.elements).forEach(el => {
      if (el.name && Object.prototype.hasOwnProperty.call(u, el.name)) {
        el.value = u[el.name] == null ? '' : u[el.name];
      }
    });
    new bootstrap.Modal(document.getElementById('editPersonalInfoModal')).show();
  }

  document.getElementById('editPersonalInfoForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {};
    Array.from(form.elements).forEach(el => {
      if (el.name) payload[el.name] = el.value;
    });
    try {
      const res = await fetch(`/api/v1/students/${USER_ID}/personal-info`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
      if (res.ok && !json.error) {
        bootstrap.Modal.getInstance(document.getElementById('editPersonalInfoModal'))?.hide();
        await loadRecord();
      }
    } catch (err) {
      flashMsg('danger', 'Error al guardar cambios.');
    }
  });

  document.getElementById('coordUploadPhotoForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const res = await fetch(`/api/v1/users/${USER_ID}/photo`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: fd,
      });
      const json = await res.json();
      if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
      if (res.ok && !json.error) {
        bootstrap.Modal.getInstance(document.getElementById('coordUploadPhotoModal'))?.hide();
        e.target.reset();
        await loadRecord();
      }
    } catch (err) {
      flashMsg('danger', 'Error de red al subir foto.');
    }
  });

  // ── Other tabs ──────────────────────────────────────────────────────────
  function renderAcademic() {
    const programs = RECORD.programs || [];
    const el = document.getElementById('recordAcademic');
    if (!programs.length) {
      el.innerHTML = `<div class="card-body"><div class="empty-state empty-state--compact">
        <i class="empty-state__icon bi bi-mortarboard"></i>
        <h3 class="empty-state__title">Sin programa académico</h3>
      </div></div>`;
      return;
    }
    el.innerHTML = `<div class="card-body p-0"><div class="siiap-table-wrapper">
      <table class="table mb-0">
        <thead>
          <tr><th>Programa</th><th>Estado</th><th>Periodo admisión</th><th>Semestre</th><th>CONACyT</th><th>Inscripción</th></tr>
        </thead>
        <tbody>
          ${programs.map(p => `
            <tr>
              <td>${escHtml(p.program_name || '—')}</td>
              <td><span class="status-badge status-badge--${escHtml(p.admission_status || 'pending')}">${escHtml(p.admission_status || '—')}</span></td>
              <td>${escHtml(p.admission_period_name || '—')}</td>
              <td>${escHtml(p.current_semester || '—')}</td>
              <td>${p.has_conacyt_scholarship ? '<span class="badge bg-success-soft text-success-strong">Sí</span>' : '<span class="badge bg-secondary">No</span>'}</td>
              <td>${escHtml(fmtDateOnly(p.enrollment_date))}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div></div>`;
  }

  function statusBadge(status) {
    return `<span class="status-badge status-badge--${escHtml(status || 'pending')}">${escHtml(status || '—')}</span>`;
  }

  function docList(docs) {
    if (!docs || !docs.length) return `<div class="text-muted small px-3 py-2">Sin documentos.</div>`;
    return `<ul class="list-group list-group-flush">${docs.map(d => `
      <li class="list-group-item d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
          <div class="fw-medium">${escHtml(d.archive_name || 'Documento')}</div>
          <small class="text-muted">
            ${d.upload_date ? escHtml(fmtDate(d.upload_date)) : ''}
            ${d.semester ? ` · Semestre ${escHtml(d.semester)}` : ''}
          </small>
        </div>
        <div class="d-flex align-items-center gap-2">
          ${statusBadge(d.status)}
          ${d.file_url ? `<a href="${escHtml(d.file_url)}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a>` : ''}
        </div>
      </li>`).join('')}</ul>`;
  }

  function renderDocuments() {
    const grouped = RECORD.documents_by_phase || {};
    const adm = grouped.admission || [];
    const con = grouped.conclusion || [];
    const perm = grouped.permanence || {};
    const semKeys = Object.keys(perm).sort((a, b) => parseInt(a) - parseInt(b));
    const permCount = semKeys.reduce((acc, k) => acc + (perm[k]?.length || 0), 0);

    const acc = (id, title, count, body) => `
      <div class="accordion-item">
        <h2 class="accordion-header">
          <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#dh-${id}">
            <i class="bi bi-folder2-open me-2"></i>${escHtml(title)}
            <span class="badge bg-secondary ms-2">${count}</span>
          </button>
        </h2>
        <div id="dh-${id}" class="accordion-collapse collapse" data-bs-parent="#docsHistAcc">
          <div class="accordion-body p-0">${body}</div>
        </div>
      </div>`;

    const permBody = semKeys.map(s => `
      <div class="border-bottom">
        <div class="px-3 py-2 bg-body-tertiary fw-semibold small">Semestre ${escHtml(s)} · ${perm[s].length} documento(s)</div>
        ${docList(perm[s])}
      </div>`).join('') || `<div class="text-muted small px-3 py-2">Sin documentos.</div>`;

    document.getElementById('recordDocuments').innerHTML = `
      <div class="accordion" id="docsHistAcc">
        ${acc('adm', 'Admisión', adm.length, docList(adm))}
        ${acc('perm', 'Permanencia', permCount, permBody)}
        ${acc('con', 'Conclusión', con.length, docList(con))}
      </div>`;
  }

  function renderAcceptance() {
    const docs = RECORD.acceptance_documents || [];
    if (!docs.length) {
      document.getElementById('recordAcceptance').innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-file-earmark-check"></i>
          <h3 class="empty-state__title">Sin documentos de aceptación</h3>
        </div>`;
      return;
    }
    const labels = {
      acceptance_letter: 'Carta de Aceptación',
      course_schedule: 'Tira de Materias',
      enrollment_receipt: 'Boleta de Servicios Escolares',
      acceptance_opinion: 'Dictamen de Aceptación',
    };
    document.getElementById('recordAcceptance').innerHTML = `
      <div class="siiap-table-wrapper">
        <table class="table">
          <thead><tr><th>Tipo</th><th>Estado</th><th>Subido</th><th>Acciones</th></tr></thead>
          <tbody>
            ${docs.map(d => `
              <tr>
                <td>${escHtml(labels[d.document_type] || d.document_type)}</td>
                <td>${statusBadge(d.status)}</td>
                <td>${escHtml(fmtDate(d.uploaded_at))}</td>
                <td>${d.file_url ? `<a href="${escHtml(d.file_url)}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye me-1"></i>Ver</a>` : '—'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderSemesters() {
    const items = RECORD.semester_enrollments || [];
    if (!items.length) {
      document.getElementById('recordSemesters').innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-list-ol"></i>
          <h3 class="empty-state__title">Sin inscripciones registradas</h3>
        </div>`;
      return;
    }
    document.getElementById('recordSemesters').innerHTML = `
      <div class="siiap-table-wrapper">
        <table class="table">
          <thead><tr><th>Semestre</th><th>Periodo</th><th>Estado</th><th>Confirmado</th><th>Confirmado el</th><th>Comprobante</th></tr></thead>
          <tbody>
            ${items.map(s => `
              <tr>
                <td><span class="badge bg-info-soft text-info-strong">${escHtml(s.semester_number)}</span></td>
                <td>${escHtml(s.academic_period_name || '—')}</td>
                <td>${statusBadge(s.status)}</td>
                <td>${s.enrollment_confirmed ? '<i class="bi bi-check-circle-fill text-success"></i>' : '<i class="bi bi-x-circle text-muted"></i>'}</td>
                <td>${escHtml(fmtDate(s.confirmed_at))}</td>
                <td>${s.payment_proof_url ? `<a href="${escHtml(s.payment_proof_url)}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="bi bi-file-earmark-pdf"></i></a>` : '—'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderInterview() {
    const i = RECORD.interview;
    const el = document.getElementById('recordInterview');
    if (!i) {
      el.innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-chat-dots"></i>
          <h3 class="empty-state__title">Sin entrevista registrada</h3>
        </div>`;
      return;
    }
    el.innerHTML = `
      <h5 class="mb-2">${escHtml(i.event_title || 'Entrevista')}</h5>
      <p class="mb-1"><strong>Estado:</strong> ${statusBadge(i.status)}</p>
      <p class="mb-1"><strong>Fecha:</strong> ${escHtml(fmtDate(i.event_date, { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }))}</p>
      ${i.interviewer ? `<p class="mb-1"><strong>Entrevistador:</strong> ${escHtml(i.interviewer.name)} <small class="text-muted">(${escHtml(i.interviewer.email)})</small></p>` : ''}
      ${i.notes ? `<div class="alert alert-light small mt-3 mb-0"><strong>Notas:</strong><br>${escHtml(i.notes)}</div>` : ''}`;
  }

  function renderEvents() {
    const past = RECORD.events_attended || [];
    const upcoming = RECORD.upcoming_events || [];

    const renderList = (items, empty) => {
      if (!items.length) return `<p class="text-muted small mb-0">${empty}</p>`;
      return `<ul class="list-group list-group-flush">${items.map(ev => `
        <li class="list-group-item">
          <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
            <div>
              <div class="fw-medium">${escHtml(ev.title)}</div>
              <small class="text-muted">${escHtml(fmtDate(ev.event_date, { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }))}</small>
            </div>
            ${statusBadge(ev.attendance_status || ev.status)}
          </div>
        </li>`).join('')}</ul>`;
    };

    document.getElementById('recordEvents').innerHTML = `
      <h6 class="mb-2">Próximos / Inscrito</h6>
      ${renderList(upcoming, 'Sin eventos próximos.')}
      <hr>
      <h6 class="mb-2">Histórico</h6>
      ${renderList(past, 'Sin participación previa.')}`;
  }

  function renderDeferrals() {
    const items = RECORD.deferrals || [];
    if (!items.length) {
      document.getElementById('recordDeferrals').innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-pause-circle"></i>
          <h3 class="empty-state__title">Sin diferimientos</h3>
        </div>`;
      return;
    }
    document.getElementById('recordDeferrals').innerHTML = `
      <div class="siiap-table-wrapper">
        <table class="table">
          <thead><tr><th>#</th><th>Estado</th><th>Solicitado por</th><th>Periodo origen</th><th>Periodo destino</th><th>Creado</th></tr></thead>
          <tbody>
            ${items.map(d => `
              <tr>
                <td>${escHtml(d.deferral_number)}</td>
                <td>${statusBadge(d.status)}</td>
                <td>${escHtml(d.requested_by)}</td>
                <td>${escHtml(d.original_period_name || '—')}</td>
                <td>${escHtml(d.deferred_to_period_name || '—')}</td>
                <td>${escHtml(fmtDate(d.created_at))}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderHistory() {
    const items = RECORD.history || [];
    if (!items.length) {
      document.getElementById('recordHistory').innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-clock-history"></i>
          <h3 class="empty-state__title">Sin historial</h3>
        </div>`;
      return;
    }
    document.getElementById('recordHistory').innerHTML = `
      <ul class="list-group list-group-flush">
        ${items.map(h => `
          <li class="list-group-item">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
              <div>
                <div class="fw-medium">${escHtml(h.action_label || h.action)}</div>
                <small class="text-muted">${escHtml(h.details || '')}</small>
              </div>
              <small class="text-muted">${escHtml(fmtDate(h.timestamp, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }))}<br>${escHtml(h.admin_name || 'Sistema')}</small>
            </div>
          </li>`).join('')}
      </ul>`;
  }

  function setupBackLink() {
    const link = document.getElementById('recordBackLink');
    if (!link) return;
    // If there is real navigation history within same origin, prefer history.back().
    // Otherwise leave the href as the dashboard fallback (works on new tabs / direct links).
    const ref = document.referrer || '';
    const sameOrigin = ref && ref.startsWith(window.location.origin);
    const recordUrl = window.location.pathname;
    const refPath = sameOrigin ? new URL(ref).pathname : '';
    if (sameOrigin && refPath && refPath !== recordUrl && window.history.length > 1) {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        window.history.back();
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupBackLink();
    loadRecord();
  });
})();

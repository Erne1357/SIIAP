// app/static/js/coordinator/permanence.js
// Fase 6 + Iteración 3: Permanencia Semestral + Seguimiento Documental

'use strict';

class PermanenceManager {
  constructor(programId, activePeriodId) {
    this.programId = programId;
    this.activePeriodId = activePeriodId;
    this.students = [];
    this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    this.init();
  }

  init() {
    if (!this.programId) return;
    this.bindEvents();
    this.loadStudents();
    this.loadStats();
    this.bindTabEvents();
  }

  bindEvents() {
    // Selector de programa
    const progSel = document.getElementById('programSelector');
    if (progSel) {
      progSel.addEventListener('change', () => {
        window.location.href = `/coordinator/permanence/${progSel.value}`;
      });
    }

    // Búsqueda en tabla de estudiantes
    document.getElementById('searchInput')?.addEventListener('input', e => {
      this.filterTable(e.target.value);
    });

    // Confirmar inscripción
    document.getElementById('confirmEnrollBtn')?.addEventListener('click', () => {
      this.submitConfirmEnrollment();
    });

    // Actualizar estado semestral
    document.getElementById('confirmUpdateStatusBtn')?.addEventListener('click', () => {
      this.submitUpdateStatus();
    });

    // Botones nueva ventana
    document.getElementById('btnNewDeadline')?.addEventListener('click', () => {
      this.showCreateDeadlineModal();
    });
    document.getElementById('btnNewDeadlineEmpty')?.addEventListener('click', () => {
      this.showCreateDeadlineModal();
    });

    // Crear ventanas mensuales CONACyT
    document.getElementById('btnConacytMonthly')?.addEventListener('click', () => {
      this.createConacytMonthlyDeadlines();
    });

    // Auto-label al seleccionar archive en modal nueva ventana
    document.getElementById('deadlineArchiveId')?.addEventListener('change', e => {
      const opt = e.target.selectedOptions[0];
      const labelInput = document.getElementById('deadlineLabel');
      if (opt && opt.dataset.name && !labelInput.value.trim()) {
        labelInput.value = opt.dataset.name;
      }
    });

    // Guardar nueva ventana
    document.getElementById('btnSaveDeadline')?.addEventListener('click', () => {
      this.submitCreateDeadline();
    });

    // Revisar documento: aprobar / rechazar
    document.getElementById('btnApproveDoc')?.addEventListener('click', () => {
      this.submitReview('approved');
    });
    document.getElementById('btnRejectDoc')?.addEventListener('click', () => {
      this.submitReview('rejected');
    });

    // Aprobar / Rechazar baja temporal
    document.getElementById('btnApproveLeave')?.addEventListener('click', () => {
      this.submitLeaveDecision(true);
    });
    document.getElementById('btnRejectLeave')?.addEventListener('click', () => {
      this.submitLeaveDecision(false);
    });

    // Botón refrescar solicitudes
    document.getElementById('btnRefreshLeave')?.addEventListener('click', () => {
      this.loadLeaveRequestsTab();
    });
  }

  bindTabEvents() {
    document.getElementById('tab-leave')?.addEventListener('shown.bs.tab', () => {
      this.loadLeaveRequestsTab();
    });
    document.getElementById('tab-documents')?.addEventListener('shown.bs.tab', () => {
      this.loadDocumentsTabData();
    });
  }

  // ── Carga de datos ─────────────────────────────────────────────────────────

  async loadStudents() {
    this.showLoading(true);
    try {
      const res = await fetch(`/api/v1/permanence/program/${this.programId}/students`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      this.students = json.data;
      this.renderTable(this.students);
    } catch (e) {
      showFlash('danger', `Error al cargar estudiantes: ${e.message}`);
    } finally {
      this.showLoading(false);
    }
  }

  async loadStats() {
    try {
      const res = await fetch(`/api/v1/permanence/program/${this.programId}/stats`);
      const json = await res.json();
      if (!res.ok || json.error) return;
      this.renderStats(json.data);
    } catch (_) { /* silencioso */ }
  }

  async loadDocumentsTabData() {
    const loading = document.getElementById('deadlinesLoading');
    const empty = document.getElementById('deadlinesEmpty');
    const list = document.getElementById('deadlinesList');
    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    if (list) list.innerHTML = '';

    try {
      const [dlRes, pdRes] = await Promise.all([
        fetch(`/api/v1/permanence/program/${this.programId}/deadlines`),
        fetch(`/api/v1/permanence/program/${this.programId}/pending-documents`),
      ]);
      const [dlJson, pdJson] = await Promise.all([dlRes.json(), pdRes.json()]);
      loading?.classList.add('d-none');

      if (!dlRes.ok || dlJson.error) throw new Error(dlJson.error?.message || 'Error cargando ventanas');

      const deadlines = dlJson.data || [];
      const pendingDocs = pdRes.ok && !pdJson.error ? (pdJson.data || []) : [];

      // Agrupar pending por deadline_id
      const pendingByDeadline = {};
      for (const doc of pendingDocs) {
        const dlId = doc.submission.document_deadline_id;
        if (!pendingByDeadline[dlId]) pendingByDeadline[dlId] = [];
        pendingByDeadline[dlId].push(doc);
      }

      const badge = document.getElementById('deadlinesBadge');
      if (badge) {
        badge.textContent = deadlines.length;
        badge.style.display = deadlines.length ? '' : 'none';
      }

      if (!deadlines.length) {
        empty?.classList.remove('d-none');
        return;
      }
      list.innerHTML = deadlines
        .map(dl => this.renderDeadlineCard(dl, pendingByDeadline[dl.id] || []))
        .join('');
    } catch (e) {
      loading?.classList.add('d-none');
      showFlash('danger', `Error al cargar ventanas: ${e.message}`);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  renderStats(stats) {
    const container = document.getElementById('statsContainer');
    if (!container) return;
    const items = [
      { label: 'Total estudiantes', value: stats.total_students, icon: 'bi-people-fill', color: 'primary' },
      { label: 'Confirmados', value: stats.confirmed, icon: 'bi-check-circle-fill', color: 'success' },
      { label: 'Pendientes', value: stats.pending, icon: 'bi-hourglass-split', color: 'warning' },
      { label: 'Baja temporal', value: stats.on_leave, icon: 'bi-pause-circle-fill', color: 'secondary' },
    ];
    container.innerHTML = items.map(i => `
      <div class="card border-0 shadow-sm px-3 py-2 d-flex flex-row align-items-center gap-2">
        <i class="bi ${i.icon} text-${i.color} fs-4"></i>
        <div>
          <div class="fw-bold fs-5 lh-1">${i.value}</div>
          <div class="small text-muted">${i.label}</div>
        </div>
      </div>
    `).join('');
  }

  renderTable(students) {
    const tbody = document.getElementById('studentsTableBody');
    const empty = document.getElementById('emptyState');
    const table = document.getElementById('tableContainer');

    if (!students.length) {
      empty.classList.remove('d-none');
      table.classList.add('d-none');
      return;
    }
    empty.classList.add('d-none');
    table.classList.remove('d-none');

    tbody.innerHTML = students.map((s, i) => this.renderStudentRow(s, i)).join('');

  }

  renderStudentRow(s, index) {
    const up = s.user_program;
    const user = s.user;
    const ce = s.current_enrollment;

    const semesterBadge = `<span class="badge bg-info text-dark">Sem. ${up.current_semester || 1}</span>`;

    let periodCell = '<span class="text-muted small">—</span>';
    if (s.current_period) {
      periodCell = `<span class="small">${s.current_period.name}</span>`;
    }

    let statusCell = '';
    let actionCell = '';

    if (!this.activePeriodId) {
      statusCell = '<span class="badge bg-secondary">Sin periodo activo</span>';
      actionCell = '—';
    } else if (!ce) {
      statusCell = '<span class="badge bg-warning text-dark">Pendiente confirmación</span>';
      actionCell = `
        <button class="btn btn-sm btn-success" onclick="permanenceManager.showConfirmModal(${up.id}, '${this.escapeHtml(user.full_name)}')">
          <i class="bi bi-check-lg me-1"></i>Confirmar
        </button>`;
    } else {
      const statusMap = {
        active: ['bg-success', 'Activo'],
        completed: ['bg-primary', 'Completado'],
        on_leave: ['bg-secondary', 'Baja temporal'],
        dropped: ['bg-danger', 'Baja definitiva'],
        pending: ['bg-warning text-dark', 'Pendiente'],
      };
      const [cls, label] = statusMap[ce.status] || ['bg-secondary', ce.status];
      statusCell = `<span class="badge ${cls}">${label}</span>`;
      if (ce.enrollment_confirmed) {
        actionCell = `
          <div class="d-flex gap-1 justify-content-center">
            <button class="btn btn-sm btn-outline-secondary"
              onclick="permanenceManager.showUpdateStatusModal(${ce.id}, '${this.escapeHtml(user.full_name)}', '${ce.status}')">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-outline-info"
              onclick="permanenceManager.showHistoryByIndex(${index})">
              <i class="bi bi-clock-history"></i>
            </button>
          </div>`;
      } else {
        actionCell = `
          <button class="btn btn-sm btn-success" onclick="permanenceManager.showConfirmModal(${up.id}, '${this.escapeHtml(user.full_name)}')">
            <i class="bi bi-check-lg me-1"></i>Confirmar
          </button>`;
      }
    }

    // Columna CONACyT
    const conacytBadge = up.has_conacyt_scholarship
      ? `<span class="badge bg-success" title="Becario CONACyT activo"><i class="bi bi-patch-check-fill"></i></span>`
      : `<span class="badge bg-light text-muted border">—</span>`;
    const conacytToggle = `
      <button class="btn btn-sm ${up.has_conacyt_scholarship ? 'btn-outline-success' : 'btn-outline-secondary'} ms-1"
        title="${up.has_conacyt_scholarship ? 'Quitar beca CONACyT' : 'Marcar como becario CONACyT'}"
        onclick="permanenceManager.toggleConacyt(${up.id}, ${!up.has_conacyt_scholarship})">
        <i class="bi bi-toggles"></i>
      </button>`;

    return `
      <tr>
        <td>
          <div class="fw-semibold">${this.escapeHtml(user.full_name)}</div>
          <div class="small text-muted">${this.escapeHtml(user.email)}</div>
        </td>
        <td class="text-center">
          <span class="badge bg-dark font-monospace">${user.control_number || '—'}</span>
        </td>
        <td class="text-center">${semesterBadge}</td>
        <td class="text-center">${periodCell}</td>
        <td class="text-center">${statusCell}</td>
        <td class="text-center">${conacytBadge}${conacytToggle}</td>
        <td class="text-center">${actionCell}</td>
      </tr>`;
  }

  renderDeadlineCard(dl, pendingDocs = []) {
    const statusBadge = dl.is_currently_open
      ? '<span class="badge bg-success"><i class="bi bi-unlock-fill me-1"></i>Abierta</span>'
      : '<span class="badge bg-secondary"><i class="bi bi-lock-fill me-1"></i>Cerrada</span>';

    const closesAt = dl.closes_at
      ? `Cierra: ${new Date(dl.closes_at).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' })}`
      : 'Sin fecha límite';

    const opensAt = dl.opens_at
      ? `Abre: ${new Date(dl.opens_at).toLocaleDateString('es-MX', { day:'2-digit', month:'short' })}`
      : '';

    const toggleIcon = dl.is_open ? 'bi-lock-fill' : 'bi-unlock-fill';
    const toggleTitle = dl.is_open ? 'Cerrar ventana' : 'Abrir ventana';
    const toggleCls = dl.is_open ? 'btn-outline-secondary' : 'btn-outline-success';

    const pendingSection = pendingDocs.length ? `
      <div class="border-top mt-2 pt-2">
        <div class="small fw-semibold text-warning mb-2">
          <i class="bi bi-hourglass-split me-1"></i>${pendingDocs.length} entrega(s) por revisar
        </div>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <tbody>
              ${pendingDocs.map(d => {
                const sub = d.submission;
                const uploadDate = sub.upload_date
                  ? new Date(sub.upload_date).toLocaleDateString('es-MX', {day:'2-digit', month:'short', year:'numeric'})
                  : '—';
                const viewBtn = sub.file_path
                  ? `<a href="/files/doc/${sub.file_path}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2">
                       <i class="bi bi-eye"></i>
                     </a>`
                  : '';
                return `
                  <tr>
                    <td class="py-1">
                      <span class="fw-semibold small">${this.escapeHtml(d.user.full_name)}</span>
                      <span class="text-muted small ms-1 font-monospace">${d.user.control_number || ''}</span>
                    </td>
                    <td class="py-1 text-muted small">${uploadDate}</td>
                    <td class="py-1 text-end">
                      <div class="d-flex gap-1 justify-content-end">
                        ${viewBtn}
                        <button class="btn btn-sm btn-success py-0 px-2"
                          onclick="permanenceManager.showReviewModal(${sub.id}, '${this.escapeHtml(d.user.full_name)}', '${this.escapeHtml(d.deadline_label)}')">
                          <i class="bi bi-check-lg"></i>
                        </button>
                        <button class="btn btn-sm btn-danger py-0 px-2"
                          onclick="permanenceManager.showReviewModal(${sub.id}, '${this.escapeHtml(d.user.full_name)}', '${this.escapeHtml(d.deadline_label)}', true)">
                          <i class="bi bi-x-lg"></i>
                        </button>
                      </div>
                    </td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>` : '';

    return `
      <div class="card mb-2">
        <div class="card-body py-2 px-3">
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <div class="flex-grow-1">
              <div class="fw-semibold">${this.escapeHtml(dl.label)}</div>
              <div class="small text-muted">
                ${this.escapeHtml(dl.archive_name || '')}
                &nbsp;·&nbsp; Secuencia: ${dl.sequence}
                ${opensAt ? '&nbsp;·&nbsp; ' + opensAt : ''}
                &nbsp;·&nbsp; ${closesAt}
              </div>
            </div>
            <div class="d-flex align-items-center gap-2">
              ${statusBadge}
              <span class="badge bg-light text-dark border">
                ${dl.stats.total} entregas
                ${dl.stats.approved ? `· <span class="text-success">${dl.stats.approved} ✓</span>` : ''}
              </span>
              <button class="btn btn-sm ${toggleCls}" title="${toggleTitle}"
                onclick="permanenceManager.toggleDeadline(${dl.id}, ${!dl.is_open})">
                <i class="bi ${toggleIcon}"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" title="Eliminar ventana"
                onclick="permanenceManager.deleteDeadline(${dl.id}, '${this.escapeHtml(dl.label)}')">
                <i class="bi bi-trash3"></i>
              </button>
            </div>
          </div>
          ${pendingSection}
        </div>
      </div>`;
  }

  // ── Acciones: Estudiantes ───────────────────────────────────────────────────

  showConfirmModal(userProgramId, studentName) {
    document.getElementById('confirmEnrollStudentName').textContent = studentName;
    document.getElementById('confirmEnrollUserProgramId').value = userProgramId;
    document.getElementById('confirmEnrollNotes').value = '';
    new bootstrap.Modal(document.getElementById('confirmEnrollmentModal')).show();
  }

  async submitConfirmEnrollment() {
    const upId = parseInt(document.getElementById('confirmEnrollUserProgramId').value);
    const notes = document.getElementById('confirmEnrollNotes').value.trim();
    bootstrap.Modal.getInstance(document.getElementById('confirmEnrollmentModal'))?.hide();

    try {
      const res = await fetch(`/api/v1/permanence/user-program/${upId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ academic_period_id: this.activePeriodId, notes: notes || null }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) {
        await this.loadStudents();
        await this.loadStats();
      }
    } catch (e) {
      showFlash('danger', `Error al confirmar inscripción: ${e.message}`);
    }
  }

  showUpdateStatusModal(enrollmentId, studentName, currentStatus) {
    document.getElementById('updateStatusStudentName').textContent = studentName;
    document.getElementById('updateStatusEnrollmentId').value = enrollmentId;
    document.getElementById('updateStatusSelect').value = currentStatus;
    document.getElementById('updateStatusNotes').value = '';
    new bootstrap.Modal(document.getElementById('updateStatusModal')).show();
  }

  async submitUpdateStatus() {
    const seId = parseInt(document.getElementById('updateStatusEnrollmentId').value);
    const newStatus = document.getElementById('updateStatusSelect').value;
    const notes = document.getElementById('updateStatusNotes').value.trim();
    bootstrap.Modal.getInstance(document.getElementById('updateStatusModal'))?.hide();

    try {
      const res = await fetch(`/api/v1/permanence/semester-enrollment/${seId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ status: newStatus, notes: notes || null }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) await this.loadStudents();
    } catch (e) {
      showFlash('danger', `Error al actualizar estado: ${e.message}`);
    }
  }

  showHistoryByIndex(index) {
    const s = this.students[index];
    if (!s) return;
    this.showHistory(s.user.full_name, s.history);
  }

  showHistory(studentName, history) {
    document.getElementById('historyStudentName').textContent = studentName;
    const container = document.getElementById('historyContent');
    if (!history.length) {
      container.innerHTML = '<p class="text-muted text-center py-3">Sin historial semestral registrado.</p>';
    } else {
      const statusMap = {
        active: ['bg-success', 'Activo'],
        completed: ['bg-primary', 'Completado'],
        on_leave: ['bg-secondary', 'Baja temporal'],
        dropped: ['bg-danger', 'Baja definitiva'],
        pending: ['bg-warning text-dark', 'Pendiente'],
      };
      container.innerHTML = `
        <table class="table table-sm table-bordered">
          <thead class="table-light">
            <tr>
              <th class="text-center">Semestre</th>
              <th>Periodo</th>
              <th class="text-center">Estado</th>
              <th class="text-center">Confirmado</th>
            </tr>
          </thead>
          <tbody>
            ${history.map(h => {
              const [cls, label] = statusMap[h.status] || ['bg-secondary', h.status];
              const confirmed = h.enrollment_confirmed
                ? '<i class="bi bi-check-circle-fill text-success"></i>'
                : '<i class="bi bi-dash-circle text-muted"></i>';
              return `
                <tr>
                  <td class="text-center fw-bold">Sem. ${h.semester_number}</td>
                  <td>${this.escapeHtml(h.period_name)} <span class="badge bg-light text-dark border">${h.period_code}</span></td>
                  <td class="text-center"><span class="badge ${cls}">${label}</span></td>
                  <td class="text-center">${confirmed}</td>
                </tr>`;
            }).join('')}
          </tbody>
        </table>`;
    }
    new bootstrap.Modal(document.getElementById('historyModal')).show();
  }

  // ── Movilidad / Baja Temporal ───────────────────────────────────────────────

  async loadLeaveRequestsTab() {
    const loading = document.getElementById('leaveLoading');
    const empty = document.getElementById('leaveEmpty');
    const list = document.getElementById('leaveList');
    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    if (list) list.innerHTML = '';

    try {
      const res = await fetch(`/api/v1/permanence/program/${this.programId}/leave-requests`);
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      const requests = json.data || [];

      // Actualizar badge
      const badge = document.getElementById('leaveBadge');
      if (badge) {
        badge.textContent = requests.length;
        badge.style.display = requests.length ? '' : 'none';
      }

      if (!requests.length) {
        empty?.classList.remove('d-none');
      } else {
        this.renderLeaveRequests(requests);
      }
    } catch (e) {
      if (list) list.innerHTML = `<div class="alert alert-danger m-2 small">Error al cargar solicitudes: ${e.message}</div>`;
    } finally {
      loading?.classList.add('d-none');
    }
  }

  renderLeaveRequests(requests) {
    const list = document.getElementById('leaveList');
    if (!list) return;
    list.innerHTML = requests.map(r => {
      const sub = r.submission;
      const uploadDate = sub.upload_date
        ? new Date(sub.upload_date).toLocaleDateString('es-MX', {day:'2-digit', month:'short', year:'numeric'})
        : '—';
      return `
        <div class="border rounded p-3 mb-2 d-flex flex-wrap align-items-center gap-3">
          <div class="flex-grow-1">
            <div class="fw-semibold">${this.escapeHtml(r.user.full_name)}</div>
            <div class="small text-muted">
              N° Control: ${this.escapeHtml(r.user.control_number || '—')}
              &nbsp;·&nbsp; Semestre ${r.current_semester || '—'}
              &nbsp;·&nbsp; Subida: ${uploadDate}
            </div>
          </div>
          <div class="d-flex gap-2 flex-shrink-0">
            ${r.file_url ? `<a href="${r.file_url}" target="_blank" class="btn btn-sm btn-outline-secondary">
              <i class="bi bi-file-earmark-text me-1"></i>Ver
            </a>` : ''}
            <button class="btn btn-sm btn-success"
              onclick="permanenceManager.showLeaveModal(${sub.id}, '${this.escapeHtml(r.user.full_name)}', ${r.current_semester || 0}, '${r.file_url || ''}')">
              <i class="bi bi-check-lg me-1"></i>Revisar
            </button>
          </div>
        </div>`;
    }).join('');
  }

  showLeaveModal(submissionId, studentName, semester, fileUrl) {
    document.getElementById('leaveSubmissionId').value = submissionId;
    document.getElementById('leaveStudentName').textContent = studentName;
    document.getElementById('leaveStudentSemester').textContent = semester || '—';
    document.getElementById('leaveNotes').value = '';
    const fileLink = document.getElementById('leaveFileLink');
    if (fileLink) {
      fileLink.href = fileUrl || '#';
      fileLink.style.display = fileUrl ? '' : 'none';
    }
    new bootstrap.Modal(document.getElementById('processLeaveModal')).show();
  }

  async submitLeaveDecision(approve) {
    const submissionId = document.getElementById('leaveSubmissionId')?.value;
    const notes = document.getElementById('leaveNotes')?.value.trim() || null;
    if (!submissionId) return;

    const btn = approve
      ? document.getElementById('btnApproveLeave')
      : document.getElementById('btnRejectLeave');
    btn.disabled = true;

    try {
      const res = await fetch(`/api/v1/permanence/submissions/${submissionId}/leave-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ approve, notes }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) {
        bootstrap.Modal.getInstance(document.getElementById('processLeaveModal'))?.hide();
        await this.loadLeaveRequestsTab();
        await this.loadStudents(); // refrescar badge CONACyT y estado
      }
    } catch (e) {
      showFlash('danger', `Error al procesar solicitud: ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  }

  async createConacytMonthlyDeadlines() {
    const btn = document.getElementById('btnConacytMonthly');
    btn.disabled = true;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Creando...';
    try {
      const res = await fetch(`/api/v1/permanence/program/${this.programId}/deadlines/conacyt-monthly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({}),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && json.data?.created > 0) {
        await this.loadDocumentsTabData();
      }
    } catch (e) {
      showFlash('danger', `Error al crear ventanas CONACyT: ${e.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }

  async toggleConacyt(userProgramId, newValue) {
    try {
      const res = await fetch(`/api/v1/permanence/user-program/${userProgramId}/conacyt-scholarship`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ value: newValue }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) await this.loadStudents();
    } catch (e) {
      showFlash('danger', `Error al actualizar beca CONACyT: ${e.message}`);
    }
  }

  // ── Acciones: Ventanas de Entrega ─────────────────────────────────────────

  showCreateDeadlineModal() {
    document.getElementById('deadlineArchiveId').value = '';
    document.getElementById('deadlineLabel').value = '';
    document.getElementById('deadlineSequence').value = '1';
    document.getElementById('deadlineOpensAt').value = '';
    document.getElementById('deadlineClosesAt').value = '';
    new bootstrap.Modal(document.getElementById('createDeadlineModal')).show();
  }

  async submitCreateDeadline() {
    const archiveId = parseInt(document.getElementById('deadlineArchiveId').value);
    const label = document.getElementById('deadlineLabel').value.trim();
    const sequence = parseInt(document.getElementById('deadlineSequence').value) || 1;
    const periodId = parseInt(document.getElementById('deadlinePeriodId').value);
    const opensAt = document.getElementById('deadlineOpensAt').value || null;
    const closesAt = document.getElementById('deadlineClosesAt').value || null;

    if (!archiveId || !label) {
      showFlash('warning', 'Selecciona un documento y escribe una etiqueta.');
      return;
    }

    bootstrap.Modal.getInstance(document.getElementById('createDeadlineModal'))?.hide();

    try {
      const res = await fetch(`/api/v1/permanence/program/${this.programId}/deadlines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({
          archive_id: archiveId,
          label,
          sequence,
          academic_period_id: periodId || null,
          opens_at: opensAt,
          closes_at: closesAt,
        }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) this.loadDocumentsTabData();
    } catch (e) {
      showFlash('danger', `Error al crear ventana: ${e.message}`);
    }
  }

  async toggleDeadline(deadlineId, isOpen) {
    try {
      const res = await fetch(`/api/v1/permanence/deadlines/${deadlineId}/toggle`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ is_open: isOpen }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) this.loadDocumentsTabData();
    } catch (e) {
      showFlash('danger', `Error al actualizar ventana: ${e.message}`);
    }
  }

  deleteDeadline(deadlineId, label) {
    document.getElementById('deleteDeadlineId').value = deadlineId;
    document.getElementById('deleteDeadlineLabel').textContent = label;
    new bootstrap.Modal(document.getElementById('deleteDeadlineModal')).show();
  }

  async _confirmDeleteDeadline() {
    const deadlineId = document.getElementById('deleteDeadlineId').value;
    bootstrap.Modal.getInstance(document.getElementById('deleteDeadlineModal'))?.hide();
    try {
      const res = await fetch(`/api/v1/permanence/deadlines/${deadlineId}`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': this.csrfToken },
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) this.loadDocumentsTabData();
    } catch (e) {
      showFlash('danger', `Error al eliminar ventana: ${e.message}`);
    }
  }

  // ── Acciones: Revisión de Documentos ─────────────────────────────────────

  showReviewModal(submissionId, studentName, deadlineLabel, focusReject = false) {
    document.getElementById('reviewDocSubmissionId').value = submissionId;
    document.getElementById('reviewDocStudentName').textContent = studentName;
    document.getElementById('reviewDocLabel').textContent = deadlineLabel;
    document.getElementById('reviewDocNotes').value = '';
    if (focusReject) {
      document.getElementById('reviewDocNotes').placeholder = 'Motivo del rechazo (requerido)...';
    } else {
      document.getElementById('reviewDocNotes').placeholder = 'Comentarios opcionales...';
    }
    new bootstrap.Modal(document.getElementById('reviewDocModal')).show();
  }

  async submitReview(status) {
    const subId = parseInt(document.getElementById('reviewDocSubmissionId').value);
    const notes = document.getElementById('reviewDocNotes').value.trim();

    if (status === 'rejected' && !notes) {
      showFlash('warning', 'Escribe el motivo del rechazo antes de continuar.');
      return;
    }

    bootstrap.Modal.getInstance(document.getElementById('reviewDocModal'))?.hide();

    try {
      const res = await fetch(`/api/v1/permanence/submissions/${subId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ status, notes: notes || null }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) this.loadDocumentsTabData();
    } catch (e) {
      showFlash('danger', `Error al revisar documento: ${e.message}`);
    }
  }

  // ── Utilidades ─────────────────────────────────────────────────────────────

  filterTable(query) {
    const q = query.toLowerCase();
    const filtered = this.students.filter(s =>
      s.user.full_name.toLowerCase().includes(q) ||
      (s.user.control_number || '').toLowerCase().includes(q) ||
      (s.user.email || '').toLowerCase().includes(q)
    );
    this.renderTable(filtered);
  }

  showLoading(show) {
    document.getElementById('loadingSpinner')?.classList.toggle('d-none', !show);
    if (show) document.getElementById('tableContainer')?.classList.add('d-none');
  }

  escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}

// Inicializar
let permanenceManager;
document.addEventListener('DOMContentLoaded', () => {
  if (typeof PROGRAM_ID !== 'undefined' && PROGRAM_ID) {
    permanenceManager = new PermanenceManager(PROGRAM_ID, ACTIVE_PERIOD_ID);
  }

  // ── Confirmar eliminación de ventana ──
  document.getElementById('btnConfirmDeleteDeadline')?.addEventListener('click', () => {
    permanenceManager?._confirmDeleteDeadline();
  });

  // ── Tiempo real: nuevo documento de permanencia recibido ──
  window.addEventListener('siiap:submission:new', (e) => {
    const data = e.detail;
    if (!data || !permanenceManager) return;
    // Solo recargar si el evento es del programa que estamos viendo
    if (data.program_id && String(data.program_id) !== String(PROGRAM_ID)) return;

    if (data.context === 'permanence') {
      permanenceManager.loadStats();
      permanenceManager.loadDocumentsTabData();
    } else if (data.context === 'leave_request') {
      permanenceManager.loadStats();
      permanenceManager.loadLeaveRequestsTab();
    }
  });
});

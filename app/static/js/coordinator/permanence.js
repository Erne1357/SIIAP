// app/static/js/coordinator/permanence.js
// Fase 6: Permanencia Semestral — Coordinador

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
  }

  bindEvents() {
    // Selector de programa
    const progSel = document.getElementById('programSelector');
    if (progSel) {
      progSel.addEventListener('change', () => {
        const newId = parseInt(progSel.value);
        window.location.href = `/coordinator/permanence/${newId}`;
      });
    }

    // Búsqueda en tabla
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', () => this.filterTable(searchInput.value));
    }

    // Confirmar inscripción
    document.getElementById('confirmEnrollBtn')?.addEventListener('click', () => {
      this.submitConfirmEnrollment();
    });

    // Actualizar estado
    document.getElementById('confirmUpdateStatusBtn')?.addEventListener('click', () => {
      this.submitUpdateStatus();
    });
  }

  // ── Carga de datos ────────────────────────────────────────────────────────

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

  // ── Render ────────────────────────────────────────────────────────────────

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

    tbody.innerHTML = students.map(s => this.renderStudentRow(s)).join('');
  }

  renderStudentRow(s) {
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
              onclick="permanenceManager.showHistory('${this.escapeHtml(user.full_name)}', ${JSON.stringify(s.history).replace(/"/g, '&quot;')})">
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
        <td class="text-center">${actionCell}</td>
      </tr>`;
  }

  // ── Acciones ──────────────────────────────────────────────────────────────

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
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({
          academic_period_id: this.activePeriodId,
          notes: notes || null,
        }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) {
        await this.loadStudents();
        await this.loadStats();
      }
    } catch (e) {
      showFlash('danger', `Error al confirmar inscripcion: ${e.message}`);
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
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({ status: newStatus, notes: notes || null }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => showFlash(f.level, f.message));
      if (res.ok && !json.error) {
        await this.loadStudents();
      }
    } catch (e) {
      showFlash('danger', `Error al actualizar estado: ${e.message}`);
    }
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
                ? '<span class="text-success"><i class="bi bi-check-circle-fill"></i></span>'
                : '<span class="text-muted"><i class="bi bi-dash-circle"></i></span>';
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

  // ── Utilidades ────────────────────────────────────────────────────────────

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
    const spinner = document.getElementById('loadingSpinner');
    const table = document.getElementById('tableContainer');
    spinner?.classList.toggle('d-none', !show);
    if (show) table?.classList.add('d-none');
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
});

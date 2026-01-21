/**
 * Deliberation Management for Coordinators
 */
class DeliberationManager {
    constructor() {
        this.programSelector = document.getElementById('programSelector');
        this.statsContainer = document.getElementById('statsContainer');
        this.currentProgramId = this.programSelector?.value || null;

        // Modals
        this.decisionModal = new bootstrap.Modal(document.getElementById('decisionModal'));
        this.startDeliberationModal = new bootstrap.Modal(document.getElementById('startDeliberationModal'));

        this.init();
    }

    init() {
        this.bindEvents();
        if (this.currentProgramId) {
            this.loadStats();
            this.loadPendingInterview();
        }
    }

    bindEvents() {
        // Program selector change
        if (this.programSelector) {
            this.programSelector.addEventListener('change', () => {
                this.currentProgramId = this.programSelector.value;
                this.loadStats();
                this.loadCurrentTab();
            });
        }

        // Tab changes
        document.querySelectorAll('#statusTabs button[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const status = e.target.dataset.status;
                if (status === 'pending_interview') {
                    this.loadPendingInterview();
                } else {
                    this.loadApplicants(status);
                }
            });
        });

        // Rejection type change
        document.getElementById('rejectionType')?.addEventListener('change', (e) => {
            const correctionSection = document.getElementById('correctionSection');
            correctionSection.style.display = e.target.value === 'partial' ? 'block' : 'none';
        });

        // Confirm decision
        document.getElementById('confirmDecisionBtn')?.addEventListener('click', () => {
            this.submitDecision();
        });

        // Confirm start deliberation
        document.getElementById('confirmStartDelibBtn')?.addEventListener('click', () => {
            this.startDeliberation();
        });
    }

    loadCurrentTab() {
        const activeTab = document.querySelector('#statusTabs button.active');
        if (activeTab) {
            const status = activeTab.dataset.status;
            if (status === 'pending_interview') {
                this.loadPendingInterview();
            } else {
                this.loadApplicants(status);
            }
        }
    }

    async loadPendingInterview() {
        if (!this.currentProgramId) return;

        const tbody = document.querySelector('#pendingInterviewTable tbody');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4"><span class="loading-spinner"></span> Cargando...</td></tr>';

        try {
            const response = await fetch(`/api/v1/deliberation/program/${this.currentProgramId}/pending-interview`);
            const result = await response.json();

            if (result.error) {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">Error: ${result.error.message}</td></tr>`;
                return;
            }

            // Update badge count
            document.getElementById('pendingInterviewCount').textContent = result.meta?.count || 0;

            if (!result.data || result.data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="empty-state">
                            <i class="bi bi-inbox"></i>
                            <p>No hay aspirantes con entrevista agendada pendiente de marcar</p>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = result.data.map(item => this.renderPendingInterviewRow(item)).join('');

        } catch (error) {
            console.error('Error loading pending interviews:', error);
            tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-danger">Error al cargar datos</td></tr>';
        }
    }

    renderPendingInterviewRow(item) {
        const user = item.user;
        const up = item.user_program;
        const formatDate = (dateStr) => {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' });
        };

        return `
            <tr>
                <td class="applicant-name">${user.full_name}</td>
                <td class="applicant-email">${user.email}</td>
                <td>${user.curp || '-'}</td>
                <td class="text-center">${formatDate(up.enrollment_date)}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-success btn-action"
                            onclick="deliberationManager.markInterviewCompleted(${user.id}, ${up.program_id}, '${user.full_name}')">
                        <i class="bi bi-check2-circle"></i> Marcar Completada
                    </button>
                </td>
            </tr>
        `;
    }

    async markInterviewCompleted(userId, programId, applicantName) {
        if (!confirm(`¿Confirmas que ${applicantName} completó su entrevista?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/v1/deliberation/user/${userId}/program/${programId}/interview-completed`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            });

            const result = await response.json();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadPendingInterview();
            }
        } catch (error) {
            console.error('Error marking interview completed:', error);
            this.showToast('Error al marcar entrevista', 'danger');
        }
    }

    async loadStats() {
        if (!this.currentProgramId) return;

        try {
            const response = await fetch(`/api/v1/deliberation/program/${this.currentProgramId}/stats`);
            const result = await response.json();

            if (result.error) {
                console.error('Error loading stats:', result.error);
                return;
            }

            const stats = result.data;

            // Update tab badges
            document.getElementById('interviewCompletedCount').textContent = stats.interview_completed || 0;
            document.getElementById('deliberationCount').textContent = stats.deliberation || 0;
            document.getElementById('acceptedCount').textContent = stats.accepted || 0;
            document.getElementById('rejectedCount').textContent = stats.rejected || 0;

            // Update stats cards if container exists
            if (this.statsContainer) {
                this.statsContainer.innerHTML = `
                    <div class="stat-card stat-interview">
                        <div class="stat-value">${stats.interview_completed || 0}</div>
                        <div class="stat-label">Entrevista Completada</div>
                    </div>
                    <div class="stat-card stat-deliberation">
                        <div class="stat-value">${stats.deliberation || 0}</div>
                        <div class="stat-label">En Deliberacion</div>
                    </div>
                    <div class="stat-card stat-accepted">
                        <div class="stat-value">${stats.accepted || 0}</div>
                        <div class="stat-label">Aceptados</div>
                    </div>
                    <div class="stat-card stat-rejected">
                        <div class="stat-value">${stats.rejected || 0}</div>
                        <div class="stat-label">Rechazados</div>
                    </div>
                `;
            }

            // Also load pending interview count separately
            this.loadPendingInterviewCount();
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadPendingInterviewCount() {
        if (!this.currentProgramId) return;

        try {
            const response = await fetch(`/api/v1/deliberation/program/${this.currentProgramId}/pending-interview`);
            const result = await response.json();

            if (!result.error) {
                document.getElementById('pendingInterviewCount').textContent = result.meta?.count || 0;
            }
        } catch (error) {
            console.error('Error loading pending interview count:', error);
        }
    }

    async loadApplicants(status) {
        if (!this.currentProgramId) return;

        const tableId = this.getTableIdForStatus(status);
        const tbody = document.querySelector(`#${tableId} tbody`);

        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><span class="loading-spinner"></span> Cargando...</td></tr>';

        try {
            const response = await fetch(`/api/v1/deliberation/program/${this.currentProgramId}/by-status/${status}`);
            const result = await response.json();

            if (result.error) {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Error: ${result.error.message}</td></tr>`;
                return;
            }

            if (!result.data || result.data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="empty-state">
                            <i class="bi bi-inbox"></i>
                            <p>No hay aspirantes en este estado</p>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = result.data.map(item => this.renderApplicantRow(item, status)).join('');

        } catch (error) {
            console.error('Error loading applicants:', error);
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-danger">Error al cargar datos</td></tr>';
        }
    }

    getTableIdForStatus(status) {
        const mapping = {
            'interview_completed': 'interviewCompletedTable',
            'deliberation': 'deliberationTable',
            'accepted': 'acceptedTable',
            'rejected': 'rejectedTable'
        };
        return mapping[status] || 'interviewCompletedTable';
    }

    renderApplicantRow(item, status) {
        const user = item.user;
        const up = item.user_program;
        const formatDate = (dateStr) => {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' });
        };

        switch (status) {
            case 'interview_completed':
                return `
                    <tr>
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td>${user.curp || '-'}</td>
                        <td class="text-center">${formatDate(up.enrollment_date)}</td>
                        <td class="text-center">
                            <div class="btn-group-actions">
                                <button class="btn btn-sm btn-primary btn-action"
                                        onclick="deliberationManager.showStartDeliberation(${user.id}, ${up.program_id}, '${user.full_name}')">
                                    <i class="bi bi-play-fill"></i> Iniciar
                                </button>
                            </div>
                        </td>
                    </tr>
                `;

            case 'deliberation':
                return `
                    <tr>
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td class="text-center">${formatDate(up.deliberation_started_at)}</td>
                        <td class="text-center">
                            <div class="btn-group-actions">
                                <button class="btn btn-sm btn-success btn-action"
                                        onclick="deliberationManager.showDecisionModal(${user.id}, ${up.program_id}, '${user.full_name}', 'accept')">
                                    <i class="bi bi-check-lg"></i> Aceptar
                                </button>
                                <button class="btn btn-sm btn-danger btn-action"
                                        onclick="deliberationManager.showDecisionModal(${user.id}, ${up.program_id}, '${user.full_name}', 'reject')">
                                    <i class="bi bi-x-lg"></i> Rechazar
                                </button>
                            </div>
                        </td>
                    </tr>
                `;

            case 'accepted':
                return `
                    <tr>
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td class="text-center">${formatDate(up.decision_at)}</td>
                        <td class="notes-cell">${up.decision_notes || '-'}</td>
                    </tr>
                `;

            case 'rejected':
                const rejectionBadge = up.rejection_type === 'partial'
                    ? '<span class="badge badge-partial">Correcciones</span>'
                    : '<span class="badge badge-full">Definitivo</span>';
                const resetBtn = up.rejection_type === 'partial'
                    ? `<button class="btn btn-sm btn-outline-primary btn-action"
                               onclick="deliberationManager.resetApplicant(${user.id}, ${up.program_id})">
                           <i class="bi bi-arrow-counterclockwise"></i> Reiniciar
                       </button>`
                    : '';

                return `
                    <tr>
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td class="text-center">${rejectionBadge}</td>
                        <td class="text-center">${formatDate(up.decision_at)}</td>
                        <td class="notes-cell">${up.decision_notes || up.correction_required || '-'}</td>
                        <td class="text-center">${resetBtn}</td>
                    </tr>
                `;

            default:
                return '';
        }
    }

    showStartDeliberation(userId, programId, applicantName) {
        document.getElementById('startDelibUserId').value = userId;
        document.getElementById('startDelibProgramId').value = programId;
        document.getElementById('startDelibApplicantName').textContent = applicantName;
        this.startDeliberationModal.show();
    }

    async startDeliberation() {
        const userId = document.getElementById('startDelibUserId').value;
        const programId = document.getElementById('startDelibProgramId').value;

        try {
            const response = await fetch(`/api/v1/deliberation/user/${userId}/program/${programId}/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            });

            const result = await response.json();

            this.startDeliberationModal.hide();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('interview_completed');
            }
        } catch (error) {
            console.error('Error starting deliberation:', error);
            this.showToast('Error al iniciar deliberacion', 'danger');
        }
    }

    showDecisionModal(userId, programId, applicantName, action) {
        document.getElementById('decisionUserId').value = userId;
        document.getElementById('decisionProgramId').value = programId;
        document.getElementById('decisionAction').value = action;
        document.getElementById('decisionApplicantName').textContent = applicantName;
        document.getElementById('decisionNotes').value = '';

        // Show/hide rejection section
        const rejectionSection = document.getElementById('rejectionSection');
        const correctionSection = document.getElementById('correctionSection');
        const modalTitle = document.getElementById('decisionModalTitle');
        const confirmBtn = document.getElementById('confirmDecisionBtn');

        if (action === 'reject') {
            rejectionSection.style.display = 'block';
            correctionSection.style.display = 'none';
            document.getElementById('rejectionType').value = 'full';
            modalTitle.textContent = 'Rechazar Aspirante';
            confirmBtn.className = 'btn btn-danger';
            confirmBtn.textContent = 'Confirmar Rechazo';
        } else {
            rejectionSection.style.display = 'none';
            modalTitle.textContent = 'Aceptar Aspirante';
            confirmBtn.className = 'btn btn-success';
            confirmBtn.textContent = 'Confirmar Aceptacion';
        }

        this.decisionModal.show();
    }

    async submitDecision() {
        const userId = document.getElementById('decisionUserId').value;
        const programId = document.getElementById('decisionProgramId').value;
        const action = document.getElementById('decisionAction').value;
        const notes = document.getElementById('decisionNotes').value;

        let endpoint, body;

        if (action === 'accept') {
            endpoint = `/api/v1/deliberation/user/${userId}/program/${programId}/accept`;
            body = { notes };
        } else {
            const rejectionType = document.getElementById('rejectionType').value;
            const correctionRequired = document.getElementById('correctionRequired').value;
            endpoint = `/api/v1/deliberation/user/${userId}/program/${programId}/reject`;
            body = { rejection_type: rejectionType, notes, correction_required: correctionRequired };
        }

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify(body)
            });

            const result = await response.json();

            this.decisionModal.hide();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('deliberation');
            }
        } catch (error) {
            console.error('Error submitting decision:', error);
            this.showToast('Error al procesar decision', 'danger');
        }
    }

    async resetApplicant(userId, programId) {
        if (!confirm('Deseas reiniciar el estado de este aspirante? Podra volver a enviar documentos.')) {
            return;
        }

        try {
            const response = await fetch(`/api/v1/deliberation/user/${userId}/program/${programId}/reset`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify({ reason: 'Correcciones completadas' })
            });

            const result = await response.json();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('rejected');
            }
        } catch (error) {
            console.error('Error resetting applicant:', error);
            this.showToast('Error al reiniciar estado', 'danger');
        }
    }

    showToast(message, level = 'info') {
        // Simple toast implementation using Bootstrap
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        const toastId = `toast-${Date.now()}`;

        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-bg-${level} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        const toastEl = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 4000 });
        toast.show();

        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }
}

// Initialize when DOM is ready
let deliberationManager;
document.addEventListener('DOMContentLoaded', () => {
    deliberationManager = new DeliberationManager();
});

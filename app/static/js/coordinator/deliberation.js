/**
 * Deliberation Management for Coordinators
 */
class DeliberationManager {
    constructor() {
        this.programSelector = document.getElementById('programSelector');
        this.statsContainer = document.getElementById('statsContainer');
        this.currentProgramId = this.programSelector?.value || '';

        // Modals
        this.decisionModal = new bootstrap.Modal(document.getElementById('decisionModal'));
        this.startDeliberationModal = new bootstrap.Modal(document.getElementById('startDeliberationModal'));

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadStats();
        this.loadPendingInterview();
        this.joinDeliberationRoom();
        this.listenWebSocket();
    }

    // ── Helpers para modo "Todos los programas" ─────────────────────────────
    _isAllMode() { return !this.currentProgramId; }

    _targetProgramIds() {
        if (this.currentProgramId) return [parseInt(this.currentProgramId)];
        return (window.COORDINATOR_PROGRAMS || []).map(p => p.id);
    }

    _programName(pid) {
        const p = (window.COORDINATOR_PROGRAMS || []).find(x => x.id === pid);
        return p ? p.name : '—';
    }

    async _fanFetch(urlBuilder) {
        const ids = this._targetProgramIds();
        return Promise.all(ids.map(async (pid) => {
            try {
                const res = await fetch(urlBuilder(pid));
                const json = await res.json();
                if (!res.ok || json.error) return { pid, data: null, meta: null };
                return { pid, data: json.data, meta: json.meta };
            } catch (e) {
                return { pid, data: null, meta: null };
            }
        }));
    }

    _toggleProgramHeader(tableId) {
        const thead = document.querySelector(`#${tableId} thead tr`);
        if (!thead) return;
        const existing = thead.querySelector('th.program-col');
        const want = this._isAllMode();
        if (want && !existing) {
            const th = document.createElement('th');
            th.className = 'program-col';
            th.textContent = 'Programa';
            thead.insertBefore(th, thead.firstChild);
        } else if (!want && existing) {
            existing.remove();
        }
    }

    // ── WebSocket ─────────────────────────────────────────────────────────────

    joinDeliberationRoom() {
        /**
         * Une al coordinador a la sala Socket.IO del programa para recibir
         * actualizaciones en tiempo real cuando otro coordinador toma una decisión.
         * En modo "Todos" se une a todos los programas accesibles.
         */
        if (!window.siiapSocket) return;
        this._targetProgramIds().forEach(pid => {
            window.siiapSocket.emit('join_deliberation', { program_id: pid });
        });
    }

    listenWebSocket() {
        window.addEventListener('siiap:deliberation:updated', (e) => {
            const data = e.detail || {};

            // En modo específico, sólo reaccionar al programa actual.
            // En modo "Todos", reaccionar a cualquier programa accesible.
            if (this.currentProgramId &&
                data.program_id &&
                String(data.program_id) !== String(this.currentProgramId)) return;

            // Recargar stats y la pestaña activa para reflejar el nuevo estado
            this.loadStats();
            this.loadCurrentTab();

            // Notificar visualmente
            window.dispatchEvent(new CustomEvent('flash', {
                detail: {
                    level: 'info',
                    message: `Estado actualizado: ${data.user_name || 'aspirante'} → ${data.status}`
                }
            }));
        });
    }

    bindEvents() {
        // Program selector change
        if (this.programSelector) {
            this.programSelector.addEventListener('change', () => {
                this.currentProgramId = this.programSelector.value;
                this.loadStats();
                this.loadCurrentTab();
                this.joinDeliberationRoom();
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
            const isPartial = e.target.value === 'partial';
            correctionSection.style.display = isPartial ? 'block' : 'none';
            if (isPartial) {
                this.loadProgramArchivesForRejection();
            }
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
        const tbody = document.querySelector('#pendingInterviewTable tbody');
        if (!tbody) return;
        this._toggleProgramHeader('pendingInterviewTable');

        const colspan = this._isAllMode() ? 6 : 5;
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-4"><span class="loading-spinner"></span> Cargando...</td></tr>`;

        try {
            const results = await this._fanFetch(pid => `/api/v1/deliberation/program/${pid}/pending-interview`);
            const items = [];
            results.forEach(r => {
                if (!r.data) return;
                const programName = this._programName(r.pid);
                r.data.forEach(it => { it.__program_name = programName; items.push(it); });
            });

            document.getElementById('pendingInterviewCount').textContent = items.length;

            if (!items.length) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="${colspan}" class="empty-state">
                            <i class="bi bi-inbox"></i>
                            <p>No hay aspirantes con entrevista agendada pendiente de marcar</p>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = items.map(item => this.renderPendingInterviewRow(item)).join('');

        } catch (error) {
            console.error('Error loading pending interviews:', error);
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-4 text-danger">Error al cargar datos</td></tr>`;
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
        const programCell = this._isAllMode()
            ? `<td class="text-muted small">${item.__program_name || ''}</td>` : '';

        return `
            <tr>
                ${programCell}
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

    markInterviewCompleted(userId, programId, applicantName) {
        this.showConfirm(
            'Confirmar Entrevista Completada',
            `¿Confirmas que ${applicantName} completó su entrevista?`,
            () => this._doMarkInterviewCompleted(userId, programId),
            'btn-success'
        );
    }

    async _doMarkInterviewCompleted(userId, programId) {
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
                result.flash.forEach(f => showFlash(f.level, f.message));
            }

            if (!result.error) {
                this.loadStats();
                this.loadPendingInterview();
            }
        } catch (error) {
            console.error('Error marking interview completed:', error);
            showFlash('danger', 'Error al marcar entrevista');
        }
    }

    async loadStats() {
        try {
            const results = await this._fanFetch(pid => `/api/v1/deliberation/program/${pid}/stats`);
            const stats = { interview_completed: 0, deliberation: 0, accepted: 0, rejected: 0 };
            results.forEach(r => {
                if (!r.data) return;
                stats.interview_completed += r.data.interview_completed || 0;
                stats.deliberation        += r.data.deliberation        || 0;
                stats.accepted            += r.data.accepted            || 0;
                stats.rejected            += r.data.rejected            || 0;
            });

            // Update tab badges
            document.getElementById('interviewCompletedCount').textContent = stats.interview_completed;
            document.getElementById('deliberationCount').textContent = stats.deliberation;
            document.getElementById('acceptedCount').textContent = stats.accepted;
            document.getElementById('rejectedCount').textContent = stats.rejected;

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
        try {
            const results = await this._fanFetch(pid => `/api/v1/deliberation/program/${pid}/pending-interview`);
            let count = 0;
            results.forEach(r => { count += (r.data || []).length; });
            document.getElementById('pendingInterviewCount').textContent = count;
        } catch (error) {
            console.error('Error loading pending interview count:', error);
        }
    }

    async loadApplicants(status) {
        const tableId = this.getTableIdForStatus(status);
        const tbody = document.querySelector(`#${tableId} tbody`);
        if (!tbody) return;
        this._toggleProgramHeader(tableId);

        const colspan = this._isAllMode() ? 7 : 6;
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-4"><span class="loading-spinner"></span> Cargando...</td></tr>`;

        try {
            const results = await this._fanFetch(pid => `/api/v1/deliberation/program/${pid}/by-status/${status}`);
            const items = [];
            results.forEach(r => {
                if (!r.data) return;
                const programName = this._programName(r.pid);
                r.data.forEach(it => { it.__program_name = programName; items.push(it); });
            });

            if (!items.length) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="${colspan}" class="empty-state">
                            <i class="bi bi-inbox"></i>
                            <p>No hay aspirantes en este estado</p>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = items.map(item => this.renderApplicantRow(item, status)).join('');

        } catch (error) {
            console.error('Error loading applicants:', error);
            tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-4 text-danger">Error al cargar datos</td></tr>`;
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
        const programCell = this._isAllMode()
            ? `<td class="text-muted small">${item.__program_name || ''}</td>` : '';

        switch (status) {
            case 'interview_completed':
                return `
                    <tr>
                        ${programCell}
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
                        ${programCell}
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

            case 'accepted': {
                const forceResetBtn = window.canForceReset
                    ? `<button class="btn btn-sm btn-outline-secondary btn-action"
                               title="Reiniciar estado a En Proceso (solo admin)"
                               onclick="deliberationManager.forceResetApplicant(${user.id}, ${up.program_id}, '${user.full_name}')">
                           <i class="bi bi-arrow-counterclockwise"></i>
                       </button>`
                    : '';
                return `
                    <tr>
                        ${programCell}
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td class="text-center">${formatDate(up.decision_at)}</td>
                        <td class="notes-cell">${up.decision_notes || '-'}</td>
                        <td class="text-center">${forceResetBtn}</td>
                    </tr>
                `;
            }

            case 'rejected': {
                const rejectionBadge = up.rejection_type === 'partial'
                    ? '<span class="badge badge-partial">Correcciones</span>'
                    : '<span class="badge badge-full">Definitivo</span>';
                const resetBtn = up.rejection_type === 'partial'
                    ? `<button class="btn btn-sm btn-outline-primary btn-action"
                               onclick="deliberationManager.resetApplicant(${user.id}, ${up.program_id})">
                           <i class="bi bi-arrow-counterclockwise"></i> Reiniciar
                       </button>`
                    : '';

                // Parsear correction_required: puede ser JSON {archive_id, archive_name, notes} o texto plano
                let correctionDisplay = up.correction_required || up.decision_notes || '-';
                if (up.correction_required) {
                    try {
                        const corr = JSON.parse(up.correction_required);
                        const parts = [];
                        if (corr.archive_name) parts.push(`<strong>Documento:</strong> ${corr.archive_name}`);
                        if (corr.notes) parts.push(corr.notes);
                        correctionDisplay = parts.join('<br>') || '-';
                    } catch (e) {
                        // No es JSON, usar el texto tal cual
                    }
                }

                return `
                    <tr>
                        ${programCell}
                        <td class="applicant-name">${user.full_name}</td>
                        <td class="applicant-email">${user.email}</td>
                        <td class="text-center">${rejectionBadge}</td>
                        <td class="text-center">${formatDate(up.decision_at)}</td>
                        <td class="notes-cell">${correctionDisplay}</td>
                        <td class="text-center">${resetBtn}</td>
                    </tr>
                `;
            }

            default:
                return '';
        }
    }

    async loadProgramArchivesForRejection() {
        // Usa el program_id del aspirante en el modal (no el del selector global,
        // que puede ser '' en modo "Todos").
        const programId = document.getElementById('decisionProgramId')?.value
            || this.currentProgramId;
        if (!programId) return;

        const select = document.getElementById('rejectionArchiveSelect');
        if (!select) return;

        select.innerHTML = '<option value="">Cargando documentos...</option>';
        select.disabled = true;

        try {
            const response = await fetch(`/api/v1/deliberation/program/${programId}/admission-archives`);
            const result = await response.json();

            if (result.error || !result.data) {
                select.innerHTML = '<option value="">Error al cargar documentos</option>';
                return;
            }

            select.innerHTML = '<option value="">— Sin documento específico —</option>';
            result.data.forEach(archive => {
                const opt = document.createElement('option');
                opt.value = archive.id;
                opt.dataset.name = archive.name;
                opt.textContent = archive.name;
                select.appendChild(opt);
            });
            select.disabled = false;
        } catch (error) {
            console.error('Error loading archives:', error);
            select.innerHTML = '<option value="">Error al cargar documentos</option>';
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
                result.flash.forEach(f => showFlash(f.level, f.message));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('interview_completed');
            }
        } catch (error) {
            console.error('Error starting deliberation:', error);
            showFlash('danger', 'Error al iniciar deliberacion');
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
            // Reset archive select
            const archiveSelect = document.getElementById('rejectionArchiveSelect');
            if (archiveSelect) {
                archiveSelect.innerHTML = '<option value="">— Sin documento específico —</option>';
                archiveSelect.disabled = true;
            }
            document.getElementById('correctionRequired').value = '';
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
            const correctionText = document.getElementById('correctionRequired').value;
            endpoint = `/api/v1/deliberation/user/${userId}/program/${programId}/reject`;

            // Si es parcial, incluir el documento específico seleccionado (si se eligió uno)
            let correctionRequired = correctionText;
            if (rejectionType === 'partial') {
                const archiveSelect = document.getElementById('rejectionArchiveSelect');
                const archiveId = archiveSelect?.value;
                const archiveName = archiveSelect?.options[archiveSelect.selectedIndex]?.dataset?.name;
                if (archiveId && archiveName) {
                    correctionRequired = JSON.stringify({
                        archive_id: parseInt(archiveId),
                        archive_name: archiveName,
                        notes: correctionText
                    });
                }
            }

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
                result.flash.forEach(f => showFlash(f.level, f.message));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('deliberation');
            }
        } catch (error) {
            console.error('Error submitting decision:', error);
            showFlash('danger', 'Error al procesar decision');
        }
    }

    resetApplicant(userId, programId) {
        this.showConfirm(
            'Reiniciar Estado',
            '¿Deseas reiniciar el estado de este aspirante? Podrá volver a enviar documentos.',
            () => this._doResetApplicant(userId, programId),
            'btn-primary'
        );
    }

    async _doResetApplicant(userId, programId) {
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
                result.flash.forEach(f => showFlash(f.level, f.message));
            }

            if (!result.error) {
                this.loadStats();
                this.loadApplicants('rejected');
            }
        } catch (error) {
            console.error('Error resetting applicant:', error);
            showFlash('danger', 'Error al reiniciar estado');
        }
    }

    forceResetApplicant(userId, programId, applicantName) {
        this.showConfirm(
            'Reinicio Administrativo',
            `¿Reiniciar el estado de "${applicantName}" a "En Proceso"? Se registrará en el historial.`,
            () => this._doForceResetApplicant(userId, programId, applicantName),
            'btn-warning'
        );
    }

    async _doForceResetApplicant(userId, programId, applicantName) {
        try {
            const response = await fetch(`/api/v1/deliberation/user/${userId}/program/${programId}/force-reset`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify({ reason: 'Reinicio administrativo desde panel de deliberación' })
            });
            const result = await response.json();
            if (result.flash) result.flash.forEach(f => showFlash(f.level, f.message));
            if (!result.error) {
                this.loadStats();
                this.loadApplicants('accepted');
            }
        } catch (error) {
            console.error('Error force resetting applicant:', error);
            showFlash('danger', 'Error al reiniciar estado');
        }
    }

    showConfirm(title, message, onConfirm, btnClass = 'btn-primary') {
        document.getElementById('confirmModalTitle').textContent = title;
        document.getElementById('confirmModalMessage').textContent = message;
        const btn = document.getElementById('confirmModalBtn');
        btn.className = `btn ${btnClass}`;
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        btn.onclick = () => {
            modal.hide();
            onConfirm();
        };
        modal.show();
    }
}

// Initialize when DOM is ready
let deliberationManager;
document.addEventListener('DOMContentLoaded', () => {
    deliberationManager = new DeliberationManager();
});

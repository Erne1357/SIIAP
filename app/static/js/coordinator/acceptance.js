/**
 * Acceptance & Enrollment Document Management for Coordinators
 * Fase 4 - Aceptacion e Inscripcion
 */
class AcceptanceManager {
    constructor() {
        this.programSelector = document.getElementById('programSelector');
        this.statsContainer = document.getElementById('statsContainer');
        this.currentProgramId = this.programSelector?.value || null;

        // Modals
        this.uploadDocModal = new bootstrap.Modal(document.getElementById('uploadDocModal'));
        this.reviewReceiptModal = new bootstrap.Modal(document.getElementById('reviewReceiptModal'));

        this.init();
    }

    init() {
        this.bindEvents();
        if (this.currentProgramId) {
            this.loadStats();
            this.loadTab('pending_docs');
        }
    }

    bindEvents() {
        if (this.programSelector) {
            this.programSelector.addEventListener('change', () => {
                this.currentProgramId = this.programSelector.value;
                this.loadStats();
                this.loadCurrentTab();
            });
        }

        // Tab changes
        document.querySelectorAll('#acceptanceTabs button[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const tabName = e.target.dataset.tab;
                this.loadTab(tabName);
            });
        });

        // Upload doc confirm
        document.getElementById('confirmUploadDocBtn')?.addEventListener('click', () => {
            this.submitUploadDoc();
        });

        // Review receipt confirm
        document.getElementById('confirmReviewReceiptBtn')?.addEventListener('click', () => {
            this.submitReviewReceipt();
        });

        // Show/hide notes required indicator when selecting reject
        document.querySelectorAll('input[name="reviewReceiptStatus"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const notesRequired = document.getElementById('notesRequired');
                notesRequired.style.display = e.target.value === 'rejected' ? 'inline' : 'none';
            });
        });
    }

    loadCurrentTab() {
        const activeTab = document.querySelector('#acceptanceTabs button.active');
        if (activeTab) {
            this.loadTab(activeTab.dataset.tab);
        }
    }

    async loadStats() {
        if (!this.currentProgramId) return;

        try {
            const response = await fetch(`/api/v1/acceptance/program/${this.currentProgramId}/stats`);
            const result = await response.json();

            if (result.error) {
                console.error('Error loading stats:', result.error);
                return;
            }

            const stats = result.data;

            document.getElementById('pendingDocsCount').textContent = stats.pending_docs || 0;
            document.getElementById('receiptCount').textContent = stats.receipt_submitted || 0;
            document.getElementById('completedCount').textContent = stats.completed || 0;

            if (this.statsContainer) {
                this.statsContainer.innerHTML = `
                    <div class="stat-card stat-pending">
                        <div class="stat-value">${stats.total_accepted || 0}</div>
                        <div class="stat-label">Total Aceptados</div>
                    </div>
                    <div class="stat-card stat-warning">
                        <div class="stat-value">${stats.pending_docs || 0}</div>
                        <div class="stat-label">Pendientes</div>
                    </div>
                    <div class="stat-card stat-info">
                        <div class="stat-value">${stats.receipt_submitted || 0}</div>
                        <div class="stat-label">Boleta Recibida</div>
                    </div>
                    <div class="stat-card stat-success">
                        <div class="stat-value">${stats.completed || 0}</div>
                        <div class="stat-label">Completados</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadTab(tabName) {
        if (!this.currentProgramId) return;

        try {
            const response = await fetch(`/api/v1/acceptance/program/${this.currentProgramId}/applicants`);
            const result = await response.json();

            if (result.error) {
                console.error('Error loading applicants:', result.error);
                return;
            }

            const allApplicants = result.data || [];

            if (tabName === 'pending_docs') {
                this.renderPendingDocsTab(allApplicants.filter(a => this.isPendingDocs(a)));
            } else if (tabName === 'receipt_submitted') {
                this.renderReceiptTab(allApplicants.filter(a => this.isReceiptSubmitted(a)));
            } else if (tabName === 'completed') {
                this.renderCompletedTab(allApplicants.filter(a => this.isCompleted(a)));
            }
        } catch (error) {
            console.error('Error loading tab:', error);
        }
    }

    isPendingDocs(applicant) {
        const docs = applicant.acceptance_docs;
        const letterOk = docs.acceptance_letter?.status === 'uploaded' || docs.acceptance_letter?.status === 'approved';
        const scheduleOk = docs.course_schedule?.status === 'uploaded' || docs.course_schedule?.status === 'approved';
        const receiptApproved = docs.enrollment_receipt?.status === 'approved';
        const receiptUploaded = docs.enrollment_receipt?.status === 'uploaded';
        return (!letterOk || !scheduleOk) && !receiptApproved && !receiptUploaded;
    }

    isReceiptSubmitted(applicant) {
        const docs = applicant.acceptance_docs;
        return docs.enrollment_receipt?.status === 'uploaded';
    }

    isCompleted(applicant) {
        const docs = applicant.acceptance_docs;
        return docs.enrollment_receipt?.status === 'approved';
    }

    renderPendingDocsTab(applicants) {
        const tbody = document.querySelector('#pendingDocsTable tbody');
        if (!tbody) return;

        if (!applicants.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state"><i class="bi bi-inbox"></i><p>No hay aspirantes pendientes</p></td></tr>`;
            return;
        }

        tbody.innerHTML = applicants.map(a => {
            const user = a.user;
            const up = a.user_program;
            const docs = a.acceptance_docs;
            const letterStatus = this.renderDocBadge(docs.acceptance_letter);
            const scheduleStatus = this.renderDocBadge(docs.course_schedule);

            return `
                <tr>
                    <td class="applicant-name">${user.full_name}</td>
                    <td class="applicant-email">${user.email}</td>
                    <td class="text-center">${letterStatus}</td>
                    <td class="text-center">${scheduleStatus}</td>
                    <td class="text-center">
                        <div class="btn-group-actions">
                            ${!docs.acceptance_letter?.file_path ? `
                            <button class="btn btn-sm btn-outline-primary btn-action"
                                    onclick="acceptanceManager.showUploadModal(${user.id}, ${up.program_id}, '${user.full_name}', 'acceptance_letter')">
                                <i class="bi bi-upload"></i> Carta
                            </button>` : `
                            <button class="btn btn-sm btn-outline-secondary btn-action"
                                    onclick="acceptanceManager.showUploadModal(${user.id}, ${up.program_id}, '${user.full_name}', 'acceptance_letter')">
                                <i class="bi bi-arrow-repeat"></i> Carta
                            </button>`}
                            ${!docs.course_schedule?.file_path ? `
                            <button class="btn btn-sm btn-outline-primary btn-action"
                                    onclick="acceptanceManager.showUploadModal(${user.id}, ${up.program_id}, '${user.full_name}', 'course_schedule')">
                                <i class="bi bi-upload"></i> Tira
                            </button>` : `
                            <button class="btn btn-sm btn-outline-secondary btn-action"
                                    onclick="acceptanceManager.showUploadModal(${user.id}, ${up.program_id}, '${user.full_name}', 'course_schedule')">
                                <i class="bi bi-arrow-repeat"></i> Tira
                            </button>`}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderReceiptTab(applicants) {
        const tbody = document.querySelector('#receiptTable tbody');
        if (!tbody) return;

        if (!applicants.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state"><i class="bi bi-inbox"></i><p>No hay boletas pendientes de revision</p></td></tr>`;
            return;
        }

        tbody.innerHTML = applicants.map(a => {
            const user = a.user;
            const docs = a.acceptance_docs;
            const receiptDoc = docs.enrollment_receipt;

            return `
                <tr>
                    <td class="applicant-name">${user.full_name}</td>
                    <td class="applicant-email">${user.email}</td>
                    <td class="text-center">${this.renderDocBadge(docs.acceptance_letter)}</td>
                    <td class="text-center">${this.renderDocBadge(docs.course_schedule)}</td>
                    <td class="text-center">
                        <span class="badge bg-info">Subida</span>
                    </td>
                    <td class="text-center">
                        <button class="btn btn-sm btn-primary btn-action"
                                onclick="acceptanceManager.showReviewModal(${receiptDoc.id}, '${user.full_name}', '${receiptDoc.file_path}')">
                            <i class="bi bi-eye"></i> Revisar
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderCompletedTab(applicants) {
        const tbody = document.querySelector('#completedTable tbody');
        if (!tbody) return;

        if (!applicants.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state"><i class="bi bi-inbox"></i><p>No hay procesos completados aun</p></td></tr>`;
            return;
        }

        tbody.innerHTML = applicants.map(a => {
            const user = a.user;
            const docs = a.acceptance_docs;

            return `
                <tr>
                    <td class="applicant-name">${user.full_name}</td>
                    <td class="applicant-email">${user.email}</td>
                    <td class="text-center"><span class="badge bg-success">Disponible</span></td>
                    <td class="text-center"><span class="badge bg-success">Disponible</span></td>
                    <td class="text-center"><span class="badge bg-success">Aprobada</span></td>
                </tr>
            `;
        }).join('');
    }

    renderDocBadge(doc) {
        if (!doc || doc.status === 'pending' || !doc.file_path) {
            return '<span class="badge bg-secondary">Pendiente</span>';
        }
        if (doc.status === 'uploaded' || doc.status === 'approved') {
            return '<span class="badge bg-success">Subida</span>';
        }
        if (doc.status === 'rejected') {
            return '<span class="badge bg-danger">Rechazada</span>';
        }
        return '<span class="badge bg-secondary">-</span>';
    }

    showUploadModal(userId, programId, applicantName, documentType) {
        const typeLabels = {
            'acceptance_letter': 'Carta de Aceptacion',
            'course_schedule': 'Tira de Materias',
        };

        document.getElementById('uploadDocUserId').value = userId;
        document.getElementById('uploadDocProgramId').value = programId;
        document.getElementById('uploadDocType').value = documentType;
        document.getElementById('uploadDocApplicantName').textContent = applicantName;
        document.getElementById('uploadDocTypeLabel').textContent = typeLabels[documentType] || documentType;
        document.getElementById('uploadDocModalTitle').textContent = `Subir ${typeLabels[documentType] || documentType}`;
        document.getElementById('uploadDocFile').value = '';

        this.uploadDocModal.show();
    }

    async submitUploadDoc() {
        const userId = document.getElementById('uploadDocUserId').value;
        const programId = document.getElementById('uploadDocProgramId').value;
        const documentType = document.getElementById('uploadDocType').value;
        const fileInput = document.getElementById('uploadDocFile');

        if (!fileInput.files[0]) {
            this.showToast('Selecciona un archivo', 'warning');
            return;
        }

        const spinner = document.getElementById('uploadDocSpinner');
        const btn = document.getElementById('confirmUploadDocBtn');
        spinner.classList.remove('d-none');
        btn.disabled = true;

        const formData = new FormData();
        formData.append('document_type', documentType);
        formData.append('file', fileInput.files[0]);

        try {
            const response = await fetch(
                `/api/v1/acceptance/user/${userId}/program/${programId}/upload-doc`,
                {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                    },
                    body: formData
                }
            );

            const result = await response.json();
            this.uploadDocModal.hide();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadCurrentTab();
            }
        } catch (error) {
            console.error('Error uploading doc:', error);
            this.showToast('Error al subir el documento', 'danger');
        } finally {
            spinner.classList.add('d-none');
            btn.disabled = false;
        }
    }

    showReviewModal(docId, applicantName, filePath) {
        document.getElementById('reviewReceiptDocId').value = docId;
        document.getElementById('reviewReceiptApplicantName').textContent = applicantName;
        document.getElementById('reviewReceiptNotes').value = '';
        document.getElementById('notesRequired').style.display = 'none';

        // Reset radios
        document.querySelectorAll('input[name="reviewReceiptStatus"]').forEach(r => r.checked = false);

        // Construir URL de descarga del archivo
        if (filePath) {
            // filePath tiene formato: user_id/acceptance/filename.pdf
            const parts = filePath.split('/');
            const userId = parts[0];
            const phase = parts[1];
            const filename = parts.slice(2).join('/');
            const downloadUrl = `/files/doc/${userId}/${phase}/${filename}`;
            document.getElementById('viewReceiptBtn').href = downloadUrl;
        }

        this.reviewReceiptModal.show();
    }

    async submitReviewReceipt() {
        const docId = document.getElementById('reviewReceiptDocId').value;
        const status = document.querySelector('input[name="reviewReceiptStatus"]:checked')?.value;
        const notes = document.getElementById('reviewReceiptNotes').value.trim();

        if (!status) {
            this.showToast('Selecciona una decision (Aprobar o Rechazar)', 'warning');
            return;
        }

        if (status === 'rejected' && !notes) {
            this.showToast('Debes indicar el motivo del rechazo', 'warning');
            return;
        }

        try {
            const response = await fetch(`/api/v1/acceptance/document/${docId}/review`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify({ status, notes })
            });

            const result = await response.json();
            this.reviewReceiptModal.hide();

            if (result.flash) {
                result.flash.forEach(f => this.showToast(f.message, f.level));
            }

            if (!result.error) {
                this.loadStats();
                this.loadCurrentTab();
            }
        } catch (error) {
            console.error('Error reviewing receipt:', error);
            this.showToast('Error al revisar la boleta', 'danger');
        }
    }

    showToast(message, level = 'info') {
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

let acceptanceManager;
document.addEventListener('DOMContentLoaded', () => {
    acceptanceManager = new AcceptanceManager();
});

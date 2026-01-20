// app/static/js/admin/settings/academic_periods.js

class AcademicPeriodsManager {
    constructor() {
        this.API_BASE = '/api/v1/academic-periods';
        this.periods = [];
        this.currentDeleteId = null;
        this.modalPeriod = null;
        this.modalDelete = null;
        this.init();
    }

    init() {
        // Inicializar modales de Bootstrap
        const modalPeriodEl = document.getElementById('modalPeriod');
        const modalDeleteEl = document.getElementById('modalDelete');

        if (modalPeriodEl) {
            this.modalPeriod = new bootstrap.Modal(modalPeriodEl);
        }
        if (modalDeleteEl) {
            this.modalDelete = new bootstrap.Modal(modalDeleteEl);
        }

        this.wireEvents();
        this.loadPeriods();
    }

    wireEvents() {
        // Formulario de periodo
        const formPeriod = document.getElementById('formPeriod');
        if (formPeriod) {
            formPeriod.addEventListener('submit', (e) => this.handleSavePeriod(e));
        }

        // Boton confirmar eliminacion
        const btnConfirmDelete = document.getElementById('btnConfirmDelete');
        if (btnConfirmDelete) {
            btnConfirmDelete.addEventListener('click', () => this.handleConfirmDelete());
        }

        // Reset form cuando se abre el modal para nuevo periodo
        const modalPeriodEl = document.getElementById('modalPeriod');
        if (modalPeriodEl) {
            modalPeriodEl.addEventListener('show.bs.modal', (e) => {
                if (!e.relatedTarget || !e.relatedTarget.classList.contains('btn-edit')) {
                    this.resetForm();
                    document.getElementById('modalPeriodLabel').textContent = 'Nuevo Periodo Academico';
                }
            });
        }
    }

    async loadPeriods() {
        const container = document.getElementById('periodsContainer');
        const alertNoPeriods = document.getElementById('alertNoPeriods');

        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p class="text-muted mt-2">Cargando periodos...</p>
            </div>
        `;

        try {
            const response = await fetch(this.API_BASE, {
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.error) {
                this.showFlash('danger', result.error.message);
                return;
            }

            this.periods = result.data || [];
            this.renderPeriods();

        } catch (error) {
            console.error('Error loading periods:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Error al cargar los periodos academicos
                </div>
            `;
        }
    }

    renderPeriods() {
        const container = document.getElementById('periodsContainer');
        const alertNoPeriods = document.getElementById('alertNoPeriods');
        const template = document.getElementById('templatePeriodCard');

        if (this.periods.length === 0) {
            container.innerHTML = '';
            alertNoPeriods.classList.remove('d-none');
            return;
        }

        alertNoPeriods.classList.add('d-none');
        container.innerHTML = '';

        this.periods.forEach(period => {
            const card = template.content.cloneNode(true);
            const cardEl = card.querySelector('.period-card');

            cardEl.dataset.periodId = period.id;
            card.querySelector('.period-code').textContent = period.code;
            card.querySelector('.period-name').textContent = period.name;

            // Fechas
            card.querySelector('.admission-dates').textContent =
                `${this.formatDate(period.admission_start_date)} - ${this.formatDate(period.admission_end_date)}`;
            card.querySelector('.class-dates').textContent =
                `${this.formatDate(period.start_date)} - ${this.formatDate(period.end_date)}`;

            // Indicador y estado
            const indicator = card.querySelector('.period-indicator');
            const badge = card.querySelector('.period-status-badge');

            if (period.is_active) {
                indicator.classList.add('active');
                cardEl.classList.add('is-active');
                badge.textContent = 'ACTIVO';
                badge.classList.add('text-bg-success');
            } else {
                indicator.classList.add('inactive');
                badge.textContent = this.getStatusLabel(period.status);
                badge.classList.add('text-bg-secondary');
                // Mostrar boton activar solo para periodos no activos
                card.querySelectorAll('.btn-activate').forEach(btn => btn.classList.remove('d-none'));
            }

            // Event listeners para los botones
            card.querySelectorAll('.btn-edit').forEach(btn => {
                btn.addEventListener('click', () => this.openEditModal(period));
            });

            card.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', () => this.openDeleteModal(period));
            });

            card.querySelectorAll('.btn-activate').forEach(btn => {
                btn.addEventListener('click', () => this.activatePeriod(period.id));
            });

            container.appendChild(card);
        });
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr + 'T00:00:00');
        return date.toLocaleDateString('es-MX', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }

    getStatusLabel(status) {
        const labels = {
            'upcoming': 'PROXIMO',
            'active': 'ACTIVO',
            'admission_closed': 'ADMISION CERRADA',
            'completed': 'COMPLETADO'
        };
        return labels[status] || status.toUpperCase();
    }

    resetForm() {
        const form = document.getElementById('formPeriod');
        if (form) {
            form.reset();
        }
        document.getElementById('periodId').value = '';
    }

    openEditModal(period) {
        document.getElementById('modalPeriodLabel').textContent = 'Editar Periodo Academico';
        document.getElementById('periodId').value = period.id;
        document.getElementById('periodCode').value = period.code;
        document.getElementById('periodName').value = period.name;
        document.getElementById('startDate').value = period.start_date;
        document.getElementById('endDate').value = period.end_date;
        document.getElementById('admissionStartDate').value = period.admission_start_date;
        document.getElementById('admissionEndDate').value = period.admission_end_date;
        this.modalPeriod.show();
    }

    openDeleteModal(period) {
        this.currentDeleteId = period.id;
        document.getElementById('deletePeriodCode').textContent = period.code;
        this.modalDelete.show();
    }

    async handleSavePeriod(e) {
        e.preventDefault();

        const btn = document.getElementById('btnSavePeriod');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';

        const periodId = document.getElementById('periodId').value;
        const data = {
            code: document.getElementById('periodCode').value.trim(),
            name: document.getElementById('periodName').value.trim(),
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            admission_start_date: document.getElementById('admissionStartDate').value,
            admission_end_date: document.getElementById('admissionEndDate').value
        };

        console.log('Saving period data:', data);

        const url = periodId ? `${this.API_BASE}/${periodId}` : this.API_BASE;
        const method = periodId ? 'PATCH' : 'POST';
        
        console.log(`Sending ${method} request to ${url} with data:`, data);

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrf()
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.error) {
                this.showFlash('danger', result.error.message);
                return;
            }

            this.showFlash('success', result.flash?.[0]?.message || 'Periodo guardado correctamente');
            this.modalPeriod.hide();
            this.loadPeriods();

        } catch (error) {
            console.error('Error saving period:', error);
            this.showFlash('danger', 'Error al guardar el periodo');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    async activatePeriod(periodId) {
        try {
            const response = await fetch(`${this.API_BASE}/${periodId}/activate`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            const result = await response.json();

            if (result.error) {
                this.showFlash('danger', result.error.message);
                return;
            }

            this.showFlash('success', result.flash?.[0]?.message || 'Periodo activado correctamente');
            this.loadPeriods();

        } catch (error) {
            console.error('Error activating period:', error);
            this.showFlash('danger', 'Error al activar el periodo');
        }
    }

    async handleConfirmDelete() {
        if (!this.currentDeleteId) return;

        const btn = document.getElementById('btnConfirmDelete');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Eliminando...';

        try {
            const response = await fetch(`${this.API_BASE}/${this.currentDeleteId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            const result = await response.json();

            if (result.error) {
                this.showFlash('danger', result.error.message);
                return;
            }

            this.showFlash('success', result.flash?.[0]?.message || 'Periodo eliminado correctamente');
            this.modalDelete.hide();
            this.currentDeleteId = null;
            this.loadPeriods();

        } catch (error) {
            console.error('Error deleting period:', error);
            this.showFlash('danger', 'Error al eliminar el periodo');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    showFlash(level, message) {
        // Usar el sistema de flash existente
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level, message }
        }));
    }

    getCsrf() {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }
}

// Inicializar
let academicPeriodsManager = null;

function initAcademicPeriods() {
    if (document.getElementById('periodsContainer')) {
        academicPeriodsManager = new AcademicPeriodsManager();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAcademicPeriods);
} else {
    initAcademicPeriods();
}

// Reiniciar con Swup si esta disponible
if (typeof swup !== 'undefined') {
    swup.on('contentReplaced', () => {
        if (document.getElementById('periodsContainer')) {
            initAcademicPeriods();
        }
    });
}

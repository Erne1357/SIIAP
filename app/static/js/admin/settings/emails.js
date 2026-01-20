// app/static/js/admin/settings/emails.js

class EmailConfigManager {
    constructor() {
        this.init();
    }

    init() {
        this.wireEvents();
        this.loadPendingEmails();
        this.startAutoRefresh();
    }

    wireEvents() {
        // Desconectar
        const btnDisconnect = document.getElementById('btnDisconnect');
        if (btnDisconnect) {
            btnDisconnect.addEventListener('click', () => this.disconnect());
        }

        // Procesar cola
        const btnProcessQueue = document.getElementById('btnProcessQueue');
        if (btnProcessQueue) {
            btnProcessQueue.addEventListener('click', () => this.processQueue());
        }

        // Reintentar fallidos
        const btnRetryFailed = document.getElementById('btnRetryFailed');
        if (btnRetryFailed) {
            btnRetryFailed.addEventListener('click', () => this.retryFailed());
        }

        // Enviar prueba
        const btnSendTest = document.getElementById('btnSendTest');
        if (btnSendTest) {
            btnSendTest.addEventListener('click', () => this.sendTest());
        }

        // Actualizar lista
        const btnRefreshList = document.getElementById('btnRefreshList');
        if (btnRefreshList) {
            btnRefreshList.addEventListener('click', () => this.loadPendingEmails());
        }
    }

    async disconnect() {
        if (!confirm('¿Desconectar la cuenta de Microsoft? Los correos pendientes no se enviarán hasta que vuelvas a conectar.')) {
            return;
        }

        try {
            const res = await fetch('/admin/emails/logout', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            if (res.ok) {
                window.location.reload();
            } else {
                this.showFlash('error', 'Error al desconectar');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showFlash('error', 'Error de conexión');
        }
    }

    async processQueue() {
        const btn = document.getElementById('btnProcessQueue');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';

        try {
            const res = await fetch('/admin/emails/process-queue', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            const json = await res.json();

            if (res.ok && json.ok) {
                const result = json.result;
                this.showFlash('success', `Procesados: ${result.processed}, Enviados: ${result.sent}, Fallidos: ${result.failed}`);
                await this.refreshStats();
                await this.loadPendingEmails();
            } else if (json.error) {
                this.showFlash('error', json.error);
            }
        } catch (error) {
            console.error('Error:', error);
            this.showFlash('error', 'Error al procesar cola');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    async retryFailed() {
        const btn = document.getElementById('btnRetryFailed');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Reintentando...';

        try {
            const res = await fetch('/admin/emails/retry-failed', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrf()
                }
            });

            const json = await res.json();

            if (res.ok && json.ok) {
                const result = json.result;
                this.showFlash('success', `Reintentados: ${result.processed}, Enviados: ${result.sent}`);
                await this.refreshStats();
                await this.loadPendingEmails();
            } else if (json.error) {
                this.showFlash('error', json.error);
            }
        } catch (error) {
            console.error('Error:', error);
            this.showFlash('error', 'Error al reintentar');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    async sendTest() {
        this.showFlash('info', 'Funcionalidad de correo de prueba próximamente disponible');
    }

    async refreshStats() {
        // Las estadísticas se actualizar´an con el reload de la página por ahora
        // Ya que están en el template y se calculan en el servidor
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    }

    async loadPendingEmails() {
        const container = document.getElementById('pendingEmailsList');
        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
            </div>
        `;

        try {
            const res = await fetch('/admin/emails/queue?per_page=20');
            const json = await res.json();

            if (!res.ok) {
                throw new Error('Error al cargar correos');
            }

            const emails = json.emails;

            if (emails.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="bi bi-inbox"></i>
                        <p class="mt-3 mb-0">No hay correos pendientes</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = emails.map(email => this.renderEmailItem(email)).join('');

        } catch (error) {
            console.error('Error:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Error al cargar la lista de correos
                </div>
            `;
        }
    }

    renderEmailItem(email) {
        const statusClass = email.status;
        const statusText = {
            'pending': 'Pendiente',
            'sent': 'Enviado',
            'failed': 'Fallido'
        }[email.status] || email.status;

        const createdAt = new Date(email.created_at).toLocaleString('es-MX', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const errorHtml = email.error_message ? `
            <div class="mt-2">
                <small class="text-danger">
                    <i class="bi bi-exclamation-circle me-1"></i>
                    <strong>Error:</strong> ${this.escapeHtml(email.error_message)}
                </small>
            </div>
        ` : '';

        return `
            <div class="email-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2 mb-2">
                            <span class="email-status ${statusClass}">${statusText}</span>
                            ${email.attempts > 0 ? `
                                <span class="badge bg-warning text-dark">
                                    ${email.attempts} ${email.attempts === 1 ? 'intento' : 'intentos'}
                                </span>
                            ` : ''}
                        </div>
                        <strong>${this.escapeHtml(email.subject)}</strong>
                        <div class="email-meta">
                            <span>
                                <i class="bi bi-envelope me-1"></i>
                                ${this.escapeHtml(email.recipient_email)}
                            </span>
                            <span>
                                <i class="bi bi-clock me-1"></i>
                                ${createdAt}
                            </span>
                        </div>
                        ${errorHtml}
                    </div>
                </div>
            </div>
        `;
    }

    startAutoRefresh() {
        // Refrescar estadísticas cada 30 segundos
        setInterval(() => {
            this.refreshStats();
        }, 30000);
    }

    showFlash(level, message) {
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level, message }
        }));
    }

    getCsrf() {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Inicializar
let emailConfigManager = null;

function initEmailConfig() {
    emailConfigManager = new EmailConfigManager();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEmailConfig);
} else {
    initEmailConfig();
}

// Reiniciar con Swup si está disponible
if (typeof swup !== 'undefined') {
    swup.on('contentReplaced', () => {
        if (document.getElementById('pendingEmailsList')) {
            initEmailConfig();
        }
    });
}
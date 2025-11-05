// app/static/js/user/profile_notifications.js

class ProfileNotificationsManager {
    constructor() {
        this.currentFilter = 'all';
        this.currentPage = 1;
        this.limit = 20;
        this.init();
    }

    init() {
        this.wireEvents();
        this.loadNotifications();
    }

    wireEvents() {
        // Botón marcar todas como leídas
        const markAllBtn = document.getElementById('markAllNotificationsRead');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', () => this.markAllAsRead());
        }

        // Filtro de todas/no leídas
        const filterAllBtn = document.getElementById('filterAllNotifications');
        const filterUnreadBtn = document.getElementById('filterUnreadNotifications');
        
        if (filterAllBtn) {
            filterAllBtn.addEventListener('click', () => {
                this.currentFilter = 'all';
                this.currentPage = 1;
                this.updateFilterButtons();
                this.loadNotifications();
            });
        }

        if (filterUnreadBtn) {
            filterUnreadBtn.addEventListener('click', () => {
                this.currentFilter = 'unread';
                this.currentPage = 1;
                this.updateFilterButtons();
                this.loadNotifications();
            });
        }

        // Limpiar notificaciones leídas
        const clearReadBtn = document.getElementById('clearReadNotifications');
        if (clearReadBtn) {
            clearReadBtn.addEventListener('click', () => this.clearReadNotifications());
        }

        // Filtro por tipo
        const typeFilter = document.getElementById('filterNotificationType');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                this.currentPage = 1;
                this.loadNotifications();
            });
        }

        // Búsqueda
        const searchInput = document.getElementById('searchNotifications');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.currentPage = 1;
                    this.loadNotifications();
                }, 500);
            });
        }
    }

    updateFilterButtons() {
        const filterAllBtn = document.getElementById('filterAllNotifications');
        const filterUnreadBtn = document.getElementById('filterUnreadNotifications');

        if (this.currentFilter === 'all') {
            filterAllBtn?.classList.add('active');
            filterUnreadBtn?.classList.remove('active');
        } else {
            filterAllBtn?.classList.remove('active');
            filterUnreadBtn?.classList.add('active');
        }
    }

    async loadNotifications() {
        const container = document.getElementById('notificationsFull');
        if (!container) return;

        container.innerHTML = '<div class="notification-loading"><div class="spinner-border"></div><p class="mt-2">Cargando notificaciones...</p></div>';

        try {
            const unreadOnly = this.currentFilter === 'unread';
            const offset = (this.currentPage - 1) * this.limit;
            
            // Usar ApiClient para construir URL segura
            const res = await window.apiClient.get(`/api/v1/notifications?unread_only=${unreadOnly}&limit=${this.limit}&offset=${offset}`);
            const json = await res.json();
            
            const notifications = json.data.notifications;
            const total = json.data.total;

            // Habilitar/deshabilitar botón de marcar todas
            const markAllBtn = document.getElementById('markAllNotificationsRead');
            if (markAllBtn) {
                markAllBtn.disabled = json.data.unread_count === 0;
            }

            if (notifications.length === 0) {
                container.innerHTML = `
                    <div class="notification-empty py-5">
                        <i class="bi bi-bell-slash"></i>
                        <p class="mt-3 text-muted">
                            ${unreadOnly ? 'No tienes notificaciones sin leer' : 'No tienes notificaciones'}
                        </p>
                    </div>
                `;
                return;
            }

            // Agrupar por fecha
            const grouped = this.groupByDate(notifications);
            
            let html = '';
            for (const [dateLabel, items] of Object.entries(grouped)) {
                html += `
                    <div class="notification-group">
                        <h6 class="notification-date-header">${dateLabel}</h6>
                        <div class="notification-items">
                            ${items.map(n => this.renderFullNotification(n)).join('')}
                        </div>
                    </div>
                `;
            }

            container.innerHTML = html;

            // Wire eventos
            this.wireNotificationEvents();

            // Renderizar paginación
            this.renderPagination(total);

        } catch (error) {
            console.error('Error loading notifications:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Error al cargar las notificaciones
                </div>
            `;
        }
    }

    groupByDate(notifications) {
        const groups = {};
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        for (const notif of notifications) {
            const date = new Date(notif.created_at);
            const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());

            let label;
            if (dateOnly.getTime() === today.getTime()) {
                label = 'Hoy';
            } else if (dateOnly.getTime() === yesterday.getTime()) {
                label = 'Ayer';
            } else {
                label = date.toLocaleDateString('es-MX', { 
                    day: 'numeric', 
                    month: 'long',
                    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
                });
            }

            if (!groups[label]) {
                groups[label] = [];
            }
            groups[label].push(notif);
        }

        return groups;
    }

    renderFullNotification(notification) {
        const icon = this.getIconForType(notification.type);
        const color = this.getColorForType(notification.type);
        const unreadClass = notification.is_read ? '' : 'unread';
        const priorityClass = notification.priority;
        const time = new Date(notification.created_at).toLocaleTimeString('es-MX', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        let actionsHtml = '';
        
        if (notification.type === 'event_invitation' && !notification.is_read && notification.related_invitation_id) {
            actionsHtml = `
                <div class="notification-actions">
                    <button class="btn btn-sm btn-success respond-invitation" 
                            data-notification-id="${notification.id}"
                            data-response="accepted">
                        <i class="bi bi-check"></i> Aceptar
                    </button>
                    <button class="btn btn-sm btn-danger respond-invitation" 
                            data-notification-id="${notification.id}"
                            data-response="rejected">
                        <i class="bi bi-x"></i> Rechazar
                    </button>
                </div>
            `;
        }

        return `
            <div class="notification-item ${unreadClass}" data-id="${notification.id}">
                <div class="notification-full-item">
                    <div class="notification-icon bg-${color}">
                        <i class="${icon}"></i>
                    </div>
                    <div class="notification-content flex-grow-1">
                        <strong>${this.escapeHtml(notification.title)}</strong>
                        <p class="mb-2">${this.escapeHtml(notification.message)}</p>
                        ${actionsHtml}
                        <div class="notification-meta">
                            <span>
                                <span class="notification-priority ${priorityClass}">${priorityClass}</span>
                                <span class="ms-2">${time}</span>
                            </span>
                            <div>
                                ${!notification.is_read ? `
                                    <button class="btn btn-sm btn-outline-primary mark-read-btn" 
                                            data-id="${notification.id}">
                                        <i class="bi bi-check"></i> Marcar leída
                                    </button>
                                ` : ''}
                                <button class="btn btn-sm btn-outline-danger delete-btn" 
                                        data-id="${notification.id}">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    wireNotificationEvents() {
        // Marcar como leída
        document.querySelectorAll('.mark-read-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                await this.markAsRead(id);
            });
        });

        // Eliminar
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                if (confirm('¿Eliminar esta notificación?')) {
                    await this.deleteNotification(id);
                }
            });
        });

        // Responder invitación
        document.querySelectorAll('.respond-invitation').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.notificationId);
                const response = btn.dataset.response;
                await this.respondInvitation(id, response);
            });
        });
    }

    renderPagination(total) {
        const container = document.getElementById('notificationsPagination');
        if (!container) return;

        const totalPages = Math.ceil(total / this.limit);
        
        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = '';
        
        // Anterior
        html += `
            <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${this.currentPage - 1}">Anterior</a>
            </li>
        `;

        // Páginas
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                html += `
                    <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" data-page="${i}">${i}</a>
                    </li>
                `;
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }

        // Siguiente
        html += `
            <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${this.currentPage + 1}">Siguiente</a>
            </li>
        `;

        container.innerHTML = html;

        // Wire eventos
        container.querySelectorAll('a.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(link.dataset.page);
                if (page > 0 && page <= totalPages) {
                    this.currentPage = page;
                    this.loadNotifications();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
    }

    async markAsRead(id) {
        try {
            const res = await window.apiClient.patch(`/api/v1/notifications/${id}/read`);

            if (res.ok) {
                await this.loadNotifications();
                // Actualizar badge del header
                if (window.notificationManager) {
                    window.notificationManager.updateBadge();
                }
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async deleteNotification(id) {
        try {
            const res = await window.apiClient.delete(`/api/v1/notifications/${id}`);

            const json = await res.json();
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }

            if (res.ok) {
                await this.loadNotifications();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async markAllAsRead() {
        try {
            const res = await window.apiClient.post(`/api/v1/notifications/mark-all-read`);

            const json = await res.json();
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }

            if (res.ok) {
                await this.loadNotifications();
                if (window.notificationManager) {
                    window.notificationManager.updateBadge();
                }
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async clearReadNotifications() {
        if (!confirm('¿Eliminar todas las notificaciones leídas? Esta acción no se puede deshacer.')) {
            return;
        }

        try {
            const res = await window.apiClient.post(`/api/v1/notifications/clear-read`);

            const json = await res.json();
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }

            if (res.ok) {
                await this.loadNotifications();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async respondInvitation(notificationId, response) {
        try {
            const res = await window.apiClient.post(`/api/v1/notifications/${notificationId}/respond-invitation`, { response });

            const json = await res.json();
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }

            if (res.ok) {
                await this.loadNotifications();
                if (window.notificationManager) {
                    window.notificationManager.updateBadge();
                }
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    getIconForType(type) {
        const icons = {
            'document_approved': 'bi bi-check-circle',
            'document_rejected': 'bi bi-x-circle',
            'coordinator_uploaded': 'bi bi-file-earmark-arrow-up',
            'extension_approved': 'bi bi-calendar-check',
            'extension_rejected': 'bi bi-calendar-x',
            'appointment_assigned': 'bi bi-calendar-event',
            'appointment_cancelled': 'bi bi-calendar-x',
            'event_invitation': 'bi bi-envelope',
            'password_reset': 'bi bi-shield-lock',
            'control_number_assigned': 'bi bi-person-badge',
            'account_deactivated': 'bi bi-person-x',
            'program_changed': 'bi bi-arrow-left-right'
        };
        return icons[type] || 'bi bi-bell';
    }

    getColorForType(type) {
        const colors = {
            'document_approved': 'success',
            'extension_approved': 'success',
            'document_rejected': 'danger',
            'extension_rejected': 'danger',
            'appointment_cancelled': 'danger',
            'account_deactivated': 'danger',
            'appointment_assigned': 'primary',
            'event_invitation': 'primary',
            'control_number_assigned': 'info',
            'coordinator_uploaded': 'info',
            'password_reset': 'warning',
            'program_changed': 'warning'
        };
        return colors[type] || 'info';
    }



    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Inicializar solo si estamos en el tab de notificaciones
function initProfileNotifications() {
    const container = document.getElementById('notificationsFull');
    if (container) {
        new ProfileNotificationsManager();
    }
}

// Bootstrap tabs event
const notificationsTab = document.getElementById('notifications-tab');
if (notificationsTab) {
    notificationsTab.addEventListener('shown.bs.tab', initProfileNotifications);
    
    // Si el tab está activo al cargar
    if (notificationsTab.classList.contains('active')) {
        initProfileNotifications();
    }
}
// app/static/js/notifications.js

class NotificationManager {
    constructor() {
        this.dropdownOpen = false;
        this.isMobile = window.innerWidth < 768;
        this.init();
    }

    async init() {
        await this.updateBadge();
        this.wireEvents();
        this.wireFabEvents();
        this.listenWebSocket();
        window.addEventListener('resize', () => {
            this.isMobile = window.innerWidth < 768;
        });
    }

    // ── WebSocket ─────────────────────────────────────────────────────────────

    listenWebSocket() {
        /**
         * Escucha el CustomEvent global 'siiap:notification:new' emitido por socket-client.js.
         * Actualiza el badge inmediatamente y muestra un toast.
         * Si el dropdown ya está abierto, recarga la lista.
         */
        window.addEventListener('siiap:notification:new', (e) => {
            const notification = e.detail?.notification;
            if (!notification) return;

            this.incrementBadge();
            this.showToast(notification);

            if (this.dropdownOpen) {
                this.loadUnreadNotifications();
            }

            // Permite que otros módulos reaccionen al tipo de notificación
            window.dispatchEvent(new CustomEvent('siiap:notification:received', {
                detail: notification
            }));
        });
    }

    // ── Badge ─────────────────────────────────────────────────────────────────

    async updateBadge() {
        try {
            const res = await window.apiClient.get('/api/v1/notifications/unread-count');
            const json = await res.json();
            this.setBadgeCount(json.data.count);
        } catch (error) {
            console.error('Error updating notification badge:', error);
        }
    }

    setBadgeCount(count) {
        const label = count > 99 ? '99+' : count;
        const show = count > 0;

        const badge = document.getElementById('notificationBadge');
        if (badge) {
            badge.textContent = label;
            badge.classList.toggle('d-none', !show);
        }

        const badgeMobile = document.getElementById('notificationBadgeMobile');
        if (badgeMobile) {
            badgeMobile.textContent = label;
            badgeMobile.classList.toggle('d-none', !show);
        }
    }

    incrementBadge() {
        ['notificationBadge', 'notificationBadgeMobile'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            const current = parseInt(el.textContent) || 0;
            const next = current + 1;
            el.textContent = next > 99 ? '99+' : next;
            el.classList.remove('d-none');
        });
    }

    // ── Toast ─────────────────────────────────────────────────────────────────

    showToast(notification) {
        const level = {
            'critical': 'danger',
            'high': 'warning',
            'medium': 'info',
            'low': 'secondary',
        }[notification.priority] || 'info';

        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level, message: notification.title }
        }));
    }

    // ── Dropdown ──────────────────────────────────────────────────────────────

    wireEvents() {
        const bell = document.getElementById('notificationBell');
        const dropdown = document.getElementById('notificationDropdown');

        if (!bell || !dropdown) return;

        bell.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown();
        });

        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && !bell.contains(e.target)) {
                this.closeDropdown();
            }
        });

        const markAllBtn = document.getElementById('markAllReadBtn');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', () => this.markAllAsRead());
        }
    }

    wireFabEvents() {
        const fab = document.getElementById('notificationFab');
        const dropdown = document.getElementById('notificationDropdown');
        if (!fab || !dropdown) return;

        fab.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown(true);
        });
    }

    async toggleDropdown(fromFab = false) {
        const dropdown = document.getElementById('notificationDropdown');

        if (this.dropdownOpen) {
            this.closeDropdown();
        } else {
            await this.loadUnreadNotifications();
            dropdown.classList.add('show');
            if (fromFab) dropdown.classList.add('from-fab');
            this.dropdownOpen = true;
        }
    }

    closeDropdown() {
        const dropdown = document.getElementById('notificationDropdown');
        dropdown.classList.remove('show', 'from-fab');
        this.dropdownOpen = false;
    }

    // ── Lista de notificaciones ───────────────────────────────────────────────

    async loadUnreadNotifications() {
        const container = document.getElementById('notificationsList');
        if (!container) return;

        container.innerHTML = '<div class="notification-loading"><div class="spinner-border spinner-border-sm"></div></div>';

        try {
            const res = await window.apiClient.get('/api/v1/notifications?unread_only=true&limit=5');
            const json = await res.json();
            const notifications = json.data.notifications;

            if (notifications.length === 0) {
                container.innerHTML = `
                    <div class="notification-empty">
                        <i class="bi bi-bell-slash"></i>
                        <p class="mb-0">No hay notificaciones nuevas</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = notifications.map(n => this.renderNotificationItem(n)).join('');

            container.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (!e.target.closest('.notification-actions') && !e.target.closest('.btn-mark-read')) {
                        this.handleNotificationClick(parseInt(item.dataset.id));
                    }
                });

                const markReadBtn = item.querySelector('.btn-mark-read');
                if (markReadBtn) {
                    markReadBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.markAsRead(parseInt(item.dataset.id));
                    });
                }
            });

            container.querySelectorAll('[data-respond-invitation]').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const notifId = parseInt(btn.dataset.notificationId);
                    const response = btn.dataset.respondInvitation;
                    await this.respondInvitation(notifId, response);
                });
            });

        } catch (error) {
            console.error('Error loading notifications:', error);
            container.innerHTML = `
                <div class="notification-empty">
                    <i class="bi bi-exclamation-circle"></i>
                    <p class="mb-0">Error al cargar notificaciones</p>
                </div>
            `;
        }
    }

    renderNotificationItem(notification) {
        const icon = this.getIconForType(notification.type);
        const color = this.getColorForType(notification.type);
        const unreadClass = notification.is_read ? '' : 'unread';
        const timeAgo = this.getTimeAgo(notification.created_at);

        let actionsHtml = '';

        if (notification.type === 'event_invitation' && !notification.is_read && notification.related_invitation_id) {
            actionsHtml = `
                <div class="notification-actions">
                    <button class="btn btn-sm btn-success"
                            data-respond-invitation="accepted"
                            data-notification-id="${notification.id}">
                        <i class="bi bi-check"></i> Aceptar
                    </button>
                    <button class="btn btn-sm btn-danger"
                            data-respond-invitation="rejected"
                            data-notification-id="${notification.id}">
                        <i class="bi bi-x"></i> Rechazar
                    </button>
                </div>
            `;
        }

        return `
            <div class="notification-item ${unreadClass}" data-id="${notification.id}">
                <div class="d-flex gap-3">
                    <div class="notification-icon bg-${color}">
                        <i class="${icon}"></i>
                    </div>
                    <div class="notification-content flex-grow-1">
                        <strong>${this.escapeHtml(notification.title)}</strong>
                        <p class="mb-1">${this.escapeHtml(notification.message)}</p>
                        ${actionsHtml}
                        <small>${timeAgo}</small>
                    </div>
                    ${!notification.is_read ? `
                        <button class="btn-mark-read" title="Marcar como leída">
                            <i class="bi bi-check"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
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
            'appointment_change_accepted': 'bi bi-calendar-check',
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
            'appointment_change_accepted': 'success',
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

    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return 'Hace unos segundos';
        if (seconds < 3600) return `Hace ${Math.floor(seconds / 60)} minutos`;
        if (seconds < 86400) return `Hace ${Math.floor(seconds / 3600)} horas`;
        if (seconds < 604800) return `Hace ${Math.floor(seconds / 86400)} días`;

        return date.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    }

    // ── Acciones ──────────────────────────────────────────────────────────────

    async handleNotificationClick(notificationId) {
        await this.markAsRead(notificationId);
        this.closeDropdown();
    }

    async markAsRead(notificationId) {
        try {
            const res = await window.apiClient.patch(`/api/v1/notifications/${notificationId}/read`);
            if (res.ok) {
                await this.updateBadge();
                await this.loadUnreadNotifications();
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    async markAllAsRead() {
        try {
            const res = await window.apiClient.post('/api/v1/notifications/mark-all-read');
            if (res.ok) {
                const json = await res.json();
                if (json.flash) {
                    json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
                }
                await this.updateBadge();
                await this.loadUnreadNotifications();
            }
        } catch (error) {
            console.error('Error marking all as read:', error);
        }
    }

    async respondInvitation(notificationId, response) {
        try {
            const res = await window.apiClient.post(
                `/api/v1/notifications/${notificationId}/respond-invitation`,
                { response }
            );
            const json = await res.json();
            if (json.flash) {
                json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
            }
            if (res.ok) {
                await this.updateBadge();
                await this.loadUnreadNotifications();
            }
        } catch (error) {
            console.error('Error responding to invitation:', error);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ── Inicialización ────────────────────────────────────────────────────────────

let notificationManager = null;

function initNotifications() {
    if (document.querySelector('#notificationBell')) {
        notificationManager = new NotificationManager();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotifications);
} else {
    initNotifications();
}

// Reiniciar con Swup — socket-client.js mantiene la conexión WS activa
if (typeof swup !== 'undefined') {
    swup.on('contentReplaced', () => {
        initNotifications();
    });
}

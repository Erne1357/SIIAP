// app/static/js/admin/settings/users.js
(function() {
    'use strict';
    
    const API_BASE = '/api/v1/admin/users';
    let currentPage = 1;
    let currentFilters = {};
    
    // Función para obtener CSRF token
    const getCsrf = () => {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    };
    
    // Cargar lista de usuarios
    async function loadUsers(page = 1) {
        const loadingIndicator = document.getElementById('loadingIndicator');
        const tableContainer = document.getElementById('usersTableContainer');
        const noResults = document.getElementById('noResultsMessage');
        
        loadingIndicator.style.display = 'block';
        tableContainer.style.display = 'none';
        noResults.style.display = 'none';
        
        // Construir query params
        const params = new URLSearchParams({
            page: page,
            per_page: 20,
            ...currentFilters
        });
        
        try {
            const res = await fetch(`${API_BASE}?${params}`);
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message || 'Error al cargar usuarios');
            
            console.log("JSON DATA en load users:", json);


            const { users, pagination } = json.data;
            
            loadingIndicator.style.display = 'none';
            
            if (users.length === 0) {
                noResults.style.display = 'block';
                return;
            }
            
            renderUsersTable(users);
            renderPagination(pagination);
            updateTotalCount(pagination.total);
            
            tableContainer.style.display = 'block';
            
        } catch (error) {
            console.error('Error:', error);
            loadingIndicator.style.display = 'none';
            showFlash('danger', 'Error al cargar usuarios: ' + error.message);
        }
    }
    
    // Renderizar tabla de usuarios
    function renderUsersTable(users) {
        const tbody = document.getElementById('usersTableBody');
        
        tbody.innerHTML = users.map(user => `
            <tr class="user-row" onclick="window.usersManager.showUserDetail(${user.id})">
                <td>
                    <div class="d-flex align-items-center">
                        <img src="${user.avatar_url}" class="rounded-circle user-avatar-sm me-2" alt="Avatar">
                        <div>
                            <div class="fw-semibold">${user.first_name} ${user.last_name}</div>
                            <small class="text-muted">${user.email}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="badge ${getRoleBadgeClass(user.role)}">
                        ${getRoleLabel(user.role)}
                    </span>
                </td>
                <td>
                    ${user.program 
                        ? `<span class="badge bg-secondary">${user.program.name}</span>` 
                        : '<small class="text-muted">Sin asignar</small>'
                    }
                </td>
                <td>
                    ${user.control_number 
                        ? `<span class="badge bg-dark control-number-badge">${user.control_number}</span>`
                        : '<small class="text-muted">Sin asignar</small>'
                    }
                </td>
                <td>
                    <span class="badge badge-status ${user.is_active ? 'bg-success' : 'bg-danger'}">
                        ${user.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                </td>
                <td class="text-end">
                    <div class="btn-group btn-group-sm" role="group" onclick="event.stopPropagation();">
                        <button class="btn btn-outline-primary" onclick="window.usersManager.editUser(${user.id})" 
                                title="Editar">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-warning" onclick="window.usersManager.resetPassword(${user.id}, '${user.first_name} ${user.last_name}')" 
                                title="Resetear contraseña">
                            <i class="bi bi-key"></i>
                        </button>
                        ${!user.control_number ? `
                        <button class="btn btn-outline-info" onclick="window.usersManager.assignControlNumber(${user.id})" 
                                title="Asignar # control">
                            <i class="bi bi-123"></i>
                        </button>
                        ` : ''}
                        <button class="btn btn-outline-${user.is_active ? 'danger' : 'success'}" 
                                onclick="window.usersManager.toggleUserActive(${user.id})" 
                                title="${user.is_active ? 'Desactivar' : 'Activar'}">
                            <i class="bi bi-${user.is_active ? 'x-circle' : 'check-circle'}"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }
    
    // Renderizar paginación
    function renderPagination(pagination) {
        const container = document.getElementById('paginationControls');
        const { page, pages, has_prev, has_next } = pagination;
        
        if (pages <= 1) {
            container.innerHTML = '';
            return;
        }
        
        let html = '';
        
        // Anterior
        html += `
            <li class="page-item ${!has_prev ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="window.usersManager.loadUsers(${page - 1}); return false;">
                    <i class="bi bi-chevron-left"></i>
                </a>
            </li>
        `;
        
        // Páginas
        for (let i = 1; i <= pages; i++) {
            if (i === 1 || i === pages || (i >= page - 2 && i <= page + 2)) {
                html += `
                    <li class="page-item ${i === page ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="window.usersManager.loadUsers(${i}); return false;">
                            ${i}
                        </a>
                    </li>
                `;
            } else if (i === page - 3 || i === page + 3) {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }
        
        // Siguiente
        html += `
            <li class="page-item ${!has_next ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="window.usersManager.loadUsers(${page + 1}); return false;">
                    <i class="bi bi-chevron-right"></i>
                </a>
            </li>
        `;
        
        container.innerHTML = html;
    }
    
    // Actualizar contador total
    function updateTotalCount(total) {
        document.getElementById('totalUsersCount').textContent = `${total} usuario${total !== 1 ? 's' : ''}`;
    }
    
    // Ver detalles de usuario
    async function showUserDetail(userId) {
        const modal = new bootstrap.Modal(document.getElementById('userDetailModal'));
        const content = document.getElementById('userDetailContent');
        
        content.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
        modal.show();
        
        try {
            const res = await fetch(`${API_BASE}/${userId}`);
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);

            console.log("JSON DATA en showUserDetail:", json);


            const user = json.data.user;
            const program = json.data.user.program;
            const history = json.data.history || [];
            
            content.innerHTML = `
                <div class="row">
                    <div class="col-md-4 text-center">
                        <img src="${user.avatar_url}" class="rounded-circle" style="width: 150px; height: 150px;">
                        <h5 class="mt-3">${user.first_name} ${user.last_name}</h5>
                        <span class="badge ${getRoleBadgeClass(user.role)}">${getRoleLabel(user.role)}</span>
                        <br>
                        <span class="badge ${user.is_active ? 'bg-success' : 'bg-danger'} mt-2">
                            ${user.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </div>
                    <div class="col-md-8">
                        <h6>Información Básica</h6>
                        <table class="table table-sm">
                            <tr><th>Email:</th><td>${user.email}</td></tr>
                            <tr><th>Username:</th><td>${user.username}</td></tr>
                            <tr><th>Teléfono:</th><td>${user.phone || 'No registrado'}</td></tr>
                            <tr><th>CURP:</th><td>${user.curp || 'No registrado'}</td></tr>
                            <tr><th>Fecha de registro:</th><td>${formatDate(user.registration_date)}</td></tr>
                            <tr><th>Último acceso:</th><td>${formatDate(user.last_login)}</td></tr>
                        </table>
                        
                        ${program ? `
                        <h6 class="mt-3">Programa</h6>
                        <p><strong>${program.name}</strong> (${program.slug})</p>
                        ` : ''}
                        
                        ${user.control_number ? `
                        <h6 class="mt-3">Número de Control</h6>
                        <p class="font-monospace fs-5">${user.control_number}</p>
                        ` : ''}
                        
                        <h6 class="mt-3">Historial Reciente</h6>
                        ${history.length > 0 ? `
                            <ul class="list-group list-group-flush">
                                ${history.slice(0, 5).map(entry => `
                                    <li class="list-group-item px-0 py-2">
                                        <small>
                                            <strong>${entry.action_label}</strong><br>
                                            ${entry.admin_name} - ${formatDate(entry.timestamp)}
                                        </small>
                                    </li>
                                `).join('')}
                            </ul>
                        ` : '<p class="text-muted">Sin historial</p>'}
                        
                        ${history.length > 5 ? `
                            <button class="btn btn-sm btn-link" onclick="window.usersManager.showHistory(${userId})">
                                Ver historial completo
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
            
        } catch (error) {
            content.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    }
    
    // Editar usuario
    async function editUser(userId) {
        try {
            const res = await fetch(`${API_BASE}/${userId}`);
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            const user = json.data.user;
            
            document.getElementById('edit_user_id').value = user.id;
            document.getElementById('edit_first_name').value = user.first_name;
            document.getElementById('edit_last_name').value = user.last_name;
            document.getElementById('edit_mother_last_name').value = user.mother_last_name || '';
            document.getElementById('edit_email').value = user.email;
            
            const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
            modal.show();
            
        } catch (error) {
            showFlash('danger', 'Error al cargar usuario: ' + error.message);
        }
    }
    
    // Guardar cambios de edición
    async function saveUserEdit(event) {
        event.preventDefault();
        
        const userId = document.getElementById('edit_user_id').value;
        const data = {
            first_name: document.getElementById('edit_first_name').value,
            last_name: document.getElementById('edit_last_name').value,
            mother_last_name: document.getElementById('edit_mother_last_name').value,
            email: document.getElementById('edit_email').value
        };
        
        try {
            const res = await fetch(`${API_BASE}/${userId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrf()
                },
                body: JSON.stringify(data)
            });
            
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            if (json.flash) {
                json.flash.forEach(f => showFlash(f.level, f.message));
            }
            
            bootstrap.Modal.getInstance(document.getElementById('editUserModal')).hide();
            loadUsers(currentPage);
            
        } catch (error) {
            showFlash('danger', 'Error al guardar: ' + error.message);
        }
    }
    
    // Resetear contraseña
    async function resetPassword(userId, userName) {
        if (!confirm(`¿Resetear la contraseña de ${userName} a "tecno#2K"?\n\nEl usuario deberá cambiarla en su próximo inicio de sesión.`)) {
            return;
        }
        
        try {
            const res = await fetch(`${API_BASE}/${userId}/reset-password`, {
                method: 'POST',
                headers: {
                    'X-CSRF-Token': getCsrf()
                }
            });
            
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            if (json.flash) {
                json.flash.forEach(f => showFlash(f.level, f.message));
            }
            
        } catch (error) {
            showFlash('danger', 'Error: ' + error.message);
        }
    }
    
    // Toggle activo/inactivo
    async function toggleUserActive(userId) {
        try {
            const res = await fetch(`${API_BASE}/${userId}/toggle-active`, {
                method: 'PATCH',
                headers: {
                    'X-CSRF-Token': getCsrf()
                }
            });
            
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            if (json.flash) {
                json.flash.forEach(f => showFlash(f.level, f.message));
            }
            
            loadUsers(currentPage);
            
        } catch (error) {
            showFlash('danger', 'Error: ' + error.message);
        }
    }
    
    // Asignar número de control
    async function assignControlNumber(userId) {
        try {
            const res = await fetch(`${API_BASE}/${userId}`);
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            const user = json.data.user;
            const program = json.data.user.program;
            
            if (!program) {
                showFlash('warning', 'El usuario debe tener un programa asignado primero.');
                return;
            }
            
            document.getElementById('control_user_id').value = user.id;
            document.getElementById('control_user_name').value = `${user.first_name} ${user.last_name}`;
            document.getElementById('control_program_name').value = program.name;
            document.getElementById('control_number').value = '';
            document.getElementById('controlNumberFeedback').textContent = '';
            
            const modal = new bootstrap.Modal(document.getElementById('assignControlNumberModal'));
            modal.show();
            
        } catch (error) {
            showFlash('danger', 'Error: ' + error.message);
        }
    }
    
    // Guardar número de control
    async function saveControlNumber(event) {
        event.preventDefault();
        
        const userId = document.getElementById('control_user_id').value;
        const controlNumber = document.getElementById('control_number').value.trim().toUpperCase();
        
        // Validación básica del formato
        if (!/^[MD]\d{8}$/.test(controlNumber)) {
            showFlash('danger', 'Formato inválido. Debe ser M o D seguido de 8 dígitos.');
            return;
        }
        
        try {
            const res = await fetch(`${API_BASE}/${userId}/assign-control-number`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrf()
                },
                body: JSON.stringify({ control_number: controlNumber })
            });
            
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            if (json.flash) {
                json.flash.forEach(f => showFlash(f.level, f.message));
            }
            
            bootstrap.Modal.getInstance(document.getElementById('assignControlNumberModal')).hide();
            loadUsers(currentPage);
            
        } catch (error) {
            showFlash('danger', 'Error: ' + error.message);
        }
    }
    
    // Ver historial completo
    async function showHistory(userId) {
        const modal = new bootstrap.Modal(document.getElementById('userHistoryModal'));
        const content = document.getElementById('userHistoryContent');
        
        content.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
        modal.show();
        
        try {
            const res = await fetch(`${API_BASE}/${userId}/history`);
            const json = await res.json();
            
            if (!res.ok) throw new Error(json.error?.message);
            
            const history = json.data.history || [];
            
            if (history.length === 0) {
                content.innerHTML = '<p class="text-center text-muted">Sin historial</p>';
                return;
            }
            
            content.innerHTML = `
                <div class="list-group">
                    ${history.map(entry => `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">${entry.action_label}</h6>
                                    ${entry.details ? `<p class="mb-1 small">${entry.details}</p>` : ''}
                                    <small class="text-muted">Por: ${entry.admin_name}</small>
                                </div>
                                <small class="text-muted">${formatDate(entry.timestamp)}</small>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
        } catch (error) {
            content.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    }
    
    // Aplicar filtros
    function applyFilters() {
        currentFilters = {};
        
        const search = document.getElementById('searchInput').value.trim();
        if (search) currentFilters.search = search;
        
        const role = document.getElementById('roleFilter').value;
        if (role) currentFilters.role = role;
        
        const active = document.getElementById('activeFilter').value;
        if (active !== 'all') currentFilters.active = active;
        
        currentPage = 1;
        loadUsers(1);
    }
    
    // Limpiar filtros
    function clearFilters() {
        document.getElementById('searchInput').value = '';
        document.getElementById('roleFilter').value = '';
        document.getElementById('activeFilter').value = 'true';
        currentFilters = {};
        currentPage = 1;
        loadUsers(1);
    }
    
    // Utilidades
    function getRoleBadgeClass(role) {
        const classes = {
            'applicant': 'bg-info',
            'student': 'bg-primary',
            'graduate': 'bg-success',
            'program_admin': 'bg-warning text-dark',
            'postgraduate_admin': 'bg-danger',
            'social_service': 'bg-secondary'
        };
        return classes[role] || 'bg-secondary';
    }
    
    function getRoleLabel(role) {
        const labels = {
            'applicant': 'Aspirante',
            'student': 'Estudiante',
            'graduate': 'Egresado',
            'program_admin': 'Admin. Programa',
            'postgraduate_admin': 'Admin. Posgrado',
            'social_service': 'Servicio Social'
        };
        return labels[role] || role;
    }
    
    function formatDate(isoString) {
        if (!isoString) return 'N/A';
        const date = new Date(isoString);
        return date.toLocaleDateString('es-MX', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
    
    function showFlash(level, message) {
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level, message }
        }));
    }
    
    // Event Listeners
    document.addEventListener('DOMContentLoaded', function() {
        // Cargar usuarios inicial
        loadUsers();
        
        // Búsqueda
        document.getElementById('btnSearch').addEventListener('click', applyFilters);
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') applyFilters();
        });
        
        // Limpiar filtros
        document.getElementById('btnClearFilters').addEventListener('click', clearFilters);
        
        // Formularios
        document.getElementById('editUserForm').addEventListener('submit', saveUserEdit);
        document.getElementById('assignControlNumberForm').addEventListener('submit', saveControlNumber);
        
        // Validación en tiempo real del número de control
        const controlInput = document.getElementById('control_number');
        if (controlInput) {
            controlInput.addEventListener('input', function() {
                const value = this.value.toUpperCase();
                const feedback = document.getElementById('controlNumberFeedback');
                
                if (!value) {
                    feedback.textContent = '';
                    feedback.className = 'form-text';
                } else if (!/^[MD]\d{0,8}$/.test(value)) {
                    feedback.textContent = 'Debe comenzar con M o D seguido de 8 dígitos';
                    feedback.className = 'form-text text-danger';
                } else if (value.length < 9) {
                    feedback.textContent = `Faltan ${9 - value.length} dígitos`;
                    feedback.className = 'form-text text-warning';
                } else {
                    feedback.textContent = '✓ Formato correcto';
                    feedback.className = 'form-text text-success';
                }
            });
        }
    });
    
    // Exportar funciones al window para usarlas desde el HTML
    window.usersManager = {
        loadUsers,
        showUserDetail,
        editUser,
        resetPassword,
        toggleUserActive,
        assignControlNumber,
        showHistory
    };
})();
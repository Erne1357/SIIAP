// app/static/js/admin/settings/users.js
(function() {
    'use strict';
    
    // Usar el origen actual para evitar problemas de mixed content en HTTPS
    const API_BASE = `${window.location.origin}/api/v1/admin/users`;
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
                        ${(!user.control_number && user.role === 'applicant') ? `
                        <button class="btn btn-outline-info" onclick="window.usersManager.assignControlNumber(${user.id})"
                                title="Asignar # control y transicionar a estudiante">
                            <i class="bi bi-123"></i>
                        </button>
                        ` : ''}
                        <button class="btn btn-outline-${user.is_active ? 'danger' : 'success'}"
                                onclick="window.usersManager.toggleUserActive(${user.id})"
                                title="${user.is_active ? 'Desactivar' : 'Activar'}">
                            <i class="bi bi-${user.is_active ? 'x-circle' : 'check-circle'}"></i>
                        </button>
                        ${window.siiapStudentRecordBtn ? window.siiapStudentRecordBtn(user.id) : ''}
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
                <div id="userDelegationsSection"></div>
            `;

            if (user.role === 'social_service') {
                const section = document.getElementById('userDelegationsSection');
                if (section) {
                    section.innerHTML = '<div class="text-center py-2"><div class="spinner-border spinner-border-sm"></div></div>';
                    const delsHtml = await loadUserDelegations(userId);
                    section.innerHTML = delsHtml;
                }
            }

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
                    'X-CSRFToken': getCsrf()
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
        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Resetear contraseña',
            message: `¿Resetear la contraseña de ${userName} a "tecno#2K"?\n\nEl usuario deberá cambiarla en su próximo inicio de sesión.`,
            confirmLabel: 'Sí, resetear',
        });
        if (!ok) return;
        
        try {
            const res = await fetch(`${API_BASE}/${userId}/reset-password`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrf()
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
                    'X-CSRFToken': getCsrf()
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
                    'X-CSRFToken': getCsrf()
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
    
    // ========================================================================
    // Servicio Social — crear usuario con delegación
    // ========================================================================

    const PERMISSIONS_API = `${window.location.origin}/api/v1/permissions`;

    let delegatableCache = null;

    async function openCreateSocialService() {
        const ctx = window.SIIAP_USERS_CTX || {};
        const form = document.getElementById('createSocialServiceForm');
        if (form) form.reset();

        const scopeInfo = document.getElementById('ss_scope_info');
        if (ctx.canDelegateGlobal) {
            scopeInfo.style.display = 'none';
        } else {
            const progs = (ctx.coordinatedProgramNames || []).join(', ') || '(sin programas)';
            scopeInfo.innerHTML = `<i class="bi bi-diagram-3 me-1"></i>Ámbito de delegación: <strong>${progs}</strong>. Los permisos se aplicarán a cada uno de tus programas coordinados.`;
            scopeInfo.style.display = 'block';
        }

        const list = document.getElementById('ss_permissions_list');
        const loading = document.getElementById('ss_permissions_loading');
        list.style.display = 'none';
        loading.style.display = 'block';

        const modal = new bootstrap.Modal(document.getElementById('createSocialServiceModal'));
        modal.show();

        try {
            if (!delegatableCache) {
                const res = await fetch(`${PERMISSIONS_API}/delegatable`);
                const json = await res.json();
                if (!res.ok) throw new Error(json.error?.message || 'Error al cargar permisos');
                delegatableCache = json.data || [];
            }
            renderDelegatablePermissions(delegatableCache);
        } catch (error) {
            loading.innerHTML = `<div class="alert alert-danger mb-0">${error.message}</div>`;
        }
    }

    function renderDelegatablePermissions(perms) {
        const list = document.getElementById('ss_permissions_list');
        const loading = document.getElementById('ss_permissions_loading');

        if (!perms.length) {
            loading.innerHTML = `<div class="alert alert-warning mb-0">No tienes permisos delegables.</div>`;
            return;
        }

        const byResource = {};
        perms.forEach(p => {
            const res = p.codename.split('.')[0];
            if (!byResource[res]) byResource[res] = [];
            byResource[res].push(p);
        });

        const html = Object.keys(byResource).sort().map(resource => {
            const items = byResource[resource].map(p => `
                <div class="form-check">
                    <input class="form-check-input ss-perm-check" type="checkbox"
                           id="ss_perm_${p.permission_id}" value="${p.codename}">
                    <label class="form-check-label small" for="ss_perm_${p.permission_id}">
                        <code class="small">${p.codename}</code>
                        <span class="text-muted ms-1">— ${p.display_name}</span>
                    </label>
                </div>
            `).join('');
            return `
                <div class="mb-2">
                    <div class="fw-semibold text-uppercase small text-muted mb-1">${resource}</div>
                    ${items}
                </div>
            `;
        }).join('');

        list.innerHTML = `
            <div class="d-flex justify-content-between mb-2">
                <small class="text-muted"><span id="ssSelectedCount">0</span> de ${perms.length} seleccionados</small>
                <div>
                    <button type="button" class="btn btn-link btn-sm p-0 me-2" id="ssSelectAllBtn">Seleccionar todos</button>
                    <button type="button" class="btn btn-link btn-sm p-0" id="ssClearAllBtn">Limpiar</button>
                </div>
            </div>
            <div class="border rounded p-3" style="max-height: 320px; overflow-y: auto;">${html}</div>
        `;

        loading.style.display = 'none';
        list.style.display = 'block';

        list.querySelectorAll('.ss-perm-check').forEach(cb => {
            cb.addEventListener('change', updateSelectedCount);
        });
        document.getElementById('ssSelectAllBtn').addEventListener('click', () => {
            list.querySelectorAll('.ss-perm-check').forEach(cb => cb.checked = true);
            updateSelectedCount();
        });
        document.getElementById('ssClearAllBtn').addEventListener('click', () => {
            list.querySelectorAll('.ss-perm-check').forEach(cb => cb.checked = false);
            updateSelectedCount();
        });

        updateSelectedCount();
    }

    function updateSelectedCount() {
        const count = document.querySelectorAll('.ss-perm-check:checked').length;
        const el = document.getElementById('ssSelectedCount');
        if (el) el.textContent = count;
    }

    async function submitCreateSocialService(event) {
        event.preventDefault();

        const selected = Array.from(document.querySelectorAll('.ss-perm-check:checked')).map(cb => cb.value);
        if (!selected.length) {
            showFlash('warning', 'Selecciona al menos un permiso.');
            return;
        }

        const ctx = window.SIIAP_USERS_CTX || {};
        const expiresDate = document.getElementById('ss_expires_at').value;
        let expires_at = null;
        if (expiresDate) {
            expires_at = new Date(expiresDate + 'T23:59:59').toISOString();
        }

        const payload = {
            first_name:       document.getElementById('ss_first_name').value.trim(),
            last_name:        document.getElementById('ss_last_name').value.trim(),
            mother_last_name: document.getElementById('ss_mother_last_name').value.trim() || null,
            email:            document.getElementById('ss_email').value.trim().toLowerCase(),
            permissions:      selected,
            expires_at:       expires_at,
        };

        if (ctx.canDelegateGlobal) {
            payload.program_ids = null;
        }

        const btn = event.submitter;
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Creando...'; }

        try {
            const res = await fetch(`${API_BASE}/social-service`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf()
                },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (!res.ok) throw new Error(json.error?.message || 'Error al crear usuario');

            if (json.flash) json.flash.forEach(f => showFlash(f.level, f.message));

            bootstrap.Modal.getInstance(document.getElementById('createSocialServiceModal')).hide();
            delegatableCache = null;
            currentFilters = { role: 'social_service' };
            document.getElementById('roleFilter').value = 'social_service';
            loadUsers(1);
        } catch (error) {
            showFlash('danger', error.message);
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Crear y Delegar'; }
        }
    }

    // ========================================================================
    // Delegaciones de un usuario (vista + revocación)
    // ========================================================================

    async function loadUserDelegations(userId) {
        const ctx = window.SIIAP_USERS_CTX || {};
        if (!ctx.canViewDelegations) return '';

        try {
            const res = await fetch(`${PERMISSIONS_API}/user/${userId}`);
            const json = await res.json();
            if (!res.ok) return '';
            const dels = json.data || [];
            if (!dels.length) {
                return `<div class="text-muted small mt-2">Sin permisos delegados directos.</div>`;
            }

            const rows = dels.map(d => {
                const active = d.is_active && !d.is_expired;
                const scope = d.program_name
                    ? d.program_name
                    : (d.program_id ? `Programa #${d.program_id}` : 'Global');
                const expires = d.expires_at
                    ? `<small class="text-muted ms-2">Vence: ${formatDate(d.expires_at)}</small>`
                    : '';
                const revokeBtn = (active && ctx.canRevokeDelegations)
                    ? `<button class="btn btn-sm btn-outline-danger" onclick="window.usersManager.revokeDelegation(${d.id}, ${userId})" title="Revocar">
                           <i class="bi bi-x-circle"></i>
                       </button>`
                    : '';
                return `
                    <tr class="${active ? '' : 'text-muted'}">
                        <td>
                            <code class="small">${d.permission_codename || ''}</code>
                            ${d.permission_display_name ? `<div class="text-muted small">${d.permission_display_name}</div>` : ''}
                        </td>
                        <td>${scope}</td>
                        <td>
                            ${active
                                ? '<span class="badge bg-success">Activa</span>'
                                : (d.is_expired
                                    ? '<span class="badge bg-warning text-dark">Vencida</span>'
                                    : '<span class="badge bg-secondary">Revocada</span>')}
                            ${expires}
                        </td>
                        <td class="text-end">${revokeBtn}</td>
                    </tr>
                `;
            }).join('');

            return `
                <h6 class="mt-3"><i class="bi bi-shield-check me-1"></i>Permisos Delegados</h6>
                <div class="table-responsive">
                    <table class="table table-sm table-hover mb-0">
                        <thead class="table-light">
                            <tr><th>Permiso</th><th>Ámbito</th><th>Estado</th><th></th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `;
        } catch (error) {
            return `<div class="alert alert-warning small mt-2">No se pudieron cargar las delegaciones.</div>`;
        }
    }

    async function revokeDelegation(upId, userId) {
        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Revocar delegación',
            message: '¿Revocar este permiso delegado? El usuario perderá acceso inmediatamente.',
            confirmLabel: 'Sí, revocar',
        });
        if (!ok) return;

        try {
            const res = await fetch(`${PERMISSIONS_API}/delegation/${upId}`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': getCsrf() }
            });
            const json = await res.json();
            if (!res.ok) throw new Error(json.error?.message || 'Error al revocar');
            if (json.flash) json.flash.forEach(f => {
                const level = Array.isArray(f) ? f[1] : f.level;
                const message = Array.isArray(f) ? f[0] : f.message;
                showFlash(level, message);
            });
            if (userId) showUserDetail(userId);
        } catch (error) {
            showFlash('danger', error.message);
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

        // Tiempo real: otro admin creó/modificó/eliminó un usuario → refrescar lista
        window.addEventListener('siiap:admin_user:changed', (e) => {
            const d = e.detail || {};
            const labels = { created: 'creado', updated: 'modificado', deleted: 'eliminado' };
            const verb = labels[d.action] || 'modificado';
            showFlash('info', `Usuario ${verb}: ${d.full_name || d.email || ''}. Actualizando lista...`);
            loadUsers(currentPage);
        });

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

        // Crear servicio social
        const btnCreateSS = document.getElementById('btnCreateSocialService');
        if (btnCreateSS) btnCreateSS.addEventListener('click', openCreateSocialService);
        const ssForm = document.getElementById('createSocialServiceForm');
        if (ssForm) ssForm.addEventListener('submit', submitCreateSocialService);
        
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
        showHistory,
        openCreateSocialService,
        revokeDelegation
    };
})();
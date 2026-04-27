// app/static/js/admin/events/events.js
(() => {
    const API = "/api/v1";

    // Elementos DOM
    const eventsTable = document.getElementById("eventsTable");
    const slotsTable = document.getElementById("slotsTable");
    const slotsCard = document.getElementById("slotsCard");
    const selectedEventTitle = document.getElementById("selectedEventTitle");
    const eligibleStudents = document.getElementById("eligibleStudents");

    // Modales - Inicialización segura
    const createEventModalEl = document.getElementById("createEventModal");
    const addWindowModalEl = document.getElementById("addWindowModal");
    const assignSlotModalEl = document.getElementById("assignSlotModal");
    const confirmDeleteEventModalEl = document.getElementById("confirmDeleteEventModal");
    const confirmCancelAppointmentModalEl = document.getElementById("confirmCancelAppointmentModal");

    const createEventModal = createEventModalEl ? new bootstrap.Modal(createEventModalEl) : null;
    const addWindowModal = addWindowModalEl ? new bootstrap.Modal(addWindowModalEl) : null;
    const assignSlotModal = assignSlotModalEl ? new bootstrap.Modal(assignSlotModalEl) : null;
    const confirmDeleteEventModal = confirmDeleteEventModalEl ? new bootstrap.Modal(confirmDeleteEventModalEl) : null;
    const confirmCancelAppointmentModal = confirmCancelAppointmentModalEl ? new bootstrap.Modal(confirmCancelAppointmentModalEl) : null;

    const acceptChangeRequestModalEl = document.getElementById("acceptChangeRequestModal");
    const acceptChangeRequestModal = acceptChangeRequestModalEl ? new bootstrap.Modal(acceptChangeRequestModalEl) : null;

    // Formularios
    const createEventForm = document.getElementById("createEventForm");
    const addWindowForm = document.getElementById("addWindowForm");
    const assignSlotForm = document.getElementById("assignSlotForm");
    const cancelAppointmentForm = document.getElementById("cancelAppointmentForm");

    // Estado
    let currentEvents = [];
    let currentSlots = [];
    let eligibleStudentsList = [];
    let currentChangeRequests = [];
    let selectedEventId = null;
    let programs = [];

    let currentWindows = [];
    const confirmDeleteWindowModalEl = document.getElementById("confirmDeleteWindowModal");
    const confirmDeleteSlotModalEl = document.getElementById("confirmDeleteSlotModal");
    const confirmDeleteWindowModal = confirmDeleteWindowModalEl ? new bootstrap.Modal(confirmDeleteWindowModalEl) : null;
    const confirmDeleteSlotModal = confirmDeleteSlotModalEl ? new bootstrap.Modal(confirmDeleteSlotModalEl) : null;
    const windowsTable = document.getElementById("windowsTable");

    const viewRegistrationsModal = new bootstrap.Modal(document.getElementById("viewRegistrationsModal"));
    const registrationsTable = document.getElementById("registrationsTable");
    let currentRegistrations = [];
    let currentFilterStatus = '';

    function flash(message, level = "success") {
        window.dispatchEvent(new CustomEvent('flash', {
            detail: { level: level, message: message }
        }));
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
    async function apiRequest(url, options = {}) {
        const defaultOptions = {
            credentials: "same-origin",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                ...options.headers
            }
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('text/html')) {
                throw new Error('No tienes permisos para realizar esta acción');
            }

            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                throw new Error('Error al procesar la respuesta del servidor');
            }

            if (!response.ok) {
                throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
            }

            if (data.ok === false) {
                throw new Error(data.error || 'Operación fallida');
            }

            return { response, data };
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    // ========== CARGA INICIAL ==========
    async function init() {
        await loadPrograms();
        await loadAcademicPeriods();
        await loadEvents();
        await loadEligibleStudents();
        setupEventListeners();
        setupFiltersHandler();
        // New UX features (Fase 4)
        setupWizard();
        setupCoverDropzone();
        setupGalleryDropzone();
        setupHostsPanel();
        setupHostEditor();
        setupContentTabVisibility();
        setupEventEditor();
    }

    async function loadPrograms() {
        try {
            // CAMBIAR: Usar API correcta de programas
            const { data } = await apiRequest(`${API}/programs`);
            programs = data.data || [];  // Nota: la API devuelve {data: [...]}

            const programSelects = [
                document.getElementById("eventProgram"),
                document.getElementById("programFilter"),
                document.getElementById("filterProgram"),
                document.getElementById("editProgram")
            ];

            programSelects.forEach(select => {
                if (select) {
                    // AGREGAR OPCIÓN "TODOS LOS PROGRAMAS"
                    let html = '<option value="">Todos los programas</option>';
                    html += programs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
                    select.innerHTML = html;
                }
            });

        } catch (err) {
            console.error('Error loading programs:', err);
        }
    }

    async function loadAcademicPeriods() {
        try {
            const { data } = await apiRequest(`${API}/academic-periods`);
            const periods = data.data || data.items || [];

            const formSelect = document.getElementById('eventAcademicPeriod');
            const filterSelect = document.getElementById('filterAcademicPeriod');

            if (formSelect) {
                let html = '<option value="">Sin periodo (atemporal)</option>';
                html += periods.map(p => {
                    const tag = p.status === 'active' ? ' (activo)' : '';
                    const selected = p.status === 'active' ? 'selected' : '';
                    return `<option value="${p.id}" ${selected}>${p.code} — ${p.name}${tag}</option>`;
                }).join('');
                formSelect.innerHTML = html;
            }

            if (filterSelect) {
                let html = '<option value="">Todos los periodos</option>';
                html += periods.map(p => {
                    const tag = p.status === 'active' ? ' (activo)' : '';
                    return `<option value="${p.id}">${p.code}${tag}</option>`;
                }).join('');
                filterSelect.innerHTML = html;
            }

            const editSelect = document.getElementById('editAcademicPeriod');
            if (editSelect) {
                let html = '<option value="">Sin periodo (atemporal)</option>';
                html += periods.map(p => {
                    const tag = p.status === 'active' ? ' (activo)' : '';
                    return `<option value="${p.id}">${p.code} — ${p.name}${tag}</option>`;
                }).join('');
                editSelect.innerHTML = html;
            }
        } catch (err) {
            console.error('Error loading academic periods:', err);
        }
    }

    function buildFilterQuery() {
        const params = new URLSearchParams();
        const map = {
            academic_period_id: document.getElementById('filterAcademicPeriod')?.value,
            program_id: document.getElementById('filterProgram')?.value,
            type: document.getElementById('filterType')?.value,
            status: document.getElementById('filterStatus')?.value,
            search: document.getElementById('filterSearch')?.value?.trim(),
        };
        Object.entries(map).forEach(([k, v]) => {
            if (v) params.append(k, v);
        });
        const qs = params.toString();
        return qs ? `?${qs}` : '';
    }

    async function loadEvents() {
        try {
            const qs = buildFilterQuery();
            const { data } = await apiRequest(`${API}/events${qs}`);
            currentEvents = data.items || [];
            renderEventsTable();

        } catch (err) {
            console.error('Error loading events:', err);
            flash(`Error cargando eventos: ${err.message}`, 'danger');
        }
    }

    function setupFiltersHandler() {
        const ids = ['filterAcademicPeriod', 'filterProgram', 'filterType', 'filterStatus'];
        ids.forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => loadEvents());
        });
        let searchTimer = null;
        document.getElementById('filterSearch')?.addEventListener('input', () => {
            if (searchTimer) clearTimeout(searchTimer);
            searchTimer = setTimeout(() => loadEvents(), 350);
        });
    }

    function renderEventsTable() {
        const tbody = eventsTable?.querySelector('tbody');
        if (!tbody) return;

        if (currentEvents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay eventos creados</td></tr>';
            return;
        }

        tbody.innerHTML = currentEvents.map(event => {
            // Determinar badge de tipo de capacidad
            let capacityBadge = '';
            if (event.capacity_type === 'single') {
                capacityBadge = '<span class="badge bg-info me-1" title="Capacidad Individual">1:1</span>';
            } else if (event.capacity_type === 'multiple') {
                capacityBadge = `<span class="badge bg-warning me-1" title="Capacidad Múltiple">Max: ${event.max_capacity || '?'}</span>`;
            } else if (event.capacity_type === 'unlimited') {
                capacityBadge = '<span class="badge bg-success me-1" title="Sin Límite">∞</span>';
            }

            // CAMBIAR: Manejar programa null
            const programBadge = event.program_name
                ? `<span class="badge bg-primary">${event.program_name}</span>`
                : `<span class="badge bg-secondary">Todos los programas</span>`;

            const statusMap = {
                draft:      { label: 'Borrador',   cls: 'bg-secondary' },
                published:  { label: 'Publicado',  cls: 'bg-success'   },
                ongoing:    { label: 'En curso',   cls: 'bg-info'      },
                completed:  { label: 'Concluido',  cls: 'bg-dark'      },
                archived:   { label: 'Archivado',  cls: 'bg-warning text-dark' },
                cancelled:  { label: 'Cancelado',  cls: 'bg-danger'    }
            };
            const s = statusMap[event.status] || { label: event.status || '?', cls: 'bg-light text-dark' };
            const statusBadge = `<span class="badge ${s.cls}">${s.label}</span>`;

            const privacyBadge = event.visibility === 'private'
                ? '<span class="badge bg-warning text-dark ms-1" title="Privado — solo invitados"><i class="bi bi-lock-fill"></i> Privado</span>'
                : '';

            const canConclude = ['published', 'ongoing'].includes(event.status);
            const canArchive = event.status !== 'archived';
            const canUnarchive = event.status === 'archived';

            return `
      <tr data-event-id="${event.id}" class="event-row">
        <td>
          <div class="fw-semibold">${event.title}</div>
          <small class="text-muted">
            ${event.type === 'interview' ? 'Entrevista' :
                    event.type === 'defense' ? 'Defensa' :
                        event.type === 'workshop' ? 'Taller' :
                            event.type === 'seminar' ? 'Seminario' :
                                event.type === 'conference' ? 'Conferencia' :
                                    event.type === 'info_session' ? 'Sesión Info' : 'Otro'}
          </small>
          <div class="mt-1">${capacityBadge}${statusBadge}${privacyBadge}</div>
        </td>
        <td>
          ${programBadge}
        </td>
        <td class="text-center">${event.windows_count || 0}</td>
        <td class="text-center">${event.slots_total || 0}</td>
        <td class="text-center">
          <span class="badge bg-${event.slots_booked > 0 ? 'warning' : 'secondary'}">
            ${event.slots_booked || 0}
          </span>
        </td>
        <td class="text-end">
          <div class="d-inline-flex gap-1 align-items-center event-actions-primary">
            <button class="btn btn-outline-primary btn-sm btn-view-slots" title="Ver / gestionar horarios">
              <i class="bi bi-calendar-week me-1"></i>Gestionar
            </button>
            ${event.capacity_type !== 'single' ? `
              <button class="btn btn-outline-success btn-sm btn-view-registrations" title="Ver registros">
                <i class="bi bi-people"></i>
              </button>
            ` : ''}
            <div class="dropdown event-actions-dropdown">
              <button class="btn btn-outline-secondary btn-sm dropdown-toggle" type="button"
                      data-bs-toggle="dropdown" aria-expanded="false" title="Más acciones">
                <i class="bi bi-three-dots-vertical"></i>
              </button>
              <ul class="dropdown-menu dropdown-menu-end">
                ${canConclude ? `
                  <li>
                    <button class="dropdown-item btn-conclude-event">
                      <i class="bi bi-flag-fill me-2 text-dark"></i>Concluir evento
                    </button>
                  </li>
                ` : ''}
                ${canArchive ? `
                  <li>
                    <button class="dropdown-item btn-archive-event">
                      <i class="bi bi-archive me-2 text-warning"></i>Archivar
                    </button>
                  </li>
                ` : ''}
                ${canUnarchive ? `
                  <li>
                    <button class="dropdown-item btn-unarchive-event">
                      <i class="bi bi-arrow-counterclockwise me-2 text-success"></i>Reactivar
                    </button>
                  </li>
                ` : ''}
                <li><hr class="dropdown-divider"></li>
                <li>
                  <button class="dropdown-item text-danger btn-delete-event">
                    <i class="bi bi-trash me-2"></i>Eliminar
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </td>
      </tr>
    `;
        }).join('');
    }

    async function loadSlots(eventId) {
        try {
            // Cargar slots y obtener información de appointments
            const { data: slotsData } = await apiRequest(`${API}/events/${eventId}/slots`);

            // Para cada slot, si está booked, obtener info del appointment
            const slotsWithInfo = await Promise.all(
                (slotsData.items || []).map(async (slot) => {
                    if (slot.status === 'booked') {
                        try {
                            const { data: apptData } = await apiRequest(`${API}/appointments/by-slot/${slot.id}`);
                            if (apptData.appointment) {
                                return {
                                    ...slot,
                                    appointment_id: apptData.appointment.id,
                                    student_name: apptData.appointment.student?.full_name || 'Sin asignar'
                                };
                            }
                        } catch (err) {
                            console.error(`Error loading appointment for slot ${slot.id}:`, err);
                        }
                    }
                    return slot;
                })
            );

            currentSlots = slotsWithInfo;
            renderSlotsTable();
            updateSlotCounts();

        } catch (err) {
            console.error('Error loading slots:', err);
            flash(`Error cargando horarios: ${err.message}`, 'danger');
        }
    }

    function renderSlotsTable() {
        const tbody = slotsTable?.querySelector('tbody');
        if (!tbody) return;

        if (currentSlots.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No hay horarios generados</td></tr>';
            return;
        }

        tbody.innerHTML = currentSlots.map(slot => {
            const startTime = new Date(slot.starts_at);
            const endTime = new Date(slot.ends_at);
            const dateStr = startTime.toLocaleDateString('es-MX');
            const timeStr = `${startTime.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${endTime.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;

            return `
      <tr data-slot-id="${slot.id}" class="slot-${slot.status}">
        <td>${dateStr}</td>
        <td>${timeStr}</td>
        <td class="text-center">
          <span class="badge bg-${slot.status === 'free' ? 'success' : slot.status === 'booked' ? 'primary' : 'secondary'}">
            ${slot.status === 'free' ? 'Libre' : slot.status === 'booked' ? 'Ocupado' : slot.status}
          </span>
        </td>
        <td>
          ${slot.student_name || '—'}
        </td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            ${slot.status === 'free' ? `
              <button class="btn btn-outline-primary btn-assign-slot" 
                      data-slot-id="${slot.id}" 
                      data-slot-info="${dateStr} ${timeStr}">
                <i class="fas fa-user-plus"></i>
              </button>
            ` : slot.status === 'booked' && slot.appointment_id ? `
              <button class="btn btn-outline-danger btn-cancel-appointment" 
                      data-appointment-id="${slot.appointment_id}"
                      data-slot-info="${dateStr} ${timeStr}"
                      data-student-name="${slot.student_name || 'Sin asignar'}">
                <i class="fas fa-times"></i>
              </button>
            ` : ''}
            <button class="btn btn-outline-secondary btn-delete-slot"
                    data-slot-id="${slot.id}"
                    data-slot-info="${dateStr} ${timeStr}"
                    data-student-name="${slot.student_name || ''}"
                    data-is-booked="${slot.status === 'booked'}"
                    title="Eliminar slot">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
        }).join('');
    }

    function updateSlotCounts() {
        const free = currentSlots.filter(s => s.status === 'free').length;
        const booked = currentSlots.filter(s => s.status === 'booked').length;
        const total = currentSlots.length;

        document.getElementById('freeSlots').textContent = free;
        document.getElementById('bookedSlots').textContent = booked;
        document.getElementById('totalSlots').textContent = total;
    }

    async function loadEligibleStudents(programId = null) {
        if (!programId) {
            eligibleStudentsList = [];
            if (eligibleStudents) {
                eligibleStudents.innerHTML = '<div class="list-group-item text-center text-muted py-4"><i class="bi bi-info-circle me-1"></i>Selecciona un programa para ver aspirantes elegibles</div>';
            }
            return;
        }

        try {
            const url = `${API}/interviews/eligible-students/${programId}`;
            const { data } = await apiRequest(url);
            eligibleStudentsList = data.eligible_students || [];
            renderEligibleStudents();

        } catch (err) {
            console.error('Error loading eligible students:', err);
            if (eligibleStudents) {
                eligibleStudents.innerHTML = '<div class="list-group-item text-danger">Error cargando estudiantes</div>';
            }
        }
    }

    function renderEligibleStudents() {
        if (eligibleStudentsList.length === 0) {
            eligibleStudents.innerHTML = '<div class="list-group-item text-center text-muted py-4">No hay estudiantes elegibles</div>';
            return;
        }

        eligibleStudents.innerHTML = eligibleStudentsList.map(student => `
      <div class="list-group-item student-card" data-student-id="${student.id}">
        <div class="d-flex align-items-center">
          <img src="${student.avatar_url || '/static/assets/images/default.jpg'}" 
               class="rounded-circle me-2" width="32" height="32" alt="Avatar">
          <div class="flex-grow-1">
            <div class="fw-semibold small">${student.full_name}</div>
            <div class="text-muted small">${student.email}</div>
          </div>
          <div class="text-end">
            <span class="badge bg-success small">Elegible</span>
          </div>
        </div>
      </div>
    `).join('');
    }

    // ========== EVENT LISTENERS (continuación) ==========
    function setupEventListeners() {
        createEventForm?.addEventListener('submit', handleCreateEvent);
        addWindowForm?.addEventListener('submit', handleAddWindow);
        assignSlotForm?.addEventListener('submit', handleAssignSlot);
        cancelAppointmentForm?.addEventListener('submit', handleCancelAppointment);

        // ==================== TIEMPO REAL ====================
        // Partial refresh: recarga eventos/slots cuando cambia una cita en cualquier
        // evento. Debounce 700ms para evitar ráfagas si varios aspirantes reservan
        // al mismo tiempo.
        let refreshTimer = null;
        const refreshEvents = () => {
            clearTimeout(refreshTimer);
            refreshTimer = setTimeout(() => {
                loadEvents();
                if (selectedEventId) loadSlots(selectedEventId);
            }, 700);
        };

        window.addEventListener('siiap:appointment:changed', (e) => {
            const d = e.detail || {};
            if (typeof showFlash === 'function') {
                const msg = d.action === 'booked' ? 'Nueva cita reservada' : 'Cita cancelada';
                showFlash('info', msg);
            }
            refreshEvents();
        });

        window.addEventListener('siiap:appointment:change_requested', () => {
            if (typeof showFlash === 'function') {
                showFlash('info', 'Nueva solicitud de cambio de cita');
            }
            refreshEvents();
        });

        window.addEventListener('siiap:event:changed', (e) => {
            const d = e.detail || {};
            if (typeof showFlash === 'function') {
                const labels = { created: 'Nuevo evento creado', updated: 'Evento actualizado', deleted: 'Evento eliminado' };
                showFlash('info', labels[d.action] || 'Evento modificado');
            }
            refreshEvents();
        });
        document.getElementById('btnGenerateSlots')?.addEventListener('click', handleGenerateSlots);
        document.getElementById('confirmDeleteEventBtn')?.addEventListener('click', handleDeleteEvent);
        document.getElementById('btnExportAttendance')?.addEventListener('click', exportAttendance);

        document.getElementById('programFilter')?.addEventListener('change', (e) => {
            const programId = e.target.value;
            loadEligibleStudents(programId || null);
        });
        document.getElementById('confirmDeleteWindowBtn')?.addEventListener('click', handleDeleteWindow);
        document.getElementById('confirmDeleteSlotBtn')?.addEventListener('click', handleDeleteSlot);
        document.getElementById('btnGenerateSlotsFromWindows')?.addEventListener('click', handleGenerateSlots);
        document.getElementById('btnRefreshSlots')?.addEventListener('click', () => {
            if (selectedEventId) {
                loadSlots(selectedEventId);
                loadWindows(selectedEventId);
            }
        });
        document.querySelectorAll('input[name="filterStatus"]').forEach(input => {
            input.addEventListener('change', (e) => {
                currentFilterStatus = e.target.value;
                renderRegistrationsTable();
            });
        });
        document.getElementById('btnSendInvitations')?.addEventListener('click', sendInvitations);
        document.getElementById('btnSaveEventDates')?.addEventListener('click', saveEventDates);
        document.getElementById('btnViewFullAttendance')?.addEventListener('click', () => {
            openRegistrationsModal(selectedEventId);
        });
        document.querySelector('[data-bs-target="#inviteStudentsModal"]')?.addEventListener('click', openInviteModal);
        eventsTable?.addEventListener('click', (e) => {
            const row = e.target.closest('tr[data-event-id]');
            if (!row) return;

            const eventId = parseInt(row.dataset.eventId);

            if (e.target.closest('.btn-conclude-event')) {
                e.stopPropagation();
                handleConcludeEvent(eventId);
                return;
            }
            if (e.target.closest('.btn-archive-event')) {
                e.stopPropagation();
                handleArchiveEvent(eventId);
                return;
            }
            if (e.target.closest('.btn-unarchive-event')) {
                e.stopPropagation();
                handleUnarchiveEvent(eventId);
                return;
            }
            if (e.target.closest('.btn-view-slots') || e.target.closest('.event-row')) {
                selectEvent(eventId);
            } else if (e.target.closest('.btn-delete-event')) {
                e.stopPropagation();
                openDeleteEventModal(eventId);
            }
            if (e.target.closest('.btn-view-registrations')) {
                e.stopPropagation();
                const row = e.target.closest('tr[data-event-id]');
                const eventId = parseInt(row.dataset.eventId);
                openRegistrationsModal(eventId);
            }
        });
        registrationsTable?.addEventListener('click', (e) => {
            if (e.target.closest('.btn-mark-attended')) {
                const button = e.target.closest('.btn-mark-attended');
                const userId = parseInt(button.dataset.userId);
                markAttendance(userId, true);
            } else if (e.target.closest('.btn-mark-no-show')) {
                const button = e.target.closest('.btn-mark-no-show');
                const userId = parseInt(button.dataset.userId);
                markAttendance(userId, false);
            } else if (e.target.closest('.btn-undo-attendance')) {
                const button = e.target.closest('.btn-undo-attendance');
                const userId = parseInt(button.dataset.userId);
                undoAttendance(userId);
            }
        });
        slotsTable?.addEventListener('click', (e) => {
            if (e.target.closest('.btn-assign-slot')) {
                const button = e.target.closest('.btn-assign-slot');
                const slotId = button.dataset.slotId;
                const slotInfo = button.dataset.slotInfo;
                openAssignModal(slotId, slotInfo);
            } else if (e.target.closest('.btn-cancel-appointment')) {
                const button = e.target.closest('.btn-cancel-appointment');
                const appointmentId = button.dataset.appointmentId;
                const slotInfo = button.dataset.slotInfo;
                const studentName = button.dataset.studentName;
                openCancelAppointmentModal(appointmentId, slotInfo, studentName);
            }
            if (e.target.closest('.btn-delete-slot')) {
                const button = e.target.closest('.btn-delete-slot');
                const slotId = parseInt(button.dataset.slotId);
                const slotInfo = button.dataset.slotInfo;
                const studentName = button.dataset.studentName;
                const isBooked = button.dataset.isBooked === 'true';
                openDeleteSlotModal(slotId, slotInfo, studentName, isBooked);
            }
        });
        windowsTable?.addEventListener('click', (e) => {
            if (e.target.closest('.btn-generate-window-slots')) {
                const button = e.target.closest('.btn-generate-window-slots');
                const windowId = parseInt(button.dataset.windowId);
                handleGenerateWindowSlots(windowId);
            } else if (e.target.closest('.btn-delete-window')) {
                const button = e.target.closest('.btn-delete-window');
                const windowId = parseInt(button.dataset.windowId);
                const date = button.dataset.date;
                const time = button.dataset.time;
                const slotsBooked = parseInt(button.dataset.slotsBooked);
                openDeleteWindowModal(windowId, date, time, slotsBooked);
            }
        });
        invitationsTable?.addEventListener('click', (e) => {
            if (e.target.closest('.btn-cancel-invitation')) {
                const button = e.target.closest('.btn-cancel-invitation');
                const invitationId = parseInt(button.dataset.invitationId);
                cancelInvitation(invitationId);
            }
        });

        document.getElementById('confirmAcceptChangeBtn')?.addEventListener('click', acceptChangeRequest);

        document.getElementById('changeRequestsTable')?.addEventListener('click', (e) => {
            if (e.target.closest('.btn-accept-change')) {
                const btn = e.target.closest('.btn-accept-change');
                openAcceptChangeModal(
                    btn.dataset.reqId,
                    btn.dataset.studentName,
                    btn.dataset.currentSlot,
                    btn.dataset.reason,
                    btn.dataset.suggestions
                );
            } else if (e.target.closest('.btn-reject-change')) {
                const btn = e.target.closest('.btn-reject-change');
                rejectChangeRequest(btn.dataset.reqId);
            }
        });

    }

    // ========== HANDLERS ==========
    async function handleCreateEvent(e) {
        e.preventDefault();

        // Enforce stage 2 is active (user must have selected a purpose)
        if (!wizardState.purpose) {
            flash('Selecciona el tipo de evento antes de continuar', 'warning');
            showWizardStage(1);
            return;
        }

        const capacityType = document.getElementById('eventCapacityType').value;
        const maxCapacity  = document.getElementById('eventMaxCapacity').value;
        const programId    = document.getElementById('eventProgram').value;

        // Validate max_capacity for multiple-capacity events
        if (capacityType === 'multiple' && (!maxCapacity || parseInt(maxCapacity) < 1)) {
            flash('Debes especificar una capacidad máxima válida para eventos de capacidad múltiple', 'warning');
            return;
        }

        const periodId    = document.getElementById('eventAcademicPeriod')?.value;
        const eventDate   = document.getElementById('eventDateCreate')?.value || null;
        const eventEndDate = document.getElementById('eventEndDateCreate')?.value || null;

        const payload = {
            title: document.getElementById('eventTitle').value.trim(),
            program_id: programId ? parseInt(programId) : null,
            academic_period_id: periodId ? parseInt(periodId) : null,
            type: document.getElementById('eventType').value,
            location: document.getElementById('eventLocation').value,
            description: document.getElementById('eventDescription').value,
            capacity_type: capacityType,
            max_capacity: capacityType === 'multiple' ? parseInt(maxCapacity) : null,
            event_date: eventDate || null,
            event_end_date: eventEndDate || null,
            requires_registration: document.getElementById('eventRequiresRegistration').checked,
            allows_attendance_tracking: document.getElementById('eventAllowsAttendance').checked,
            visible_to_students: document.getElementById('eventVisibleToStudents').checked,
            visibility: document.querySelector('input[name="eventVisibility"]:checked')?.value || 'public',
            reminders_enabled: document.getElementById('eventRemindersEnabled').checked,
            status: document.getElementById('eventStatus').value
        };

        if (!payload.title) {
            flash('El título es requerido', 'warning');
            return;
        }

        try {
            await apiRequest(`${API}/events`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            flash('Evento creado correctamente', 'success');
            createEventModal.hide();
            createEventForm.reset();
            resetWizard();
            await loadEvents();

        } catch (err) {
            flash(`Error creando evento: ${err.message}`, 'danger');
        }
    }

    async function handleAddWindow(e) {
        e.preventDefault();

        if (!selectedEventId) {
            flash('Selecciona un evento primero', 'warning');
            return;
        }

        const payload = {
            date: document.getElementById('windowDate').value,
            start_time: document.getElementById('windowStartTime').value,
            end_time: document.getElementById('windowEndTime').value,
            slot_minutes: parseInt(document.getElementById('windowSlotMinutes').value)
        };

        try {
            await apiRequest(`${API}/events/${selectedEventId}/windows`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            flash('Ventana de horarios creada correctamente', 'success');
            addWindowModal.hide();
            addWindowForm.reset();
            await loadEvents();
            await loadWindows(selectedEventId);

        } catch (err) {
            flash(`Error creando ventana: ${err.message}`, 'danger');
        }
    }

    async function handleGenerateSlots() {
        if (!selectedEventId) {
            flash('Selecciona un evento primero', 'warning');
            return;
        }

        try {
            const { data: eventData } = await apiRequest(`${API}/events/${selectedEventId}`);
            const event = eventData;

            if (!event || !event.windows || event.windows.length === 0) {
                flash('Primero agrega ventanas de horarios para este evento', 'warning');
                return;
            }

            let totalCreated = 0;

            for (const window of event.windows) {
                try {
                    const { data: slotsData } = await apiRequest(
                        `${API}/events/windows/${window.id}/generate-slots`,
                        { method: 'POST' }
                    );
                    totalCreated += slotsData.created || 0;
                } catch (err) {
                    // Si falla una ventana, continuar con las demás
                    console.error(`Error generando slots para ventana ${window.id}:`, err);
                }
            }

            if (totalCreated > 0) {
                flash(`Se generaron ${totalCreated} nuevos horarios`, 'success');
            } else {
                flash('No se generaron nuevos horarios. Puede que ya existan.', 'info');
            }

            await loadEvents();
            await loadSlots(selectedEventId);

        } catch (err) {
            flash(`Error generando horarios: ${err.message}`, 'danger');
        }
    }

    async function handleAssignSlot(e) {
        e.preventDefault();

        const payload = {
            event_id: document.getElementById('assignEventId').value,
            slot_id: document.getElementById('assignSlotId').value,
            applicant_id: parseInt(document.getElementById('assignStudentId').value),
            notes: document.getElementById('assignNotes').value
        };

        if (!payload.applicant_id) {
            flash('Selecciona un estudiante', 'warning');
            return;
        }

        try {
            await apiRequest(`${API}/appointments`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            flash('Cita asignada correctamente', 'success');
            assignSlotModal.hide();
            assignSlotForm.reset();
            await loadSlots(selectedEventId);

        } catch (err) {
            flash(`Error asignando cita: ${err.message}`, 'danger');
        }
    }

    async function handleCancelAppointment(e) {
        e.preventDefault();

        const appointmentId = document.getElementById('cancelAppointmentId').value;
        const reason = document.getElementById('cancelReason').value.trim();

        try {
            await apiRequest(`${API}/appointments/${appointmentId}/cancel`, {
                method: 'POST',
                body: JSON.stringify({ reason: reason || 'Cancelada por coordinador' })
            });

            flash('Cita cancelada correctamente', 'success');
            confirmCancelAppointmentModal.hide();
            cancelAppointmentForm.reset();
            await loadSlots(selectedEventId);

        } catch (err) {
            flash(`Error cancelando cita: ${err.message}`, 'danger');
        }
    }

    async function handleConcludeEvent(eventId) {
        const event = currentEvents.find(ev => ev.id === eventId);
        const title = event ? event.title : `evento #${eventId}`;

        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Concluir evento',
            message: `¿Concluir "${title}"?\n\nSe marcará como completado, se cancelarán las invitaciones pendientes y se eliminarán sus imágenes del servidor. Esta acción no se puede revertir.`,
            confirmLabel: 'Sí, concluir',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/events/${eventId}/conclude`, { method: 'POST' });
            flash('Evento concluido correctamente', 'success');
            await loadEvents();
        } catch (err) {
            flash(`Error al concluir: ${err.message}`, 'danger');
        }
    }

    async function handleArchiveEvent(eventId) {
        const event = currentEvents.find(ev => ev.id === eventId);
        const title = event ? event.title : `evento #${eventId}`;

        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Archivar evento',
            message: `¿Archivar "${title}"?\n\nSe ocultará del listado público, se notificará a los registrados, se cancelarán las invitaciones pendientes y se eliminarán sus imágenes.`,
            confirmLabel: 'Sí, archivar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/events/${eventId}/archive`, { method: 'POST' });
            flash('Evento archivado', 'success');
            await loadEvents();
        } catch (err) {
            flash(`Error al archivar: ${err.message}`, 'danger');
        }
    }

    async function handleUnarchiveEvent(eventId) {
        const ok = await siiapConfirm({
            type: 'info',
            title: 'Reactivar evento',
            message: '¿Volver a publicar este evento? Reaparecerá en el listado público.',
            confirmLabel: 'Sí, reactivar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/events/${eventId}/unarchive`, {
                method: 'POST',
                body: JSON.stringify({ new_status: 'published' })
            });
            flash('Evento reactivado', 'success');
            await loadEvents();
        } catch (err) {
            flash(`Error al reactivar: ${err.message}`, 'danger');
        }
    }

    async function handleDeleteEvent() {
        const eventId = parseInt(document.getElementById('deleteEventId').value);
        if (!eventId) return;

        try {
            // Intentar eliminación normal
            const { response, data } = await apiRequest(`${API}/events/${eventId}`, {
                method: 'DELETE'
            });

            // Si tiene citas, requerir force
            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger',
                    title: 'Eliminar evento con citas',
                    message: data.message + '\n\n¿Deseas eliminar el evento de todas formas?',
                    confirmLabel: 'Sí, eliminar',
                });
                if (confirmed) {
                    await apiRequest(`${API}/events/${eventId}?force=true`, { method: 'DELETE' });
                } else {
                    return;
                }
            }

            currentEvents = currentEvents.filter(e => e.id !== eventId);
            renderEventsTable();

            if (selectedEventId === eventId) {
                selectedEventId = null;
                slotsCard.style.display = 'none';
            }

            flash('Evento eliminado correctamente', 'success');
            confirmDeleteEventModal.hide();

        } catch (err) {
            flash(`Error eliminando evento: ${err.message}`, 'danger');
        }
    }

    // ========== UTILITY FUNCTIONS ==========
    function selectEvent(eventId) {
        const event = currentEvents.find(e => e.id === eventId);
        if (!event) return;

        selectedEventId = eventId;
        selectedEventTitle.textContent = event.title;

        // Reset and prefetch media / hosts in background
        currentEventImages = { cover: null, gallery: [] };
        currentEventHosts  = [];
        loadEventMedia(eventId).catch(() => {});
        loadEventHosts(eventId).catch(() => {});
        populateEditForm(event);
        updatePrivacyToggle(event);

        // Actualizar badge de tipo
        const typeBadge = document.getElementById('selectedEventTypeBadge');
        if (event.capacity_type === 'single') {
            typeBadge.textContent = 'Capacidad Individual (1:1)';
            typeBadge.className = 'badge bg-info';
        } else if (event.capacity_type === 'multiple') {
            typeBadge.textContent = `Capacidad Múltiple (Max: ${event.max_capacity})`;
            typeBadge.className = 'badge bg-warning';
        } else {
            typeBadge.textContent = 'Sin Límite';
            typeBadge.className = 'badge bg-success';
        }

        document.querySelectorAll('.event-row').forEach(row => {
            row.classList.toggle('table-active', parseInt(row.dataset.eventId) === eventId);
        });

        // Colorear cabecera del panel según tipo de evento
        const managementCardHeader = document.querySelector('#eventManagementCard .card-header');
        if (managementCardHeader) {
            const headerTypeClasses = [
                'event-management-header-interview', 'event-management-header-defense',
                'event-management-header-workshop',  'event-management-header-seminar',
                'event-management-header-conference', 'event-management-header-info_session',
                'event-management-header-other',
            ];
            managementCardHeader.classList.remove(...headerTypeClasses);
            if (event.type) {
                managementCardHeader.classList.add(`event-management-header-${event.type}`);
            }
        }

        // Mostrar contenido apropiado según tipo
        const singleContent = document.getElementById('singleCapacityContent');
        const multipleContent = document.getElementById('multipleCapacityContent');
        const card = document.getElementById('eventManagementCard');
        const rightPanel = document.getElementById('eligibleStudentsPanel');

        card.style.display = 'block';

        if (event.capacity_type === 'single') {
            singleContent.style.display = 'block';
            multipleContent.style.display = 'none';
            document.getElementById('windowEventId').value = eventId;
            rightPanel.style.display = 'block';

            loadWindows(eventId);
            loadSlots(eventId);
            loadChangeRequests(eventId);
            // Cargar aspirantes elegibles del programa del evento
            loadEligibleStudents(event.program_id || null);
        } else {
            singleContent.style.display = 'none';
            multipleContent.style.display = 'block';
            document.getElementById('eligibleStudentsPanel').style.display = 'none';
            // Cargar fechas del evento si existen
            if (event.event_date) {
                const date = new Date(event.event_date);
                document.getElementById('eventDateTime').value = date.toISOString().slice(0, 16);
            }
            if (event.event_end_date) {
                const endDate = new Date(event.event_end_date);
                document.getElementById('eventEndDateTime').value = endDate.toISOString().slice(0, 16);
            }

            loadRegistrations(eventId).then(() => {
                renderQuickRegistrations();  // AGREGAR ESTO
            });
            loadInvitations(eventId);
        }
    }

    function openAssignModal(slotId, slotInfo) {
        // Verificar que los elementos existan antes de acceder a ellos
        const assignEventIdEl = document.getElementById('assignEventId');
        const assignSlotIdEl = document.getElementById('assignSlotId');
        const assignSlotInfoEl = document.getElementById('assignSlotInfo');
        const studentSelect = document.getElementById('assignStudentId');

        if (!assignEventIdEl || !assignSlotIdEl || !assignSlotInfoEl || !studentSelect) {
            console.error('Elementos del modal assignSlotModal no encontrados');
            return;
        }

        assignEventIdEl.value = selectedEventId;
        assignSlotIdEl.value = slotId;
        assignSlotInfoEl.textContent = slotInfo;

        studentSelect.innerHTML = '<option value="">Seleccionar estudiante...</option>' +
            eligibleStudentsList.map(s =>
                `<option value="${s.id}">${s.full_name} - ${s.email}</option>`
            ).join('');

        if (assignSlotModal) {
            assignSlotModal.show();
        }
    }

    function openDeleteEventModal(eventId) {
        const event = currentEvents.find(e => e.id === eventId);
        if (!event) return;

        // Verificar que los elementos existan
        const deleteEventIdEl = document.getElementById('deleteEventId');
        const deleteEventTitleEl = document.getElementById('deleteEventTitle');
        const warningEl = document.getElementById('deleteEventWarning');
        const appointmentsCountEl = document.getElementById('deleteEventAppointmentsCount');

        if (!deleteEventIdEl || !deleteEventTitleEl || !warningEl) {
            console.error('Elementos del modal confirmDeleteEventModal no encontrados');
            return;
        }

        deleteEventIdEl.value = eventId;
        deleteEventTitleEl.textContent = event.title;

        if (event.slots_booked > 0 && appointmentsCountEl) {
            appointmentsCountEl.textContent = event.slots_booked;
            warningEl.classList.remove('d-none');
        } else {
            warningEl.classList.add('d-none');
        }

        if (confirmDeleteEventModal) {
            confirmDeleteEventModal.show();
        }
    }

    function openCancelAppointmentModal(appointmentId, slotInfo, studentName) {
        // Verificar que los elementos existan
        const cancelAppointmentIdEl = document.getElementById('cancelAppointmentId');
        const cancelSlotInfoEl = document.getElementById('cancelSlotInfo');
        const cancelStudentNameEl = document.getElementById('cancelStudentName');
        const cancelReasonEl = document.getElementById('cancelReason');

        if (!cancelAppointmentIdEl || !cancelSlotInfoEl || !cancelStudentNameEl || !cancelReasonEl) {
            console.error('Elementos del modal confirmCancelAppointmentModal no encontrados');
            return;
        }

        cancelAppointmentIdEl.value = appointmentId;
        cancelSlotInfoEl.textContent = slotInfo;
        cancelStudentNameEl.textContent = studentName;
        cancelReasonEl.value = '';

        if (confirmCancelAppointmentModal) {
            confirmCancelAppointmentModal.show();
        }
    }

    // ========== GESTIÓN DE VENTANAS ==========

    async function loadWindows(eventId) {
        try {
            const { data } = await apiRequest(`${API}/events/${eventId}/windows-list`);
            currentWindows = data.windows || [];
            renderWindowsTable();
        } catch (err) {
            console.error('Error loading windows:', err);
            flash(`Error cargando ventanas: ${err.message}`, 'danger');
        }
    }

    function renderWindowsTable() {
        const tbody = windowsTable?.querySelector('tbody');
        if (!tbody) return;

        if (currentWindows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No hay ventanas creadas</td></tr>';
            return;
        }

        tbody.innerHTML = currentWindows.map(window => {
            const date = new Date(window.date).toLocaleDateString('es-MX');
            const startTime = window.start_time.substring(0, 5);
            const endTime = window.end_time.substring(0, 5);

            return `
      <tr data-window-id="${window.id}">
        <td>${date}</td>
        <td>${startTime} - ${endTime}</td>
        <td>${window.slot_minutes} min</td>
        <td class="text-center">
          ${window.slots_generated
                    ? '<span class="badge bg-success"><i class="fas fa-check"></i> Sí</span>'
                    : '<span class="badge bg-secondary"><i class="fas fa-times"></i> No</span>'}
        </td>
        <td class="text-center">${window.slots_total}</td>
        <td class="text-center">
          <span class="badge bg-success">${window.slots_free}</span>
        </td>
        <td class="text-center">
          <span class="badge bg-${window.slots_booked > 0 ? 'warning' : 'secondary'}">
            ${window.slots_booked}
          </span>
        </td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            ${!window.slots_generated ? `
              <button class="btn btn-outline-success btn-generate-window-slots" 
                      data-window-id="${window.id}" title="Generar slots">
                <i class="fas fa-cogs"></i>
              </button>
            ` : ''}
            <button class="btn btn-outline-danger btn-delete-window" 
                    data-window-id="${window.id}"
                    data-date="${date}"
                    data-time="${startTime} - ${endTime}"
                    data-slots-booked="${window.slots_booked}"
                    title="Eliminar ventana">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
        }).join('');
    }

    async function handleGenerateWindowSlots(windowId) {
        try {
            const { data } = await apiRequest(
                `${API}/events/windows/${windowId}/generate-slots`,
                { method: 'POST' }
            );

            if (data.created > 0) {
                flash(`Se generaron ${data.created} nuevos slots`, 'success');
            } else {
                flash('No se generaron nuevos slots. Ya existen todos.', 'info');
            }

            await loadWindows(selectedEventId);
            await loadSlots(selectedEventId);
            await loadEvents();
        } catch (err) {
            flash(`Error generando slots: ${err.message}`, 'danger');
        }
    }

    function openDeleteWindowModal(windowId, date, time, slotsBooked) {
        // Verificar que los elementos existan
        const deleteWindowIdEl = document.getElementById('deleteWindowId');
        const deleteWindowDateEl = document.getElementById('deleteWindowDate');
        const deleteWindowTimeEl = document.getElementById('deleteWindowTime');
        const warningEl = document.getElementById('deleteWindowWarning');
        const slotsCountEl = document.getElementById('deleteWindowSlotsCount');

        if (!deleteWindowIdEl || !deleteWindowDateEl || !deleteWindowTimeEl || !warningEl) {
            console.error('Elementos del modal confirmDeleteWindowModal no encontrados');
            return;
        }

        deleteWindowIdEl.value = windowId;
        deleteWindowDateEl.textContent = date;
        deleteWindowTimeEl.textContent = time;

        if (slotsBooked > 0 && slotsCountEl) {
            slotsCountEl.textContent = slotsBooked;
            warningEl.classList.remove('d-none');
        } else {
            warningEl.classList.add('d-none');
        }

        if (confirmDeleteWindowModal) {
            confirmDeleteWindowModal.show();
        }
    }

    async function handleDeleteWindow() {
        const windowId = parseInt(document.getElementById('deleteWindowId').value);
        if (!windowId) return;

        try {
            const { data } = await apiRequest(`${API}/events/windows/${windowId}`, {
                method: 'DELETE'
            });

            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger',
                    title: 'Eliminar ventana',
                    message: data.message + '\n\n¿Deseas eliminar la ventana de todas formas?',
                    confirmLabel: 'Sí, eliminar',
                });
                if (confirmed) {
                    await apiRequest(`${API}/events/windows/${windowId}?force=true`, {
                        method: 'DELETE'
                    });
                } else {
                    return;
                }
            }

            flash('Ventana eliminada correctamente', 'success');
            confirmDeleteWindowModal.hide();

            await loadWindows(selectedEventId);
            await loadSlots(selectedEventId);
            await loadEvents();

        } catch (err) {
            flash(`Error eliminando ventana: ${err.message}`, 'danger');
        }
    }

    // ========== GESTIÓN DE SLOTS ==========

    function openDeleteSlotModal(slotId, slotInfo, studentName, isBooked) {
        // Verificar que los elementos existan antes de acceder a ellos
        const deleteSlotIdEl = document.getElementById('deleteSlotId');
        const deleteSlotInfoEl = document.getElementById('deleteSlotInfo');
        const studentDiv = document.getElementById('deleteSlotStudent');
        const warningEl = document.getElementById('deleteSlotWarning');
        const deleteSlotStudentNameEl = document.getElementById('deleteSlotStudentName');

        if (!deleteSlotIdEl || !deleteSlotInfoEl || !studentDiv || !warningEl) {
            console.error('Elementos del modal confirmDeleteSlotModal no encontrados');
            return;
        }

        deleteSlotIdEl.value = slotId;
        deleteSlotInfoEl.textContent = slotInfo;

        if (isBooked && studentName && deleteSlotStudentNameEl) {
            deleteSlotStudentNameEl.textContent = studentName;
            studentDiv.classList.remove('d-none');
            warningEl.classList.remove('d-none');
        } else {
            studentDiv.classList.add('d-none');
            warningEl.classList.add('d-none');
        }

        if (confirmDeleteSlotModal) {
            confirmDeleteSlotModal.show();
        }
    }

    async function handleDeleteSlot() {
        const slotId = parseInt(document.getElementById('deleteSlotId').value);
        if (!slotId) return;

        try {
            const { data } = await apiRequest(`${API}/events/slots/${slotId}`, {
                method: 'DELETE'
            });

            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger',
                    title: 'Eliminar slot',
                    message: data.message + '\n\n¿Deseas eliminar el slot de todas formas?',
                    confirmLabel: 'Sí, eliminar',
                });
                if (confirmed) {
                    await apiRequest(`${API}/events/slots/${slotId}?force=true`, {
                        method: 'DELETE'
                    });
                } else {
                    return;
                }
            }

            flash('Slot eliminado correctamente', 'success');
            confirmDeleteSlotModal.hide();

            await loadWindows(selectedEventId);
            await loadSlots(selectedEventId);
            await loadEvents();

        } catch (err) {
            flash(`Error eliminando slot: ${err.message}`, 'danger');
        }
    }

    // ========== GESTIÓN DE REGISTROS Y ASISTENCIA ==========

    async function loadRegistrations(eventId) {
        try {
            const { data } = await apiRequest(`${API}/attendance/event/${eventId}/registrations`);
            currentRegistrations = data.registrations || [];
            updateRegistrationStats();
            renderRegistrationsTable();
        } catch (err) {
            console.error('Error loading registrations:', err);
            flash(`Error cargando registros: ${err.message}`, 'danger');
        }
    }

    function updateRegistrationStats() {
        const total = currentRegistrations.length;
        const attended = currentRegistrations.filter(r => r.status === 'attended').length;
        const noShow = currentRegistrations.filter(r => r.status === 'no_show').length;
        const registered = currentRegistrations.filter(r => r.status === 'registered').length;

        document.getElementById('statsTotal').textContent = total;
        document.getElementById('statsAttended').textContent = attended;
        document.getElementById('statsNoShow').textContent = noShow;
        document.getElementById('statsRegistered').textContent = registered;
    }

    function renderRegistrationsTable() {
        const tbody = registrationsTable?.querySelector('tbody');
        if (!tbody) return;

        // Filtrar por estado si hay filtro activo
        let filtered = currentRegistrations;
        if (currentFilterStatus) {
            filtered = currentRegistrations.filter(r => r.status === currentFilterStatus);
        }

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay registros</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(reg => {
            const registeredDate = new Date(reg.registered_at).toLocaleString('es-MX', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });

            const attendedDate = reg.attended_at
                ? new Date(reg.attended_at).toLocaleString('es-MX', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                })
                : '—';

            let statusBadge = '';
            if (reg.status === 'registered') {
                statusBadge = '<span class="badge bg-info">Registrado</span>';
            } else if (reg.status === 'attended') {
                statusBadge = '<span class="badge bg-success">Asistió</span>';
            } else if (reg.status === 'no_show') {
                statusBadge = '<span class="badge bg-warning">No Asistió</span>';
            }

            return `
      <tr data-registration-id="${reg.id}" data-user-id="${reg.user_id}">
        <td>
          <div class="fw-semibold">${reg.full_name}</div>
        </td>
        <td>${reg.email}</td>
        <td>${registeredDate}</td>
        <td class="text-center">${statusBadge}</td>
        <td>${attendedDate}</td>
        <td class="text-end">
          ${reg.status === 'registered' ? `
            <div class="btn-group btn-group-sm">
              <button class="btn btn-outline-success btn-mark-attended" 
                      data-user-id="${reg.user_id}"
                      title="Marcar asistencia">
                <i class="fas fa-check"></i>
              </button>
              <button class="btn btn-outline-warning btn-mark-no-show" 
                      data-user-id="${reg.user_id}"
                      title="Marcar como ausente">
                <i class="fas fa-times"></i>
              </button>
            </div>
          ` : reg.status === 'attended' ? `
            <button class="btn btn-outline-secondary btn-sm btn-undo-attendance" 
                    data-user-id="${reg.user_id}"
                    title="Deshacer asistencia">
              <i class="fas fa-undo"></i>
            </button>
          ` : `
            <button class="btn btn-outline-secondary btn-sm btn-undo-attendance" 
                    data-user-id="${reg.user_id}"
                    title="Marcar como registrado">
              <i class="fas fa-undo"></i>
            </button>
          `}
        </td>
      </tr>
    `;
        }).join('');
    }

    async function markAttendance(userId, attended) {
        const eventId = parseInt(document.getElementById('registrationsEventId').value);

        try {
            await apiRequest(`${API}/attendance/event/${eventId}/mark-attendance`, {
                method: 'POST',
                body: JSON.stringify({
                    user_id: userId,
                    attended: attended
                })
            });

            flash(attended ? 'Asistencia registrada' : 'Marcado como ausente', 'success');
            await loadRegistrations(eventId);

        } catch (err) {
            flash(`Error al marcar asistencia: ${err.message}`, 'danger');
        }
    }

    async function undoAttendance(userId) {
        const eventId = parseInt(document.getElementById('registrationsEventId').value);

        try {
            await apiRequest(`${API}/attendance/event/${eventId}/mark-attendance`, {
                method: 'POST',
                body: JSON.stringify({
                    user_id: userId,
                    reset: true  // USAR ESTO EN LUGAR DE attended: null
                })
            });

            flash('Estado actualizado a registrado', 'success');
            await loadRegistrations(eventId);

        } catch (err) {
            flash(`Error al actualizar asistencia: ${err.message}`, 'danger');
        }
    }

    function openRegistrationsModal(eventId) {
        const event = currentEvents.find(e => e.id === eventId);
        if (!event) return;

        document.getElementById('registrationsEventId').value = eventId;
        document.getElementById('registrationsEventTitle').textContent = event.title;

        // Reset filtros
        currentFilterStatus = '';
        document.getElementById('filterAll').checked = true;

        loadRegistrations(eventId);
        viewRegistrationsModal.show();
    }

    function exportAttendance() {
        const eventId = document.getElementById('registrationsEventId').value;
        const event = currentEvents.find(e => e.id === parseInt(eventId));

        if (currentRegistrations.length === 0) {
            flash('No hay registros para exportar', 'warning');
            return;
        }

        // Crear CSV
        let csv = 'Estudiante,Email,Fecha Registro,Estado,Fecha Asistencia\n';

        currentRegistrations.forEach(reg => {
            const registeredDate = new Date(reg.registered_at).toLocaleString('es-MX');
            const attendedDate = reg.attended_at
                ? new Date(reg.attended_at).toLocaleString('es-MX')
                : '';

            csv += `"${reg.full_name}","${reg.email}","${registeredDate}","${reg.status}","${attendedDate}"\n`;
        });

        // Descargar
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);

        link.setAttribute('href', url);
        link.setAttribute('download', `asistencia_${event?.title || 'evento'}_${Date.now()}.csv`);
        link.style.visibility = 'hidden';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        flash('Archivo exportado correctamente', 'success');
    }
    // ========== GESTIÓN DE INVITACIONES ==========

    const inviteStudentsModal = new bootstrap.Modal(document.getElementById("inviteStudentsModal"));
    const invitationsTable = document.getElementById("invitationsTable");
    const quickRegistrationsTable = document.getElementById("quickRegistrationsTable");
    let currentInvitations = [];

    async function loadInvitations(eventId) {
        try {
            const { data } = await apiRequest(`${API}/invitations/event/${eventId}/list`);
            currentInvitations = data.invitations || [];
            renderInvitationsTable();
            document.getElementById('countInvitations').textContent = currentInvitations.length;
        } catch (err) {
            console.error('Error loading invitations:', err);
        }
    }

    function renderInvitationsTable() {
        const tbody = invitationsTable?.querySelector('tbody');
        if (!tbody) return;

        if (currentInvitations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Sin invitaciones</td></tr>';
            return;
        }

        tbody.innerHTML = currentInvitations.map(inv => {
            const invitedDate = new Date(inv.invited_at).toLocaleString('es-MX');
            const respondedDate = inv.responded_at ? new Date(inv.responded_at).toLocaleString('es-MX') : '—';

            let statusBadge = '';
            if (inv.status === 'pending') {
                statusBadge = '<span class="badge bg-warning">Pendiente</span>';
            } else if (inv.status === 'accepted') {
                statusBadge = '<span class="badge bg-success">Aceptada</span>';
            } else if (inv.status === 'rejected') {
                statusBadge = '<span class="badge bg-danger">Rechazada</span>';
            }

            return `
      <tr data-invitation-id="${inv.id}">
        <td>${inv.full_name}</td>
        <td>${inv.inviter_name}</td>
        <td>${invitedDate}</td>
        <td>${statusBadge}</td>
        <td class="text-end">
          ${inv.status === 'pending' ? `
            <button class="btn btn-sm btn-outline-danger btn-cancel-invitation"
                    data-invitation-id="${inv.id}"
                    title="Cancelar invitación">
              <i class="fas fa-times"></i>
            </button>
          ` : ''}
        </td>
      </tr>
    `;
        }).join('');
    }

    function renderQuickRegistrations() {
        const tbody = quickRegistrationsTable?.querySelector('tbody');
        if (!tbody) return;

        if (currentRegistrations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Sin registros</td></tr>';
            return;
        }

        tbody.innerHTML = currentRegistrations.map(reg => {
            let originBadge = '';
            if (reg.notes && reg.notes.includes('invitación')) {
                originBadge = '<span class="badge bg-info">Invitación</span>';
            } else {
                originBadge = '<span class="badge bg-secondary">Auto-registro</span>';
            }

            let statusBadge = '';
            if (reg.status === 'registered') {
                statusBadge = '<span class="badge bg-info">Registrado</span>';
            } else if (reg.status === 'attended') {
                statusBadge = '<span class="badge bg-success">Asistió</span>';
            } else if (reg.status === 'no_show') {
                statusBadge = '<span class="badge bg-warning">No Asistió</span>';
            }

            return `
      <tr>
        <td>${reg.full_name}</td>
        <td>${reg.email}</td>
        <td>${originBadge}</td>
        <td>${statusBadge}</td>
      </tr>
    `;
        }).join('');

        document.getElementById('countRegistered').textContent = currentRegistrations.length;
    }

    async function openInviteModal() {
        const eventId = selectedEventId;
        const event = currentEvents.find(e => e.id === eventId);

        document.getElementById('inviteEventId').value = eventId;

        const select = document.getElementById('inviteStudentSelect');
        select.innerHTML = '<option disabled>Cargando estudiantes...</option>';

        try {
            const registeredIds = currentRegistrations.map(r => r.user_id);
            const invitedIds = currentInvitations.filter(i => i.status === 'pending').map(i => i.user_id);
            const excludedIds = [...new Set([...registeredIds, ...invitedIds])];

            // CAMBIAR: Cargar según si tiene programa o no
            let studentsUrl = `${API}/coordinator/students`;

            if (event.program_id) {
                // Filtrar por programa específico
                studentsUrl += `?program_id=${event.program_id}`;
            }
            // Si no tiene program_id, carga todos los estudiantes

            const { data } = await apiRequest(studentsUrl);
            const allStudents = data.students || [];
            const available = allStudents.filter(s => !excludedIds.includes(s.id));

            if (available.length === 0) {
                select.innerHTML = '<option disabled>No hay estudiantes disponibles para invitar</option>';
            } else {
                select.innerHTML = available.map(s =>
                    `<option value="${s.id}">${s.full_name} - ${s.program_name}</option>`
                ).join('');
            }

            inviteStudentsModal.show();
        } catch (err) {
            flash(`Error cargando estudiantes: ${err.message}`, 'danger');
        }
    }

    async function sendInvitations() {
        const eventId = document.getElementById('inviteEventId').value;
        const select = document.getElementById('inviteStudentSelect');
        const message = document.getElementById('inviteMessage').value;

        const selectedIds = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));

        if (selectedIds.length === 0) {
            flash('Selecciona al menos un estudiante', 'warning');
            return;
        }

        try {
            const { data } = await apiRequest(`${API}/invitations/event/${eventId}/invite`, {
                method: 'POST',
                body: JSON.stringify({
                    user_ids: selectedIds,
                    notes: message
                })
            });

            flash(`${data.invited} invitaciones enviadas correctamente`, 'success');

            if (data.already_invited > 0) {
                flash(`${data.already_invited} estudiantes ya tenían invitación`, 'info');
            }

            if (data.already_registered > 0) {
                flash(`${data.already_registered} estudiantes ya estaban registrados`, 'info');
            }

            // NUEVO: Mostrar estudiantes del programa incorrecto
            if (data.details && data.details.wrong_program && data.details.wrong_program.length > 0) {
                flash(`${data.details.wrong_program.length} estudiantes no pertenecen al programa del evento`, 'warning');
            }

            inviteStudentsModal.hide();
            document.getElementById('inviteMessage').value = '';

            await loadInvitations(eventId);

        } catch (err) {
            flash(`Error enviando invitaciones: ${err.message}`, 'danger');
        }
    }

    async function cancelInvitation(invitationId) {
        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Cancelar invitación',
            message: '¿Cancelar esta invitación?',
            confirmLabel: 'Sí, cancelar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/invitations/${invitationId}`, {
                method: 'DELETE'
            });

            flash('Invitación cancelada', 'success');
            await loadInvitations(selectedEventId);

        } catch (err) {
            flash(`Error cancelando invitación: ${err.message}`, 'danger');
        }
    }

    async function saveEventDates() {
        const eventId = selectedEventId;
        const eventDate = document.getElementById('eventDateTime').value;
        const eventEndDate = document.getElementById('eventEndDateTime').value;

        if (!eventDate) {
            flash('La fecha del evento es requerida', 'warning');
            return;
        }

        try {
            await apiRequest(`${API}/invitations/event/${eventId}/dates`, {
                method: 'PUT',
                body: JSON.stringify({
                    event_date: eventDate,
                    event_end_date: eventEndDate || null
                })
            });

            flash('Fechas actualizadas correctamente', 'success');
            await loadEvents();

        } catch (err) {
            flash(`Error actualizando fechas: ${err.message}`, 'danger');
        }
    }

    // ========== GESTIÓN DE SOLICITUDES DE CAMBIO ==========

    async function loadChangeRequests(eventId) {
        const tbody = document.querySelector('#changeRequestsTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Cargando...</td></tr>';

        try {
            const { data } = await apiRequest(`${API}/appointments/change-requests/by-event/${eventId}`);
            currentChangeRequests = data.change_requests || [];
            renderChangeRequestsTable();

            const badge = document.getElementById('changeRequestsBadge');
            if (badge) {
                if (currentChangeRequests.length > 0) {
                    badge.textContent = currentChangeRequests.length;
                    badge.style.display = 'inline';
                } else {
                    badge.style.display = 'none';
                }
            }
        } catch (err) {
            console.error('Error loading change requests:', err);
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-3">Error cargando solicitudes</td></tr>';
        }
    }

    function renderChangeRequestsTable() {
        const tbody = document.querySelector('#changeRequestsTable tbody');
        if (!tbody) return;

        if (currentChangeRequests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay solicitudes de cambio pendientes</td></tr>';
            return;
        }

        tbody.innerHTML = currentChangeRequests.map(req => {
            const start = new Date(req.current_slot.starts_at);
            const end = new Date(req.current_slot.ends_at);
            const slotStr = `${start.toLocaleDateString('es-MX')} ${start.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${end.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;
            const createdDate = new Date(req.created_at).toLocaleDateString('es-MX');
            const reason = (req.reason || '').replace(/"/g, '&quot;');
            const suggestions = (req.suggestions || '').replace(/"/g, '&quot;');

            return `
      <tr data-req-id="${req.id}">
        <td>
          <div class="fw-semibold small">${req.student.full_name}</div>
          <div class="text-muted small">${req.student.email}</div>
        </td>
        <td><small>${slotStr}</small></td>
        <td><small>${req.reason || '—'}</small></td>
        <td><small>${req.suggestions || '—'}</small></td>
        <td><small>${createdDate}</small></td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-success btn-accept-change"
                    data-req-id="${req.id}"
                    data-student-name="${req.student.full_name}"
                    data-current-slot="${slotStr}"
                    data-reason="${reason}"
                    data-suggestions="${suggestions}"
                    title="Aprobar cambio">
              <i class="fas fa-check"></i>
            </button>
            <button class="btn btn-outline-danger btn-reject-change"
                    data-req-id="${req.id}"
                    title="Rechazar cambio">
              <i class="fas fa-times"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
        }).join('');
    }

    async function openAcceptChangeModal(reqId, studentName, currentSlot, reason, suggestions) {
        document.getElementById('acceptChangeReqId').value = reqId;
        document.getElementById('acceptChangeStudentName').textContent = studentName;
        document.getElementById('acceptChangeCurrentSlot').textContent = currentSlot;
        document.getElementById('acceptChangeReason').textContent = reason || '—';
        document.getElementById('acceptChangeSuggestions').textContent = suggestions || '—';

        const slotSelect = document.getElementById('acceptChangeNewSlot');
        const freeSlots = currentSlots.filter(s => s.status === 'free');

        if (freeSlots.length === 0) {
            slotSelect.innerHTML = '<option value="">No hay horarios libres disponibles</option>';
        } else {
            slotSelect.innerHTML = '<option value="">Seleccionar nuevo horario...</option>' +
                freeSlots.map(slot => {
                    const s = new Date(slot.starts_at);
                    const e = new Date(slot.ends_at);
                    const label = `${s.toLocaleDateString('es-MX')} ${s.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${e.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;
                    return `<option value="${slot.id}">${label}</option>`;
                }).join('');
        }

        if (acceptChangeRequestModal) acceptChangeRequestModal.show();
    }

    async function acceptChangeRequest() {
        const reqId = document.getElementById('acceptChangeReqId').value;
        const newSlotId = document.getElementById('acceptChangeNewSlot').value;

        if (!newSlotId) {
            flash('Debes seleccionar un nuevo horario', 'warning');
            return;
        }

        try {
            await apiRequest(`${API}/appointments/change-requests/${reqId}/decision`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'accepted', new_slot_id: parseInt(newSlotId) })
            });

            flash('Cambio de horario aprobado correctamente', 'success');
            if (acceptChangeRequestModal) acceptChangeRequestModal.hide();
            await loadSlots(selectedEventId);
            await loadChangeRequests(selectedEventId);
        } catch (err) {
            flash(`Error aprobando cambio: ${err.message}`, 'danger');
        }
    }

    async function rejectChangeRequest(reqId) {
        const ok = await siiapConfirm({
            type: 'danger',
            title: 'Rechazar solicitud',
            message: '¿Rechazar esta solicitud de cambio?',
            confirmLabel: 'Sí, rechazar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/appointments/change-requests/${reqId}/decision`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'rejected' })
            });

            flash('Solicitud de cambio rechazada', 'success');
            await loadChangeRequests(selectedEventId);
        } catch (err) {
            flash(`Error rechazando solicitud: ${err.message}`, 'danger');
        }
    }

    // ========== WIZARD DE CREACIÓN ==========

    /** Internal wizard state */
    const wizardState = { purpose: null, stage: 1, data: {} };

    function showWizardStage(n) {
        document.getElementById('wizardStage1').classList.toggle('active', n === 1);
        document.getElementById('wizardStage2').classList.toggle('active', n === 2);

        const indicator = document.getElementById('wizardStepIndicator');
        indicator.textContent = n === 1
            ? 'Paso 1 de 2 — Selecciona el propósito'
            : 'Paso 2 de 2 — Configura el evento';

        document.getElementById('wizardBtnBack').classList.toggle('d-none', n === 1);
        document.getElementById('wizardBtnSubmit').classList.toggle('d-none', n === 1);
        wizardState.stage = n;
    }

    /**
     * selectPurpose — Applies field visibility rules for the chosen purpose and
     * advances to stage 2.
     *
     * @param {'single'|'multiple'|'other'} purpose
     */
    function selectPurpose(purpose) {
        wizardState.purpose = purpose;

        // Highlight selected card
        document.querySelectorAll('.wizard-purpose-card').forEach(c => {
            c.classList.toggle('selected', c.dataset.purpose === purpose);
        });

        // Pre-set capacity type hidden field and control field visibility
        const capTypeSelect = document.getElementById('eventCapacityType');
        const fieldType    = document.getElementById('fieldEventType');
        const fieldDates   = document.getElementById('fieldEventDates');
        const fieldMaxCap  = document.getElementById('fieldMaxCapacity');
        const fieldCapType = document.getElementById('fieldCapacityType');

        if (purpose === 'single') {
            capTypeSelect.value = 'single';
            // Lock type to interview/defense — show the field but restrict
            fieldType.classList.remove('d-none');
            // Filter type options to 1:1 types
            const typeSelect = document.getElementById('eventType');
            Array.from(typeSelect.options).forEach(opt => {
                opt.hidden = !['interview', 'defense'].includes(opt.value);
            });
            typeSelect.value = 'interview';

            fieldDates.classList.add('d-none');
            fieldMaxCap.classList.add('d-none');
            fieldCapType.classList.add('d-none');
        } else if (purpose === 'multiple') {
            capTypeSelect.value = 'multiple';
            // Show type select with group subtypes only
            fieldType.classList.remove('d-none');
            const typeSelect = document.getElementById('eventType');
            Array.from(typeSelect.options).forEach(opt => {
                opt.hidden = ['interview', 'defense'].includes(opt.value);
            });
            typeSelect.value = 'workshop';

            fieldDates.classList.remove('d-none');
            fieldMaxCap.classList.remove('d-none');
            document.getElementById('eventMaxCapacity').required = true;
            // Permitir override a 'unlimited' — mostrar selector de capacidad.
            // Ocultar la opción 'single' para forzar multiple o unlimited.
            fieldCapType.classList.remove('d-none');
            Array.from(capTypeSelect.options).forEach(opt => {
                opt.hidden = opt.value === 'single';
            });
        } else {
            // 'other' — show everything
            fieldType.classList.remove('d-none');
            const typeSelect = document.getElementById('eventType');
            Array.from(typeSelect.options).forEach(opt => { opt.hidden = false; });
            typeSelect.value = 'other';

            fieldDates.classList.remove('d-none');
            fieldMaxCap.classList.add('d-none');  // shown dynamically via capType change
            document.getElementById('eventMaxCapacity').required = false;
            fieldCapType.classList.remove('d-none');
        }

        showWizardStage(2);
    }

    function setupWizard() {
        // Card click
        document.querySelectorAll('.wizard-purpose-card').forEach(card => {
            card.addEventListener('click', () => selectPurpose(card.dataset.purpose));
        });

        // Back button
        document.getElementById('wizardBtnBack')?.addEventListener('click', () => {
            showWizardStage(1);
        });

        // Capacity type change: visible tanto en 'multiple' como 'other'
        document.getElementById('eventCapacityType')?.addEventListener('change', (e) => {
            if (!['multiple', 'other'].includes(wizardState.purpose)) return;
            const fieldMaxCap = document.getElementById('fieldMaxCapacity');
            const maxInput    = document.getElementById('eventMaxCapacity');
            if (e.target.value === 'multiple') {
                fieldMaxCap.classList.remove('d-none');
                maxInput.required = true;
            } else {
                fieldMaxCap.classList.add('d-none');
                maxInput.required = false;
                maxInput.value = '';
            }
        });

        // Reset wizard when modal closes
        const modalEl = document.getElementById('createEventModal');
        modalEl?.addEventListener('hidden.bs.modal', resetWizard);
    }

    function resetWizard() {
        wizardState.purpose = null;
        wizardState.stage   = 1;
        wizardState.data    = {};

        // Reset card selection
        document.querySelectorAll('.wizard-purpose-card').forEach(c => c.classList.remove('selected'));

        // Reset type options visibility
        const typeSelect = document.getElementById('eventType');
        if (typeSelect) {
            Array.from(typeSelect.options).forEach(opt => { opt.hidden = false; });
            typeSelect.value = 'interview';
        }

        // Reset field visibility to defaults (all hidden except what stage1 needs)
        document.getElementById('fieldEventDates')?.classList.remove('d-none');
        document.getElementById('fieldMaxCapacity')?.classList.add('d-none');
        document.getElementById('fieldCapacityType')?.classList.add('d-none');
        document.getElementById('eventMaxCapacity').required = false;
        document.getElementById('eventMaxCapacity').value = '';

        showWizardStage(1);
    }

    // ========== PANEL CONTENIDO: PORTADA ==========

    /** Currently loaded images for the selected event */
    let currentEventImages = { cover: null, gallery: [] };
    /** Currently loaded hosts for the selected event */
    let currentEventHosts  = [];

    /**
     * Construye URL de imagen de evento. Backend devuelve `path` relativo
     * tipo "42/cover.webp" o "42/gallery/uuid.png". Se sirve via /files/event/<id>/<kind>/<filename>.
     */
    function buildEventImageUrl(eventId, image, kind) {
        if (!image || !image.path) return '';
        const filename = image.path.split('/').pop();
        return `/files/event/${eventId}/${kind}/${filename}`;
    }

    async function loadEventMedia(eventId) {
        try {
            const { data } = await apiRequest(`${API}/events/${eventId}/images`);
            currentEventImages = {
                cover:   data.cover   || null,
                gallery: data.gallery || [],
                eventId: eventId
            };
            renderCoverPreview();
            renderGalleryGrid();
        } catch (err) {
            console.error('Error loading event images:', err);
        }
    }

    function renderCoverPreview() {
        const preview  = document.getElementById('coverPreview');
        const delBtn   = document.getElementById('coverDeleteBtn');
        const coverId  = document.getElementById('coverImageId');
        if (!preview) return;

        if (currentEventImages.cover) {
            const url = buildEventImageUrl(currentEventImages.eventId, currentEventImages.cover, 'cover');
            preview.style.backgroundImage = `url('${url}')`;
            preview.classList.remove('empty');
            preview.innerHTML = '';
            delBtn?.classList.remove('d-none');
            if (coverId) coverId.value = currentEventImages.cover.id;
        } else {
            preview.style.backgroundImage = '';
            preview.classList.add('empty');
            preview.innerHTML = `
                <div class="text-center">
                    <i class="bi bi-image fs-1 d-block mb-2"></i>
                    <span class="text-muted small">Sin portada</span>
                </div>`;
            delBtn?.classList.add('d-none');
            if (coverId) coverId.value = '';
        }
    }

    function renderGalleryGrid() {
        const grid     = document.getElementById('galleryGrid');
        const empty    = document.getElementById('galleryEmpty');
        if (!grid) return;

        const images = currentEventImages.gallery;
        if (images.length === 0) {
            grid.innerHTML = '';
            empty?.classList.remove('d-none');
            return;
        }

        empty?.classList.add('d-none');
        grid.innerHTML = images.map(img => {
            const url = buildEventImageUrl(currentEventImages.eventId, img, 'gallery');
            return `
            <div class="event-gallery-item">
                <img src="${url}" alt="${escapeAttr(img.caption || '')}">
                <button type="button"
                    class="btn btn-danger btn-sm btn-remove btn-delete-gallery-image"
                    data-image-id="${img.id}"
                    title="Eliminar imagen">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>`;
        }).join('');
    }

    function setupCoverDropzone() {
        const dropzone  = document.getElementById('coverDropzone');
        const selectBtn = document.getElementById('coverSelectBtn');
        const fileInput = document.getElementById('coverFileInput');
        const delBtn    = document.getElementById('coverDeleteBtn');

        if (!dropzone) return;

        selectBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
        dropzone.addEventListener('click', () => fileInput.click());

        fileInput?.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadCover(fileInput.files[0]);
        });

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) uploadCover(file);
        });

        delBtn?.addEventListener('click', deleteCover);
    }

    async function uploadCover(file) {
        if (!selectedEventId) { flash('Selecciona un evento primero', 'warning'); return; }
        if (file.size > 5 * 1024 * 1024) { flash('La imagen supera el límite de 5 MB', 'warning'); return; }

        const fd = new FormData();
        fd.append('file', file);

        try {
            const res = await fetch(`${API}/events/${selectedEventId}/cover`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                credentials: 'same-origin',
                body: fd
            });
            const data = await res.json();
            if (!res.ok) { flash(data.error?.message || 'Error al subir la portada', 'danger'); return; }
            flash('Portada actualizada correctamente', 'success');
            await loadEventMedia(selectedEventId);
        } catch (err) {
            flash(`Error al subir portada: ${err.message}`, 'danger');
        }
    }

    async function deleteCover() {
        const imageId = document.getElementById('coverImageId')?.value;
        if (!imageId) return;
        const ok = await siiapConfirm({ type: 'danger', title: 'Eliminar portada', message: '¿Eliminar la portada de este evento?', confirmLabel: 'Sí, eliminar' });
        if (!ok) return;
        try {
            await apiRequest(`${API}/events/images/${imageId}`, { method: 'DELETE' });
            flash('Portada eliminada', 'success');
            currentEventImages.cover = null;
            renderCoverPreview();
        } catch (err) {
            flash(`Error al eliminar portada: ${err.message}`, 'danger');
        }
    }

    // ========== PANEL CONTENIDO: GALERÍA ==========

    function setupGalleryDropzone() {
        const dropzone  = document.getElementById('galleryDropzone');
        const selectBtn = document.getElementById('gallerySelectBtn');
        const fileInput = document.getElementById('galleryFileInput');

        if (!dropzone) return;

        selectBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
        dropzone.addEventListener('click', () => fileInput.click());

        fileInput?.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadGalleryImages(Array.from(fileInput.files));
        });

        dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            uploadGalleryImages(Array.from(e.dataTransfer.files));
        });

        // Delete buttons (event delegation on grid)
        document.getElementById('galleryGrid')?.addEventListener('click', async (e) => {
            const btn = e.target.closest('.btn-delete-gallery-image');
            if (!btn) return;
            const imageId = parseInt(btn.dataset.imageId);
            const ok = await siiapConfirm({ type: 'danger', title: 'Eliminar imagen', message: '¿Eliminar esta imagen de la galería?', confirmLabel: 'Sí, eliminar' });
            if (!ok) return;
            try {
                await apiRequest(`${API}/events/images/${imageId}`, { method: 'DELETE' });
                flash('Imagen eliminada', 'success');
                await loadEventMedia(selectedEventId);
            } catch (err) {
                flash(`Error al eliminar imagen: ${err.message}`, 'danger');
            }
        });
    }

    async function uploadGalleryImages(files) {
        if (!selectedEventId) { flash('Selecciona un evento primero', 'warning'); return; }

        let uploaded = 0;
        for (const file of files) {
            if (file.size > 5 * 1024 * 1024) {
                flash(`"${file.name}" supera el límite de 5 MB y fue omitida`, 'warning');
                continue;
            }
            const fd = new FormData();
            fd.append('file', file);
            try {
                const res = await fetch(`${API}/events/${selectedEventId}/images`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken() },
                    credentials: 'same-origin',
                    body: fd
                });
                if (res.ok) uploaded++;
                else {
                    const d = await res.json();
                    flash(d.error?.message || `Error subiendo "${file.name}"`, 'danger');
                }
            } catch (err) {
                flash(`Error al subir "${file.name}": ${err.message}`, 'danger');
            }
        }
        if (uploaded > 0) {
            flash(`${uploaded} imagen${uploaded > 1 ? 'es' : ''} subida${uploaded > 1 ? 's' : ''} correctamente`, 'success');
            await loadEventMedia(selectedEventId);
        }
    }

    // ========== PANEL CONTENIDO: PONENTES ==========

    /**
     * loadEventHosts — Fetches hosts from API and populates the in-memory list.
     * @param {number} eventId
     */
    async function loadEventHosts(eventId) {
        try {
            const { data } = await apiRequest(`${API}/events/${eventId}/hosts`);
            currentEventHosts = data.hosts || [];
            renderHostsList();
        } catch (err) {
            console.error('Error loading hosts:', err);
        }
    }

    /**
     * renderHostsList — Renders the host cards from `currentEventHosts`.
     */
    function renderHostsList() {
        const list  = document.getElementById('hostsList');
        const empty = document.getElementById('hostsEmpty');
        if (!list) return;

        if (currentEventHosts.length === 0) {
            list.innerHTML = '';
            list.appendChild(empty || document.createElement('div'));
            empty?.classList.remove('d-none');
            return;
        }
        empty?.classList.add('d-none');

        list.innerHTML = currentEventHosts.map((host, idx) => {
            const isInternal = !!host.user_id;
            const typeBadge  = isInternal
                ? '<span class="badge bg-info text-dark">Interno</span>'
                : '<span class="badge bg-secondary">Externo</span>';
            const avatarSrc  = host.avatar_url || host.photo_url || '/static/assets/images/default.jpg';
            const name       = host.full_name || host.name || host.external_name || 'Sin nombre';

            return `
            <div class="event-host-card" data-host-idx="${idx}">
                <img src="${avatarSrc}" alt="Avatar" class="avatar">
                <div class="host-info">
                    <div class="fw-semibold">${name}</div>
                    <div class="text-muted small">${host.role_label || ''} ${typeBadge}</div>
                </div>
                <div class="host-actions d-flex gap-1">
                    <button type="button" class="btn btn-sm btn-outline-secondary btn-move-host-up"
                        data-idx="${idx}" title="Subir" ${idx === 0 ? 'disabled' : ''}>
                        <i class="bi bi-arrow-up"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary btn-move-host-down"
                        data-idx="${idx}" title="Bajar" ${idx === currentEventHosts.length - 1 ? 'disabled' : ''}>
                        <i class="bi bi-arrow-down"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-primary btn-edit-host"
                        data-idx="${idx}" title="Editar">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger btn-remove-host"
                        data-idx="${idx}" title="Eliminar">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>`;
        }).join('');
    }

    function setupHostsPanel() {
        document.getElementById('addHostBtn')?.addEventListener('click', () => openHostEditor(-1));
        document.getElementById('saveHostsBtn')?.addEventListener('click', saveHosts);
        document.getElementById('hostsList')?.addEventListener('click', (e) => {
            const up   = e.target.closest('.btn-move-host-up');
            const down = e.target.closest('.btn-move-host-down');
            const edit = e.target.closest('.btn-edit-host');
            const del  = e.target.closest('.btn-remove-host');

            if (up)   { const i = parseInt(up.dataset.idx);   moveHost(i, i - 1); }
            if (down) { const i = parseInt(down.dataset.idx); moveHost(i, i + 1); }
            if (edit) { openHostEditor(parseInt(edit.dataset.idx)); }
            if (del)  { removeHost(parseInt(del.dataset.idx)); }
        });
    }

    function moveHost(fromIdx, toIdx) {
        if (toIdx < 0 || toIdx >= currentEventHosts.length) return;
        const arr = [...currentEventHosts];
        [arr[fromIdx], arr[toIdx]] = [arr[toIdx], arr[fromIdx]];
        currentEventHosts = arr;
        renderHostsList();
    }

    function removeHost(idx) {
        currentEventHosts = currentEventHosts.filter((_, i) => i !== idx);
        renderHostsList();
    }

    /**
     * openHostEditor — Opens #hostEditorModal for adding (idx=-1) or editing an existing host.
     * @param {number} idx  Index in currentEventHosts (-1 = new)
     */
    function openHostEditor(idx) {
        const isNew = idx === -1;
        document.getElementById('hostEditorModalTitle').textContent = isNew ? 'Agregar Ponente' : 'Editar Ponente';
        document.getElementById('hostEditIndex').value = idx;

        // Reset form
        document.getElementById('hostTypeInternal').checked = true;
        document.getElementById('hostUserSearch').value    = '';
        document.getElementById('hostUserId').value        = '';
        document.getElementById('hostSelectedUserCard').classList.add('d-none');
        document.getElementById('hostExternalName').value  = '';
        document.getElementById('hostExternalBio').value   = '';
        document.getElementById('hostExternalPhoto').value = '';
        document.getElementById('hostExternalPhotoPath').value = '';
        document.getElementById('hostRoleLabel').value     = '';
        document.getElementById('hostInternalPanel').classList.remove('d-none');
        document.getElementById('hostExternalPanel').classList.add('d-none');

        if (!isNew) {
            const host = currentEventHosts[idx];
            if (host.user_id) {
                document.getElementById('hostTypeInternal').checked = true;
                document.getElementById('hostUserId').value = host.user_id;
                showSelectedUser({
                    id: host.user_id,
                    full_name: host.full_name || host.name || '',
                    email: host.email || '',
                    role: host.role_display || host.role || '',
                    avatar_url: host.avatar_url || host.photo_url || ''
                });
            } else {
                document.getElementById('hostTypeExternal').checked = true;
                document.getElementById('hostInternalPanel').classList.add('d-none');
                document.getElementById('hostExternalPanel').classList.remove('d-none');
                document.getElementById('hostExternalName').value  = host.external_name || host.name || '';
                document.getElementById('hostExternalBio').value   = host.external_bio  || host.bio || '';
                document.getElementById('hostExternalPhotoPath').value = host.external_photo_path || '';
            }
            document.getElementById('hostRoleLabel').value = host.role_label || '';
        }

        const modalEl = document.getElementById('hostEditorModal');
        if (modalEl) new bootstrap.Modal(modalEl).show();
    }

    function showSelectedUser(user) {
        document.getElementById('hostUserId').value         = user.id;
        document.getElementById('hostSelectedName').textContent  = user.full_name || '';
        document.getElementById('hostSelectedEmail').textContent = user.email || '';
        document.getElementById('hostSelectedRole').textContent  = user.role || '';
        const avatar = document.getElementById('hostSelectedAvatar');
        avatar.src = user.avatar_url || '/static/assets/images/default.jpg';
        document.getElementById('hostSelectedUserCard').classList.remove('d-none');
        document.getElementById('hostUserSearch').value = '';
        document.getElementById('hostUserDropdown').style.display = 'none';
    }

    function setupHostEditor() {
        // Toggle internal / external
        document.querySelectorAll('input[name="hostTypeRadio"]').forEach(radio => {
            radio.addEventListener('change', () => {
                const isInternal = document.getElementById('hostTypeInternal').checked;
                document.getElementById('hostInternalPanel').classList.toggle('d-none', !isInternal);
                document.getElementById('hostExternalPanel').classList.toggle('d-none', isInternal);
            });
        });

        // Typeahead user search
        let searchTimer = null;
        document.getElementById('hostUserSearch')?.addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            const q = e.target.value.trim();
            if (q.length < 2) {
                document.getElementById('hostUserDropdown').style.display = 'none';
                return;
            }
            searchTimer = setTimeout(() => searchUsers(q), 300);
        });

        document.getElementById('hostClearUserBtn')?.addEventListener('click', () => {
            document.getElementById('hostUserId').value = '';
            document.getElementById('hostSelectedUserCard').classList.add('d-none');
        });

        // Save host button
        document.getElementById('hostEditorSaveBtn')?.addEventListener('click', saveHostFromModal);
    }

    function escapeAttr(s) {
        return String(s ?? '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    async function searchUsers(query) {
        try {
            const { data } = await apiRequest(`${API}/admin/users/?search=${encodeURIComponent(query)}&per_page=10&active=true`);
            // Endpoint retorna {data: {users: [...], pagination: ...}, error, meta}
            const users = data?.data?.users || data?.users || data?.items || [];
            renderUserDropdown(users);
        } catch (err) {
            console.error('Error searching users:', err);
            renderUserDropdown([]);
        }
    }

    function renderUserDropdown(users) {
        const dropdown = document.getElementById('hostUserDropdown');
        if (!dropdown) return;

        if (users.length === 0) {
            dropdown.innerHTML = '<div class="list-group-item text-muted small">Sin resultados</div>';
            dropdown.style.display = 'block';
            return;
        }

        const fullNameOf = (u) => {
            if (u.full_name) return u.full_name;
            if (u.name) return u.name;
            return [u.first_name, u.last_name, u.mother_last_name].filter(Boolean).join(' ');
        };

        dropdown.innerHTML = users.map(u => {
            const fullName = fullNameOf(u);
            const role     = u.role_name || u.role || '';
            return `
            <button type="button" class="list-group-item list-group-item-action py-2"
                data-user-id="${u.id}"
                data-full-name="${escapeAttr(fullName)}"
                data-email="${escapeAttr(u.email || '')}"
                data-role="${escapeAttr(role)}"
                data-avatar="${escapeAttr(u.avatar_url || '')}">
                <div class="d-flex align-items-center gap-2">
                    <img src="${u.avatar_url || '/static/assets/images/default.jpg'}" width="28" height="28"
                        class="rounded-circle" style="object-fit:cover">
                    <div>
                        <div class="fw-semibold small">${escapeAttr(fullName)}</div>
                        <div class="text-muted small">${escapeAttr(u.email || '')} &bull; ${escapeAttr(role)}</div>
                    </div>
                </div>
            </button>`;
        }).join('');

        dropdown.querySelectorAll('button[data-user-id]').forEach(btn => {
            btn.addEventListener('click', () => {
                showSelectedUser({
                    id: parseInt(btn.dataset.userId),
                    full_name: btn.dataset.fullName,
                    email: btn.dataset.email,
                    role: btn.dataset.role,
                    avatar_url: btn.dataset.avatar
                });
            });
        });

        dropdown.style.display = 'block';
    }

    async function saveHostFromModal() {
        const isInternal = document.getElementById('hostTypeInternal').checked;
        const roleLabel  = document.getElementById('hostRoleLabel').value.trim();
        const editIdx    = parseInt(document.getElementById('hostEditIndex').value);

        if (!roleLabel) {
            flash('El rol o etiqueta del ponente es requerido', 'warning');
            return;
        }

        let hostObj = { role_label: roleLabel };

        if (isInternal) {
            const userId = parseInt(document.getElementById('hostUserId').value);
            if (!userId) {
                flash('Selecciona un usuario del sistema', 'warning');
                return;
            }
            hostObj.user_id    = userId;
            hostObj.full_name  = document.getElementById('hostSelectedName').textContent;
            hostObj.email      = document.getElementById('hostSelectedEmail').textContent;
            hostObj.avatar_url = document.getElementById('hostSelectedAvatar').src;
        } else {
            const externalName  = document.getElementById('hostExternalName').value.trim();
            const externalBio   = document.getElementById('hostExternalBio').value.trim();
            const photoFile     = document.getElementById('hostExternalPhoto').files[0];
            const existingPath  = document.getElementById('hostExternalPhotoPath').value;

            if (!externalName) {
                flash('El nombre del ponente externo es requerido', 'warning');
                return;
            }

            // Upload photo if selected
            let photoPath = existingPath;
            if (photoFile && selectedEventId) {
                try {
                    const fd = new FormData();
                    fd.append('file', photoFile);
                    const res = await fetch(`${API}/events/${selectedEventId}/hosts/photo`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCsrfToken() },
                        credentials: 'same-origin',
                        body: fd
                    });
                    const d = await res.json();
                    if (res.ok && d.path) photoPath = d.path;
                } catch (err) {
                    flash('Error al subir la foto del ponente', 'warning');
                }
            }

            hostObj.external_name       = externalName;
            hostObj.external_bio        = externalBio;
            hostObj.external_photo_path = photoPath || null;
        }

        if (editIdx === -1) {
            currentEventHosts.push(hostObj);
        } else {
            currentEventHosts[editIdx] = hostObj;
        }

        renderHostsList();

        const modalEl = document.getElementById('hostEditorModal');
        const modal   = bootstrap.Modal.getInstance(modalEl);
        modal?.hide();
    }

    /**
     * saveHosts — Sends PUT /api/v1/events/<id>/hosts with the full hosts array.
     */
    async function saveHosts() {
        if (!selectedEventId) { flash('Selecciona un evento primero', 'warning'); return; }
        try {
            await apiRequest(`${API}/events/${selectedEventId}/hosts`, {
                method: 'PUT',
                body: JSON.stringify({ hosts: currentEventHosts })
            });
            flash('Ponentes guardados correctamente', 'success');
        } catch (err) {
            flash(`Error al guardar ponentes: ${err.message}`, 'danger');
        }
    }

    // ========== CONTENT PANE VISIBILITY ==========

    /**
     * setupContentTabVisibility — Listens for Bootstrap tab events on the
     * "Contenido" buttons and shows/hides #pane-content-media accordingly.
     */
    function setupContentTabVisibility() {
        const contentPane = document.getElementById('pane-content-media');
        const infoPane    = document.getElementById('pane-event-info');

        if (contentPane) {
            document.querySelectorAll('.tab-content-media').forEach(btn => {
                btn.addEventListener('shown.bs.tab', () => {
                    contentPane.style.display = 'block';
                    if (infoPane) infoPane.style.display = 'none';
                    if (selectedEventId) {
                        loadEventMedia(selectedEventId);
                        loadEventHosts(selectedEventId);
                    }
                });
                btn.addEventListener('hide.bs.tab', () => {
                    contentPane.style.display = 'none';
                });
            });
        }

        if (infoPane) {
            document.querySelectorAll('.tab-event-info').forEach(btn => {
                btn.addEventListener('shown.bs.tab', () => {
                    infoPane.style.display = 'block';
                    if (contentPane) contentPane.style.display = 'none';
                    if (selectedEventId) {
                        const ev = currentEvents.find(e => e.id === selectedEventId);
                        if (ev) populateEditForm(ev);
                    }
                });
                btn.addEventListener('hide.bs.tab', () => {
                    infoPane.style.display = 'none';
                });
            });
        }

        // Hide both when other tabs are shown
        document.querySelectorAll('[data-bs-toggle="tab"]:not(.tab-content-media):not(.tab-event-info)').forEach(btn => {
            btn.addEventListener('shown.bs.tab', () => {
                if (contentPane) contentPane.style.display = 'none';
                if (infoPane)    infoPane.style.display    = 'none';
            });
        });
    }

    // ========== EDITOR DE INFORMACIÓN ==========

    function populateEditForm(event) {
        const f = (id) => document.getElementById(id);
        if (!f('editEventId')) return;

        f('editEventId').value          = event.id;
        f('editTitle').value            = event.title || '';
        f('editType').value             = event.type || 'interview';
        f('editLocation').value         = event.location || '';
        f('editDescription').value      = event.description || '';
        f('editStatus').value           = event.status || 'published';
        f('editVisibility').value       = event.visibility || 'public';
        f('editProgram').value          = event.program_id || '';
        f('editAcademicPeriod').value   = event.academic_period_id || '';
        f('editRequiresRegistration').checked = !!event.requires_registration;
        f('editAllowsAttendance').checked     = !!event.allows_attendance_tracking;
        f('editVisibleToStudents').checked    = event.visible_to_students !== false;
        f('editRemindersEnabled').checked     = event.reminders_enabled !== false;

        // Filas condicionales por capacity_type
        const showDates    = event.capacity_type !== 'single';
        const showMaxCap   = event.capacity_type === 'multiple';
        f('editDatesRow').classList.toggle('d-none', !showDates);
        f('editDatesRow2').classList.toggle('d-none', !showDates);
        f('editMaxCapacityRow').classList.toggle('d-none', !showMaxCap);

        if (event.event_date) {
            f('editEventDate').value = event.event_date.slice(0, 16);
        } else {
            f('editEventDate').value = '';
        }
        if (event.event_end_date) {
            f('editEventEndDate').value = event.event_end_date.slice(0, 16);
        } else {
            f('editEventEndDate').value = '';
        }
        if (event.max_capacity) {
            f('editMaxCapacity').value = event.max_capacity;
        }
    }

    async function handleEditEvent(e) {
        e.preventDefault();
        const eventId = parseInt(document.getElementById('editEventId').value);
        if (!eventId) return;

        const f = (id) => document.getElementById(id);
        const payload = {
            title: f('editTitle').value.trim(),
            type:  f('editType').value,
            location: f('editLocation').value.trim(),
            description: f('editDescription').value,
            status: f('editStatus').value,
            visibility: f('editVisibility').value,
            program_id: f('editProgram').value ? parseInt(f('editProgram').value) : null,
            academic_period_id: f('editAcademicPeriod').value ? parseInt(f('editAcademicPeriod').value) : null,
            requires_registration: f('editRequiresRegistration').checked,
            allows_attendance_tracking: f('editAllowsAttendance').checked,
            visible_to_students: f('editVisibleToStudents').checked,
            reminders_enabled: f('editRemindersEnabled').checked,
        };

        const eventDate    = f('editEventDate').value;
        const eventEndDate = f('editEventEndDate').value;
        if (eventDate)    payload.event_date    = eventDate;
        if (eventEndDate) payload.event_end_date = eventEndDate;

        const maxCap = f('editMaxCapacity').value;
        if (maxCap) payload.max_capacity = parseInt(maxCap);

        if (!payload.title) {
            flash('El título es requerido', 'warning');
            return;
        }

        try {
            await apiRequest(`${API}/events/${eventId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            flash('Evento actualizado', 'success');
            await loadEvents();
            // Re-seleccionar para reflejar cambios
            const updated = currentEvents.find(e => e.id === eventId);
            if (updated) {
                populateEditForm(updated);
                updatePrivacyToggle(updated);
            }
        } catch (err) {
            flash(`Error al actualizar: ${err.message}`, 'danger');
        }
    }

    function updatePrivacyToggle(event) {
        const btn   = document.getElementById('btnTogglePrivacy');
        const label = document.getElementById('togglePrivacyLabel');
        const badge = document.getElementById('selectedEventVisibilityBadge');
        if (!btn || !label) return;

        if (event.visibility === 'private') {
            label.textContent = 'Hacer público';
            btn.classList.remove('btn-outline-warning');
            btn.classList.add('btn-outline-success');
            badge?.classList.remove('d-none');
        } else {
            label.textContent = 'Hacer privado';
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-outline-warning');
            badge?.classList.add('d-none');
        }
    }

    async function handleTogglePrivacy() {
        if (!selectedEventId) return;
        const ev = currentEvents.find(e => e.id === selectedEventId);
        if (!ev) return;
        const newVis = ev.visibility === 'private' ? 'public' : 'private';

        if (newVis === 'public') {
            const ok = await siiapConfirm({
                type: 'warning',
                title: 'Hacer evento público',
                message: `Este evento será visible a todos los usuarios elegibles. ¿Continuar?`,
                confirmLabel: 'Sí, hacer público',
            });
            if (!ok) return;
        }

        try {
            await apiRequest(`${API}/events/${selectedEventId}`, {
                method: 'PUT',
                body: JSON.stringify({ visibility: newVis }),
            });
            flash(`Evento ahora es ${newVis === 'private' ? 'privado' : 'público'}`, 'success');
            await loadEvents();
            const updated = currentEvents.find(e => e.id === selectedEventId);
            if (updated) {
                populateEditForm(updated);
                updatePrivacyToggle(updated);
            }
        } catch (err) {
            flash(`Error: ${err.message}`, 'danger');
        }
    }

    function setupEventEditor() {
        document.getElementById('editEventForm')?.addEventListener('submit', handleEditEvent);
        document.getElementById('btnRevertEdit')?.addEventListener('click', () => {
            if (!selectedEventId) return;
            const ev = currentEvents.find(e => e.id === selectedEventId);
            if (ev) populateEditForm(ev);
        });
        document.getElementById('btnTogglePrivacy')?.addEventListener('click', handleTogglePrivacy);

        // Poblar selects de programa/periodo en form de edición
        // (reusa los datos cargados por loadPrograms / loadAcademicPeriods)
    }

    // ========== INICIALIZACIÓN ==========
    init();

})();
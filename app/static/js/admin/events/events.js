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

    // Formularios
    const createEventForm = document.getElementById("createEventForm");
    const addWindowForm = document.getElementById("addWindowForm");
    const assignSlotForm = document.getElementById("assignSlotForm");
    const cancelAppointmentForm = document.getElementById("cancelAppointmentForm");

    // Estado
    let currentEvents = [];
    let currentSlots = [];
    let eligibleStudentsList = [];
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
    function setupCapacityTypeHandler() {
        const capacityTypeSelect = document.getElementById('eventCapacityType');
        const maxCapacityGroup = document.getElementById('maxCapacityGroup');
        const maxCapacityInput = document.getElementById('eventMaxCapacity');

        if (!capacityTypeSelect) return;

        capacityTypeSelect.addEventListener('change', (e) => {
            const type = e.target.value;

            if (type === 'multiple') {
                maxCapacityGroup.style.display = 'block';
                maxCapacityInput.required = true;
            } else {
                maxCapacityGroup.style.display = 'none';
                maxCapacityInput.required = false;
                maxCapacityInput.value = '';
            }
        });
    }
    async function apiRequest(url, options = {}) {
        const defaultOptions = {
            credentials: "same-origin",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken(),
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
        await loadEvents();
        await loadEligibleStudents();
        setupEventListeners();
        setupCapacityTypeHandler();
    }

    async function loadPrograms() {
        try {
            // CAMBIAR: Usar API correcta de programas
            const { data } = await apiRequest(`${API}/programs`);
            programs = data.data || [];  // Nota: la API devuelve {data: [...]}

            const programSelects = [
                document.getElementById("eventProgram"),
                document.getElementById("programFilter")
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

    async function loadEvents() {
        try {
            const { data } = await apiRequest(`${API}/events`);
            currentEvents = data.items || [];
            renderEventsTable();

        } catch (err) {
            console.error('Error loading events:', err);
            flash(`Error cargando eventos: ${err.message}`, 'danger');
        }
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
          ${capacityBadge}
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
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary btn-view-slots" title="Ver horarios">
              <i class="fas fa-calendar-alt"></i>
            </button>
            ${event.capacity_type !== 'single' ? `
              <button class="btn btn-outline-success btn-view-registrations" title="Ver registros">
                <i class="fas fa-users"></i>
              </button>
            ` : ''}
            <button class="btn btn-outline-danger btn-delete-event" title="Eliminar">
              <i class="fas fa-trash"></i>
            </button>
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
        try {
            const url = `${API}/interviews/eligible-students/${programId}`;

            const { data } = await apiRequest(url);
            eligibleStudentsList = data.eligible_students || data.students || [];
            renderEligibleStudents();

        } catch (err) {
            console.error('Error loading eligible students:', err);
            eligibleStudents.innerHTML = '<div class="list-group-item text-danger">Error cargando estudiantes</div>';
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

    }

    // ========== HANDLERS ==========
    async function handleCreateEvent(e) {
        e.preventDefault();
        const capacityType = document.getElementById('eventCapacityType').value;
        const maxCapacity = document.getElementById('eventMaxCapacity').value;
        const programId = document.getElementById('eventProgram').value;
        console.log(capacityType, maxCapacity, programId);
        // Validar capacidad máxima si es requerida
        if (capacityType === 'multiple' && (!maxCapacity || parseInt(maxCapacity) < 1)) {
            flash('Debes especificar una capacidad máxima válida para eventos de capacidad múltiple', 'warning');
            return;
        }

        const payload = {
            title: document.getElementById('eventTitle').value.trim(),
            program_id: programId ? parseInt(programId) : null,  // CAMBIAR: Permitir null
            type: document.getElementById('eventType').value,
            location: document.getElementById('eventLocation').value,
            description: document.getElementById('eventDescription').value,
            capacity_type: capacityType,
            max_capacity: capacityType === 'multiple' ? parseInt(maxCapacity) : null,
            requires_registration: document.getElementById('eventRequiresRegistration').checked,
            allows_attendance_tracking: document.getElementById('eventAllowsAttendance').checked,
            visible_to_students: document.getElementById('eventVisibleToStudents').checked,
            status: document.getElementById('eventStatus').value
        };
        console.log(payload);
        // CAMBIAR: Ya no requerir programa
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
            document.getElementById('maxCapacityGroup').style.display = 'none';
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
                const confirmed = confirm(data.message + '\n\n¿Deseas eliminar el evento de todas formas?');
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
            console.log("rightPanel", rightPanel);
            console.log("display", rightPanel.style.display);
            loadWindows(eventId);
            loadSlots(eventId);
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
                const confirmed = confirm(data.message + '\n\n¿Deseas eliminar la ventana de todas formas?');
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
                const confirmed = confirm(data.message + '\n\n¿Deseas eliminar el slot de todas formas?');
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
        if (!confirm('¿Cancelar esta invitación?')) return;

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

    // ========== INICIALIZACIÓN ==========
    init();

})();
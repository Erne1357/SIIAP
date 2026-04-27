/* Admin events detail page (orchestrator). */
(() => {
    const C = window.EventsCommon;
    if (!C) {
        console.error('EventsCommon not loaded');
        return;
    }
    const ctx = window.EVENT_DETAIL || {};
    const eventId = ctx.eventId;

    // ---------- State ----------
    let currentEvent = null;
    let currentWindows = [];
    let currentSlots = [];
    let currentChangeRequests = [];
    let currentRegistrations = [];
    let currentInvitations = [];
    let eligibleStudents = [];
    let programs = [];
    let attendanceFilter = '';
    let slotsFilter = 'all';

    // Track loaded panes to avoid duplicate fetches
    const loaded = {
        windows: false, slots: false, changeRequests: false,
        registrations: false, invitations: false, attendance: false
    };

    // Modals (lazy init)
    const modal = (id) => {
        const elNode = document.getElementById(id);
        return elNode ? bootstrap.Modal.getOrCreateInstance(elNode) : null;
    };

    function el(id) { return document.getElementById(id); }

    // =================================================================
    // HEADER
    // =================================================================
    function setBreadcrumb(title) {
        const node = el('breadcrumbEventTitle');
        if (node) node.textContent = title || 'Evento';
        document.title = `${title || 'Evento'} - SIIAP`;
    }

    function renderHeader(ev) {
        const iconNode = el('eventDetailIcon');
        if (iconNode) iconNode.innerHTML = `<i class="bi ${C.TYPE_ICON[ev.type] || 'bi-calendar-event'}"></i>`;

        const titleNode = el('eventDetailTitle');
        if (titleNode) titleNode.textContent = ev.title || '';

        const typeBadge = el('eventDetailTypeBadge');
        if (typeBadge) {
            typeBadge.className = `badge ${C.TYPE_BADGE_CLASS[ev.type] || 'bg-secondary'}`;
            typeBadge.textContent = C.TYPE_LABEL[ev.type] || ev.type;
        }

        const statusBadge = el('eventDetailStatusBadge');
        if (statusBadge) {
            statusBadge.className = `badge ${C.STATUS_BADGE_CLASS[ev.status] || 'bg-secondary'}`;
            statusBadge.textContent = C.STATUS_LABEL[ev.status] || ev.status;
            statusBadge.classList.remove('d-none');
        }

        const visBadge = el('eventDetailVisibilityBadge');
        if (visBadge) visBadge.classList.toggle('d-none', ev.visibility !== 'private');

        const subtitle = el('eventDetailSubtitle');
        if (subtitle) {
            const parts = [];
            parts.push(ev.program_name
                ? `<i class="bi bi-mortarboard me-1"></i>${C.escapeHtml(ev.program_name)}`
                : '<i class="bi bi-globe me-1"></i>Todos los programas');
            parts.push(ev.academic_period_code
                ? `<i class="bi bi-calendar3 me-1"></i>${C.escapeHtml(ev.academic_period_code)}`
                : '<i class="bi bi-infinity me-1"></i>Atemporal');
            parts.push(`<i class="bi bi-people-fill me-1"></i>${C.CAPACITY_LABEL[ev.capacity_type] || ev.capacity_type}`);
            subtitle.innerHTML = parts.join(' &middot; ');
        }

        const header = el('eventDetailHeader');
        if (header) header.className = `event-detail-header card mb-3 event-detail-border-${ev.type || 'other'}`;

        const togglePrivacyLabel = el('togglePrivacyLabel');
        if (togglePrivacyLabel) {
            togglePrivacyLabel.textContent = ev.visibility === 'private' ? 'Hacer público' : 'Hacer privado';
        }

        const btnArchive = el('btnArchiveEvent');
        const btnUnarchive = el('btnUnarchiveEvent');
        if (btnArchive && btnUnarchive) {
            const isArchived = ev.status === 'archived';
            btnArchive.classList.toggle('d-none', isArchived);
            btnUnarchive.classList.toggle('d-none', !isArchived);
        }
    }

    function renderStatChips(ev) {
        const node = el('eventStatChips');
        if (!node) return;
        const chips = [];

        if (ev.capacity_type === 'single') {
            chips.push(`<span class="event-stat-chip"><i class="bi bi-calendar2-check"></i> Slots: <strong>${ev.slots_booked || 0}/${ev.slots_total || 0}</strong></span>`);
            if (ev.windows_count) {
                chips.push(`<span class="event-stat-chip"><i class="bi bi-clock-history"></i> ${ev.windows_count} plazo(s)</span>`);
            }
        } else {
            const cap = ev.max_capacity ? `/${ev.max_capacity}` : '';
            chips.push(`<span class="event-stat-chip"><i class="bi bi-people"></i> Registrados: <strong>${ev.registrations_count || 0}${cap}</strong></span>`);
            if (ev.invitations_pending) {
                chips.push(`<span class="event-stat-chip text-warning"><i class="bi bi-envelope"></i> ${ev.invitations_pending} invitaciones pendientes</span>`);
            }
            if (ev.event_date) {
                chips.push(`<span class="event-stat-chip"><i class="bi bi-calendar-event"></i> ${C.formatDateTime(ev.event_date)}</span>`);
            }
        }

        if (ev.location) {
            chips.push(`<span class="event-stat-chip"><i class="bi bi-geo-alt"></i> ${C.escapeHtml(ev.location)}</span>`);
        }

        node.innerHTML = chips.join('');
    }

    function applyTabsByCapacity(capacityType) {
        const isSingle = capacityType === 'single';
        document.querySelectorAll('#eventDetailTabs .single-only').forEach(li => li.classList.toggle('d-none', !isSingle));
        document.querySelectorAll('#eventDetailTabs .multi-only').forEach(li => li.classList.toggle('d-none', isSingle));
    }

    function renderSummary(ev) {
        const set = (id, val) => { const node = el(id); if (node) node.innerHTML = val || '&mdash;'; };
        set('summaryProgram', ev.program_name ? C.escapeHtml(ev.program_name) : '<span class="text-muted">Todos los programas</span>');
        set('summaryPeriod', ev.academic_period_code ? C.escapeHtml(ev.academic_period_code) : '<span class="text-muted">Sin periodo</span>');
        let cap = C.CAPACITY_LABEL[ev.capacity_type] || ev.capacity_type;
        if (ev.capacity_type === 'multiple' && ev.max_capacity) cap += ` &mdash; máx. ${ev.max_capacity}`;
        set('summaryCapacity', cap);
        set('summaryLocation', ev.location ? C.escapeHtml(ev.location) : '<span class="text-muted">Sin lugar</span>');

        let datesHtml = '<span class="text-muted">No definidas</span>';
        if (ev.event_date) {
            datesHtml = C.formatDateTime(ev.event_date);
            if (ev.event_end_date) datesHtml += ` &rarr; ${C.formatDateTime(ev.event_end_date)}`;
        }
        set('summaryDates', datesHtml);

        const flags = [];
        if (ev.requires_registration) flags.push('Requiere registro');
        if (ev.allows_attendance_tracking) flags.push('Control de asistencia');
        if (ev.visible_to_students) flags.push('Visible a estudiantes');
        if (ev.reminders_enabled) flags.push('Recordatorios activos');
        set('summaryFlags', flags.length
            ? flags.map(f => `<span class="badge bg-light text-dark border me-1">${f}</span>`).join('')
            : '<span class="text-muted">Sin opciones activadas</span>');

        const desc = el('summaryDescription');
        if (desc) {
            if (ev.description) {
                desc.textContent = ev.description;
                desc.classList.remove('text-muted', 'fst-italic');
            } else {
                desc.innerHTML = '<span class="text-muted fst-italic">Sin descripción</span>';
            }
        }
    }

    // =================================================================
    // EVENT DETAIL LOAD
    // =================================================================
    async function loadEventDetails() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}`);
            currentEvent = data;
            setBreadcrumb(data.title);
            renderHeader(data);
            renderStatChips(data);
            applyTabsByCapacity(data.capacity_type);
            renderSummary(data);
            return data;
        } catch (err) {
            C.flash(err.message || 'No se pudo cargar el evento', 'error');
            setBreadcrumb('Evento no encontrado');
        }
    }

    async function refreshEventOnly() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}`);
            currentEvent = data;
            renderHeader(data);
            renderStatChips(data);
            renderSummary(data);
        } catch (err) {
            console.error(err);
        }
    }

    // =================================================================
    // PROGRAMS (for assign program filter)
    // =================================================================
    async function loadPrograms() {
        try {
            const { data } = await C.apiRequest(`${C.API}/programs`);
            programs = data.data || data.items || [];
            const filter = el('assignProgramFilter');
            if (filter && programs.length) {
                filter.innerHTML = '<option value="">Todos los programas</option>' +
                    programs.map(p => `<option value="${p.id}">${C.escapeHtml(p.name)}</option>`).join('');
            }
        } catch (err) {
            console.error('Error loading programs:', err);
        }
    }

    // =================================================================
    // WINDOWS
    // =================================================================
    async function loadWindows() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}/windows-list`);
            currentWindows = data.windows || [];
            renderWindowsTable();
            loaded.windows = true;
        } catch (err) {
            C.flash(`Error cargando plazos: ${err.message}`, 'danger');
        }
    }

    function renderWindowsTable() {
        const tbody = document.querySelector('#windowsTable tbody');
        if (!tbody) return;
        if (currentWindows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No hay plazos creados</td></tr>';
            return;
        }
        tbody.innerHTML = currentWindows.map(w => {
            const date = C.formatDate(w.date);
            const startTime = (w.start_time || '').substring(0, 5);
            const endTime = (w.end_time || '').substring(0, 5);
            return `
                <tr data-window-id="${w.id}">
                    <td>${date}</td>
                    <td>${startTime} - ${endTime}</td>
                    <td>${w.slot_minutes} min</td>
                    <td class="text-center">
                        ${w.slots_generated
                            ? '<span class="badge bg-success"><i class="bi bi-check"></i> Sí</span>'
                            : '<span class="badge bg-secondary"><i class="bi bi-x"></i> No</span>'}
                    </td>
                    <td class="text-center">${w.slots_total}</td>
                    <td class="text-center"><span class="badge bg-success">${w.slots_free}</span></td>
                    <td class="text-center">
                        <span class="badge bg-${w.slots_booked > 0 ? 'warning text-dark' : 'secondary'}">${w.slots_booked}</span>
                    </td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            ${!w.slots_generated ? `
                                <button class="btn btn-outline-success btn-generate-window-slots"
                                    data-window-id="${w.id}" title="Generar slots">
                                    <i class="bi bi-gear"></i>
                                </button>
                            ` : ''}
                            <button class="btn btn-outline-danger btn-delete-window"
                                data-window-id="${w.id}"
                                data-date="${date}"
                                data-time="${startTime} - ${endTime}"
                                data-slots-booked="${w.slots_booked}"
                                title="Eliminar plazo">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    async function handleAddWindow(e) {
        e.preventDefault();
        const payload = {
            date: el('windowDate').value,
            start_time: el('windowStartTime').value,
            end_time: el('windowEndTime').value,
            slot_minutes: parseInt(el('windowSlotMinutes').value)
        };
        try {
            await C.apiRequest(`${C.API}/events/${eventId}/windows`, {
                method: 'POST', body: JSON.stringify(payload)
            });
            C.flash('Plazo creado correctamente', 'success');
            modal('addWindowModal')?.hide();
            el('addWindowForm').reset();
            await loadWindows();
            if (loaded.slots) await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error creando plazo: ${err.message}`, 'danger');
        }
    }

    async function handleGenerateWindowSlots(windowId) {
        try {
            const { data } = await C.apiRequest(
                `${C.API}/events/windows/${windowId}/generate-slots`, { method: 'POST' });
            C.flash(data.created > 0
                ? `Se generaron ${data.created} nuevos slots`
                : 'No se generaron nuevos slots. Ya existen.', data.created > 0 ? 'success' : 'info');
            await loadWindows();
            if (loaded.slots) await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error generando slots: ${err.message}`, 'danger');
        }
    }

    async function handleGenerateAllSlots() {
        if (!currentEvent || !currentWindows.length) {
            C.flash('Primero agrega plazos de horarios', 'warning');
            return;
        }
        let totalCreated = 0;
        for (const w of currentWindows) {
            try {
                const { data } = await C.apiRequest(
                    `${C.API}/events/windows/${w.id}/generate-slots`, { method: 'POST' });
                totalCreated += data.created || 0;
            } catch (err) {
                console.error(`Error generando slots ventana ${w.id}:`, err);
            }
        }
        C.flash(totalCreated > 0
            ? `Se generaron ${totalCreated} nuevos horarios`
            : 'No se generaron nuevos horarios.', totalCreated > 0 ? 'success' : 'info');
        await loadWindows();
        if (loaded.slots) await loadSlots();
        await refreshEventOnly();
    }

    function openDeleteWindowModal(windowId, date, time, slotsBooked) {
        el('deleteWindowId').value = windowId;
        el('deleteWindowDate').textContent = date;
        el('deleteWindowTime').textContent = time;
        const warning = el('deleteWindowWarning');
        const count = el('deleteWindowSlotsCount');
        if (slotsBooked > 0) {
            count.textContent = slotsBooked;
            warning.classList.remove('d-none');
        } else {
            warning.classList.add('d-none');
        }
        modal('confirmDeleteWindowModal')?.show();
    }

    async function handleDeleteWindow() {
        const windowId = parseInt(el('deleteWindowId').value);
        if (!windowId) return;
        try {
            const { data } = await C.apiRequest(`${C.API}/events/windows/${windowId}`, { method: 'DELETE' });
            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger', title: 'Eliminar plazo',
                    message: data.message + '\n\n¿Eliminar de todas formas?',
                    confirmLabel: 'Sí, eliminar'
                });
                if (!confirmed) return;
                await C.apiRequest(`${C.API}/events/windows/${windowId}?force=true`, { method: 'DELETE' });
            }
            C.flash('Plazo eliminado correctamente', 'success');
            modal('confirmDeleteWindowModal')?.hide();
            await loadWindows();
            if (loaded.slots) await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error eliminando plazo: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // SLOTS
    // =================================================================
    async function loadSlots() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}/slots`);
            const items = data.items || [];
            const enriched = await Promise.all(items.map(async (slot) => {
                if (slot.status === 'booked') {
                    try {
                        const { data: a } = await C.apiRequest(`${C.API}/appointments/by-slot/${slot.id}`);
                        if (a.appointment) {
                            return {
                                ...slot,
                                appointment_id: a.appointment.id,
                                student_name: a.appointment.student?.full_name || 'Sin asignar'
                            };
                        }
                    } catch (e) { /* ignore */ }
                }
                return slot;
            }));
            currentSlots = enriched;
            renderSlotsTable();
            updateSlotCounts();
            loaded.slots = true;
        } catch (err) {
            C.flash(`Error cargando horarios: ${err.message}`, 'danger');
        }
    }

    function filteredSlots() {
        if (slotsFilter === 'free') return currentSlots.filter(s => s.status === 'free');
        if (slotsFilter === 'booked') return currentSlots.filter(s => s.status === 'booked');
        return currentSlots;
    }

    function renderSlotsTable() {
        const tbody = document.querySelector('#slotsTable tbody');
        if (!tbody) return;
        const list = filteredSlots();
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No hay horarios</td></tr>';
            return;
        }
        tbody.innerHTML = list.map(slot => {
            const startTime = new Date(slot.starts_at);
            const endTime = new Date(slot.ends_at);
            const dateStr = startTime.toLocaleDateString('es-MX');
            const timeStr = `${startTime.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${endTime.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;
            const slotInfo = `${dateStr} ${timeStr}`;
            return `
                <tr data-slot-id="${slot.id}" class="slot-${slot.status}">
                    <td>${dateStr}</td>
                    <td>${timeStr}</td>
                    <td class="text-center">
                        <span class="badge bg-${slot.status === 'free' ? 'success' : slot.status === 'booked' ? 'primary' : 'secondary'}">
                            ${slot.status === 'free' ? 'Libre' : slot.status === 'booked' ? 'Ocupado' : slot.status}
                        </span>
                    </td>
                    <td>${C.escapeHtml(slot.student_name || '—')}</td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            ${slot.status === 'free' ? `
                                <button class="btn btn-outline-primary btn-assign-slot"
                                    data-slot-id="${slot.id}" data-slot-info="${C.escapeHtml(slotInfo)}">
                                    <i class="bi bi-person-plus"></i>
                                </button>
                            ` : slot.status === 'booked' && slot.appointment_id ? `
                                <button class="btn btn-outline-danger btn-cancel-appointment"
                                    data-appointment-id="${slot.appointment_id}"
                                    data-slot-info="${C.escapeHtml(slotInfo)}"
                                    data-student-name="${C.escapeHtml(slot.student_name || 'Sin asignar')}">
                                    <i class="bi bi-x"></i>
                                </button>
                            ` : ''}
                            <button class="btn btn-outline-secondary btn-delete-slot"
                                data-slot-id="${slot.id}"
                                data-slot-info="${C.escapeHtml(slotInfo)}"
                                data-student-name="${C.escapeHtml(slot.student_name || '')}"
                                data-is-booked="${slot.status === 'booked'}"
                                title="Eliminar slot">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    function updateSlotCounts() {
        const free = currentSlots.filter(s => s.status === 'free').length;
        const booked = currentSlots.filter(s => s.status === 'booked').length;
        el('freeSlots').textContent = free;
        el('bookedSlots').textContent = booked;
        el('totalSlots').textContent = currentSlots.length;
    }

    function openAssignModal(slotId, slotInfo) {
        el('assignEventId').value = eventId;
        el('assignSlotId').value = slotId;
        el('assignStudentId').value = '';
        el('assignSlotInfo').textContent = slotInfo;
        el('assignStudentSearch').value = '';
        el('assignNotes').value = '';
        el('btnConfirmAssign').disabled = true;

        const filter = el('assignProgramFilter');
        if (filter) {
            if (currentEvent?.program_id) {
                filter.value = currentEvent.program_id;
                filter.disabled = true;
            } else {
                filter.value = '';
                filter.disabled = false;
            }
        }

        renderAssignStudentsList();
        modal('assignSlotModal')?.show();
    }

    function renderAssignStudentsList() {
        const list = el('assignStudentsList');
        if (!list) return;
        const search = (el('assignStudentSearch').value || '').toLowerCase().trim();
        const programFilter = el('assignProgramFilter').value;
        let filtered = eligibleStudents;
        if (programFilter) filtered = filtered.filter(s => String(s.program_id) === String(programFilter));
        if (search) {
            filtered = filtered.filter(s => {
                const blob = `${s.full_name || ''} ${s.email || ''} ${s.program_name || ''}`.toLowerCase();
                return blob.includes(search);
            });
        }
        if (filtered.length === 0) {
            const msg = eligibleStudents.length === 0
                ? 'No hay estudiantes elegibles registrados'
                : 'Sin coincidencias para los filtros actuales';
            list.innerHTML = `<div class="list-group-item text-center text-muted py-3">${msg}</div>`;
            return;
        }
        const selectedId = el('assignStudentId').value;
        list.innerHTML = filtered.map(s => `
            <button type="button" class="list-group-item list-group-item-action assign-student-item ${selectedId == s.id ? 'active' : ''}"
                data-student-id="${s.id}">
                <div class="d-flex align-items-center gap-2">
                    <img src="${s.avatar_url || '/static/assets/images/default.jpg'}"
                        class="rounded-circle" width="32" height="32" alt="">
                    <div class="flex-grow-1 text-start">
                        <div class="fw-semibold small">${C.escapeHtml(s.full_name)}</div>
                        <div class="text-muted small">${C.escapeHtml(s.email || '')} ${s.program_name ? '&middot; ' + C.escapeHtml(s.program_name) : ''}</div>
                    </div>
                </div>
            </button>
        `).join('');
    }

    async function loadEligibleStudents(programId) {
        try {
            if (programId) {
                const { data } = await C.apiRequest(`${C.API}/interviews/eligible-students/${programId}`);
                eligibleStudents = (data.eligible_students || []).map(s => ({ ...s, program_id: programId }));
            } else {
                const { data } = await C.apiRequest(`${C.API}/interviews/eligible-students`);
                const groups = data.programs || [];
                eligibleStudents = [];
                groups.forEach(g => {
                    (g.eligible_students || []).forEach(s => {
                        eligibleStudents.push({ ...s, program_id: g.program_id, program_name: g.program_name });
                    });
                });
            }
        } catch (err) {
            console.error('Error loading eligible students:', err);
            eligibleStudents = [];
        }
    }

    async function handleAssignSlot(e) {
        e.preventDefault();
        const payload = {
            event_id: el('assignEventId').value,
            slot_id: el('assignSlotId').value,
            applicant_id: parseInt(el('assignStudentId').value),
            notes: el('assignNotes').value
        };
        if (!payload.applicant_id) {
            C.flash('Selecciona un estudiante', 'warning');
            return;
        }
        try {
            await C.apiRequest(`${C.API}/appointments`, { method: 'POST', body: JSON.stringify(payload) });
            C.flash('Cita asignada correctamente', 'success');
            modal('assignSlotModal')?.hide();
            el('assignSlotForm').reset();
            await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error asignando cita: ${err.message}`, 'danger');
        }
    }

    function openCancelAppointmentModal(appointmentId, slotInfo, studentName) {
        el('cancelAppointmentId').value = appointmentId;
        el('cancelSlotInfo').textContent = slotInfo;
        el('cancelStudentName').textContent = studentName;
        el('cancelReason').value = '';
        modal('confirmCancelAppointmentModal')?.show();
    }

    async function handleCancelAppointment(e) {
        e.preventDefault();
        const appointmentId = el('cancelAppointmentId').value;
        const reason = el('cancelReason').value.trim();
        try {
            await C.apiRequest(`${C.API}/appointments/${appointmentId}/cancel`, {
                method: 'POST',
                body: JSON.stringify({ reason: reason || 'Cancelada por coordinador' })
            });
            C.flash('Cita cancelada correctamente', 'success');
            modal('confirmCancelAppointmentModal')?.hide();
            el('cancelAppointmentForm').reset();
            await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error cancelando cita: ${err.message}`, 'danger');
        }
    }

    function openDeleteSlotModal(slotId, slotInfo, studentName, isBooked) {
        el('deleteSlotId').value = slotId;
        el('deleteSlotInfo').textContent = slotInfo;
        const studentDiv = el('deleteSlotStudent');
        const warning = el('deleteSlotWarning');
        if (isBooked && studentName) {
            el('deleteSlotStudentName').textContent = studentName;
            studentDiv.classList.remove('d-none');
            warning.classList.remove('d-none');
        } else {
            studentDiv.classList.add('d-none');
            warning.classList.add('d-none');
        }
        modal('confirmDeleteSlotModal')?.show();
    }

    async function handleDeleteSlot() {
        const slotId = parseInt(el('deleteSlotId').value);
        if (!slotId) return;
        try {
            const { data } = await C.apiRequest(`${C.API}/events/slots/${slotId}`, { method: 'DELETE' });
            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger', title: 'Eliminar slot',
                    message: data.message + '\n\n¿Eliminar de todas formas?',
                    confirmLabel: 'Sí, eliminar'
                });
                if (!confirmed) return;
                await C.apiRequest(`${C.API}/events/slots/${slotId}?force=true`, { method: 'DELETE' });
            }
            C.flash('Slot eliminado correctamente', 'success');
            modal('confirmDeleteSlotModal')?.hide();
            await loadWindows();
            await loadSlots();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error eliminando slot: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // CHANGE REQUESTS
    // =================================================================
    async function loadChangeRequests() {
        const tbody = document.querySelector('#changeRequestsTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Cargando&hellip;</td></tr>';
        try {
            const { data } = await C.apiRequest(`${C.API}/appointments/change-requests/by-event/${eventId}`);
            currentChangeRequests = data.change_requests || [];
            renderChangeRequestsTable();
            const badge = el('changeRequestsBadge');
            if (badge) {
                if (currentChangeRequests.length > 0) {
                    badge.textContent = currentChangeRequests.length;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            }
            loaded.changeRequests = true;
        } catch (err) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-3">Error cargando solicitudes</td></tr>';
        }
    }

    function renderChangeRequestsTable() {
        const tbody = document.querySelector('#changeRequestsTable tbody');
        if (!tbody) return;
        if (currentChangeRequests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay solicitudes pendientes</td></tr>';
            return;
        }
        tbody.innerHTML = currentChangeRequests.map(req => {
            const start = new Date(req.current_slot.starts_at);
            const end = new Date(req.current_slot.ends_at);
            const slotStr = `${start.toLocaleDateString('es-MX')} ${start.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} - ${end.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}`;
            const createdDate = new Date(req.created_at).toLocaleDateString('es-MX');
            const reasonAttr = (req.reason || '').replace(/"/g, '&quot;');
            const sugAttr = (req.suggestions || '').replace(/"/g, '&quot;');
            return `
                <tr data-req-id="${req.id}">
                    <td>
                        <div class="fw-semibold small">${C.escapeHtml(req.student.full_name)}</div>
                        <div class="text-muted small">${C.escapeHtml(req.student.email)}</div>
                    </td>
                    <td><small>${slotStr}</small></td>
                    <td><small>${C.escapeHtml(req.reason || '—')}</small></td>
                    <td><small>${C.escapeHtml(req.suggestions || '—')}</small></td>
                    <td><small>${createdDate}</small></td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-success btn-accept-change"
                                data-req-id="${req.id}"
                                data-student-name="${C.escapeHtml(req.student.full_name)}"
                                data-current-slot="${C.escapeHtml(slotStr)}"
                                data-reason="${reasonAttr}"
                                data-suggestions="${sugAttr}"
                                title="Aprobar cambio">
                                <i class="bi bi-check"></i>
                            </button>
                            <button class="btn btn-outline-danger btn-reject-change"
                                data-req-id="${req.id}" title="Rechazar cambio">
                                <i class="bi bi-x"></i>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    async function openAcceptChangeModal(reqId, studentName, currentSlot, reason, suggestions) {
        el('acceptChangeReqId').value = reqId;
        el('acceptChangeStudentName').textContent = studentName;
        el('acceptChangeCurrentSlot').textContent = currentSlot;
        el('acceptChangeReason').textContent = reason || '—';
        el('acceptChangeSuggestions').textContent = suggestions || '—';

        if (!loaded.slots) await loadSlots();
        const slotSelect = el('acceptChangeNewSlot');
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
        modal('acceptChangeRequestModal')?.show();
    }

    async function acceptChangeRequest() {
        const reqId = el('acceptChangeReqId').value;
        const newSlotId = el('acceptChangeNewSlot').value;
        if (!newSlotId) {
            C.flash('Selecciona un nuevo horario', 'warning');
            return;
        }
        try {
            await C.apiRequest(`${C.API}/appointments/change-requests/${reqId}/decision`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'accepted', new_slot_id: parseInt(newSlotId) })
            });
            C.flash('Cambio de horario aprobado', 'success');
            modal('acceptChangeRequestModal')?.hide();
            await loadSlots();
            await loadChangeRequests();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error aprobando cambio: ${err.message}`, 'danger');
        }
    }

    async function rejectChangeRequest(reqId) {
        const ok = await siiapConfirm({
            type: 'danger', title: 'Rechazar solicitud',
            message: '¿Rechazar esta solicitud de cambio?',
            confirmLabel: 'Sí, rechazar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/appointments/change-requests/${reqId}/decision`, {
                method: 'PUT', body: JSON.stringify({ status: 'rejected' })
            });
            C.flash('Solicitud rechazada', 'success');
            await loadChangeRequests();
        } catch (err) {
            C.flash(`Error rechazando solicitud: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // REGISTRATIONS / ATTENDANCE
    // =================================================================
    async function loadRegistrations() {
        try {
            const { data } = await C.apiRequest(`${C.API}/attendance/event/${eventId}/registrations`);
            currentRegistrations = data.registrations || [];
            updateRegistrationStats();
            renderAttendanceTable();
            renderQuickRegistrations();
            loaded.registrations = true;
            loaded.attendance = true;
        } catch (err) {
            C.flash(`Error cargando registros: ${err.message}`, 'danger');
        }
    }

    function updateRegistrationStats() {
        const total = currentRegistrations.length;
        const attended = currentRegistrations.filter(r => r.status === 'attended').length;
        const noShow = currentRegistrations.filter(r => r.status === 'no_show').length;
        const registered = currentRegistrations.filter(r => r.status === 'registered').length;
        if (el('statsTotal')) el('statsTotal').textContent = total;
        if (el('statsAttended')) el('statsAttended').textContent = attended;
        if (el('statsNoShow')) el('statsNoShow').textContent = noShow;
        if (el('statsRegistered')) el('statsRegistered').textContent = registered;
        if (el('attendeesBadge')) el('attendeesBadge').textContent = total;
    }

    function renderAttendanceTable() {
        const tbody = document.querySelector('#registrationsTable tbody');
        if (!tbody) return;
        let filtered = currentRegistrations;
        if (attendanceFilter) filtered = filtered.filter(r => r.status === attendanceFilter);
        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Sin registros</td></tr>';
            return;
        }
        tbody.innerHTML = filtered.map(reg => {
            const registeredDate = C.formatDateTime(reg.registered_at);
            const attendedDate = reg.attended_at ? C.formatDateTime(reg.attended_at) : '—';
            let statusBadge = '';
            if (reg.status === 'registered') statusBadge = '<span class="badge bg-info">Pendiente</span>';
            else if (reg.status === 'attended') statusBadge = '<span class="badge bg-success">Asistió</span>';
            else if (reg.status === 'no_show') statusBadge = '<span class="badge bg-warning text-dark">No asistió</span>';
            return `
                <tr data-registration-id="${reg.id}" data-user-id="${reg.user_id}">
                    <td><div class="fw-semibold">${C.escapeHtml(reg.full_name)}</div></td>
                    <td>${C.escapeHtml(reg.email)}</td>
                    <td>${registeredDate}</td>
                    <td class="text-center">${statusBadge}</td>
                    <td>${attendedDate}</td>
                    <td class="text-end">
                        ${reg.status === 'registered' ? `
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-success btn-mark-attended"
                                    data-user-id="${reg.user_id}" title="Marcar asistencia">
                                    <i class="bi bi-check"></i>
                                </button>
                                <button class="btn btn-outline-warning btn-mark-no-show"
                                    data-user-id="${reg.user_id}" title="Marcar como ausente">
                                    <i class="bi bi-x"></i>
                                </button>
                            </div>
                        ` : `
                            <button class="btn btn-outline-secondary btn-sm btn-undo-attendance"
                                data-user-id="${reg.user_id}" title="Restablecer estado">
                                <i class="bi bi-arrow-counterclockwise"></i>
                            </button>
                        `}
                    </td>
                </tr>`;
        }).join('');
    }

    function renderQuickRegistrations() {
        const tbody = document.querySelector('#quickRegistrationsTable tbody');
        if (!tbody) return;
        if (currentRegistrations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Sin registros</td></tr>';
            return;
        }
        tbody.innerHTML = currentRegistrations.map(reg => {
            const originBadge = (reg.notes && reg.notes.includes('invitación'))
                ? '<span class="badge bg-info">Invitación</span>'
                : '<span class="badge bg-secondary">Auto-registro</span>';
            let statusBadge = '';
            if (reg.status === 'registered') statusBadge = '<span class="badge bg-info">Pendiente</span>';
            else if (reg.status === 'attended') statusBadge = '<span class="badge bg-success">Asistió</span>';
            else if (reg.status === 'no_show') statusBadge = '<span class="badge bg-warning text-dark">No asistió</span>';
            return `
                <tr>
                    <td>${C.escapeHtml(reg.full_name)}</td>
                    <td>${C.escapeHtml(reg.email)}</td>
                    <td>${originBadge}</td>
                    <td>${statusBadge}</td>
                </tr>`;
        }).join('');
    }

    async function markAttendance(userId, attended) {
        try {
            await C.apiRequest(`${C.API}/attendance/event/${eventId}/mark-attendance`, {
                method: 'POST', body: JSON.stringify({ user_id: userId, attended: attended })
            });
            C.flash(attended ? 'Asistencia registrada' : 'Marcado como ausente', 'success');
            await loadRegistrations();
        } catch (err) {
            C.flash(`Error al marcar asistencia: ${err.message}`, 'danger');
        }
    }

    async function undoAttendance(userId) {
        try {
            await C.apiRequest(`${C.API}/attendance/event/${eventId}/mark-attendance`, {
                method: 'POST', body: JSON.stringify({ user_id: userId, reset: true })
            });
            C.flash('Estado actualizado a registrado', 'success');
            await loadRegistrations();
        } catch (err) {
            C.flash(`Error al actualizar: ${err.message}`, 'danger');
        }
    }

    function exportAttendance() {
        if (currentRegistrations.length === 0) {
            C.flash('No hay registros para exportar', 'warning');
            return;
        }
        let csv = 'Estudiante,Email,Fecha Registro,Estado,Fecha Asistencia\n';
        currentRegistrations.forEach(reg => {
            const registeredDate = C.formatDateTime(reg.registered_at);
            const attendedDate = reg.attended_at ? C.formatDateTime(reg.attended_at) : '';
            csv += `"${reg.full_name}","${reg.email}","${registeredDate}","${reg.status}","${attendedDate}"\n`;
        });
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `asistencia_${currentEvent?.title || 'evento'}_${Date.now()}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        C.flash('Archivo exportado correctamente', 'success');
    }

    // =================================================================
    // INVITATIONS
    // =================================================================
    async function loadInvitations() {
        try {
            const { data } = await C.apiRequest(`${C.API}/invitations/event/${eventId}/list`);
            currentInvitations = data.invitations || [];
            renderInvitationsTable();
            if (el('invitationsBadge')) el('invitationsBadge').textContent = currentInvitations.length;
            loaded.invitations = true;
        } catch (err) {
            console.error('Error loading invitations:', err);
        }
    }

    function renderInvitationsTable() {
        const tbody = document.querySelector('#invitationsTable tbody');
        if (!tbody) return;
        if (currentInvitations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Sin invitaciones</td></tr>';
            return;
        }
        tbody.innerHTML = currentInvitations.map(inv => {
            const invitedDate = C.formatDateTime(inv.invited_at);
            let statusBadge = '';
            if (inv.status === 'pending') statusBadge = '<span class="badge bg-warning text-dark">Pendiente</span>';
            else if (inv.status === 'accepted') statusBadge = '<span class="badge bg-success">Aceptada</span>';
            else if (inv.status === 'rejected') statusBadge = '<span class="badge bg-danger">Rechazada</span>';
            return `
                <tr data-invitation-id="${inv.id}">
                    <td>${C.escapeHtml(inv.full_name)}</td>
                    <td>${C.escapeHtml(inv.inviter_name || '')}</td>
                    <td>${invitedDate}</td>
                    <td>${statusBadge}</td>
                    <td class="text-end">
                        ${inv.status === 'pending' ? `
                            <button class="btn btn-sm btn-outline-danger btn-cancel-invitation"
                                data-invitation-id="${inv.id}" title="Cancelar invitación">
                                <i class="bi bi-x"></i>
                            </button>
                        ` : ''}
                    </td>
                </tr>`;
        }).join('');
    }

    async function openInviteModal() {
        if (!currentEvent) return;
        el('inviteEventId').value = eventId;
        const select = el('inviteStudentSelect');
        select.innerHTML = '<option disabled>Cargando estudiantes...</option>';
        try {
            const registeredIds = currentRegistrations.map(r => r.user_id);
            const invitedIds = currentInvitations.filter(i => i.status === 'pending').map(i => i.user_id);
            const excludedIds = [...new Set([...registeredIds, ...invitedIds])];
            let url = `${C.API}/coordinator/students`;
            if (currentEvent.program_id) url += `?program_id=${currentEvent.program_id}`;
            const { data } = await C.apiRequest(url);
            const allStudents = data.students || [];
            const available = allStudents.filter(s => !excludedIds.includes(s.id));
            if (available.length === 0) {
                select.innerHTML = '<option disabled>No hay estudiantes disponibles</option>';
            } else {
                select.innerHTML = available.map(s =>
                    `<option value="${s.id}">${C.escapeHtml(s.full_name)} - ${C.escapeHtml(s.program_name || '')}</option>`
                ).join('');
            }
            modal('inviteStudentsModal')?.show();
        } catch (err) {
            C.flash(`Error cargando estudiantes: ${err.message}`, 'danger');
        }
    }

    async function sendInvitations() {
        const select = el('inviteStudentSelect');
        const message = el('inviteMessage').value;
        const selectedIds = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));
        if (selectedIds.length === 0) {
            C.flash('Selecciona al menos un estudiante', 'warning');
            return;
        }
        try {
            const { data } = await C.apiRequest(`${C.API}/invitations/event/${eventId}/invite`, {
                method: 'POST', body: JSON.stringify({ user_ids: selectedIds, notes: message })
            });
            C.flash(`${data.invited} invitaciones enviadas`, 'success');
            if (data.already_invited > 0) C.flash(`${data.already_invited} ya tenían invitación`, 'info');
            if (data.already_registered > 0) C.flash(`${data.already_registered} ya estaban registrados`, 'info');
            if (data.details?.wrong_program?.length > 0) {
                C.flash(`${data.details.wrong_program.length} no pertenecen al programa del evento`, 'warning');
            }
            modal('inviteStudentsModal')?.hide();
            el('inviteMessage').value = '';
            await loadInvitations();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error enviando invitaciones: ${err.message}`, 'danger');
        }
    }

    async function cancelInvitation(invitationId) {
        const ok = await siiapConfirm({
            type: 'warning', title: 'Cancelar invitación',
            message: '¿Cancelar esta invitación?', confirmLabel: 'Sí, cancelar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/invitations/${invitationId}`, { method: 'DELETE' });
            C.flash('Invitación cancelada', 'success');
            await loadInvitations();
            await refreshEventOnly();
        } catch (err) {
            C.flash(`Error cancelando invitación: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // EDIT EVENT INFO
    // =================================================================
    let academicPeriods = [];

    async function loadAcademicPeriods() {
        try {
            const { data } = await C.apiRequest(`${C.API}/academic-periods`);
            academicPeriods = data.data || data.items || [];
        } catch (err) {
            console.error('Error loading academic periods:', err);
        }
    }

    function populateEditFormSelects() {
        const programSel = el('editProgram');
        if (programSel) {
            programSel.innerHTML = '<option value="">Todos los programas</option>' +
                programs.map(p => `<option value="${p.id}">${C.escapeHtml(p.name)}</option>`).join('');
        }
        const periodSel = el('editAcademicPeriod');
        if (periodSel) {
            periodSel.innerHTML = '<option value="">Sin periodo (atemporal)</option>' +
                academicPeriods.map(p => `<option value="${p.id}">${C.escapeHtml(p.code || p.name || `Periodo ${p.id}`)}</option>`).join('');
        }
    }

    function populateEditFormFromEvent(ev) {
        if (!ev) return;
        el('editEventId').value = ev.id;
        el('editTitle').value = ev.title || '';
        el('editType').value = ev.type || 'interview';
        el('editDescription').value = ev.description || '';
        el('editProgram').value = ev.program_id || '';
        el('editAcademicPeriod').value = ev.academic_period_id || '';
        el('editVisibility').value = ev.visibility || 'public';
        el('editStatus').value = ev.status || 'published';
        el('editLocation').value = ev.location || '';

        const isMulti = ev.capacity_type !== 'single';
        el('editDatesRow').classList.toggle('d-none', !isMulti);
        el('editDatesRow2').classList.toggle('d-none', !isMulti);
        el('editMaxCapacityRow').classList.toggle('d-none', ev.capacity_type !== 'multiple');

        if (ev.event_date) {
            try { el('editEventDate').value = new Date(ev.event_date).toISOString().slice(0, 16); }
            catch (e) { el('editEventDate').value = ''; }
        } else {
            el('editEventDate').value = '';
        }
        if (ev.event_end_date) {
            try { el('editEventEndDate').value = new Date(ev.event_end_date).toISOString().slice(0, 16); }
            catch (e) { el('editEventEndDate').value = ''; }
        } else {
            el('editEventEndDate').value = '';
        }
        el('editMaxCapacity').value = ev.max_capacity || '';

        el('editRequiresRegistration').checked = !!ev.requires_registration;
        el('editAllowsAttendance').checked = !!ev.allows_attendance_tracking;
        el('editVisibleToStudents').checked = !!ev.visible_to_students;
        el('editRemindersEnabled').checked = !!ev.reminders_enabled;
    }

    function openEditEventInfoModal() {
        if (!currentEvent) return;
        populateEditFormSelects();
        populateEditFormFromEvent(currentEvent);
        modal('editEventInfoModal')?.show();
    }

    async function handleEditEvent(e) {
        e.preventDefault();
        const evId = el('editEventId').value;
        const isSingle = currentEvent?.capacity_type === 'single';

        const payload = {
            title: el('editTitle').value.trim(),
            type: el('editType').value,
            description: el('editDescription').value,
            program_id: el('editProgram').value ? parseInt(el('editProgram').value) : null,
            academic_period_id: el('editAcademicPeriod').value ? parseInt(el('editAcademicPeriod').value) : null,
            location: el('editLocation').value,
            visibility: el('editVisibility').value,
            status: el('editStatus').value,
            requires_registration: el('editRequiresRegistration').checked,
            allows_attendance_tracking: el('editAllowsAttendance').checked,
            visible_to_students: el('editVisibleToStudents').checked,
            reminders_enabled: el('editRemindersEnabled').checked
        };

        if (!isSingle) {
            payload.event_date = el('editEventDate').value || null;
            payload.event_end_date = el('editEventEndDate').value || null;
            if (currentEvent.capacity_type === 'multiple') {
                const cap = parseInt(el('editMaxCapacity').value);
                if (!cap || cap < 1) {
                    C.flash('Capacidad máxima inválida', 'warning');
                    return;
                }
                payload.max_capacity = cap;
            }
        }

        if (!payload.title) {
            C.flash('El título es requerido', 'warning');
            return;
        }

        try {
            await C.apiRequest(`${C.API}/events/${evId}`, {
                method: 'PUT', body: JSON.stringify(payload)
            });
            C.flash('Evento actualizado correctamente', 'success');
            modal('editEventInfoModal')?.hide();
            await loadEventDetails();
        } catch (err) {
            C.flash(`Error actualizando evento: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // CONTENT VISUAL (cover / gallery / hosts)
    // =================================================================
    let currentEventImages = { cover: null, gallery: [], eventId: null };
    let currentEventHosts = [];
    let contentLoaded = false;

    function buildEventImageUrl(imgEventId, image, kind) {
        if (!image || !image.path) return '';
        const filename = image.path.split('/').pop();
        return `/files/event/${imgEventId}/${kind}/${filename}`;
    }

    async function loadEventMedia() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}/images`);
            currentEventImages = { cover: data.cover || null, gallery: data.gallery || [], eventId: eventId };
            renderCoverPreview();
            renderGalleryGrid();
            renderSummaryCover();
        } catch (err) {
            console.error('Error loading event media:', err);
        }
    }

    async function loadEventHosts() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}/hosts`);
            currentEventHosts = data.hosts || [];
            renderHostsList();
            renderSummaryHosts();
        } catch (err) {
            console.error('Error loading hosts:', err);
        }
    }

    function renderCoverPreview() {
        const preview = el('coverPreview');
        const delBtn = el('coverDeleteBtn');
        const coverIdEl = el('coverImageId');
        if (!preview) return;
        if (currentEventImages.cover) {
            const url = buildEventImageUrl(currentEventImages.eventId, currentEventImages.cover, 'cover');
            preview.style.backgroundImage = `url('${url}')`;
            preview.classList.remove('empty');
            preview.innerHTML = '';
            delBtn?.classList.remove('d-none');
            if (coverIdEl) coverIdEl.value = currentEventImages.cover.id;
        } else {
            preview.style.backgroundImage = '';
            preview.classList.add('empty');
            preview.innerHTML = `
                <div class="text-center">
                    <i class="bi bi-image fs-1 d-block mb-2"></i>
                    <span class="text-muted small">Sin portada</span>
                </div>`;
            delBtn?.classList.add('d-none');
            if (coverIdEl) coverIdEl.value = '';
        }
    }

    function renderSummaryCover() {
        const preview = el('summaryCoverPreview');
        if (!preview) return;
        if (currentEventImages.cover) {
            const url = buildEventImageUrl(currentEventImages.eventId, currentEventImages.cover, 'cover');
            preview.style.backgroundImage = `url('${url}')`;
            preview.classList.remove('empty');
            preview.innerHTML = '';
        } else {
            preview.style.backgroundImage = '';
            preview.classList.add('empty');
            preview.innerHTML = `
                <div class="text-center">
                    <i class="bi bi-image fs-1 d-block mb-2"></i>
                    <span class="text-muted small">Sin portada</span>
                </div>`;
        }
    }

    function renderGalleryGrid() {
        const grid = el('galleryGrid');
        const empty = el('galleryEmpty');
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
                    <img src="${url}" alt="${C.escapeHtml(img.caption || '')}">
                    <button type="button" class="btn btn-danger btn-sm btn-remove btn-delete-gallery-image"
                        data-image-id="${img.id}" title="Eliminar imagen">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>`;
        }).join('');
    }

    function renderHostsList() {
        const list = el('hostsList');
        const empty = el('hostsEmpty');
        if (!list) return;
        if (currentEventHosts.length === 0) {
            list.innerHTML = '';
            if (empty) {
                list.appendChild(empty);
                empty.classList.remove('d-none');
            }
            return;
        }
        empty?.classList.add('d-none');
        list.innerHTML = currentEventHosts.map((host, idx) => {
            const isInternal = !!host.user_id;
            const typeBadge = isInternal
                ? '<span class="badge bg-info text-dark">Interno</span>'
                : '<span class="badge bg-secondary">Externo</span>';
            const avatarSrc = host.avatar_url || host.photo_url || '/static/assets/images/default.jpg';
            const name = host.full_name || host.name || host.external_name || 'Sin nombre';
            return `
                <div class="event-host-card" data-host-idx="${idx}">
                    <img src="${avatarSrc}" alt="Avatar" class="avatar">
                    <div class="host-info">
                        <div class="fw-semibold">${C.escapeHtml(name)}</div>
                        <div class="text-muted small">${C.escapeHtml(host.role_label || '')} ${typeBadge}</div>
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

    function renderSummaryHosts() {
        const node = el('summaryHosts');
        if (!node) return;
        if (currentEventHosts.length === 0) {
            node.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="bi bi-person-x fs-3 d-block mb-1"></i>
                    Sin ponentes registrados
                </div>`;
            return;
        }
        node.innerHTML = currentEventHosts.map(host => {
            const isInternal = !!host.user_id;
            const avatarSrc = host.avatar_url || host.photo_url || '/static/assets/images/default.jpg';
            const name = host.full_name || host.name || host.external_name || 'Sin nombre';
            const typeBadge = isInternal
                ? '<span class="badge bg-info text-dark">Interno</span>'
                : '<span class="badge bg-secondary">Externo</span>';
            return `
                <div class="d-flex align-items-center gap-2 mb-2">
                    <img src="${avatarSrc}" class="rounded-circle" width="36" height="36" style="object-fit:cover" alt="">
                    <div class="flex-grow-1 min-width-0">
                        <div class="fw-semibold small text-truncate">${C.escapeHtml(name)}</div>
                        <div class="text-muted small text-truncate">${C.escapeHtml(host.role_label || '')} ${typeBadge}</div>
                    </div>
                </div>`;
        }).join('');
    }

    function setupCoverDropzone() {
        const dropzone = el('coverDropzone');
        const selectBtn = el('coverSelectBtn');
        const fileInput = el('coverFileInput');
        const delBtn = el('coverDeleteBtn');
        if (!dropzone) return;

        selectBtn?.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
        dropzone.addEventListener('click', () => fileInput.click());
        fileInput?.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadCover(fileInput.files[0]);
        });
        dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
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
        if (file.size > 5 * 1024 * 1024) {
            C.flash('La imagen supera el límite de 5 MB', 'warning');
            return;
        }
        const fd = new FormData();
        fd.append('file', file);
        try {
            const res = await fetch(`${C.API}/events/${eventId}/cover`, {
                method: 'POST',
                headers: { 'X-CSRFToken': C.getCsrfToken() },
                credentials: 'same-origin',
                body: fd
            });
            const data = await res.json();
            if (!res.ok) {
                C.flash(data.error?.message || 'Error al subir la portada', 'danger');
                return;
            }
            C.flash('Portada actualizada', 'success');
            await loadEventMedia();
        } catch (err) {
            C.flash(`Error al subir portada: ${err.message}`, 'danger');
        }
    }

    async function deleteCover() {
        const imageId = el('coverImageId')?.value;
        if (!imageId) return;
        const ok = await siiapConfirm({
            type: 'danger', title: 'Eliminar portada',
            message: '¿Eliminar la portada de este evento?', confirmLabel: 'Sí, eliminar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/events/images/${imageId}`, { method: 'DELETE' });
            C.flash('Portada eliminada', 'success');
            currentEventImages.cover = null;
            renderCoverPreview();
            renderSummaryCover();
        } catch (err) {
            C.flash(`Error al eliminar portada: ${err.message}`, 'danger');
        }
    }

    function setupGalleryDropzone() {
        const dropzone = el('galleryDropzone');
        const selectBtn = el('gallerySelectBtn');
        const fileInput = el('galleryFileInput');
        if (!dropzone) return;

        selectBtn?.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
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

        el('galleryGrid')?.addEventListener('click', async (e) => {
            const btn = e.target.closest('.btn-delete-gallery-image');
            if (!btn) return;
            const imageId = parseInt(btn.dataset.imageId);
            const ok = await siiapConfirm({
                type: 'danger', title: 'Eliminar imagen',
                message: '¿Eliminar esta imagen de la galería?', confirmLabel: 'Sí, eliminar'
            });
            if (!ok) return;
            try {
                await C.apiRequest(`${C.API}/events/images/${imageId}`, { method: 'DELETE' });
                C.flash('Imagen eliminada', 'success');
                await loadEventMedia();
            } catch (err) {
                C.flash(`Error al eliminar imagen: ${err.message}`, 'danger');
            }
        });
    }

    async function uploadGalleryImages(files) {
        let uploaded = 0;
        for (const file of files) {
            if (file.size > 5 * 1024 * 1024) {
                C.flash(`"${file.name}" supera el límite de 5 MB y fue omitida`, 'warning');
                continue;
            }
            const fd = new FormData();
            fd.append('file', file);
            try {
                const res = await fetch(`${C.API}/events/${eventId}/images`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': C.getCsrfToken() },
                    credentials: 'same-origin',
                    body: fd
                });
                if (res.ok) uploaded++;
                else {
                    const d = await res.json();
                    C.flash(d.error?.message || `Error subiendo "${file.name}"`, 'danger');
                }
            } catch (err) {
                C.flash(`Error al subir "${file.name}": ${err.message}`, 'danger');
            }
        }
        if (uploaded > 0) {
            C.flash(`${uploaded} imagen(es) subida(s)`, 'success');
            await loadEventMedia();
        }
    }

    function setupHostsPanel() {
        el('addHostBtn')?.addEventListener('click', () => openHostEditor(-1));
        el('saveHostsBtn')?.addEventListener('click', saveHosts);
        el('hostsList')?.addEventListener('click', (e) => {
            const up = e.target.closest('.btn-move-host-up');
            const down = e.target.closest('.btn-move-host-down');
            const edit = e.target.closest('.btn-edit-host');
            const del = e.target.closest('.btn-remove-host');
            if (up)   { const i = parseInt(up.dataset.idx);   moveHost(i, i - 1); }
            if (down) { const i = parseInt(down.dataset.idx); moveHost(i, i + 1); }
            if (edit) openHostEditor(parseInt(edit.dataset.idx));
            if (del)  removeHost(parseInt(del.dataset.idx));
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

    function openHostEditor(idx) {
        const isNew = idx === -1;
        el('hostEditorModalTitle').textContent = isNew ? 'Agregar ponente' : 'Editar ponente';
        el('hostEditIndex').value = idx;

        el('hostTypeInternal').checked = true;
        el('hostUserSearch').value = '';
        el('hostUserId').value = '';
        el('hostSelectedUserCard').classList.add('d-none');
        el('hostExternalName').value = '';
        el('hostExternalBio').value = '';
        el('hostExternalPhoto').value = '';
        el('hostExternalPhotoPath').value = '';
        el('hostRoleLabel').value = '';
        el('hostInternalPanel').classList.remove('d-none');
        el('hostExternalPanel').classList.add('d-none');

        if (!isNew) {
            const host = currentEventHosts[idx];
            if (host.user_id) {
                el('hostTypeInternal').checked = true;
                el('hostUserId').value = host.user_id;
                showSelectedUser({
                    id: host.user_id,
                    full_name: host.full_name || host.name || '',
                    email: host.email || '',
                    role: host.role_display || host.role || '',
                    avatar_url: host.avatar_url || host.photo_url || ''
                });
            } else {
                el('hostTypeExternal').checked = true;
                el('hostInternalPanel').classList.add('d-none');
                el('hostExternalPanel').classList.remove('d-none');
                el('hostExternalName').value = host.external_name || host.name || '';
                el('hostExternalBio').value = host.external_bio || host.bio || '';
                el('hostExternalPhotoPath').value = host.external_photo_path || '';
            }
            el('hostRoleLabel').value = host.role_label || '';
        }
        modal('hostEditorModal')?.show();
    }

    function showSelectedUser(user) {
        el('hostUserId').value = user.id;
        el('hostSelectedName').textContent = user.full_name || '';
        el('hostSelectedEmail').textContent = user.email || '';
        el('hostSelectedRole').textContent = user.role || '';
        el('hostSelectedAvatar').src = user.avatar_url || '/static/assets/images/default.jpg';
        el('hostSelectedUserCard').classList.remove('d-none');
        el('hostUserSearch').value = '';
        el('hostUserDropdown').style.display = 'none';
    }

    function setupHostEditor() {
        document.querySelectorAll('input[name="hostTypeRadio"]').forEach(radio => {
            radio.addEventListener('change', () => {
                const isInternal = el('hostTypeInternal').checked;
                el('hostInternalPanel').classList.toggle('d-none', !isInternal);
                el('hostExternalPanel').classList.toggle('d-none', isInternal);
            });
        });

        let searchTimer = null;
        el('hostUserSearch')?.addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            const q = e.target.value.trim();
            if (q.length < 2) {
                el('hostUserDropdown').style.display = 'none';
                return;
            }
            searchTimer = setTimeout(() => searchUsers(q), 300);
        });

        el('hostClearUserBtn')?.addEventListener('click', () => {
            el('hostUserId').value = '';
            el('hostSelectedUserCard').classList.add('d-none');
        });

        el('hostEditorSaveBtn')?.addEventListener('click', saveHostFromModal);
    }

    async function searchUsers(query) {
        try {
            const { data } = await C.apiRequest(`${C.API}/admin/users/?search=${encodeURIComponent(query)}&per_page=10&active=true`);
            const users = data?.data?.users || data?.users || data?.items || [];
            renderUserDropdown(users);
        } catch (err) {
            console.error('Error searching users:', err);
            renderUserDropdown([]);
        }
    }

    function renderUserDropdown(users) {
        const dropdown = el('hostUserDropdown');
        if (!dropdown) return;
        if (users.length === 0) {
            dropdown.innerHTML = '<div class="list-group-item text-muted small">Sin resultados</div>';
            dropdown.style.display = 'block';
            return;
        }
        const fullNameOf = (u) => u.full_name || u.name ||
            [u.first_name, u.last_name, u.mother_last_name].filter(Boolean).join(' ');
        dropdown.innerHTML = users.map(u => {
            const fullName = fullNameOf(u);
            const role = u.role_name || u.role || '';
            return `
                <button type="button" class="list-group-item list-group-item-action py-2"
                    data-user-id="${u.id}"
                    data-full-name="${C.escapeHtml(fullName)}"
                    data-email="${C.escapeHtml(u.email || '')}"
                    data-role="${C.escapeHtml(role)}"
                    data-avatar="${C.escapeHtml(u.avatar_url || '')}">
                    <div class="d-flex align-items-center gap-2">
                        <img src="${u.avatar_url || '/static/assets/images/default.jpg'}" width="28" height="28"
                            class="rounded-circle" style="object-fit:cover">
                        <div>
                            <div class="fw-semibold small">${C.escapeHtml(fullName)}</div>
                            <div class="text-muted small">${C.escapeHtml(u.email || '')} &bull; ${C.escapeHtml(role)}</div>
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
        const isInternal = el('hostTypeInternal').checked;
        const roleLabel = el('hostRoleLabel').value.trim();
        const editIdx = parseInt(el('hostEditIndex').value);
        if (!roleLabel) {
            C.flash('El rol o etiqueta es requerido', 'warning');
            return;
        }
        let hostObj = { role_label: roleLabel };
        if (isInternal) {
            const userId = parseInt(el('hostUserId').value);
            if (!userId) {
                C.flash('Selecciona un usuario del sistema', 'warning');
                return;
            }
            hostObj.user_id = userId;
            hostObj.full_name = el('hostSelectedName').textContent;
            hostObj.email = el('hostSelectedEmail').textContent;
            hostObj.avatar_url = el('hostSelectedAvatar').src;
        } else {
            const externalName = el('hostExternalName').value.trim();
            const externalBio = el('hostExternalBio').value.trim();
            const photoFile = el('hostExternalPhoto').files[0];
            const existingPath = el('hostExternalPhotoPath').value;
            if (!externalName) {
                C.flash('El nombre del ponente externo es requerido', 'warning');
                return;
            }
            let photoPath = existingPath;
            if (photoFile) {
                try {
                    const fd = new FormData();
                    fd.append('file', photoFile);
                    const res = await fetch(`${C.API}/events/${eventId}/hosts/photo`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': C.getCsrfToken() },
                        credentials: 'same-origin',
                        body: fd
                    });
                    const d = await res.json();
                    if (res.ok && d.path) photoPath = d.path;
                } catch (err) {
                    C.flash('Error al subir foto del ponente', 'warning');
                }
            }
            hostObj.external_name = externalName;
            hostObj.external_bio = externalBio;
            hostObj.external_photo_path = photoPath || null;
        }
        if (editIdx === -1) currentEventHosts.push(hostObj);
        else currentEventHosts[editIdx] = hostObj;
        renderHostsList();
        modal('hostEditorModal')?.hide();
    }

    async function saveHosts() {
        try {
            await C.apiRequest(`${C.API}/events/${eventId}/hosts`, {
                method: 'PUT', body: JSON.stringify({ hosts: currentEventHosts })
            });
            C.flash('Ponentes guardados correctamente', 'success');
            renderSummaryHosts();
        } catch (err) {
            C.flash(`Error al guardar ponentes: ${err.message}`, 'danger');
        }
    }

    function openContentVisualModal() {
        modal('contentVisualModal')?.show();
        if (!contentLoaded) {
            loadEventMedia();
            loadEventHosts();
            contentLoaded = true;
        }
    }

    // =================================================================
    // HEADER ACTIONS (conclude/archive/unarchive/delete/toggle privacy)
    // =================================================================
    async function handleConcludeEvent() {
        const ok = await siiapConfirm({
            type: 'warning', title: 'Concluir evento',
            message: `¿Concluir "${currentEvent.title}"?\n\nSe marcará como completado, se cancelarán invitaciones pendientes y se eliminarán imágenes del servidor. No se puede revertir.`,
            confirmLabel: 'Sí, concluir'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/events/${eventId}/conclude`, { method: 'POST' });
            C.flash('Evento concluido correctamente', 'success');
            await loadEventDetails();
        } catch (err) {
            C.flash(`Error al concluir: ${err.message}`, 'danger');
        }
    }

    async function handleArchiveEvent() {
        const ok = await siiapConfirm({
            type: 'warning', title: 'Archivar evento',
            message: `¿Archivar "${currentEvent.title}"?\n\nSe ocultará del listado público, se notificará a registrados, se cancelarán invitaciones pendientes y se eliminarán imágenes.`,
            confirmLabel: 'Sí, archivar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/events/${eventId}/archive`, { method: 'POST' });
            C.flash('Evento archivado', 'success');
            await loadEventDetails();
        } catch (err) {
            C.flash(`Error al archivar: ${err.message}`, 'danger');
        }
    }

    async function handleUnarchiveEvent() {
        const ok = await siiapConfirm({
            type: 'info', title: 'Reactivar evento',
            message: '¿Volver a publicar este evento?', confirmLabel: 'Sí, reactivar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/events/${eventId}/unarchive`, {
                method: 'POST', body: JSON.stringify({ new_status: 'published' })
            });
            C.flash('Evento reactivado', 'success');
            await loadEventDetails();
        } catch (err) {
            C.flash(`Error al reactivar: ${err.message}`, 'danger');
        }
    }

    function openDeleteEventModal() {
        if (!currentEvent) return;
        el('deleteEventId').value = currentEvent.id;
        el('deleteEventTitle').textContent = currentEvent.title;
        const warning = el('deleteEventWarning');
        if (currentEvent.slots_booked > 0) {
            el('deleteEventAppointmentsCount').textContent = currentEvent.slots_booked;
            warning.classList.remove('d-none');
        } else {
            warning.classList.add('d-none');
        }
        modal('confirmDeleteEventModal')?.show();
    }

    async function handleDeleteEvent() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}`, { method: 'DELETE' });
            if (data.requires_force) {
                const confirmed = await siiapConfirm({
                    type: 'danger', title: 'Eliminar evento con citas',
                    message: data.message + '\n\n¿Eliminar de todas formas?',
                    confirmLabel: 'Sí, eliminar'
                });
                if (!confirmed) return;
                await C.apiRequest(`${C.API}/events/${eventId}?force=true`, { method: 'DELETE' });
            }
            C.flash('Evento eliminado correctamente', 'success');
            modal('confirmDeleteEventModal')?.hide();
            window.location.href = ctx.listUrl;
        } catch (err) {
            C.flash(`Error eliminando evento: ${err.message}`, 'danger');
        }
    }

    async function handleTogglePrivacy() {
        if (!currentEvent) return;
        const next = currentEvent.visibility === 'private' ? 'public' : 'private';
        const ok = await siiapConfirm({
            type: 'warning',
            title: next === 'private' ? 'Hacer privado' : 'Hacer público',
            message: next === 'private'
                ? 'Solo los invitados verán este evento. ¿Continuar?'
                : 'Todos los estudiantes verán este evento. ¿Continuar?',
            confirmLabel: 'Sí, cambiar'
        });
        if (!ok) return;
        try {
            await C.apiRequest(`${C.API}/events/${eventId}`, {
                method: 'PUT', body: JSON.stringify({ visibility: next })
            });
            C.flash('Visibilidad actualizada', 'success');
            await loadEventDetails();
        } catch (err) {
            C.flash(`Error actualizando visibilidad: ${err.message}`, 'danger');
        }
    }

    // =================================================================
    // EVENT LISTENERS
    // =================================================================
    function setupEventListeners() {
        // Forms
        el('addWindowForm')?.addEventListener('submit', handleAddWindow);
        el('assignSlotForm')?.addEventListener('submit', handleAssignSlot);
        el('cancelAppointmentForm')?.addEventListener('submit', handleCancelAppointment);

        // Header buttons
        el('btnTogglePrivacy')?.addEventListener('click', handleTogglePrivacy);
        el('btnConcludeEvent')?.addEventListener('click', handleConcludeEvent);
        el('btnArchiveEvent')?.addEventListener('click', handleArchiveEvent);
        el('btnUnarchiveEvent')?.addEventListener('click', handleUnarchiveEvent);
        el('btnDeleteEvent')?.addEventListener('click', openDeleteEventModal);

        el('btnEditInfo')?.addEventListener('click', openEditEventInfoModal);
        el('btnEditContent')?.addEventListener('click', openContentVisualModal);

        // Edit info form
        el('editEventForm')?.addEventListener('submit', handleEditEvent);
        el('btnRevertEdit')?.addEventListener('click', () => populateEditFormFromEvent(currentEvent));

        // Content visual setup (drop zones + hosts panel + editor)
        setupCoverDropzone();
        setupGalleryDropzone();
        setupHostsPanel();
        setupHostEditor();

        // Confirm buttons
        el('confirmDeleteEventBtn')?.addEventListener('click', handleDeleteEvent);
        el('confirmDeleteWindowBtn')?.addEventListener('click', handleDeleteWindow);
        el('confirmDeleteSlotBtn')?.addEventListener('click', handleDeleteSlot);
        el('confirmAcceptChangeBtn')?.addEventListener('click', acceptChangeRequest);

        // Windows tab actions
        el('btnGenerateSlotsFromWindows')?.addEventListener('click', handleGenerateAllSlots);
        document.querySelector('#windowsTable')?.addEventListener('click', (e) => {
            const gen = e.target.closest('.btn-generate-window-slots');
            const del = e.target.closest('.btn-delete-window');
            if (gen) handleGenerateWindowSlots(parseInt(gen.dataset.windowId));
            if (del) openDeleteWindowModal(
                parseInt(del.dataset.windowId), del.dataset.date, del.dataset.time,
                parseInt(del.dataset.slotsBooked || 0)
            );
        });

        // Slots tab actions
        el('btnGenerateSlots')?.addEventListener('click', handleGenerateAllSlots);
        el('btnRefreshSlots')?.addEventListener('click', () => { loadSlots(); loadWindows(); });
        document.querySelectorAll('input[name="slotFilter"]').forEach(input => {
            input.addEventListener('change', (e) => {
                slotsFilter = e.target.value;
                renderSlotsTable();
            });
        });
        document.querySelector('#slotsTable')?.addEventListener('click', (e) => {
            const assignBtn = e.target.closest('.btn-assign-slot');
            const cancelBtn = e.target.closest('.btn-cancel-appointment');
            const delBtn = e.target.closest('.btn-delete-slot');
            if (assignBtn) openAssignModal(assignBtn.dataset.slotId, assignBtn.dataset.slotInfo);
            if (cancelBtn) openCancelAppointmentModal(
                cancelBtn.dataset.appointmentId, cancelBtn.dataset.slotInfo, cancelBtn.dataset.studentName
            );
            if (delBtn) openDeleteSlotModal(
                parseInt(delBtn.dataset.slotId), delBtn.dataset.slotInfo,
                delBtn.dataset.studentName, delBtn.dataset.isBooked === 'true'
            );
        });

        // Assign modal interactions
        el('assignStudentSearch')?.addEventListener('input', renderAssignStudentsList);
        el('assignProgramFilter')?.addEventListener('change', renderAssignStudentsList);
        el('assignStudentsList')?.addEventListener('click', (e) => {
            const item = e.target.closest('.assign-student-item');
            if (!item) return;
            el('assignStudentId').value = item.dataset.studentId;
            el('btnConfirmAssign').disabled = false;
            document.querySelectorAll('.assign-student-item').forEach(node => {
                node.classList.toggle('active', node === item);
            });
        });

        // Change requests
        document.querySelector('#changeRequestsTable')?.addEventListener('click', (e) => {
            const accept = e.target.closest('.btn-accept-change');
            const reject = e.target.closest('.btn-reject-change');
            if (accept) openAcceptChangeModal(
                accept.dataset.reqId, accept.dataset.studentName, accept.dataset.currentSlot,
                accept.dataset.reason, accept.dataset.suggestions
            );
            if (reject) rejectChangeRequest(reject.dataset.reqId);
        });

        // Attendance
        document.querySelectorAll('input[name="attendanceFilter"]').forEach(input => {
            input.addEventListener('change', (e) => {
                attendanceFilter = e.target.value;
                renderAttendanceTable();
            });
        });
        el('btnExportAttendance')?.addEventListener('click', exportAttendance);
        document.querySelector('#registrationsTable')?.addEventListener('click', (e) => {
            const att = e.target.closest('.btn-mark-attended');
            const ns = e.target.closest('.btn-mark-no-show');
            const undo = e.target.closest('.btn-undo-attendance');
            if (att) markAttendance(parseInt(att.dataset.userId), true);
            if (ns) markAttendance(parseInt(ns.dataset.userId), false);
            if (undo) undoAttendance(parseInt(undo.dataset.userId));
        });

        // Invitations
        document.querySelector('[data-bs-target="#inviteStudentsModal"]')?.addEventListener('click', openInviteModal);
        el('btnSendInvitations')?.addEventListener('click', sendInvitations);
        document.querySelector('#invitationsTable')?.addEventListener('click', (e) => {
            const cancelBtn = e.target.closest('.btn-cancel-invitation');
            if (cancelBtn) cancelInvitation(parseInt(cancelBtn.dataset.invitationId));
        });

        // Tab lazy-load
        document.getElementById('tab-windows')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.windows) loadWindows();
        });
        document.getElementById('tab-slots')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.slots) loadSlots();
            if (!loaded.windows) loadWindows();
        });
        document.getElementById('tab-change-requests')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.changeRequests) loadChangeRequests();
        });
        document.getElementById('tab-attendees')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.registrations) loadRegistrations();
        });
        document.getElementById('tab-invitations')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.invitations) loadInvitations();
        });
        document.getElementById('tab-attendance')?.addEventListener('shown.bs.tab', () => {
            if (!loaded.attendance) loadRegistrations();
        });

        // Realtime via sockets
        let refreshTimer = null;
        const debouncedRefresh = () => {
            clearTimeout(refreshTimer);
            refreshTimer = setTimeout(() => {
                refreshEventOnly();
                if (loaded.slots) loadSlots();
                if (loaded.windows) loadWindows();
                if (loaded.changeRequests) loadChangeRequests();
                if (loaded.registrations) loadRegistrations();
                if (loaded.invitations) loadInvitations();
            }, 700);
        };
        window.addEventListener('siiap:appointment:changed', debouncedRefresh);
        window.addEventListener('siiap:appointment:change_requested', () => {
            if (loaded.changeRequests) loadChangeRequests();
            else refreshEventOnly();
        });
        window.addEventListener('siiap:event:changed', debouncedRefresh);
    }

    // =================================================================
    // INIT
    // =================================================================
    async function init() {
        if (!eventId) {
            C.flash('Evento inválido', 'error');
            return;
        }
        const ev = await loadEventDetails();
        if (!ev) return;
        await Promise.all([loadPrograms(), loadAcademicPeriods()]);
        if (ev.capacity_type === 'single') {
            await loadEligibleStudents(ev.program_id || null);
        }
        setupEventListeners();
        // Background load for summary (cover + hosts)
        loadEventMedia().catch(() => {});
        loadEventHosts().catch(() => {});
        contentLoaded = true;
    }

    document.addEventListener('DOMContentLoaded', init);
})();

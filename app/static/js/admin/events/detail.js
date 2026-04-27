/* Admin events detail page. Phase 1 skeleton. */
(() => {
    const C = window.EventsCommon;
    if (!C) {
        console.error('EventsCommon not loaded');
        return;
    }
    const ctx = window.EVENT_DETAIL || {};
    const eventId = ctx.eventId;

    let currentEvent = null;

    function el(id) { return document.getElementById(id); }

    function setBreadcrumb(title) {
        const node = el('breadcrumbEventTitle');
        if (node) node.textContent = title || 'Evento';
        document.title = `${title || 'Evento'} - SIIAP`;
    }

    function renderHeader(ev) {
        const iconNode = el('eventDetailIcon');
        if (iconNode) {
            iconNode.innerHTML = `<i class="bi ${C.TYPE_ICON[ev.type] || 'bi-calendar-event'}"></i>`;
        }

        const titleNode = el('eventDetailTitle');
        if (titleNode) titleNode.textContent = ev.title || '';

        const typeBadge = el('eventDetailTypeBadge');
        if (typeBadge) {
            const cls = C.TYPE_BADGE_CLASS[ev.type] || 'bg-secondary';
            typeBadge.className = `badge ${cls}`;
            typeBadge.textContent = C.TYPE_LABEL[ev.type] || ev.type;
        }

        const statusBadge = el('eventDetailStatusBadge');
        if (statusBadge) {
            const cls = C.STATUS_BADGE_CLASS[ev.status] || 'bg-secondary';
            statusBadge.className = `badge ${cls}`;
            statusBadge.textContent = C.STATUS_LABEL[ev.status] || ev.status;
            statusBadge.classList.remove('d-none');
        }

        const visBadge = el('eventDetailVisibilityBadge');
        if (visBadge) {
            visBadge.classList.toggle('d-none', ev.visibility !== 'private');
        }

        const subtitle = el('eventDetailSubtitle');
        if (subtitle) {
            const parts = [];
            if (ev.program_name) parts.push(`<i class="bi bi-mortarboard me-1"></i>${C.escapeHtml(ev.program_name)}`);
            else parts.push('<i class="bi bi-globe me-1"></i>Todos los programas');
            if (ev.academic_period_code) parts.push(`<i class="bi bi-calendar3 me-1"></i>${C.escapeHtml(ev.academic_period_code)}`);
            else parts.push('<i class="bi bi-infinity me-1"></i>Atemporal');
            parts.push(`<i class="bi bi-people-fill me-1"></i>${C.CAPACITY_LABEL[ev.capacity_type] || ev.capacity_type}`);
            subtitle.innerHTML = parts.join(' &middot; ');
        }

        // Header colored border by event type
        const header = el('eventDetailHeader');
        if (header) {
            header.className = `event-detail-header card mb-3 event-detail-border-${ev.type || 'other'}`;
        }

        // Toggle privacy label
        const togglePrivacyLabel = el('togglePrivacyLabel');
        if (togglePrivacyLabel) {
            togglePrivacyLabel.textContent = ev.visibility === 'private' ? 'Hacer público' : 'Hacer privado';
        }

        // Archive/Unarchive visibility
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
        document.querySelectorAll('#eventDetailTabs .single-only').forEach(li => {
            li.classList.toggle('d-none', !isSingle);
        });
        document.querySelectorAll('#eventDetailTabs .multi-only').forEach(li => {
            li.classList.toggle('d-none', isSingle);
        });
    }

    function renderSummary(ev) {
        const set = (id, val) => {
            const node = el(id);
            if (node) node.innerHTML = val || '&mdash;';
        };
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
        set('summaryFlags', flags.length ? flags.map(f => `<span class="badge bg-light text-dark border me-1">${f}</span>`).join('') : '<span class="text-muted">Sin opciones activadas</span>');

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

    async function loadEventDetails() {
        try {
            const { data } = await C.apiRequest(`${C.API}/events/${eventId}`);
            currentEvent = data;
            setBreadcrumb(data.title);
            renderHeader(data);
            renderStatChips(data);
            applyTabsByCapacity(data.capacity_type);
            renderSummary(data);
        } catch (err) {
            C.flash(err.message || 'No se pudo cargar el evento', 'error');
            setBreadcrumb('Evento no encontrado');
        }
    }

    function setupBackButtons() {
        // Action buttons placeholders (Phase 1: no-ops or temporary alerts).
        const todoMsg = (label) => () => C.flash(`${label}: pendiente de implementar (fase siguiente)`, 'info');
        ['btnEditInfo', 'btnEditContent', 'btnTogglePrivacy', 'btnConcludeEvent',
         'btnArchiveEvent', 'btnUnarchiveEvent', 'btnDeleteEvent'].forEach(id => {
            const node = el(id);
            if (node) node.addEventListener('click', todoMsg(node.textContent.trim()));
        });
    }

    async function init() {
        if (!eventId) {
            C.flash('Evento inválido', 'error');
            return;
        }
        await loadEventDetails();
        setupBackButtons();
    }

    document.addEventListener('DOMContentLoaded', init);
})();

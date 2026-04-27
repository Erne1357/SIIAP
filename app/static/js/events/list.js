// app/static/js/events/list.js
(() => {
    'use strict';

    const API = '/api/v1';

    // ── State ──────────────────────────────────────────────────────────
    let allEvents        = [];
    let myRegistrations  = [];
    let myInvitations    = [];
    // hostsCache: eventId -> Array<host>
    const hostsCache     = new Map();
    // coverCache: eventId -> url string or null
    const coverCache     = new Map();

    // ── DOM ────────────────────────────────────────────────────────────
    const eventsContainer          = document.getElementById('eventsContainer');
    const heroStats                = document.getElementById('heroStats');
    const pendingSection           = document.getElementById('pendingInvitationsSection');
    const pendingList              = document.getElementById('pendingInvitationsList');
    const pendingCount             = document.getElementById('pendingInvitationsCount');
    const btnScrollInvitations     = document.getElementById('btnScrollInvitations');
    const filterType               = document.getElementById('filterType');
    const filterCapacity           = document.getElementById('filterCapacity');
    const filterDate               = document.getElementById('filterDate');
    const filterRegistered         = document.getElementById('filterRegistered');
    const searchEvents             = document.getElementById('searchEvents');
    const btnShowMyRegistrations   = document.getElementById('btnShowMyRegistrations');
    const myRegistrationsBody      = document.getElementById('myRegistrationsBody');

    // ── Helpers ────────────────────────────────────────────────────────

    function flash(level, message) {
        window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    /**
     * Performs a fetch and returns parsed JSON.
     * Throws on non-ok responses.
     * @param {string} url
     * @param {RequestInit} options
     * @returns {Promise<object>}
     */
    async function apiRequest(url, options = {}) {
        const res = await fetch(url, {
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                ...(options.headers || {}),
            },
            ...options,
        });
        const data = await res.json();
        if (!res.ok || data.ok === false) {
            const msg = data.error?.message || data.error || 'Error en la solicitud';
            throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        }
        return data;
    }

    /**
     * Returns a Bootstrap Icons class name for the given event type.
     * @param {string} type
     * @returns {string}
     */
    function getEventIcon(type) {
        const map = {
            interview:    'bi-person-check',
            defense:      'bi-mortarboard',
            workshop:     'bi-tools',
            seminar:      'bi-book',
            conference:   'bi-broadcast',
            info_session: 'bi-info-circle',
        };
        return map[type] || 'bi-calendar-event';
    }

    /**
     * Returns a CSS gradient string for the event type fallback cover.
     * @param {string} type
     * @returns {string}
     */
    function getEventGradient(type) {
        const map = {
            interview:    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            defense:      'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            workshop:     'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            seminar:      'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
            conference:   'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
            info_session: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
        };
        return map[type] || 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)';
    }

    /**
     * Returns the Spanish label and badge color for event type.
     * @param {string} type
     * @returns {{ label: string, color: string }}
     */
    function eventTypeMeta(type) {
        const map = {
            interview:    { label: 'Entrevista',          color: 'primary'   },
            defense:      { label: 'Defensa',             color: 'danger'    },
            workshop:     { label: 'Taller',              color: 'success'   },
            seminar:      { label: 'Seminario',           color: 'info'      },
            conference:   { label: 'Conferencia',         color: 'warning'   },
            info_session: { label: 'Sesión Informativa',  color: 'secondary' },
        };
        return map[type] || { label: type, color: 'secondary' };
    }

    /**
     * Formats a date for compact display (e.g. "lun. 12 ene. · 10:00").
     * @param {string} iso
     * @returns {string}
     */
    function formatDateShort(iso) {
        if (!iso) return 'Fecha por definir';
        try {
            const d = new Date(iso);
            const datePart = d.toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short' });
            const timePart = d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
            return `${datePart} · ${timePart}`;
        } catch { return iso; }
    }

    // ── Data loading ───────────────────────────────────────────────────

    /**
     * Main data fetch: loads events, registrations, and invitations in parallel,
     * then renders all sections.
     */
    async function loadEvents() {
        try {
            const [eventsData, regsData, invsData] = await Promise.all([
                apiRequest(`${API}/events/public`),
                apiRequest(`${API}/attendance/my-registrations`).catch(() => ({ data: { registrations: [] } })),
                apiRequest(`${API}/invitations/my-invitations`).catch(() => ({ data: { invitations: [] } })),
            ]);

            allEvents       = (eventsData.data?.items ?? eventsData.items) || [];
            myRegistrations = regsData.data?.registrations || regsData.registrations || [];
            myInvitations   = invsData.data?.invitations   || invsData.invitations   || [];

            renderHero(allEvents, myInvitations, myRegistrations);
            renderPendingInvitations(myInvitations);
            applyFiltersAndRender();

        } catch (err) {
            console.error('[list.js] Error loading events:', err);
            eventsContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-circle me-2"></i>
                        Error al cargar los eventos: ${err.message}
                    </div>
                </div>`;
        }
    }

    // ── Hero ───────────────────────────────────────────────────────────

    /**
     * Renders the hero section with live counters.
     * @param {Array} events
     * @param {Array} invitations
     * @param {Array} registrations
     */
    function renderHero(events, invitations, registrations) {
        const now   = new Date();
        const in7d  = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        const upcoming = events.filter(e => {
            if (!e.event_date) return false;
            const d = new Date(e.event_date);
            return d >= now && d <= in7d;
        });
        const pendingInvs = invitations.filter(i => i.status === 'pending');
        const registeredCount = registrations.length;

        heroStats.innerHTML = `
            <span class="hero-stat">
                <i class="bi bi-calendar-week"></i>
                Próximos <strong>${upcoming.length}</strong>
            </span>
            <span class="hero-stat">
                <i class="bi bi-envelope"></i>
                Invitaciones <strong>${pendingInvs.length}</strong>
            </span>
            <span class="hero-stat">
                <i class="bi bi-check2-circle"></i>
                Inscrito en <strong>${registeredCount}</strong>
            </span>`;
    }

    // ── Invitaciones pendientes ────────────────────────────────────────

    /**
     * Renders the pinned pending invitations section.
     * Shows cards for pending and rejected invitations.
     * @param {Array} invitations
     */
    function renderPendingInvitations(invitations) {
        const visible = invitations.filter(i => i.status === 'pending' || i.status === 'rejected');

        if (!visible.length) {
            pendingSection.classList.add('d-none');
            btnScrollInvitations.style.display = 'none';
            return;
        }

        const pendingOnly = invitations.filter(i => i.status === 'pending');
        pendingSection.classList.remove('d-none');
        pendingCount.textContent = pendingOnly.length;
        btnScrollInvitations.style.display = '';

        pendingList.innerHTML = visible.map(inv => {
            const isPending  = inv.status === 'pending';
            const isRejected = inv.status === 'rejected';
            const isPrivate  = inv.visibility === 'private';

            const statusBadge = isPending
                ? `<span class="badge bg-warning text-dark">Pendiente</span>`
                : `<span class="badge bg-secondary">Rechazaste</span>`;

            const privateBadge = isPrivate
                ? `<span class="badge bg-dark ms-1"><i class="bi bi-lock-fill me-1"></i>Privado</span>`
                : '';

            const actionButtons = isPending
                ? `<button class="btn btn-success btn-sm btn-inv-accept" data-inv-id="${inv.id}">
                        <i class="bi bi-check-lg me-1"></i>Aceptar
                   </button>
                   <button class="btn btn-outline-danger btn-sm btn-inv-reject" data-inv-id="${inv.id}">
                        <i class="bi bi-x-lg me-1"></i>Rechazar
                   </button>`
                : `<button class="btn btn-outline-success btn-sm btn-inv-reconsider" data-inv-id="${inv.id}">
                        <i class="bi bi-arrow-counterclockwise me-1"></i>Reconsiderar
                   </button>`;

            return `
                <div class="col-md-6 col-lg-4">
                    <div class="invitation-highlight-card h-100 d-flex flex-column gap-2">
                        <div class="d-flex align-items-center gap-2 flex-wrap">
                            ${statusBadge}${privateBadge}
                        </div>
                        <p class="fw-semibold mb-0">${escapeHtml(inv.event_title || inv.title || 'Evento')}</p>
                        ${inv.event_date ? `<small class="text-muted"><i class="bi bi-calendar3 me-1"></i>${formatDateShort(inv.event_date)}</small>` : ''}
                        <div class="d-flex gap-2 flex-wrap mt-auto pt-1">
                            ${actionButtons}
                            <a href="/events/${inv.event_id}" class="btn btn-outline-secondary btn-sm">
                                <i class="bi bi-eye me-1"></i>Ver detalle
                            </a>
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    // ── Filtros ────────────────────────────────────────────────────────

    /**
     * Applies all active filters to allEvents and re-renders the grid.
     */
    function applyFiltersAndRender() {
        const typeVal       = filterType.value;
        const capacityVal   = filterCapacity.value;
        const dateVal       = filterDate.value;
        const onlyRegistered = filterRegistered.checked;
        const query         = searchEvents.value.toLowerCase().trim();

        const now  = new Date();
        const in7d = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        const endOfMonth   = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);

        const filtered = allEvents.filter(ev => {
            if (typeVal && ev.type !== typeVal) return false;

            if (capacityVal === 'available') {
                if (ev.capacity_type === 'multiple' && ev.current_registrations >= ev.max_capacity) return false;
            } else if (capacityVal === 'full') {
                if (!(ev.capacity_type === 'multiple' && ev.current_registrations >= ev.max_capacity)) return false;
            }

            if (dateVal === 'week') {
                if (!ev.event_date) return false;
                const d = new Date(ev.event_date);
                if (d < now || d > in7d) return false;
            } else if (dateVal === 'month') {
                if (!ev.event_date) return false;
                const d = new Date(ev.event_date);
                if (d < startOfMonth || d > endOfMonth) return false;
            }

            if (onlyRegistered) {
                const registered = myRegistrations.some(r => r.event_id === ev.id);
                if (!registered) return false;
            }

            if (query) {
                const haystack = `${ev.title || ''} ${ev.description || ''} ${ev.location || ''}`.toLowerCase();
                if (!haystack.includes(query)) return false;
            }

            return true;
        });

        renderEvents(filtered);
    }

    // ── Render principal ───────────────────────────────────────────────

    /**
     * Renders the main events grid.
     * @param {Array} events
     */
    function renderEvents(events) {
        if (!events.length) {
            eventsContainer.innerHTML = `
                <div class="col-12">
                    <div class="events-empty-state">
                        <i class="bi bi-calendar-x"></i>
                        <h5>No hay eventos disponibles</h5>
                        <p class="text-muted mb-0">No hay eventos que coincidan con los filtros actuales.<br>Vuelve pronto para ver nuevas convocatorias.</p>
                    </div>
                </div>`;
            return;
        }

        eventsContainer.innerHTML = events.map(ev => renderEventCard(ev)).join('');

        // Lanzar lazy-load de covers e inicializar hosts visibles
        initLazyCovers();
        initVisibleHosts();
    }

    /**
     * Renders a single event card HTML string.
     * @param {object} ev - Event data from the API.
     * @returns {string}
     */
    function renderEventCard(ev) {
        const typeMeta    = eventTypeMeta(ev.type);
        const isRegistered = myRegistrations.some(r => r.event_id === ev.id);
        const myReg        = myRegistrations.find(r => r.event_id === ev.id);
        const myInv        = myInvitations.find(i => i.event_id === ev.id);
        const hasInvitation = myInv && (myInv.status === 'pending' || myInv.status === 'accepted');
        const isFull        = ev.capacity_type === 'multiple' && ev.current_registrations >= ev.max_capacity;

        // Portada: usa cover_path del backend para construir URL servida por /files/event/<id>/cover/<filename>
        const gradient      = getEventGradient(ev.type);
        const icon          = getEventIcon(ev.type);
        const coverStyle    = `background: ${gradient};`;
        const coverUrl      = buildCoverUrl(ev.id, ev.cover_path);
        const coverHtml     = `
            <div class="event-card-cover fallback" style="${coverStyle}"
                 data-event-id="${ev.id}" data-cover-url="${coverUrl}">
                <i class="bi ${icon}"></i>
                ${hasInvitation ? '<span class="cover-invitation-ribbon">Te invitaron</span>' : ''}
            </div>`;

        // Badges
        const programBadge = ev.program_name
            ? `<span class="badge bg-primary">${escapeHtml(ev.program_name)}</span>`
            : `<span class="badge bg-secondary">Abierto a todos</span>`;
        const typeBadge   = `<span class="badge bg-${typeMeta.color}">${typeMeta.label}</span>`;
        const privateBadge = ev.visibility === 'private'
            ? `<span class="badge bg-dark"><i class="bi bi-lock-fill me-1"></i>Privado</span>`
            : '';
        const previewBadge = ev.is_preview
            ? `<span class="badge bg-info"><i class="bi bi-eye me-1"></i>Vista previa</span>`
            : '';
        const creatorBadge = ev.is_creator
            ? `<span class="badge bg-warning text-dark"><i class="bi bi-person-fill-gear me-1"></i>Tú lo creaste</span>`
            : '';

        // Meta (fecha, lugar)
        const dateLine = ev.event_date
            ? `<div class="card-meta"><i class="bi bi-calendar3"></i> ${formatDateShort(ev.event_date)}</div>`
            : '';
        const locationLine = `<div class="card-meta"><i class="bi bi-geo-alt"></i> ${escapeHtml(ev.location || 'Lugar por definir')}</div>`;

        // Chips de ponentes (placeholder — se llenará por lazy load)
        const hostsPlaceholder = `<div class="host-chips" id="host-chips-${ev.id}"></div>`;

        // Barra de cupo
        let capacityHtml = '';
        if (ev.capacity_type === 'multiple') {
            const pct       = ev.max_capacity > 0 ? Math.min(100, Math.round((ev.current_registrations / ev.max_capacity) * 100)) : 0;
            const fillClass = pct >= 90 ? 'fill-danger' : pct >= 60 ? 'fill-warn' : 'fill-ok';
            capacityHtml = `
                <div>
                    <div class="d-flex justify-content-between mb-1">
                        <small class="text-muted" style="font-size:0.78rem;">Inscritos</small>
                        <small class="fw-semibold" style="font-size:0.78rem;">${ev.current_registrations} / ${ev.max_capacity}</small>
                    </div>
                    <div class="card-capacity-bar">
                        <div class="card-capacity-bar-fill ${fillClass}" style="width:${pct}%;"></div>
                    </div>
                </div>`;
        }

        // Footer: estado + acciones
        const statusBadge = isRegistered
            ? `<span class="badge bg-success-subtle text-success border border-success-subtle">
                    <i class="bi bi-check-circle me-1"></i>Inscrito
               </span>`
            : isFull
            ? `<span class="badge bg-danger-subtle text-danger border border-danger-subtle">
                    <i class="bi bi-x-circle me-1"></i>Cupo lleno
               </span>`
            : '';

        let actionBtn = '';
        if (isRegistered && myReg && myReg.status !== 'attended') {
            actionBtn = `<button class="btn btn-outline-danger btn-sm btn-unregister" data-event-id="${ev.id}">
                            <i class="bi bi-person-dash"></i>
                         </button>`;
        } else if (!isRegistered && !isFull) {
            actionBtn = `<button class="btn btn-primary btn-sm btn-register" data-event-id="${ev.id}">
                            <i class="bi bi-person-plus me-1"></i>Registrarme
                         </button>`;
        }

        const hasInv   = hasInvitation;
        const cardClass = hasInv ? 'event-card has-invitation' : 'event-card';

        return `
            <div class="col-sm-6 col-lg-4">
                <div class="${cardClass}" data-event-id="${ev.id}">
                    ${coverHtml}
                    <div class="card-body">
                        <div class="d-flex flex-wrap gap-1 mb-1">
                            ${typeBadge}${programBadge}${privateBadge}${previewBadge}${creatorBadge}
                        </div>
                        <h5 class="card-title">${escapeHtml(ev.title)}</h5>
                        ${dateLine}
                        ${locationLine}
                        ${hostsPlaceholder}
                        <p class="card-description">${escapeHtml(ev.description || 'Sin descripción')}</p>
                        ${capacityHtml}
                    </div>
                    <div class="card-footer">
                        <div class="footer-status">${statusBadge}</div>
                        <div class="footer-actions">
                            <a href="/events/${ev.id}" class="btn btn-outline-primary btn-sm">
                                <i class="bi bi-eye me-1"></i>Ver detalle
                            </a>
                            ${actionBtn}
                        </div>
                    </div>
                </div>
            </div>`;
    }

    // ── Lazy load: covers ──────────────────────────────────────────────

    /**
     * Sets up an IntersectionObserver to lazy-fetch event covers when cards
     * enter the viewport. Uses coverCache to avoid duplicate requests.
     */
    function initLazyCovers() {
        // Cover URL ya viene pre-computada en data-cover-url desde el render.
        // Observer lazy aplica la imagen al entrar en viewport (evita descargar
        // todas las portadas al mismo tiempo).
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const el  = entry.target;
                const url = el.dataset.coverUrl;
                observer.unobserve(el);
                if (url) applyCover(el, url);
            });
        }, { rootMargin: '200px' });

        document.querySelectorAll('.event-card-cover[data-event-id]').forEach(el => {
            observer.observe(el);
        });
    }

    /**
     * Construye URL de portada servida por /files/event/<id>/cover/<filename>.
     * Si no hay cover_path retorna empty string para mantener fallback.
     */
    function buildCoverUrl(eventId, coverPath) {
        if (!coverPath) return '';
        const filename = coverPath.split('/').pop();
        return `/files/event/${eventId}/cover/${filename}`;
    }

    /**
     * Applies a background-image URL to a cover element, removing the fallback style.
     * @param {HTMLElement} el
     * @param {string} url
     */
    function applyCover(el, url) {
        el.style.background = `url('${url}') center/cover no-repeat`;
        el.classList.remove('fallback');
        const icon = el.querySelector('i');
        if (icon) icon.remove();
    }

    // ── Hosts: vienen pre-computados en hosts_summary del endpoint /public ──

    /**
     * Renderiza chips de ponentes para cada evento usando hosts_summary del payload.
     * Sin fetches adicionales (elimina N+1).
     */
    function initVisibleHosts() {
        const chipEls = document.querySelectorAll('[id^="host-chips-"]');
        chipEls.forEach(el => {
            const eventId = parseInt(el.id.replace('host-chips-', ''), 10);
            const ev = allEvents.find(e => e.id === eventId);
            if (!ev) return;
            const summary = ev.hosts_summary || [];
            renderHostChips(el, summary, ev.hosts_total || summary.length, ev.id);
        });
    }

    /**
     * Renders host avatar chips inside a container element.
     * Shows up to 3 avatars overlapped, with +N for the rest.
     * @param {HTMLElement} el - The .host-chips container.
     * @param {Array} hosts
     */
    function renderHostChips(el, hosts, totalHosts, eventId) {
        if (!hosts.length) return;

        const total = totalHosts || hosts.length;
        const shown = hosts.slice(0, 3);
        const extra = total - shown.length;
        const names = hosts.slice(0, 2).map(h => (h.name || '').split(' ')[0]).join(', ');
        const nameSuffix = total > 2 ? ` y ${total - 2} más` : '';

        const avatarsHtml = shown.map(h => {
            const initials = (h.name || '?').charAt(0).toUpperCase();
            const src = buildHostPhotoUrl(eventId, h);
            return src
                ? `<img class="h-avatar" src="${escapeHtml(src)}" alt="${escapeHtml(h.name || '')}" title="${escapeHtml(h.name || '')}">`
                : `<span class="h-avatar d-flex align-items-center justify-content-center" style="background:var(--bs-secondary); color:white; font-size:0.7rem; font-weight:600;">${escapeHtml(initials)}</span>`;
        }).join('');

        const extraHtml = extra > 0 ? `<span class="host-extra">+${extra}</span>` : '';

        el.innerHTML = `
            <div class="host-avatars">${avatarsHtml}${extraHtml}</div>
            <span class="host-names">con ${escapeHtml(names)}${escapeHtml(nameSuffix)}</span>`;
    }

    /**
     * Resuelve URL de foto de host. Backend ya devuelve `photo_url` listo.
     * Mantiene fallback a `avatar_url` o construcción manual si falta.
     */
    function buildHostPhotoUrl(eventId, host) {
        return host.photo_url || host.avatar_url || '';
    }

    // ── Mis Registros (modal) ──────────────────────────────────────────

    function renderMyRegistrationsModal() {
        if (!myRegistrations.length) {
            myRegistrationsBody.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-calendar-x fs-3 d-block mb-2"></i>
                    No tienes registros en ningún evento.
                </div>`;
            return;
        }

        myRegistrationsBody.innerHTML = `
            <div class="list-group list-group-flush">
                ${myRegistrations.map(r => {
                    const ev = allEvents.find(e => e.id === r.event_id) || {};
                    const statusMap = {
                        registered: { label: 'Registrado', color: 'info' },
                        attended:   { label: 'Asististe', color: 'success' },
                        no_show:    { label: 'No asististe', color: 'warning' },
                        cancelled:  { label: 'Cancelado', color: 'secondary' },
                    };
                    const s = statusMap[r.status] || { label: r.status, color: 'secondary' };
                    return `
                        <div class="list-group-item reg-item d-flex justify-content-between align-items-center">
                            <div>
                                <p class="mb-0 fw-semibold">${escapeHtml(ev.title || r.event_title || 'Evento')}</p>
                                ${ev.event_date ? `<small class="text-muted">${formatDateShort(ev.event_date)}</small>` : ''}
                            </div>
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge bg-${s.color}">${s.label}</span>
                                <a href="/events/${r.event_id}" class="btn btn-outline-primary btn-sm">Ver</a>
                            </div>
                        </div>`;
                }).join('')}
            </div>`;
    }

    // ── Handlers de invitaciones ───────────────────────────────────────

    /**
     * Sends an invitation response.
     * @param {number} invitationId
     * @param {boolean} accept
     */
    async function respondToInvitation(invitationId, accept) {
        try {
            await apiRequest(`${API}/invitations/${invitationId}/respond`, {
                method: 'POST',
                body: JSON.stringify({ accept }),
            });
            flash('success', accept ? 'Invitación aceptada.' : 'Invitación rechazada.');
            await loadEvents();
        } catch (err) {
            flash('danger', `Error al responder la invitación: ${err.message}`);
        }
    }

    /**
     * Reconsidera una invitación previamente rechazada (vuelve a aceptar).
     * @param {number} invitationId
     */
    async function handleReconsider(invitationId) {
        const ok = await siiapConfirm({
            type: 'info',
            title: 'Reconsiderar invitación',
            message: '¿Deseas aceptar esta invitación que habías rechazado?',
            confirmLabel: 'Sí, aceptar',
        });
        if (!ok) return;
        await respondToInvitation(invitationId, true);
    }

    // ── Handlers de registro ───────────────────────────────────────────

    /**
     * Registers the current user to an event.
     * @param {number} eventId
     */
    async function registerToEvent(eventId) {
        try {
            await apiRequest(`${API}/attendance/event/${eventId}/register`, {
                method: 'POST',
                body: JSON.stringify({ notes: '' }),
            });
            flash('success', 'Te has registrado exitosamente al evento.');
            await loadEvents();
        } catch (err) {
            flash('danger', `Error al registrarse: ${err.message}`);
        }
    }

    /**
     * Unregisters the current user from an event, with confirmation.
     * @param {number} eventId
     */
    async function unregisterFromEvent(eventId) {
        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Cancelar registro',
            message: '¿Estás seguro de que deseas cancelar tu registro en este evento?',
            confirmLabel: 'Sí, cancelar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/attendance/event/${eventId}/unregister`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            flash('success', 'Registro cancelado correctamente.');
            await loadEvents();
        } catch (err) {
            flash('danger', `Error al cancelar: ${err.message}`);
        }
    }

    // ── Escape helper ──────────────────────────────────────────────────

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = String(text ?? '');
        return div.innerHTML;
    }

    // ── Event delegation ───────────────────────────────────────────────

    eventsContainer?.addEventListener('click', e => {
        const btnReg = e.target.closest('.btn-register');
        if (btnReg) { registerToEvent(parseInt(btnReg.dataset.eventId, 10)); return; }

        const btnUnreg = e.target.closest('.btn-unregister');
        if (btnUnreg) { unregisterFromEvent(parseInt(btnUnreg.dataset.eventId, 10)); return; }
    });

    pendingList?.addEventListener('click', e => {
        const btnAccept = e.target.closest('.btn-inv-accept');
        if (btnAccept) { respondToInvitation(parseInt(btnAccept.dataset.invId, 10), true); return; }

        const btnReject = e.target.closest('.btn-inv-reject');
        if (btnReject) { respondToInvitation(parseInt(btnReject.dataset.invId, 10), false); return; }

        const btnReconsider = e.target.closest('.btn-inv-reconsider');
        if (btnReconsider) { handleReconsider(parseInt(btnReconsider.dataset.invId, 10)); return; }
    });

    // Filtros
    filterType?.addEventListener('change', applyFiltersAndRender);
    filterCapacity?.addEventListener('change', applyFiltersAndRender);
    filterDate?.addEventListener('change', applyFiltersAndRender);
    filterRegistered?.addEventListener('change', applyFiltersAndRender);
    searchEvents?.addEventListener('input', applyFiltersAndRender);

    // Botón mis registros
    btnShowMyRegistrations?.addEventListener('click', () => {
        renderMyRegistrationsModal();
        const modal = new bootstrap.Modal(document.getElementById('myRegistrationsModal'));
        modal.show();
    });

    // ── Mark events seen ──────────────────────────────────────────────

    /**
     * Notifica al servidor que el usuario visitó la lista de eventos.
     * Fire-and-forget: actualiza User.last_events_seen_at y limpia el flag
     * de sessionStorage para que promo-toast.js empiece limpio la próxima sesión.
     */
    async function markEventsSeen() {
        try {
            await fetch(`${API}/events/mark-seen`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });
            sessionStorage.removeItem('eventsPromoShown');
        } catch (err) {
            console.warn('[events/list] mark-seen fallo:', err);
        }
    }

    // ── Tiempo real ────────────────────────────────────────────────────

    let reloadTimer = null;
    function debouncedReload() {
        if (reloadTimer) clearTimeout(reloadTimer);
        reloadTimer = setTimeout(() => loadEvents(), 700);
    }

    window.addEventListener('siiap:event:changed', e => {
        const detail = e.detail || {};
        if (detail.action === 'created') flash('info', 'Nuevo evento disponible.');
        else if (detail.action === 'deleted') flash('warning', 'Un evento fue eliminado.');
        debouncedReload();
    });

    window.addEventListener('siiap:appointment:changed', () => {
        debouncedReload();
    });

    // ── Init ───────────────────────────────────────────────────────────

    markEventsSeen(); // fire-and-forget: marca visita y limpia flag de promo-toast
    loadEvents();
})();

// app/static/js/events/view.js
(() => {
    'use strict';

    const API = '/api/v1';
    const eventId = window.SIIAP_EVENT?.eventId;

    // ── State ────────────────────────────────────────────────
    let eventData       = null;
    let myReg           = null;
    let myAppt          = null;
    let windows         = [];
    let eventInvitation = null;

    // ── DOM references ───────────────────────────────────────
    const loadingState   = document.getElementById('loadingState');
    const errorState     = document.getElementById('errorState');
    const errorMessage   = document.getElementById('errorMessage');
    const eventContent   = document.getElementById('eventContent');
    const breadcrumbTitle = document.getElementById('breadcrumbTitle');

    // ── Helpers ──────────────────────────────────────────────

    function flash(level, message) {
        showFlash(level, message);
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function showLoading() {
        loadingState.classList.remove('d-none');
        errorState.classList.add('d-none');
        eventContent.classList.add('d-none');
    }

    function showError(msg) {
        loadingState.classList.add('d-none');
        errorMessage.textContent = msg || 'Error inesperado.';
        errorState.classList.remove('d-none');
        eventContent.classList.add('d-none');
    }

    function showContent() {
        loadingState.classList.add('d-none');
        errorState.classList.add('d-none');
        eventContent.classList.remove('d-none');
    }

    /**
     * Formats a date-time string for display in Spanish.
     * @param {string} iso - ISO date-time string.
     * @param {object} opts - Intl.DateTimeFormat options override.
     * @returns {string}
     */
    function formatDate(iso, opts = {}) {
        if (!iso) return '—';
        const defaults = {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        };
        try {
            return new Date(iso).toLocaleDateString('es-MX', { ...defaults, ...opts });
        } catch {
            return iso;
        }
    }

    /**
     * Formats only the time portion.
     * @param {string} iso
     * @returns {string}
     */
    function formatTime(iso) {
        if (!iso) return '—';
        try {
            return new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
        } catch {
            return iso;
        }
    }

    /**
     * Returns the Spanish label and badge color for event type.
     * @param {string} type
     * @returns {{ label: string, color: string }}
     */
    function eventTypeMeta(type) {
        const map = {
            interview:    { label: 'Entrevista',          color: 'primary' },
            defense:      { label: 'Defensa',             color: 'danger'  },
            workshop:     { label: 'Taller',              color: 'success' },
            seminar:      { label: 'Seminario',           color: 'info'    },
            conference:   { label: 'Conferencia',         color: 'warning' },
            info_session: { label: 'Sesión Informativa',  color: 'secondary' },
        };
        return map[type] || { label: type, color: 'secondary' };
    }

    /**
     * Returns the Spanish label and badge color for event status.
     * @param {string} status
     * @returns {{ label: string, color: string }}
     */
    function statusMeta(status) {
        const map = {
            draft:      { label: 'Borrador',    color: 'secondary' },
            published:  { label: 'Publicado',   color: 'success'   },
            cancelled:  { label: 'Cancelado',   color: 'danger'    },
            completed:  { label: 'Completado',  color: 'info'      },
        };
        return map[status] || { label: status, color: 'secondary' };
    }

    // ── API request helper ───────────────────────────────────

    /**
     * Performs a fetch request and returns parsed JSON data.
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

    // ── Data loading ─────────────────────────────────────────

    /**
     * Fetches event detail from the public API and triggers render.
     */
    async function loadEventDetail() {
        try {
            const data = await apiRequest(`${API}/events/public/${eventId}`);
            eventData       = data.event;
            myReg           = data.my_registration || null;
            myAppt          = data.my_appointment  || null;
            windows         = data.windows         || [];
            eventInvitation = data.my_invitation   || null;
            // Anotar eventData con status de invitación para render del hero banner
            if (eventData) {
                eventData.my_invitation_status = eventInvitation?.status || null;
            }
            renderAll();
            showContent();
        } catch (err) {
            console.error('[view.js] Error loading event:', err);
            showError(err.message);
        }
    }

    // ── Render: hero (full-bleed con imagen) ─────────────────

    /**
     * Renders the full-bleed hero section with cover image or gradient fallback,
     * badges, title, meta, and invitation status banner.
     */
    function renderHero() {
        const typeMeta = eventTypeMeta(eventData.type);
        const statMeta = statusMeta(eventData.status);
        const heroEl   = document.getElementById('eventHeroEl');

        // Background: cover image or gradient fallback
        if (heroEl) {
            // Try to fetch cover image
            loadHeroCover(heroEl, eventData);
        }

        // Badges
        const heroBadges = document.getElementById('heroBadges');
        const programBadge = eventData.program_name
            ? `<span class="badge bg-primary-subtle text-primary-emphasis event-type-badge">${escapeHtml(eventData.program_name)}</span>`
            : `<span class="badge bg-secondary-subtle text-secondary-emphasis event-type-badge">Abierto a todos</span>`;
        const privateBadge = eventData.visibility === 'private'
            ? `<span class="badge bg-warning text-dark event-type-badge"><i class="bi bi-lock-fill me-1"></i>Privado</span>`
            : '';
        heroBadges.innerHTML = `
            ${programBadge}
            <span class="badge bg-${typeMeta.color} event-type-badge">${typeMeta.label}</span>
            <span class="badge bg-${statMeta.color} event-type-badge">${statMeta.label}</span>
            ${privateBadge}
        `;

        // Title + breadcrumb
        document.getElementById('heroTitle').textContent = eventData.title;
        breadcrumbTitle.textContent = eventData.title;

        // Meta row
        const heroMeta = document.getElementById('heroMeta');
        const datePart = eventData.event_date
            ? `<span><i class="bi bi-calendar3 me-1"></i>${formatDate(eventData.event_date)}</span>`
            : '';
        const endPart = eventData.event_end_date
            ? `<span><i class="bi bi-calendar-check me-1"></i>${formatDate(eventData.event_end_date, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>`
            : '';
        const locationPart = `<span><i class="bi bi-geo-alt me-1"></i>${escapeHtml(eventData.location || 'Por definir')}</span>`;
        heroMeta.innerHTML = [datePart, endPart, locationPart].filter(Boolean).join('');

        // Invitation banner
        renderHeroBanner();
    }

    /**
     * Fetches and applies the cover image to the hero element.
     * Falls back to a gradient based on event type.
     * @param {HTMLElement} heroEl
     * @param {object} eventData
     */
    async function loadHeroCover(heroEl, ev) {
        const gradient = getEventGradient(ev.type);
        heroEl.style.background = gradient;
        try {
            const data = await apiRequest(`${API}/events/${ev.id}/images`);
            // Backend retorna { ok, cover: {...}|null, gallery: [...] }
            const cover = data.cover || data.data?.cover;
            if (cover?.path) {
                const filename = cover.path.split('/').pop();
                const url = `/files/event/${ev.id}/cover/${filename}`;
                heroEl.style.background = `url('${url}') center/cover no-repeat`;
            }
        } catch {
            // Keep gradient fallback
        }
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
     * Renders the invitation/RSVP status banner on top of the hero.
     */
    function renderHeroBanner() {
        const bannerEl = document.getElementById('heroBannerInvitation');
        if (!bannerEl) return;

        const invStatus = eventData.my_invitation_status;

        if (eventData.visibility === 'private' && invStatus === 'pending') {
            bannerEl.innerHTML = `
                <div class="hero-invitation-banner">
                    <i class="bi bi-lock-fill"></i>
                    Evento privado — te invitaron
                </div>`;
        } else if (invStatus === 'accepted') {
            bannerEl.innerHTML = `
                <div class="hero-invitation-banner accepted">
                    <i class="bi bi-check-circle-fill"></i>
                    Has aceptado la invitación
                </div>`;
        } else if (invStatus === 'rejected') {
            bannerEl.innerHTML = `
                <div class="hero-invitation-banner rejected">
                    <i class="bi bi-x-circle-fill"></i>
                    Rechazaste la invitación
                    <button class="btn btn-sm btn-outline-light ms-2 py-0 px-2" id="btnReconsider">
                        Reconsiderar
                    </button>
                </div>`;
            document.getElementById('btnReconsider')?.addEventListener('click', reconsiderInvitation);
        }
    }

    // ── Render: ponentes ─────────────────────────────────────

    /**
     * Fetches and renders the hosts section.
     * @param {number} evId
     */
    async function loadHosts(evId) {
        try {
            const data  = await apiRequest(`${API}/events/${evId}/hosts`);
            const hosts = data.hosts || data.data?.hosts || [];
            if (!hosts.length) return;

            const card = document.getElementById('hostsCard');
            const strip = document.getElementById('hostsStrip');
            if (!card || !strip) return;

            strip.innerHTML = hosts.map(h => {
                const initials = (h.name || '?').charAt(0).toUpperCase();
                const photoUrl = resolveHostPhotoUrl(evId, h);
                const photoHtml = photoUrl
                    ? `<img class="host-photo" src="${escapeHtml(photoUrl)}" alt="${escapeHtml(h.name || '')}">`
                    : `<div class="host-photo-placeholder">${escapeHtml(initials)}</div>`;
                const hostPayload = { ...h, photo_url: photoUrl };
                return `
                    <div class="host-card" data-host-json="${escapeHtml(JSON.stringify(hostPayload))}">
                        ${photoHtml}
                        <div class="host-name">${escapeHtml(h.name || 'Ponente')}</div>
                        <div class="host-role">${escapeHtml(h.role_label || '')}</div>
                    </div>`;
            }).join('');

            card.classList.remove('d-none');

            // Click → open bio modal
            strip.addEventListener('click', e => {
                const card = e.target.closest('.host-card');
                if (!card) return;
                try {
                    const host = JSON.parse(card.dataset.hostJson || '{}');
                    openHostModal(host);
                } catch { /* ignore */ }
            });
        } catch (err) {
            console.warn('[view.js] Could not load hosts:', err.message);
        }
    }

    /**
     * Opens the host bio modal.
     * @param {object} host
     */
    function openHostModal(host) {
        const nameEl = document.getElementById('hostBioName');
        const roleEl = document.getElementById('hostBioRole');
        const bioEl  = document.getElementById('hostBioBio');
        const photoWrap = document.getElementById('hostBioPhotoWrap');

        if (nameEl) nameEl.textContent = host.name || 'Ponente';
        if (roleEl) roleEl.textContent = host.role_label || '';
        if (bioEl)  bioEl.textContent  = host.bio || 'Sin semblanza disponible.';

        if (photoWrap) {
            const src = host.photo_url || host.avatar_url || '';
            photoWrap.innerHTML = src
                ? `<img class="host-bio-photo" src="${escapeHtml(src)}" alt="${escapeHtml(host.name || '')}">`
                : `<div class="host-bio-photo-placeholder">${escapeHtml((host.name || '?').charAt(0).toUpperCase())}</div>`;
        }

        const modal = new bootstrap.Modal(document.getElementById('hostBioModal'));
        modal.show();
    }

    // ── Render: galería ──────────────────────────────────────

    /**
     * Fetches and renders the public gallery section.
     * @param {number} evId
     */
    async function loadGallery(evId) {
        try {
            const data = await apiRequest(`${API}/events/${evId}/images`);
            // Backend returns { ok, cover, gallery: [...] }
            const gallery = data.gallery || data.data?.gallery || [];
            if (!gallery.length) return;

            const card = document.getElementById('galleryCard');
            const grid = document.getElementById('publicGallery');
            if (!card || !grid) return;

            grid.innerHTML = gallery.map(img => {
                const filename = (img.path || '').split('/').pop();
                const url = `/files/event/${evId}/gallery/${filename}`;
                return `
                <div class="event-public-gallery-item" data-img-url="${escapeHtml(url)}">
                    <img src="${escapeHtml(url)}" alt="${escapeHtml(img.caption || 'Imagen del evento')}" loading="lazy">
                </div>`;
            }).join('');

            card.classList.remove('d-none');

            grid.addEventListener('click', e => {
                const item = e.target.closest('.event-public-gallery-item');
                if (!item) return;
                openImageLightbox(item.dataset.imgUrl);
            });
        } catch (err) {
            console.warn('[view.js] Could not load gallery:', err.message);
        }
    }

    /**
     * Opens the native <dialog> lightbox with the given image URL.
     * @param {string} url
     */
    function openImageLightbox(url) {
        const dialog = document.getElementById('eventLightbox');
        const img    = document.getElementById('lightboxImg');
        if (!dialog || !img) return;
        img.src = url;
        dialog.showModal();
    }

    // ── Render: compartir URL ────────────────────────────────

    /**
     * Populates the share URL input with the current page URL.
     */
    function renderShareUrl() {
        const input = document.getElementById('shareUrlInput');
        if (input) input.value = window.location.href;
    }

    // ── Escape helper ────────────────────────────────────────

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = String(text ?? '');
        return div.innerHTML;
    }

    // ── Invitación: reconsiderar ─────────────────────────────

    /**
     * Reconsidera la invitación rechazada (vuelve a aceptar).
     */
    async function reconsiderInvitation() {
        // Backend retorna payload["my_invitation"] = { id, status, ... } en /public/<id>.
        // state.eventData guarda payload.event (sin my_invitation), así que debemos
        // buscarlo en el payload completo. Lo guardamos en eventInvitation al cargar.
        const inv = eventInvitation?.id;
        if (!inv) {
            flash('warning', 'No se encontró la invitación para reconsiderar.');
            return;
        }
        try {
            await apiRequest(`${API}/invitations/${inv}/respond`, {
                method: 'POST',
                body: JSON.stringify({ accept: true }),
            });
            flash('success', 'Has aceptado la invitación.');
            await loadEventDetail();
        } catch (err) {
            flash('danger', `Error al reconsiderar: ${err.message}`);
        }
    }

    /**
     * Construye URL de foto de host.
     * Interno: `/files/avatar/<user_id>/<filename>` requiere user_id — si el backend
     * pasa `photo_path` como "42/avatar.webp" intentamos usarlo.
     * Externo: `/files/event/<event_id>/hosts/<filename>`.
     */
    function resolveHostPhotoUrl(eventId, host) {
        return host.photo_url || host.avatar_url || '';
    }

    // ── Render: details list ─────────────────────────────────

    function renderDetailsList() {
        const list = document.getElementById('eventDetailsList');

        const capacityLabel = (() => {
            if (eventData.capacity_type === 'unlimited') return 'Sin límite';
            if (eventData.capacity_type === 'multiple')
                return `${eventData.current_registrations} / ${eventData.max_capacity} inscritos`;
            return '1 a 1 (entrevista)';
        })();

        const items = [
            { label: 'Tipo',         value: eventTypeMeta(eventData.type).label },
            { label: 'Estado',       value: statusMeta(eventData.status).label },
            { label: 'Capacidad',    value: capacityLabel },
            { label: 'Inicio',       value: formatDate(eventData.event_date) },
            { label: 'Fin',          value: eventData.event_end_date ? formatDate(eventData.event_end_date) : '—' },
            { label: 'Ubicación',    value: eventData.location || 'Por definir' },
            { label: 'Programa',     value: eventData.program_name || 'Todos' },
        ];

        list.innerHTML = items.map(i => `
            <li class="list-group-item">
                <span class="detail-label">${i.label}</span>
                <span class="detail-value">${i.value}</span>
            </li>`).join('');
    }

    // ── Render: description ───────────────────────────────────

    function renderDescription() {
        const desc = document.getElementById('eventDescription');
        desc.textContent = eventData.description || 'Sin descripción disponible.';
    }

    // ── Render: action block ─────────────────────────────────

    function renderActionBlock() {
        const block = document.getElementById('actionBlock');
        const quickBody = document.getElementById('quickActionsBody');
        const timelineBlock = document.getElementById('timelineBlock');

        if (eventData.capacity_type === 'single') {
            renderSingleBlock(block, quickBody, timelineBlock);
        } else {
            renderMultiBlock(block, quickBody);
        }
    }

    /**
     * Renders the appointment card and timeline for single-slot events.
     * @param {HTMLElement} block
     * @param {HTMLElement} quickBody
     * @param {HTMLElement} timelineBlock
     */
    function renderSingleBlock(block, quickBody, timelineBlock) {
        // Main action block: appointment card or informational notice
        if (myAppt) {
            block.innerHTML = `
                <div class="appointment-card p-4 mb-4 shadow-sm">
                    <div class="d-flex flex-column flex-sm-row justify-content-between align-items-start gap-3">
                        <div>
                            <p class="text-muted small mb-1">
                                <i class="bi bi-calendar-heart-fill me-1"></i>Tu Cita
                            </p>
                            <div class="appointment-time">${formatTime(myAppt.starts_at)}</div>
                            <div class="appointment-date">${formatDate(myAppt.starts_at)}</div>
                            <div class="appointment-date mt-1">
                                <i class="bi bi-clock me-1"></i>
                                Hasta las ${formatTime(myAppt.ends_at)}
                            </div>
                        </div>
                        <div class="d-flex flex-column gap-2">
                            <button class="btn btn-outline-warning btn-sm" id="btnChangeRequest">
                                <i class="bi bi-arrow-left-right me-1"></i>Solicitar Cambio
                            </button>
                            <button class="btn btn-outline-danger btn-sm" id="btnCancelAppt">
                                <i class="bi bi-x-lg me-1"></i>Cancelar Cita
                            </button>
                        </div>
                    </div>
                </div>`;

            // Wire up buttons
            document.getElementById('btnChangeRequest')?.addEventListener('click', openChangeRequestModal);
            document.getElementById('btnCancelAppt')?.addEventListener('click', cancelAppointment);
        } else {
            block.innerHTML = `
                <div class="info-notice d-flex align-items-center gap-3 mb-4">
                    <i class="bi bi-info-circle-fill notice-icon"></i>
                    <div>
                        <strong>Sin cita asignada aún</strong>
                        <p class="mb-0 mt-1 text-muted small">
                            El coordinador te asignará un horario. Recibirás una notificación cuando esté lista.
                        </p>
                    </div>
                </div>`;
        }

        // Quick actions for single — no register button, just contextual info
        quickBody.innerHTML = `
            <p class="text-muted small mb-0">
                <i class="bi bi-shield-fill-check me-1"></i>
                Las citas son asignadas por el coordinador del programa.
            </p>`;

        // Show the timeline
        timelineBlock.classList.remove('d-none');
        renderTimeline();
    }

    /**
     * Renders capacity info and registration controls for multiple/unlimited events.
     * @param {HTMLElement} block
     * @param {HTMLElement} quickBody
     */
    function renderMultiBlock(block, quickBody) {
        const isFull = eventData.capacity_type === 'multiple' &&
            eventData.current_registrations >= eventData.max_capacity;
        const isUnlimited = eventData.capacity_type === 'unlimited';

        // Capacity bar section
        let capacityHtml = '';
        if (!isUnlimited) {
            const pct = Math.min(
                100,
                Math.round((eventData.current_registrations / eventData.max_capacity) * 100)
            );
            const fillClass = pct >= 90 ? 'fill-danger' : pct >= 60 ? 'fill-warn' : 'fill-ok';
            capacityHtml = `
                <div class="mb-3">
                    <div class="d-flex justify-content-between mb-1">
                        <small class="text-muted">Cupo</small>
                        <small class="fw-semibold">${eventData.current_registrations} / ${eventData.max_capacity}</small>
                    </div>
                    <div class="capacity-bar">
                        <div class="capacity-bar-fill ${fillClass}" style="width:${pct}%"></div>
                    </div>
                </div>`;
        } else {
            capacityHtml = `
                <div class="mb-3">
                    <span class="badge bg-success">
                        <i class="bi bi-infinity me-1"></i>Sin límite de cupos
                    </span>
                    <span class="ms-2 text-muted small">${eventData.current_registrations} inscrito(s)</span>
                </div>`;
        }

        block.innerHTML = `
            <div class="card border-0 shadow-sm mb-4">
                <div class="card-header bg-white border-bottom">
                    <h5 class="mb-0">
                        <i class="bi bi-people-fill me-2 text-primary"></i>Inscripción
                    </h5>
                </div>
                <div class="card-body">
                    ${capacityHtml}
                    <div id="registrationStatus"></div>
                </div>
            </div>`;

        const regStatus = document.getElementById('registrationStatus');

        if (myReg) {
            const attended = myReg.status === 'attended';
            regStatus.innerHTML = `
                <div class="alert alert-success d-flex align-items-center gap-2 mb-3">
                    <i class="bi bi-check-circle-fill fs-5"></i>
                    <div>
                        <strong>Estás inscrito</strong>
                        <div class="small text-muted mt-1">
                            Registrado el ${formatDate(myReg.registered_at, { year: 'numeric', month: 'long', day: 'numeric' })}
                        </div>
                        ${attended ? '<span class="badge bg-success mt-1">Asististe</span>' : ''}
                    </div>
                </div>
                ${!attended ? `
                    <button class="btn btn-outline-danger w-100" id="btnUnregister">
                        <i class="bi bi-person-dash me-1"></i>Cancelar Registro
                    </button>` : ''}`;

            document.getElementById('btnUnregister')?.addEventListener('click', unregisterFromEvent);
        } else if (isFull) {
            regStatus.innerHTML = `
                <div class="alert alert-warning d-flex align-items-center gap-2">
                    <i class="bi bi-exclamation-triangle-fill fs-5"></i>
                    <div><strong>Cupo lleno</strong><br>
                    <span class="small">No hay lugares disponibles en este momento.</span></div>
                </div>`;
        } else {
            regStatus.innerHTML = `
                <button class="btn btn-primary w-100" id="btnRegister">
                    <i class="bi bi-person-plus-fill me-1"></i>Registrarme al evento
                </button>`;
            document.getElementById('btnRegister')?.addEventListener('click', registerToEvent);
        }

        // Quick actions column
        quickBody.innerHTML = `
            <p class="text-muted small mb-0">
                <i class="bi bi-calendar3 me-1"></i>
                ${isUnlimited
                    ? 'Sin restricción de cupo.'
                    : isFull
                    ? 'Cupo agotado.'
                    : `${eventData.max_capacity - eventData.current_registrations} lugar(es) disponible(s).`}
            </p>`;
    }

    // ── Render: timeline (single capacity) ──────────────────

    function renderTimeline() {
        const container = document.getElementById('timelineContent');
        if (!windows.length) {
            container.innerHTML = `
                <div class="p-4 text-center text-muted">
                    <i class="bi bi-calendar-x fs-1 mb-2"></i>
                    <p class="mb-0">No hay ventanas de horario configuradas aún.</p>
                </div>`;
            return;
        }

        container.innerHTML = windows.map(win => {
            const slots = win.slots || [];
            const slotsHtml = slots.length
                ? slots.map(slot => {
                    const isMine = myAppt && myAppt.slot_id === slot.id;
                    const cls    = isMine ? 'slot-mine' : slot.status === 'free' ? 'slot-free' : 'slot-booked';
                    const icon   = isMine ? 'bi-star-fill' : slot.status === 'free' ? 'bi-circle-fill' : 'bi-record-circle';
                    const label  = isMine ? 'Mi cita' : slot.status === 'free' ? 'Libre' : 'Ocupado';
                    return `
                        <span class="slot-pill ${cls}" title="${formatTime(slot.starts_at)} – ${formatTime(slot.ends_at)}">
                            <i class="bi ${icon}"></i>
                            ${formatTime(slot.starts_at)}
                            <span class="slot-label-sm">${label}</span>
                        </span>`;
                }).join('')
                : `<span class="text-muted small">Sin slots en esta ventana</span>`;

            const windowDate = win.date
                ? new Date(win.date).toLocaleDateString('es-MX', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
                : '—';

            return `
                <div class="timeline-window">
                    <div class="timeline-window-header">
                        <i class="bi bi-calendar-day me-2 text-primary"></i>${windowDate}
                        <span class="text-muted fw-normal ms-2 small">${win.start_time || ''} – ${win.end_time || ''}</span>
                    </div>
                    <div class="slots-grid">${slotsHtml}</div>
                </div>`;
        }).join('');
    }

    // ── Render: orchestrator ──────────────────────────────────

    function renderAll() {
        renderHero();
        renderDescription();
        renderDetailsList();
        renderActionBlock();
        renderShareUrl();
        loadHosts(eventId);
        loadGallery(eventId);
    }

    // ── Actions ───────────────────────────────────────────────

    async function registerToEvent() {
        try {
            await apiRequest(`${API}/attendance/event/${eventId}/register`, {
                method: 'POST',
                body: JSON.stringify({ notes: '' }),
            });
            flash('success', 'Te has inscrito exitosamente al evento.');
            await loadEventDetail();
        } catch (err) {
            flash('danger', `Error al inscribirse: ${err.message}`);
        }
    }

    async function unregisterFromEvent() {
        const ok = await siiapConfirm({
            type: 'warning',
            title: 'Cancelar inscripción',
            message: '¿Estás seguro de que deseas cancelar tu inscripción a este evento?',
            confirmLabel: 'Sí, cancelar',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/attendance/event/${eventId}/unregister`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            flash('success', 'Inscripción cancelada correctamente.');
            await loadEventDetail();
        } catch (err) {
            flash('danger', `Error al cancelar: ${err.message}`);
        }
    }

    function openChangeRequestModal() {
        document.getElementById('changeReason').value      = '';
        document.getElementById('changeSuggestions').value = '';
        const modal = new bootstrap.Modal(document.getElementById('changeRequestModal'));
        modal.show();
    }

    async function submitChangeRequest() {
        const reason      = document.getElementById('changeReason').value.trim();
        const suggestions = document.getElementById('changeSuggestions').value.trim();

        if (!reason) {
            flash('warning', 'Por favor indica el motivo del cambio.');
            return;
        }

        const modal = bootstrap.Modal.getInstance(document.getElementById('changeRequestModal'));

        try {
            await apiRequest(`${API}/appointments/${myAppt.id}/change-requests`, {
                method: 'POST',
                body: JSON.stringify({ reason, suggestions }),
            });
            modal?.hide();
            flash('success', 'Solicitud de cambio enviada. El coordinador te notificará la respuesta.');
        } catch (err) {
            flash('danger', `Error al enviar la solicitud: ${err.message}`);
        }
    }

    async function cancelAppointment() {
        const ok = await siiapConfirm({
            type: 'danger',
            title: 'Cancelar cita',
            message: '¿Estás seguro de que deseas cancelar tu cita? Esta acción no se puede deshacer.',
            confirmLabel: 'Sí, cancelar cita',
        });
        if (!ok) return;

        try {
            await apiRequest(`${API}/appointments/${myAppt.id}`, {
                method: 'DELETE',
            });
            flash('success', 'Cita cancelada correctamente.');
            await loadEventDetail();
        } catch (err) {
            flash('danger', `Error al cancelar la cita: ${err.message}`);
        }
    }

    // ── Real-time socket listeners ───────────────────────────

    let reloadDebounce = null;

    function debouncedReload(delayMs = 500) {
        if (reloadDebounce) clearTimeout(reloadDebounce);
        reloadDebounce = setTimeout(() => loadEventDetail(), delayMs);
    }

    window.addEventListener('siiap:event:changed', (e) => {
        const detail = e.detail || {};
        if (String(detail.event_id) !== String(eventId)) return;

        if (detail.action === 'deleted') {
            flash('danger', 'Este evento ha sido eliminado.');
            setTimeout(() => { window.location.href = '/events/'; }, 2500);
            return;
        }

        if (detail.action === 'updated') {
            flash('info', 'El evento fue actualizado. Recargando información...');
            debouncedReload();
        }
    });

    window.addEventListener('siiap:appointment:changed', (e) => {
        const detail = e.detail || {};
        // Reload if the appointment belongs to the current event or current user's appointment
        const affectsEvent = String(detail.event_id) === String(eventId);
        const affectsMe    = myAppt && String(detail.appointment_id) === String(myAppt.id);
        if (affectsEvent || affectsMe) {
            debouncedReload(500);
        }
    });

    window.addEventListener('siiap:notification:new', () => {
        // Refresh if a new notification potentially relates to an appointment update
        if (myAppt) {
            debouncedReload(800);
        }
    });

    // ── Event listeners ───────────────────────────────────────

    document.getElementById('btnRetry')?.addEventListener('click', () => {
        showLoading();
        loadEventDetail();
    });

    document.getElementById('btnConfirmChangeRequest')?.addEventListener('click', submitChangeRequest);

    // Lightbox close
    document.getElementById('lightboxClose')?.addEventListener('click', () => {
        document.getElementById('eventLightbox')?.close();
    });

    // Close lightbox on backdrop click
    document.getElementById('eventLightbox')?.addEventListener('click', e => {
        if (e.target === e.currentTarget) e.currentTarget.close();
    });

    // Copy share URL
    document.getElementById('btnCopyUrl')?.addEventListener('click', () => {
        const input = document.getElementById('shareUrlInput');
        if (!input) return;
        navigator.clipboard.writeText(input.value)
            .then(() => flash('success', 'Enlace copiado al portapapeles.'))
            .catch(() => {
                input.select();
                document.execCommand('copy');
                flash('success', 'Enlace copiado al portapapeles.');
            });
    });

    // ── Bootstrap ─────────────────────────────────────────────

    if (!eventId) {
        showError('ID de evento no encontrado. Vuelve al listado e intenta de nuevo.');
    } else {
        loadEventDetail();
    }
})();

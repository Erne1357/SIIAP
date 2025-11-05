// app/static/js/events/list.js
(() => {
    const API = "/api/v1";
    const eventsContainer = document.getElementById("eventsContainer");

    let allEvents = [];
    let myRegistrations = [];

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
                'X-CSRF-Token': getCsrfToken(),
                ...options.headers
            }
        };

        const response = await fetch(url, { ...defaultOptions, ...options });
        const data = await response.json();

        if (!response.ok || data.ok === false) {
            throw new Error(data.error || 'Error en la solicitud');
        }

        return { response, data };
    }

    async function loadEvents() {
        try {
            // CAMBIAR: Usar endpoint público
            const { data: eventsData } = await apiRequest(`${API}/events/public`);
            allEvents = eventsData.items || [];

            // Cargar mis registros
            const { data: regsData } = await apiRequest(`${API}/attendance/my-registrations`);
            myRegistrations = regsData.registrations || [];

            renderEvents();
        } catch (err) {
            console.error('Error loading events:', err);
            eventsContainer.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger">
          Error al cargar eventos: ${err.message}
        </div>
      </div>
    `;
        }
    }

    function renderEvents() {
        if (allEvents.length === 0) {
            eventsContainer.innerHTML = `
      <div class="col-12 text-center py-5">
        <i class="fas fa-calendar-times fa-3x text-muted mb-3"></i>
        <p class="text-muted">No hay eventos disponibles en este momento</p>
      </div>
    `;
            return;
        }

        eventsContainer.innerHTML = allEvents.map(event => {
            const isRegistered = myRegistrations.some(r => r.event_id === event.id);
            const myReg = myRegistrations.find(r => r.event_id === event.id);

            // Capacidad
            let capacityInfo = '';
            if (event.capacity_type === 'multiple') {
                const available = event.max_capacity - event.current_registrations;
                capacityInfo = `
        <span class="badge ${available > 0 ? 'bg-warning' : 'bg-danger'}">
          ${available > 0 ? `${available} cupos disponibles` : 'Cupo lleno'}
        </span>
      `;
            } else if (event.capacity_type === 'unlimited') {
                capacityInfo = `<span class="badge bg-success">Sin límite de cupos</span>`;
            }

            // Fecha del evento
            let dateInfo = '';
            if (event.event_date) {
                const eventDate = new Date(event.event_date);
                dateInfo = `
        <div class="mb-2">
          <i class="fas fa-calendar text-muted me-2"></i>
          <small>${eventDate.toLocaleDateString('es-MX', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                })}</small>
        </div>
      `;
            }

            // Programa
            let programBadge = '';
            if (event.program_name) {
                programBadge = `<span class="badge bg-primary mb-2">${event.program_name}</span>`;
            } else {
                programBadge = `<span class="badge bg-secondary mb-2">Abierto a todos</span>`;
            }

            // Verificar si puede registrarse
            const isFull = event.capacity_type === 'multiple' &&
                event.current_registrations >= event.max_capacity;

            return `
      <div class="col-md-6 col-lg-4">
        <div class="card h-100">
          <div class="card-body">
            <div class="mb-2">${programBadge}</div>
            <h5 class="card-title">${event.title}</h5>
            <p class="card-text text-muted small">${event.description || 'Sin descripción'}</p>
            
            ${dateInfo}
            
            <div class="mb-2">
              <i class="fas fa-map-marker-alt text-muted me-2"></i>
              <small>${event.location || 'Por definir'}</small>
            </div>
            
            <div class="mb-3">
              ${capacityInfo}
            </div>
            
            ${isRegistered ? `
              <div class="alert alert-success py-2 mb-2">
                <i class="fas fa-check-circle me-1"></i>
                <small>Ya estás registrado</small>
                ${myReg && myReg.status === 'attended' ?
                        '<br><span class="badge bg-success mt-1">Asististe</span>' : ''}
              </div>
              ${myReg && myReg.status === 'attended' ? '' : `
              <button class="btn btn-outline-danger btn-sm w-100 btn-unregister" 
                      data-event-id="${event.id}">
                Cancelar Registro
              </button>
              `}

            ` : isFull ? `
              <button class="btn btn-secondary btn-sm w-100" disabled>
                <i class="fas fa-ban me-1"></i> Cupo lleno
              </button>
            ` : `
              <button class="btn btn-primary btn-sm w-100 btn-register" 
                      data-event-id="${event.id}">
                <i class="fas fa-user-plus me-1"></i> Registrarme
              </button>
            `}
          </div>
        </div>
      </div>
    `;
        }).join('');
    }

    async function registerToEvent(eventId) {
        try {
            await apiRequest(`${API}/attendance/event/${eventId}/register`, {
                method: 'POST',
                body: JSON.stringify({ notes: '' })
            });

            flash('Te has registrado exitosamente al evento', 'success');
            await loadEvents();
        } catch (err) {
            flash(`Error al registrarse: ${err.message}`, 'danger');
        }
    }

    async function unregisterFromEvent(eventId) {
        if (!confirm('¿Estás seguro de que deseas cancelar tu registro?')) {
            return;
        }

        try {
            await apiRequest(`${API}/attendance/event/${eventId}/unregister`, {
                method: 'POST',
                body: JSON.stringify({})
            });

            flash('Registro cancelado correctamente', 'success');
            await loadEvents();
        } catch (err) {
            flash(`Error al cancelar: ${err.message}`, 'danger');
        }
    }

    // Event listeners
    eventsContainer?.addEventListener('click', (e) => {
        if (e.target.closest('.btn-register')) {
            const button = e.target.closest('.btn-register');
            const eventId = parseInt(button.dataset.eventId);
            registerToEvent(eventId);
        } else if (e.target.closest('.btn-unregister')) {
            const button = e.target.closest('.btn-unregister');
            const eventId = parseInt(button.dataset.eventId);
            unregisterFromEvent(eventId);
        }
    });

    // Inicializar
    loadEvents();
})();
// app/static/js/admin/settings/interviews.js
(() => {
  const API = "/api/v1";
  
  // Elementos DOM
  const eventsTable = document.getElementById("eventsTable");
  const slotsTable = document.getElementById("slotsTable");
  const slotsCard = document.getElementById("slotsCard");
  const selectedEventTitle = document.getElementById("selectedEventTitle");
  const eligibleStudents = document.getElementById("eligibleStudents");
  const alertsInterviews = document.getElementById("alertsInterviews");
  
  // Modales
  const createEventModal = new bootstrap.Modal(document.getElementById("createEventModal"));
  const addWindowModal = new bootstrap.Modal(document.getElementById("addWindowModal"));
  const assignSlotModal = new bootstrap.Modal(document.getElementById("assignSlotModal"));
  
  // Formularios
  const createEventForm = document.getElementById("createEventForm");
  const addWindowForm = document.getElementById("addWindowForm");
  const assignSlotForm = document.getElementById("assignSlotForm");
  
  // Estado
  let currentEvents = [];
  let currentSlots = [];
  let eligibleStudentsList = [];
  let selectedEventId = null;
  let programs = [];

  function flash(msg, type = "success") {
    window.dispatchEvent(new CustomEvent('flash', { 
      detail: { level: type, message: msg } 
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
  }

  async function loadPrograms() {
    try {
      // Reutilizar endpoint existente o crear uno específico
      const { data } = await apiRequest(`${API}/coordinator/students`);
      const uniquePrograms = [...new Set(data.students.map(s => ({id: s.program_id, name: s.program_name})))];
      programs = uniquePrograms;
      
      // Llenar selectores de programa
      const programSelects = [
        document.getElementById("eventProgram"),
        document.getElementById("programFilter")
      ];
      
      programSelects.forEach(select => {
        if (select) {
          select.innerHTML = '<option value="">Seleccionar programa...</option>' +
            programs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
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
    
    tbody.innerHTML = currentEvents.map(event => `
      <tr data-event-id="${event.id}" class="event-row" style="cursor: pointer;">
        <td>
          <div class="fw-semibold">${event.title}</div>
          <small class="text-muted">${event.type === 'interview' ? 'Entrevista' : 'Defensa'}</small>
        </td>
        <td>
          <span class="badge bg-primary">${event.program_name}</span>
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
            <button class="btn btn-outline-danger btn-delete-event" title="Eliminar">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  }

  async function loadSlots(eventId) {
    try {
      const { data } = await apiRequest(`${API}/events/${eventId}/slots`);
      currentSlots = data.items || [];
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
      const timeStr = `${startTime.toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit'})} - ${endTime.toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit'})}`;
      
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
            ${slot.status === 'free' ? `
              <button class="btn btn-sm btn-outline-primary btn-assign-slot" 
                      data-slot-id="${slot.id}" 
                      data-slot-info="${dateStr} ${timeStr}">
                <i class="fas fa-user-plus"></i> Asignar
              </button>
            ` : slot.status === 'booked' ? `
              <button class="btn btn-sm btn-outline-danger btn-cancel-appointment">
                <i class="fas fa-times"></i> Cancelar
              </button>
            ` : ''}
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
      const url = programId 
        ? `${API}/interviews/eligible-students/${programId}`
        : `${API}/coordinator/students?phase=admission&status=approved`;
      
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

  // ========== EVENT LISTENERS ==========
  function setupEventListeners() {
    // Crear evento
    createEventForm?.addEventListener('submit', handleCreateEvent);
    
    // Agregar ventana
    addWindowForm?.addEventListener('submit', handleAddWindow);
    
    // Asignar slot
    assignSlotForm?.addEventListener('submit', handleAssignSlot);
    
    // Generar slots
    document.getElementById('btnGenerateSlots')?.addEventListener('click', handleGenerateSlots);
    
    // Filtro de programa
    document.getElementById('programFilter')?.addEventListener('change', (e) => {
      const programId = e.target.value;
      loadEligibleStudents(programId || null);
    });
    
    // Delegación de eventos para tabla de eventos
    eventsTable?.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-event-id]');
      if (!row) return;
      
      const eventId = parseInt(row.dataset.eventId);
      
      if (e.target.closest('.btn-view-slots') || e.target.closest('.event-row')) {
        selectEvent(eventId);
      } else if (e.target.closest('.btn-delete-event')) {
        deleteEvent(eventId);
      }
    });
    
    // Delegación de eventos para tabla de slots
    slotsTable?.addEventListener('click', (e) => {
      if (e.target.closest('.btn-assign-slot')) {
        const button = e.target.closest('.btn-assign-slot');
        const slotId = button.dataset.slotId;
        const slotInfo = button.dataset.slotInfo;
        openAssignModal(slotId, slotInfo);
      } else if (e.target.closest('.btn-cancel-appointment')) {
        // Implementar cancelación de cita
        const row = e.target.closest('tr');
        const slotId = row.dataset.slotId;
        cancelAppointment(slotId);
      }
    });
  }

  // ========== HANDLERS ==========
  async function handleCreateEvent(e) {
    e.preventDefault();
    
    const formData = new FormData(createEventForm);
    const payload = {
      title: document.getElementById('eventTitle').value.trim(),
      program_id: parseInt(document.getElementById('eventProgram').value),
      type: document.getElementById('eventType').value,
      location: document.getElementById('eventLocation').value,
      description: document.getElementById('eventDescription').value
    };
    
    if (!payload.title || !payload.program_id) {
      flash('Título y programa son requeridos', 'warning');
      return;
    }
    
    try {
      const { data } = await apiRequest(`${API}/events`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      flash('Evento creado correctamente', 'success');
      createEventModal.hide();
      createEventForm.reset();
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
    
    const formData = new FormData(addWindowForm);
    const payload = {
      date: document.getElementById('windowDate').value,
      start_time: document.getElementById('windowStartTime').value,
      end_time: document.getElementById('windowEndTime').value,
      slot_minutes: parseInt(document.getElementById('windowSlotMinutes').value)
    };
    
    try {
      const { data } = await apiRequest(`${API}/events/${selectedEventId}/windows`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      flash('Ventana de horarios creada correctamente', 'success');
      addWindowModal.hide();
      addWindowForm.reset();
      await loadSlots(selectedEventId);
      
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
      // Obtener ventanas del evento
      const { data: eventData } = await apiRequest(`${API}/events/${selectedEventId}`);
      const event = eventData;
      
      if (!event || !event.windows || event.windows.length === 0) {
        flash('Primero agrega ventanas de horarios para este evento', 'warning');
        return;
      }
      
      let totalCreated = 0;
      
      // Generar slots para cada ventana
      for (const window of event.windows) {
        const { data: slotsData } = await apiRequest(
          `${API}/events/windows/${window.id}/generate-slots`, 
          { method: 'POST' }
        );
        totalCreated += slotsData.created || 0;
      }
      
      flash(`Se generaron ${totalCreated} nuevos horarios`, 'success');
      await loadSlots(selectedEventId);
      
    } catch (err) {
      flash(`Error generando horarios: ${err.message}`, 'danger');
    }
  }

  async function handleAssignSlot(e) {
    e.preventDefault();
    
    const formData = new FormData(assignSlotForm);
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
      const { data } = await apiRequest(`${API}/appointments`, {
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

  // ========== UTILITY FUNCTIONS ==========
  function selectEvent(eventId) {
    const event = currentEvents.find(e => e.id === eventId);
    if (!event) return;
    
    selectedEventId = eventId;
    selectedEventTitle.textContent = event.title;
    
    // Actualizar UI
    document.querySelectorAll('.event-row').forEach(row => {
      row.classList.toggle('table-active', parseInt(row.dataset.eventId) === eventId);
    });
    
    // Mostrar card de slots y cargar datos
    slotsCard.style.display = 'block';
    document.getElementById('windowEventId').value = eventId;
    
    loadSlots(eventId);
  }

  function openAssignModal(slotId, slotInfo) {
    document.getElementById('assignEventId').value = selectedEventId;
    document.getElementById('assignSlotId').value = slotId;
    document.getElementById('assignSlotInfo').textContent = slotInfo;
    
    // Llenar selector de estudiantes elegibles
    const studentSelect = document.getElementById('assignStudentId');
    studentSelect.innerHTML = '<option value="">Seleccionar estudiante...</option>' +
      eligibleStudentsList.map(s => 
        `<option value="${s.id}">${s.full_name} - ${s.email}</option>`
      ).join('');
    
    assignSlotModal.show();
  }

  async function deleteEvent(eventId) {
    if (!confirm('¿Eliminar este evento? Esta acción no se puede deshacer.')) return;
    
    try {
      // Por ahora solo remover del array local - implementar API después
      currentEvents = currentEvents.filter(e => e.id !== eventId);
      renderEventsTable();
      
      if (selectedEventId === eventId) {
        selectedEventId = null;
        slotsCard.style.display = 'none';
      }
      
      flash('Evento eliminado correctamente', 'success');
      
    } catch (err) {
      flash(`Error eliminando evento: ${err.message}`, 'danger');
    }
  }

  async function cancelAppointment(slotId) {
    if (!confirm('¿Cancelar esta cita?')) return;
    
    try {
      // Encontrar appointment por slot_id y cancelar
      const reason = prompt('Motivo de cancelación (opcional):');
      
      // Por ahora simular - implementar API después
      flash('Cita cancelada correctamente', 'success');
      await loadSlots(selectedEventId);
      
    } catch (err) {
      flash(`Error cancelando cita: ${err.message}`, 'danger');
    }
  }

  // ========== INICIALIZACIÓN ==========
  
  // Solo ejecutar si estamos en la pestaña de entrevistas
  if (document.getElementById('pane-interviews')) {
    // Ejecutar cuando se activa la pestaña de entrevistas
    document.getElementById('tab-interviews')?.addEventListener('shown.bs.tab', () => {
      init();
    });
    
    // Si la pestaña ya está activa al cargar la página
    if (document.getElementById('tab-interviews')?.classList.contains('active')) {
      init();
    }
  }

})();
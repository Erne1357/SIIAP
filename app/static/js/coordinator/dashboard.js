// static/js/coordinator/dashboard.js - FASE 2
document.addEventListener('DOMContentLoaded', () => {
  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();

  function emitFlash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }

  // ==================== VARIABLES GLOBALES ====================
  let studentsData = [];
  let currentFilters = {};

  // ==================== INICIALIZACIÓN ====================
  loadPrograms();  // Cargar programas primero
  loadStudents();
  setupEventListeners();

  // ==================== CARGA DE PROGRAMAS ====================
  async function loadPrograms() {
    try {
      const res = await fetch('/api/v1/coordinator/programs', {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('No se pudieron cargar los programas');

      const data = await res.json();
      const programFilter = document.getElementById('programFilter');
      
      if (programFilter && data.programs) {
        programFilter.innerHTML = '<option value="">Todos los programas</option>' +
          data.programs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
      }
    } catch (err) {
      console.error('Error loading programs:', err);
    }
  }

  // ==================== CARGA DE DATOS ====================
  async function loadStudents() {
    try {
      const params = new URLSearchParams(currentFilters);
      const res = await fetch(`/api/v1/coordinator/students?${params}`, {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('No se pudieron cargar los estudiantes');

      const data = await res.json();
      

      studentsData = data.students || [];
      
      console.log('Loaded students:', studentsData);

      updateTables();
      updateCounts();

    } catch (err) {
      console.error('Error loading students:', err);
      emitFlash('danger', 'Error al cargar estudiantes');
    }
  }

  // ==================== ACTUALIZACIÓN DE TABLAS ====================
  function updateTables() {
    updateAdmissionTable();
    updatePermanenceTable();
    updateConclusionTable();
  }

  function updateAdmissionTable() {
    const tbody = document.querySelector('#admissionTable tbody');
    // Ordenar por progreso ascendente (menor progreso primero = necesita más atención)
    const admissionStudents = studentsData
      .filter(s => s.current_phase === 'admission')
      .sort((a, b) => a.progress_percentage - b.progress_percentage);

    tbody.innerHTML = admissionStudents.map(student => `
      <tr data-student-id="${student.id}" class="${student.can_manage ? '' : 'table-secondary'}" 
          title="${student.can_manage ? '' : 'Solo consulta - Programa de otro coordinador'}">
        <td>
          <img src="${student.avatar_url || '/static/assets/images/default.jpg'}" 
               alt="Avatar" class="rounded-circle student-avatar">
        </td>
        <td>
          <div>
            <div class="fw-semibold">${student.full_name}</div>
            <small class="text-muted">${student.email}</small>
          </div>
        </td>
        <td>
          <span class="badge bg-primary">${student.program_name}</span>
          ${!student.can_manage ? '<i class="fas fa-eye text-muted ms-1" title="Solo consulta"></i>' : ''}
        </td>
        <td class="text-center">
          <div class="progress">
            <div class="progress-bar" role="progressbar" 
                 style="width: ${student.progress_percentage}%"></div>
          </div>
          <small class="text-muted">${student.progress_percentage}%</small>
        </td>
        <td class="text-center">
          <span class="badge bg-success me-1" title="Aprobados">${student.approved_docs}</span>
          <span class="badge bg-warning me-1" title="Pendientes">${student.pending_docs}</span>
          <span class="badge bg-info me-1" title="En Extensión">${student.extended_docs}</span>
          <span class="badge bg-danger" title="Rechazados">${student.rejected_docs}</span>
        </td>
        <td class="text-center">
          ${getStatusBadge(student.overall_status)}
        </td>
        <td>
          <div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-outline-primary btn-view-student" 
                    data-student-id="${student.id}" title="Ver detalles">
              <i class="fas fa-eye"></i>
            </button>
            ${student.can_manage ? `
            <button class="btn btn-outline-success btn-upload-for" 
                    data-student-id="${student.id}" title="Subir documento">
              <i class="fas fa-upload"></i>
            </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="text-center text-muted py-4">No hay estudiantes en admisión</td></tr>';
  }

  function updatePermanenceTable() {
    const tbody = document.querySelector('#permanenceTable tbody');
    // Ordenar por progreso ascendente (menor progreso primero = necesita más atención)
    const permanenceStudents = studentsData
      .filter(s => s.current_phase === 'permanence')
      .sort((a, b) => a.academic_progress - b.academic_progress);

    tbody.innerHTML = permanenceStudents.map(student => `
      <tr data-student-id="${student.id}" class="${student.can_manage ? '' : 'table-secondary'}"
          title="${student.can_manage ? '' : 'Solo consulta - Programa de otro coordinador'}">
        <td>
          <img src="${student.avatar_url || '/static/assets/images/default.jpg'}" 
               alt="Avatar" class="rounded-circle student-avatar">
        </td>
        <td>
          <div>
            <div class="fw-semibold">${student.full_name}</div>
            <small class="text-muted">${student.email}</small>
          </div>
        </td>
        <td>
          <span class="badge bg-info">${student.program_name}</span>
          ${!student.can_manage ? '<i class="fas fa-eye text-muted ms-1" title="Solo consulta"></i>' : ''}
        </td>
        <td class="text-center">
          <span class="badge bg-light text-dark">${student.current_semester || 'N/A'}</span>
        </td>
        <td class="text-center">
          <div class="progress">
            <div class="progress-bar bg-info" role="progressbar" 
                 style="width: ${student.academic_progress}%"></div>
          </div>
          <small class="text-muted">${student.academic_progress}%</small>
        </td>
        <td class="text-center">
          ${getStatusBadge(student.academic_status)}
        </td>
        <td>
          <div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-outline-info btn-view-permanence"
                    data-student-id="${student.id}"
                    title="Ver detalle de permanencia">
              <i class="bi bi-person-badge"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="text-center text-muted py-4">No hay estudiantes en permanencia</td></tr>';
  }

  function updateConclusionTable() {
    const tbody = document.querySelector('#conclusionTable tbody');
    // Ordenar por progreso ascendente (menor progreso primero = necesita más atención)
    const conclusionStudents = studentsData
      .filter(s => s.current_phase === 'conclusion')
      .sort((a, b) => a.conclusion_progress - b.conclusion_progress);

    tbody.innerHTML = conclusionStudents.map(student => `
      <tr data-student-id="${student.id}" class="${student.can_manage ? '' : 'table-secondary'}"
          title="${student.can_manage ? '' : 'Solo consulta - Programa de otro coordinador'}">
        <td>
          <img src="${student.avatar_url || '/static/assets/images/default.jpg'}" 
               alt="Avatar" class="rounded-circle student-avatar">
        </td>
        <td>
          <div>
            <div class="fw-semibold">${student.full_name}</div>
            <small class="text-muted">${student.email}</small>
          </div>
        </td>
        <td>
          <span class="badge bg-success">${student.program_name}</span>
          ${!student.can_manage ? '<i class="fas fa-eye text-muted ms-1" title="Solo consulta"></i>' : ''}
        </td>
        <td class="text-center">
          <span class="badge bg-light text-dark">${student.conclusion_stage || 'Inicial'}</span>
        </td>
        <td class="text-center">
          <div class="progress">
            <div class="progress-bar bg-success" role="progressbar" 
                 style="width: ${student.conclusion_progress}%"></div>
          </div>
          <small class="text-muted">${student.conclusion_progress}%</small>
        </td>
        <td class="text-center">
          ${getStatusBadge(student.conclusion_status)}
        </td>
        <td>
          <div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-outline-primary btn-view-student" 
                    data-student-id="${student.id}">
              <i class="fas fa-eye"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="text-center text-muted py-4">No hay estudiantes en conclusión</td></tr>';
  }

  function getStatusBadge(status) {
    const statusMap = {
      'pending': '<span class="badge bg-secondary">Pendiente</span>',
      'in_progress': '<span class="badge bg-warning">En Progreso</span>',
      'review': '<span class="badge bg-info">En Revisión</span>',
      'approved': '<span class="badge bg-success">Aprobado</span>',
      'rejected': '<span class="badge bg-danger">Rechazado</span>',
      'completed': '<span class="badge bg-success">Completado</span>'
    };
    return statusMap[status] || '<span class="badge bg-light">Desconocido</span>';
  }

  function updateCounts() {
    const phases = ['admission', 'permanence', 'conclusion'];
    phases.forEach(phase => {
      const count = studentsData.filter(s => s.current_phase === phase).length;
      document.getElementById(`${phase}Count`).textContent = count;
    });
  }

  // ==================== EVENT LISTENERS ====================
  function setupEventListeners() {
    // Filtros
    document.getElementById('programFilter').addEventListener('change', updateFilters);
    document.getElementById('phaseFilter').addEventListener('change', updateFilters);
    document.getElementById('statusFilter').addEventListener('change', updateFilters);
    document.getElementById('showOtherPrograms').addEventListener('change', updateFilters);

    // Búsqueda
    document.getElementById('studentSearch').addEventListener('input', debounce(updateFilters, 300));
    document.getElementById('searchBtn').addEventListener('click', updateFilters);

    // Botones de acción
    document.getElementById('refreshBtn').addEventListener('click', loadStudents);

    // Delegación de eventos para botones dinámicos
    document.addEventListener('click', handleButtonClicks);

    // Subida de archivos por coordinador
    setupCoordinatorUpload();

    // ==================== TIEMPO REAL ====================
    // Estrategia: partial refresh (loadStudents) en lugar de reload completo,
    // para preservar filtros activos y no interrumpir workflow del coordinador.
    // Se debounces para evitar ráfagas si llegan muchos eventos juntos.
    //
    // Eventos que SÍ llegan a la sala role:coordinator:
    //   - submission:new         → aspirante/estudiante subió documento
    //   - acceptance:updated     → receipt_submitted (aspirante subió boleta)
    //   - deliberation:updated   → sólo si el coordinador entró a la sala deliberation:{pid}
    // Otros eventos (submission:reviewed, admission:status_changed, permanence:status_changed,
    // extension:decided) se emiten sólo al usuario afectado; ver PLAN_SOCKETS.md Fase 5
    // para agregar canal coordinator:feed si se requiere propagar todos los cambios.
    const refreshDebounced = debounce(loadStudents, 800);

    window.addEventListener('siiap:submission:new', (e) => {
      const d = e.detail || {};
      emitFlash('info', `Nuevo documento: ${d.archive_name || 'documento'}`);
      refreshDebounced();
    });

    window.addEventListener('siiap:acceptance:updated',   refreshDebounced);
    window.addEventListener('siiap:deliberation:updated', refreshDebounced);
  }

  function updateFilters() {
    currentFilters = {
      program_id: document.getElementById('programFilter').value,
      phase: document.getElementById('phaseFilter').value,
      status: document.getElementById('statusFilter').value,
      show_other: document.getElementById('showOtherPrograms').checked ? 'true' : '',
      search: document.getElementById('studentSearch').value.trim()
    };

    // Remover valores vacíos
    Object.keys(currentFilters).forEach(key => {
      if (!currentFilters[key]) delete currentFilters[key];
    });

    loadStudents();
  }

  function handleButtonClicks(e) {
    const button = e.target.closest('button');
    if (!button) return;

    const studentId = button.dataset.studentId;

    if (button.classList.contains('btn-view-student')) {
      viewStudentDetails(studentId);
    } else if (button.classList.contains('btn-view-permanence')) {
      viewPermanenceDetails(studentId);
    } else if (button.classList.contains('btn-upload-for')) {
      openUploadModal(studentId);
    }
  }

  // ==================== ACCIONES DE ESTUDIANTES ====================
  async function viewStudentDetails(studentId) {
    const student = studentsData.find(s => s.id == studentId);
    if (!student) return;

    // Mostrar modal con loading
    const modal = new bootstrap.Modal(document.getElementById('studentDetailsModal'));
    document.getElementById('modalStudentName').textContent = 'Cargando...';
    document.getElementById('modalStudentEmail').textContent = '';
    document.getElementById('modalStudentProgram').textContent = '';
    
    // Mostrar loading solo en el tab activo, manteniendo la estructura del modal
    document.getElementById('generalTabContent').innerHTML = `
      <div class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Cargando...</span>
        </div>
        <p class="mt-3">Obteniendo información del estudiante...</p>
      </div>
    `;
    
    // Limpiar otros tabs
    document.getElementById('documentsTabContent').innerHTML = '';
    document.getElementById('interviewTabContent').innerHTML = '';
    
    // Asegurar que el tab General esté activo
    document.getElementById('general-tab').click();
    
    modal.show();

    try {
      const res = await fetch(`/api/v1/coordinator/student/${studentId}/details`, {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('Error al cargar detalles');

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Error desconocido');

      renderStudentDetails(data.student, data.documents, data.interview, data.metrics, data.missing_documents, data.can_manage);

    } catch (err) {
      console.error('Error loading student details:', err);
      document.getElementById('modalContent').innerHTML = `
      <div class="alert alert-danger">
        <i class="fas fa-exclamation-triangle me-2"></i>
        Error al cargar información: ${err.message}
      </div>
    `;
    }
  }
  function renderStudentDetails(student, documents, interview, metrics, missing, canManage) {
    // Header
    document.getElementById('modalStudentName').textContent = student.full_name;
    document.getElementById('modalStudentEmail').textContent = student.email;
    document.getElementById('modalStudentAvatar').src = student.avatar_url || '/static/assets/images/default.jpg';
    document.getElementById('modalStudentProgram').textContent = student.program.name;

    // Tab General
    renderGeneralTab(student, metrics, missing);

    // Tab Documentos
    renderDocumentsTab(documents, student.id, canManage);

    // Tab Entrevista
    renderInterviewTab(interview, student);
  }

  function renderGeneralTab(student, metrics, missing) {
    const generalContent = document.getElementById('generalTabContent');

    generalContent.innerHTML = `
    <!-- Métricas -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3">
        <div class="card text-center">
          <div class="card-body py-3">
            <h3 class="mb-0 text-success">${metrics.approved}</h3>
            <small class="text-muted">Aprobados</small>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center">
          <div class="card-body py-3">
            <h3 class="mb-0 text-warning">${metrics.pending}</h3>
            <small class="text-muted">Pendientes</small>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center">
          <div class="card-body py-3">
            <h3 class="mb-0 text-danger">${metrics.rejected}</h3>
            <small class="text-muted">Rechazados</small>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center">
          <div class="card-body py-3">
            <h3 class="mb-0 text-info">${metrics.extended}</h3>
            <small class="text-muted">En Prórroga</small>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Progreso -->
    <div class="mb-4">
      <h6 class="mb-2">Progreso General</h6>
      <div class="progress" style="height: 20px;">
        <div class="progress-bar bg-success" role="progressbar" 
             style="width: ${metrics.progress_percentage}%">
          ${metrics.progress_percentage}%
        </div>
      </div>
    </div>
    
    <!-- Estado del Perfil -->
    <div class="alert ${student.profile_completed ? 'alert-success' : 'alert-warning'} mb-4">
      <h6 class="mb-2">
        <i class="fas fa-user-check me-2"></i>Estado del Perfil
      </h6>
      ${student.profile_completed
        ? '<p class="mb-0">✅ Perfil completo - Elegible para entrevista</p>'
        : '<p class="mb-0">⚠️ Perfil incompleto - Debe completar datos personales</p>'}
    </div>
    
    <!-- Documentos Faltantes/Rechazados -->
    ${missing.length > 0 ? `
      <div class="mb-4">
        <h6 class="mb-2">
          <i class="fas fa-exclamation-circle text-warning me-2"></i>
          Documentos Pendientes (${missing.length})
        </h6>
        <ul class="list-group">
          ${missing.map(item => `
            <li class="list-group-item d-flex justify-content-between align-items-center">
              <div>
                <strong>${item.archive}</strong>
                <small class="d-block text-muted">${item.step}</small>
              </div>
              <span class="badge ${item.status === 'rejected' ? 'bg-danger' : 'bg-secondary'}">
                ${item.status === 'rejected' ? 'Rechazado' : 'Pendiente'}
              </span>
            </li>
          `).join('')}
        </ul>
      </div>
    ` : '<div class="alert alert-success">✅ Todos los documentos en orden</div>'}
    
    <!-- Datos Personales -->
    <div>
      <h6 class="mb-3">Datos Personales</h6>
      <div class="row g-3">
        <div class="col-md-6">
          <label class="small text-muted">Teléfono</label>
          <p class="mb-0">${student.profile_data.phone || student.profile_data.mobile_phone || 'No registrado'}</p>
        </div>
        <div class="col-md-6">
          <label class="small text-muted">CURP</label>
          <p class="mb-0">${student.profile_data.curp || 'No registrado'}</p>
        </div>
        <div class="col-md-6">
          <label class="small text-muted">Fecha de Nacimiento</label>
          <p class="mb-0">${student.profile_data.birth_date ? new Date(student.profile_data.birth_date).toLocaleDateString('es-MX') : 'No registrado'}</p>
        </div>
        <div class="col-md-6">
          <label class="small text-muted">NSS</label>
          <p class="mb-0">${student.profile_data.nss || 'No registrado'}</p>
        </div>
        <div class="col-12">
          <label class="small text-muted">Contacto de Emergencia</label>
          <p class="mb-0">
            ${student.profile_data.emergency_contact.name || 'No registrado'}<br>
            <small class="text-muted">
              ${student.profile_data.emergency_contact.phone || ''} 
              ${student.profile_data.emergency_contact.relationship ? `(${student.profile_data.emergency_contact.relationship})` : ''}
            </small>
          </p>
        </div>
      </div>
    </div>
  `;
  }

  function renderDocumentsTab(documents, studentId, canManage) {
    const docsContent = document.getElementById('documentsTabContent');

    // Si es solo lectura, mostrar advertencia
    const readOnlyWarning = !canManage ? `
      <div class="alert alert-info mb-3">
        <i class="fas fa-eye me-2"></i>
        <strong>Modo solo lectura:</strong> Este estudiante pertenece a un programa de otro coordinador.
      </div>
    ` : '';

    docsContent.innerHTML = readOnlyWarning + documents.map(step => `
    <div class="card mb-3">
      <div class="card-header bg-light">
        <h6 class="mb-0">
          ${step.sequence}. ${step.step_name}
          <span class="badge ${step.state === 'approved' ? 'bg-success' : step.state === 'rejected' ? 'bg-danger' : 'bg-warning'} ms-2">
            ${getStepStateName(step.state)}
          </span>
        </h6>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-sm table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>Documento</th>
                <th class="text-center">Estado</th>
                <th>Fecha</th>
                <th>Observaciones</th>
                <th class="text-center">Acciones</th>
              </tr>
            </thead>
            <tbody>
              ${step.archives.map(arch => `
                <tr>
                  <td>
                    <strong>${arch.name}</strong>
                    ${arch.uploaded_by_role === 'program_admin' ? '<i class="fas fa-user-tie text-primary ms-1" title="Subido por coordinador"></i>' : ''}
                  </td>
                  <td class="text-center">
                    ${getArchiveStatusBadge(arch.status)}
                  </td>
                  <td>
                    ${arch.uploaded_at ? new Date(arch.uploaded_at).toLocaleDateString('es-MX') : '-'}
                  </td>
                  <td>
                    <small class="text-muted">${arch.reviewer_comment || '-'}</small>
                  </td>
                  <td class="text-center">
                    <div class="btn-group btn-group-sm" role="group">
                      ${arch.has_submission ? `
                        <a href="${arch.file_url}" target="_blank" class="btn btn-outline-primary" title="Ver documento">
                          <i class="fas fa-eye"></i>
                        </a>
                      ` : ''}
                      ${canManage && arch.allow_coordinator_upload ? `
                        <button class="btn btn-outline-success btn-upload-for-modal" 
                                data-student-id="${studentId}" data-archive-id="${arch.id}" 
                                title="Subir documento">
                          <i class="fas fa-upload"></i>
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `).join('');
  }

  function renderInterviewTab(interview, student) {
    const interviewContent = document.getElementById('interviewTabContent');
    const eligibility = interview.eligibility;
    const appt = interview.appointment;
    const apptStatus = appt?.status;
    const interviewDone = apptStatus === 'done' || apptStatus === 'no_show';

    // Mapa de estado de cita → badge + color header
    const apptStatusMap = {
      scheduled: { badge: 'bg-primary',   label: 'Programada',       headerBg: 'bg-primary'  },
      done:      { badge: 'bg-success',   label: 'Realizada',        headerBg: 'bg-success'  },
      no_show:   { badge: 'bg-danger',    label: 'No se presentó',   headerBg: 'bg-danger'   },
    };
    const apptStyle = apptStatusMap[apptStatus] || { badge: 'bg-secondary', label: apptStatus, headerBg: 'bg-secondary' };

    interviewContent.innerHTML = `
    <!-- Estado de Elegibilidad (solo si la entrevista no se realizó todavía) -->
    ${!interviewDone ? `
    <div class="alert ${eligibility.eligible ? 'alert-success' : 'alert-warning'} mb-4">
      <h6 class="mb-2">
        <i class="fas ${eligibility.eligible ? 'fa-check-circle' : 'fa-exclamation-triangle'} me-2"></i>
        Estado de Elegibilidad
      </h6>
      <p class="mb-0">
        ${eligibility.eligible
          ? '✅ El estudiante cumple con todos los requisitos para entrevista'
          : '⚠️ El estudiante NO cumple con los requisitos para entrevista'}
      </p>
      ${!eligibility.eligible && eligibility.missing_items.length > 0 ? `
        <hr>
        <p class="mb-2 small"><strong>Elementos faltantes:</strong></p>
        <ul class="small mb-0">
          ${eligibility.missing_items.map(item => `
            <li>${item.type === 'profile' ? item.description : `${item.step}: ${item.archive} (${item.current_status})`}</li>
          `).join('')}
        </ul>
      ` : ''}
    </div>
    ` : ''}

    <!-- Detalle de la cita de entrevista -->
    ${interview.has_interview ? `
      <div class="card">
        <div class="card-header ${apptStyle.headerBg} text-white">
          <h6 class="mb-0">
            <i class="fas fa-calendar-check me-2"></i>
            ${interviewDone ? 'Entrevista Completada' : 'Entrevista Asignada'}
          </h6>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <div class="col-md-6">
              <label class="small text-muted">Evento</label>
              <p class="mb-0"><strong>${appt.event.title}</strong></p>
            </div>
            <div class="col-md-6">
              <label class="small text-muted">Fecha y Hora</label>
              <p class="mb-0">
                ${new Date(appt.slot.starts_at).toLocaleDateString('es-MX', {
                  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
                })}<br>
                <small class="text-muted">
                  ${new Date(appt.slot.starts_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} –
                  ${new Date(appt.slot.ends_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                </small>
              </p>
            </div>
            <div class="col-md-6">
              <label class="small text-muted">Lugar</label>
              <p class="mb-0">${appt.event.location || 'Por confirmar'}</p>
            </div>
            <div class="col-md-6">
              <label class="small text-muted">Estado</label>
              <p class="mb-0">
                <span class="badge ${apptStyle.badge}">${apptStyle.label}</span>
              </p>
            </div>
            ${appt.notes ? `
              <div class="col-12">
                <label class="small text-muted">Notas</label>
                <p class="mb-0 small">${appt.notes}</p>
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    ` : `
      <div class="alert alert-info">
        <i class="fas fa-info-circle me-2"></i>
        El estudiante no tiene entrevista asignada aún.
        ${eligibility.eligible ? ' Sin embargo, cumple con los requisitos y puede ser asignado.' : ''}
      </div>
    `}
  `;
  }

  // Funciones auxiliares
  function getStepStateName(state) {
    const names = {
      'approved': 'Completo',
      'rejected': 'Rechazado',
      'pending': 'Pendiente',
      'extended': 'En Prórroga',
      'review': 'En Revisión'
    };
    return names[state] || state;
  }

  function getArchiveStatusBadge(status) {
    const badges = {
      'approved': '<span class="badge bg-success">Aprobado</span>',
      'rejected': '<span class="badge bg-danger">Rechazado</span>',
      'pending': '<span class="badge bg-secondary">Pendiente</span>',
      'review': '<span class="badge bg-warning text-dark">En Revisión</span>',
      'extended': '<span class="badge bg-info">En Prórroga</span>'
    };
    return badges[status] || `<span class="badge bg-light">${status}</span>`;
  }
  function openUploadModal(studentId) {
    const student = studentsData.find(s => s.id == studentId);
    if (!student) return;

    // Pre-seleccionar estudiante en el modal
    document.getElementById('targetStudent').value = studentId;
    document.getElementById('targetProgram').value = student.program_name;
    loadStudentArchives(studentId);

    const modal = new bootstrap.Modal(document.getElementById('uploadForStudentModal'));
    modal.show();
  }

  // ==================== SUBIDA POR COORDINADOR ====================
  function setupCoordinatorUpload() {
    const form = document.querySelector('form[data-coordinator-upload="true"]');
    if (!form) return;

    const studentSelect = document.getElementById('targetStudent');
    const archiveSelect = document.getElementById('targetArchive');
    const programInput = document.getElementById('targetProgram');

    // Cargar lista de estudiantes
    loadStudentsList();

    // Cambio de estudiante -> cargar archivos
    studentSelect.addEventListener('change', (e) => {
      const studentId = e.target.value;
      if (studentId) {
        const student = studentsData.find(s => s.id == studentId);
        programInput.value = student ? student.program_name : '';
        loadStudentArchives(studentId);
      } else {
        programInput.value = '';
        archiveSelect.innerHTML = '<option value="">Primero selecciona un estudiante</option>';
        archiveSelect.disabled = true;
      }
    });

    // Submit del formulario
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const formData = new FormData(form);
      const studentId = formData.get('student_id');
      const archiveId = formData.get('archive_id');
      const file = formData.get('file');

      if (!studentId || !archiveId || !file) {
        emitFlash('warning', 'Completa todos los campos obligatorios');
        return;
      }

      // Validar archivo
      if (file.size > 3 * 1024 * 1024) {
        emitFlash('danger', 'El archivo no puede superar los 3MB');
        return;
      }

      if (!file.name.toLowerCase().endsWith('.pdf')) {
        emitFlash('danger', 'Solo se permiten archivos PDF');
        return;
      }

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
      submitBtn.disabled = true;

      try {
        const res = await fetch('/api/v1/coordinator/upload-for-student', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf },
          body: formData
        });

        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          emitFlash('danger', json.error || 'No se pudo subir el documento');
          return;
        }

        emitFlash('success', 'Documento subido correctamente por coordinador');

        // Cerrar modal y recargar datos
        const modal = bootstrap.Modal.getInstance(document.getElementById('uploadForStudentModal'));
        modal.hide();
        form.reset();
        loadStudents();

      } catch (err) {
        console.error('Upload error:', err);
        emitFlash('danger', 'Error de red al subir documento');
      } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
      }
    });
  }

  async function loadStudentsList() {
    try {
      const res = await fetch('/api/v1/coordinator/manageable-students', {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('No se pudieron cargar estudiantes');

      const data = await res.json();
      const select = document.getElementById('targetStudent');

      select.innerHTML = '<option value="">Seleccionar estudiante...</option>' +
        data.students.map(s => `<option value="${s.id}">${s.full_name} - ${s.program_name}</option>`).join('');

    } catch (err) {
      console.error('Error loading students list:', err);
    }
  }

  async function loadStudentArchives(studentId) {
    try {
      const res = await fetch(`/api/v1/coordinator/student/${studentId}/uploadable-archives`, {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('No se pudieron cargar archivos');

      const data = await res.json();
      const select = document.getElementById('targetArchive');

      if (data.archives.length === 0) {
        select.innerHTML = '<option value="">No hay archivos disponibles para subir</option>';
        select.disabled = true;
      } else {
        select.innerHTML = '<option value="">Seleccionar archivo...</option>' +
          data.archives.map(a => `<option value="${a.id}">${a.name} (${a.step_name})</option>`).join('');
        select.disabled = false;
      }

    } catch (err) {
      console.error('Error loading archives:', err);
      const select = document.getElementById('targetArchive');
      select.innerHTML = '<option value="">Error al cargar archivos</option>';
      select.disabled = true;
    }
  }

  // ==================== UTILIDADES ====================
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // ==================== MODAL DE PERMANENCIA ====================

  // Estado del modal para acciones internas
  let _permCurrentStudentId = null;
  let _permCurrentUserProgramId = null;
  let _permCurrentConacyt = false;

  async function viewPermanenceDetails(studentId) {
    _permCurrentStudentId = parseInt(studentId);

    // Resetear modal
    document.getElementById('permModalAvatar').src = '/static/assets/images/default.jpg';
    document.getElementById('permModalName').textContent = 'Cargando...';
    document.getElementById('permModalEmail').textContent = '';
    document.getElementById('permModalProgram').textContent = '';
    document.getElementById('permModalControlNumber').textContent = '';
    document.getElementById('permModalSpinner').classList.remove('d-none');
    document.getElementById('permModalContent').classList.add('d-none');

    const modal = new bootstrap.Modal(document.getElementById('permanenceDetailsModal'));
    modal.show();

    try {
      const res = await fetch(`/api/v1/coordinator/student/${studentId}/permanence-details`, {
        credentials: 'same-origin'
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error al cargar');
      renderPermanenceModal(data);
    } catch (err) {
      document.getElementById('permModalSpinner').innerHTML = `
        <div class="alert alert-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>Error: ${err.message}
        </div>`;
    }
  }

  function renderPermanenceModal(data) {
    const { student, user_program, program, active_period, current_enrollment,
            pending_admission_count, semester_history, can_manage } = data;

    _permCurrentUserProgramId = user_program.id;
    _permCurrentConacyt = user_program.has_conacyt_scholarship;

    // Header
    document.getElementById('permModalAvatar').src = student.avatar_url || '/static/assets/images/default.jpg';
    document.getElementById('permModalName').textContent = student.full_name;
    document.getElementById('permModalEmail').textContent = student.email;
    document.getElementById('permModalProgram').textContent = program.name;
    document.getElementById('permModalControlNumber').textContent = student.control_number || '(sin N° control)';

    // Alerta docs admisión pendientes
    const admAlert = document.getElementById('permAdmissionAlert');
    if (pending_admission_count > 0) {
      document.getElementById('permAdmissionCount').textContent = pending_admission_count;
      admAlert.classList.remove('d-none');
      document.getElementById('permOpenAdmissionBtn').onclick = () => {
        bootstrap.Modal.getInstance(document.getElementById('permanenceDetailsModal'))?.hide();
        viewStudentDetails(_permCurrentStudentId);
      };
    } else {
      admAlert.classList.add('d-none');
    }

    // Botón "Ver expediente completo"
    document.getElementById('permOpenFullBtn').onclick = () => {
      bootstrap.Modal.getInstance(document.getElementById('permanenceDetailsModal'))?.hide();
      viewStudentDetails(_permCurrentStudentId);
    };

    // ── Tarjetas resumen ──────────────────────────────────────────
    const statusEnrollment = current_enrollment
      ? (current_enrollment.enrollment_confirmed
          ? ['bg-success', 'Confirmada', 'bi-check-circle-fill']
          : ['bg-warning text-dark', 'Pendiente', 'bi-hourglass-split'])
      : ['bg-secondary', 'Sin registro', 'bi-dash-circle'];

    document.getElementById('permSummaryCards').innerHTML = `
      <div class="col-6 col-md-4">
        <div class="card text-center h-100">
          <div class="card-body py-3">
            <i class="bi bi-mortarboard-fill fs-3 text-primary mb-1"></i>
            <div class="fw-bold fs-4 lh-1">${user_program.current_semester}</div>
            <div class="small text-muted">Semestre actual</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-4">
        <div class="card text-center h-100">
          <div class="card-body py-3">
            <i class="bi bi-calendar-event-fill fs-3 text-info mb-1"></i>
            <div class="fw-bold lh-1 small">${active_period ? active_period.name : '—'}</div>
            <div class="small text-muted">${active_period ? active_period.code : 'Sin periodo activo'}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-4">
        <div class="card text-center h-100">
          <div class="card-body py-3">
            <i class="bi ${statusEnrollment[2]} fs-3 mb-1"></i>
            <div><span class="badge ${statusEnrollment[0]}">${statusEnrollment[1]}</span></div>
            <div class="small text-muted mt-1">Inscripción semestral</div>
          </div>
        </div>
      </div>
    `;

    // ── CONACyT ────────────────────────────────────────────────────
    const badge = document.getElementById('permConacytBadge');
    const switchEl = document.getElementById('permConacytSwitch');
    const toggleWrap = document.getElementById('permConacytToggleWrap');

    badge.className = `badge fs-6 ${_permCurrentConacyt ? 'bg-warning text-dark' : 'bg-light text-muted border'}`;
    badge.textContent = _permCurrentConacyt ? 'Becario CONACyT' : 'Sin beca CONACyT';
    switchEl.checked = _permCurrentConacyt;
    toggleWrap.classList.toggle('d-none', !can_manage);

    switchEl.onchange = async () => {
      switchEl.disabled = true;
      await toggleConacytScholarship(_permCurrentUserProgramId, switchEl.checked);
      switchEl.disabled = false;
    };

    // ── Inscripción semestral detalle ──────────────────────────────
    const enrollBody = document.getElementById('permEnrollmentBody');
    if (!active_period) {
      enrollBody.innerHTML = '<p class="text-muted mb-0">No hay periodo académico activo.</p>';
    } else if (!current_enrollment) {
      enrollBody.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-warning text-dark">Pendiente de confirmación</span>
          <span class="small text-muted">El estudiante no tiene inscripción registrada para el periodo activo.</span>
        </div>`;
    } else {
      const statusMap = {
        active: ['bg-success', 'Activo'],
        pending: ['bg-warning text-dark', 'Pendiente'],
        completed: ['bg-primary', 'Completado'],
        on_leave: ['bg-secondary', 'Baja temporal'],
        dropped: ['bg-danger', 'Baja definitiva'],
      };
      const [cls, label] = statusMap[current_enrollment.status] || ['bg-secondary', current_enrollment.status];
      const confirmedAt = current_enrollment.confirmed_at
        ? new Date(current_enrollment.confirmed_at).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' })
        : null;
      enrollBody.innerHTML = `
        <div class="row g-2 align-items-center">
          <div class="col-auto">
            <span class="badge ${cls}">${label}</span>
          </div>
          ${current_enrollment.enrollment_confirmed
            ? `<div class="col-auto small text-muted">Confirmada${confirmedAt ? ' el ' + confirmedAt : ''}</div>`
            : `<div class="col-auto small text-muted">Pendiente de confirmación por el coordinador</div>`}
          ${current_enrollment.notes
            ? `<div class="col-12"><small class="text-muted fst-italic">"${current_enrollment.notes}"</small></div>`
            : ''}
        </div>`;
    }

    // ── Historial ─────────────────────────────────────────────────
    const histContainer = document.getElementById('permHistoryContent');
    if (!semester_history.length) {
      histContainer.innerHTML = '<p class="text-muted text-center py-4">Sin historial semestral registrado.</p>';
    } else {
      const statusMap = {
        active: ['bg-success', 'Activo'],
        pending: ['bg-warning text-dark', 'Pendiente'],
        completed: ['bg-primary', 'Completado'],
        on_leave: ['bg-secondary', 'Baja temporal'],
        dropped: ['bg-danger', 'Baja definitiva'],
      };
      histContainer.innerHTML = `
        <table class="table table-sm table-bordered align-middle">
          <thead class="table-light">
            <tr>
              <th class="text-center">Semestre</th>
              <th>Periodo</th>
              <th class="text-center">Estado</th>
              <th class="text-center">Confirmado</th>
            </tr>
          </thead>
          <tbody>
            ${semester_history.map(h => {
              const [cls, label] = statusMap[h.status] || ['bg-secondary', h.status];
              const confirmedIcon = h.enrollment_confirmed
                ? '<i class="bi bi-check-circle-fill text-success fs-5"></i>'
                : '<i class="bi bi-dash-circle text-muted fs-5"></i>';
              return `
                <tr>
                  <td class="text-center fw-bold">Sem. ${h.semester_number}</td>
                  <td>
                    ${h.period_name}
                    <span class="badge bg-light text-dark border ms-1">${h.period_code}</span>
                  </td>
                  <td class="text-center"><span class="badge ${cls}">${label}</span></td>
                  <td class="text-center">${confirmedIcon}</td>
                </tr>`;
            }).join('')}
          </tbody>
        </table>`;
    }

    // Mostrar contenido
    document.getElementById('permModalSpinner').classList.add('d-none');
    document.getElementById('permModalContent').classList.remove('d-none');
  }

  async function toggleConacytScholarship(userProgramId, newValue) {
    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const res = await fetch(`/api/v1/permanence/user-program/${userProgramId}/conacyt-scholarship`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ value: newValue }),
      });
      const json = await res.json();
      (json.flash || []).forEach(f => emitFlash(f.level, f.message));
      if (res.ok && !json.error) {
        _permCurrentConacyt = json.data.has_conacyt_scholarship;
        const badge = document.getElementById('permConacytBadge');
        badge.className = `badge fs-6 ${_permCurrentConacyt ? 'bg-warning text-dark' : 'bg-light text-muted border'}`;
        badge.textContent = _permCurrentConacyt ? 'Becario CONACyT' : 'Sin beca CONACyT';
        // Actualizar también en la tabla principal
        loadStudents();
      }
    } catch (err) {
      emitFlash('danger', 'Error al actualizar beca CONACyT');
    }
  }

});
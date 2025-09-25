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
  loadStudents();
  setupEventListeners();

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
    const admissionStudents = studentsData.filter(s => s.current_phase === 'admission');
    
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
        </td>
        <td class="text-center">
          <div class="progress">
            <div class="progress-bar" role="progressbar" 
                 style="width: ${student.progress_percentage}%"></div>
          </div>
          <small class="text-muted">${student.progress_percentage}%</small>
        </td>
        <td class="text-center">
          <span class="badge bg-success me-1">${student.approved_docs}</span>
          <span class="badge bg-warning me-1">${student.pending_docs}</span>
          <span class="badge bg-danger">${student.rejected_docs}</span>
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
    const permanenceStudents = studentsData.filter(s => s.current_phase === 'permanence');
    
    tbody.innerHTML = permanenceStudents.map(student => `
      <tr data-student-id="${student.id}" class="${student.can_manage ? '' : 'table-secondary'}">
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
            <button class="btn btn-outline-primary btn-view-student" 
                    data-student-id="${student.id}">
              <i class="fas fa-eye"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="text-center text-muted py-4">No hay estudiantes en permanencia</td></tr>';
  }

  function updateConclusionTable() {
    const tbody = document.querySelector('#conclusionTable tbody');
    const conclusionStudents = studentsData.filter(s => s.current_phase === 'conclusion');
    
    tbody.innerHTML = conclusionStudents.map(student => `
      <tr data-student-id="${student.id}" class="${student.can_manage ? '' : 'table-secondary'}">
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
    } else if (button.classList.contains('btn-upload-for')) {
      openUploadModal(studentId);
    }
  }

  // ==================== ACCIONES DE ESTUDIANTES ====================
  function viewStudentDetails(studentId) {
    const student = studentsData.find(s => s.id == studentId);
    if (!student) return;
    
    // Por ahora, mostrar alerta con detalles básicos
    alert(`Estudiante: ${student.full_name}\nPrograma: ${student.program_name}\nProgreso: ${student.progress_percentage}%`);
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
          headers: { 'X-CSRF-Token': csrf },
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
});
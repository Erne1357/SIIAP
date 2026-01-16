// app/static/js/admin/settings/program_config.js
(function() {
  'use strict';

  // ============================================
  // FUNCIONES PARA LISTAS DINÁMICAS (Objetivos y Competencias)
  // ============================================

  window.addObjective = function() {
    const container = document.getElementById('objectivesList');
    const count = container.children.length + 1;
    const div = document.createElement('div');
    div.className = 'list-item';
    div.innerHTML = `
      <input type="text" class="form-control" placeholder="Objetivo ${count}">
      <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeListItem(this)">
        <i class="fas fa-trash"></i>
      </button>
    `;
    container.appendChild(div);
    updateObjectivesPreview();
  };

  window.addCompetency = function() {
    const container = document.getElementById('competenciesList');
    const count = container.children.length + 1;
    const div = document.createElement('div');
    div.className = 'list-item';
    div.innerHTML = `
      <input type="text" class="form-control" placeholder="Competencia ${count}">
      <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeListItem(this)">
        <i class="fas fa-trash"></i>
      </button>
    `;
    container.appendChild(div);
    updateProfilePreview();
  };

  window.removeListItem = function(button) {
    button.parentElement.remove();
    updateObjectivesPreview();
    updateProfilePreview();
  };

  function updateObjectivesPreview() {
    const inputs = document.querySelectorAll('#objectivesList input');
    const preview = document.getElementById('objectivesPreview');
    preview.innerHTML = '';
    inputs.forEach(input => {
      if (input.value.trim()) {
        const li = document.createElement('li');
        li.textContent = input.value;
        preview.appendChild(li);
      }
    });
  }

  function updateProfilePreview() {
    const introInput = document.querySelector('[name="graduate_profile_intro"]');
    if (!introInput) return;

    const intro = introInput.value;
    const inputs = document.querySelectorAll('#competenciesList input');
    const introPreview = document.getElementById('profileIntroPreview');
    const preview = document.getElementById('competenciesPreview');

    if (introPreview) {
      introPreview.textContent = intro || 'El egresado de este programa será capaz de:';
    }

    if (preview) {
      preview.innerHTML = '';
      inputs.forEach(input => {
        if (input.value.trim()) {
          const li = document.createElement('li');
          li.textContent = input.value;
          preview.appendChild(li);
        }
      });
    }
  }

  // ============================================
  // EDITOR DE PLAN DE ESTUDIOS (CURRICULUM)
  // ============================================

  let curriculumData = {
    type: 'semestral',
    semesters: []
  };

  window.addSemester = function() {
    const semesterNumber = curriculumData.semesters.length + 1;
    curriculumData.semesters.push({
      semester: semesterNumber,
      courses: []
    });
    renderCurriculumEditor();
  };

  window.removeSemester = function(index) {
    if (confirm('¿Eliminar este semestre y todas sus materias?')) {
      curriculumData.semesters.splice(index, 1);
      // Reindexar semestres
      curriculumData.semesters.forEach((sem, idx) => {
        sem.semester = idx + 1;
      });
      renderCurriculumEditor();
    }
  };

  window.addCourse = function(semesterIndex) {
    curriculumData.semesters[semesterIndex].courses.push({
      name: '',
      code: '',
      credits: '',
      type: 'obligatoria'
    });
    renderCurriculumEditor();
  };

  window.removeCourse = function(semesterIndex, courseIndex) {
    curriculumData.semesters[semesterIndex].courses.splice(courseIndex, 1);
    renderCurriculumEditor();
  };

  function renderCurriculumEditor() {
    const container = document.getElementById('curriculumEditorContainer');
    if (!container) return;

    if (curriculumData.semesters.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-book-open"></i>
          <p>No hay semestres configurados</p>
          <button type="button" class="btn btn-primary" onclick="addSemester()">
            <i class="fas fa-plus me-2"></i>Agregar Primer Semestre
          </button>
        </div>
      `;
      return;
    }

    let html = '<div class="accordion accordion-curriculum" id="curriculumAccordion">';

    curriculumData.semesters.forEach((semester, semIdx) => {
      const collapseId = `collapse-sem-${semIdx}`;
      const isFirst = semIdx === 0;

      html += `
        <div class="accordion-item">
          <h2 class="accordion-header" id="heading-${semIdx}">
            <button class="accordion-button ${isFirst ? '' : 'collapsed'}" type="button" 
                    data-bs-toggle="collapse" data-bs-target="#${collapseId}">
              Semestre ${semester.semester} 
              <span class="badge bg-secondary ms-2">${semester.courses.length} materia(s)</span>
            </button>
          </h2>
          <div id="${collapseId}" class="accordion-collapse collapse ${isFirst ? 'show' : ''}" 
               data-bs-parent="#curriculumAccordion">
            <div class="accordion-body">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">Materias del Semestre ${semester.semester}</h6>
                <div class="btn-group btn-group-sm">
                  <button type="button" class="btn btn-outline-primary" onclick="addCourse(${semIdx})">
                    <i class="fas fa-plus me-1"></i>Agregar Materia
                  </button>
                  <button type="button" class="btn btn-outline-danger" onclick="removeSemester(${semIdx})">
                    <i class="fas fa-trash me-1"></i>Eliminar Semestre
                  </button>
                </div>
              </div>
      `;

      if (semester.courses.length === 0) {
        html += `<p class="text-muted text-center py-3">No hay materias en este semestre</p>`;
      } else {
        semester.courses.forEach((course, courseIdx) => {
          html += `
            <div class="course-item">
              <input type="text" class="form-control form-control-sm" 
                     placeholder="Nombre de la materia" 
                     value="${course.name || ''}"
                     onchange="updateCourse(${semIdx}, ${courseIdx}, 'name', this.value)">
              <input type="text" class="form-control form-control-sm" 
                     placeholder="Código" 
                     value="${course.code || ''}"
                     onchange="updateCourse(${semIdx}, ${courseIdx}, 'code', this.value)">
              <input type="number" class="form-control form-control-sm" 
                     placeholder="Créditos" 
                     value="${course.credits || ''}"
                     onchange="updateCourse(${semIdx}, ${courseIdx}, 'credits', this.value)">
              <select class="form-select form-select-sm" 
                      onchange="updateCourse(${semIdx}, ${courseIdx}, 'type', this.value)">
                <option value="obligatoria" ${course.type === 'obligatoria' ? 'selected' : ''}>Obligatoria</option>
                <option value="optativa" ${course.type === 'optativa' ? 'selected' : ''}>Optativa</option>
                <option value="electiva" ${course.type === 'electiva' ? 'selected' : ''}>Electiva</option>
              </select>
              <button type="button" class="btn btn-sm btn-outline-danger" 
                      onclick="removeCourse(${semIdx}, ${courseIdx})">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          `;
        });
      }

      html += `
            </div>
          </div>
        </div>
      `;
    });

    html += '</div>';

    // Botón para agregar más semestres
    html += `
      <div class="text-center mt-3">
        <button type="button" class="btn btn-outline-primary" onclick="addSemester()">
          <i class="fas fa-plus me-2"></i>Agregar Semestre ${curriculumData.semesters.length + 1}
        </button>
      </div>
    `;

    container.innerHTML = html;
  }

  window.updateCourse = function(semesterIndex, courseIndex, field, value) {
    curriculumData.semesters[semesterIndex].courses[courseIndex][field] = value;
  };

  // ============================================
  // EDITOR DE LÍNEAS DE INVESTIGACIÓN
  // ============================================

  let researchLinesData = [];

  window.addResearchLine = function() {
    researchLinesData.push({
      name: '',
      description: ''
    });
    renderResearchEditor();
  };

  window.removeResearchLine = function(index) {
    if (confirm('¿Eliminar esta línea de investigación?')) {
      researchLinesData.splice(index, 1);
      renderResearchEditor();
    }
  };

  window.updateResearchLine = function(index, field, value) {
    researchLinesData[index][field] = value;
  };

  function renderResearchEditor() {
    const container = document.getElementById('researchEditorContainer');
    if (!container) return;

    if (researchLinesData.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-flask"></i>
          <p>No hay líneas de investigación configuradas</p>
          <button type="button" class="btn btn-primary" onclick="addResearchLine()">
            <i class="fas fa-plus me-2"></i>Agregar Primera Línea
          </button>
        </div>
      `;
      return;
    }

    let html = '';
    researchLinesData.forEach((line, idx) => {
      html += `
        <div class="research-line-card">
          <div class="research-line-header">
            <div class="research-line-content">
              <div class="mb-2">
                <label class="form-label form-label-sm fw-semibold">Nombre de la Línea</label>
                <input type="text" class="form-control" 
                       placeholder="Ej: Inteligencia Artificial y Machine Learning"
                       value="${line.name || ''}"
                       onchange="updateResearchLine(${idx}, 'name', this.value)">
              </div>
              <div>
                <label class="form-label form-label-sm fw-semibold">Descripción</label>
                <textarea class="form-control" rows="3" 
                          placeholder="Descripción de la línea de investigación..."
                          onchange="updateResearchLine(${idx}, 'description', this.value)">${line.description || ''}</textarea>
              </div>
            </div>
            <div class="research-line-actions">
              <button type="button" class="btn btn-outline-danger btn-sm" 
                      onclick="removeResearchLine(${idx})">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>
        </div>
      `;
    });

    html += `
      <div class="text-center mt-3">
        <button type="button" class="btn btn-outline-primary" onclick="addResearchLine()">
          <i class="fas fa-plus me-2"></i>Agregar Línea de Investigación
        </button>
      </div>
    `;

    container.innerHTML = html;
  }

  // ============================================
  // INICIALIZACIÓN Y SUBMIT
  // ============================================

  function initializeEditors(programData) {
    // Inicializar curriculum
    if (programData.curriculum_structure) {
      try {
        curriculumData = typeof programData.curriculum_structure === 'string' 
          ? JSON.parse(programData.curriculum_structure) 
          : programData.curriculum_structure;
        
        // Validar estructura
        if (!curriculumData.type) curriculumData.type = 'semestral';
        if (!curriculumData.semesters) curriculumData.semesters = [];
      } catch (e) {
        console.error('Error parsing curriculum:', e);
        curriculumData = { type: 'semestral', semesters: [] };
      }
    }
    renderCurriculumEditor();

    // Inicializar research lines
    if (programData.research_lines) {
      try {
        researchLinesData = typeof programData.research_lines === 'string'
          ? JSON.parse(programData.research_lines)
          : programData.research_lines;
        
        if (!Array.isArray(researchLinesData)) researchLinesData = [];
      } catch (e) {
        console.error('Error parsing research lines:', e);
        researchLinesData = [];
      }
    }
    renderResearchEditor();
  }

  function collectFormData(form) {
    const formData = new FormData(form);
    const data = {};

    // Campos simples
    for (let [key, value] of formData.entries()) {
      if (key === 'is_active' || key === 'show_curriculum' || key === 'show_hero_cards' ||
          key === 'show_objectives' || key === 'show_graduate_profile' ||
          key === 'show_research_lines' || key === 'show_contact_section' ||
          key === 'show_contact_form') {
        data[key] = true;
      } else {
        data[key] = value || null;
      }
    }

    // Campos booleanos no marcados
    ['is_active', 'show_curriculum', 'show_hero_cards', 'show_objectives',
     'show_graduate_profile', 'show_research_lines', 'show_contact_section',
     'show_contact_form'].forEach(field => {
      if (!(field in data)) {
        data[field] = false;
      }
    });

    // Convertir números
    if (data.duration_semesters) data.duration_semesters = parseInt(data.duration_semesters);
    if (data.duration_years) data.duration_years = parseFloat(data.duration_years);

    // Recopilar objetivos
    const objectives = [];
    document.querySelectorAll('#objectivesList input').forEach(input => {
      if (input.value.trim()) objectives.push(input.value.trim());
    });
    data.objectives = objectives.length > 0 ? objectives : null;

    // Recopilar competencias
    const competencies = [];
    document.querySelectorAll('#competenciesList input').forEach(input => {
      if (input.value.trim()) competencies.push(input.value.trim());
    });
    data.graduate_competencies = competencies.length > 0 ? competencies : null;

    // Agregar datos de curriculum y research desde los editores visuales
    data.curriculum_structure = curriculumData.semesters.length > 0 ? curriculumData : null;
    data.research_lines = researchLinesData.length > 0 ? researchLinesData : null;

    return data;
  }

  // Event listeners al cargar el DOM
  document.addEventListener('DOMContentLoaded', function() {
    // Listeners para vistas previas
    document.querySelectorAll('#objectivesList input').forEach(input => {
      input.addEventListener('input', updateObjectivesPreview);
    });

    document.querySelectorAll('#competenciesList input').forEach(input => {
      input.addEventListener('input', updateProfilePreview);
    });

    const profileIntroInput = document.querySelector('[name="graduate_profile_intro"]');
    if (profileIntroInput) {
      profileIntroInput.addEventListener('input', updateProfilePreview);
    }

    // Inicializar vistas previas
    updateObjectivesPreview();
    updateProfilePreview();

    // Submit del formulario
    const form = document.getElementById('programConfigForm');
    if (form) {
      form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const data = collectFormData(this);
        const programSlug = this.dataset.programSlug;

        try {
          const response = await window.apiClient.patch(`/api/v1/programs/${programSlug}`, data);
          const json = await response.json();

          if (json.flash) {
            json.flash.forEach(f => window.dispatchEvent(new CustomEvent('flash', { detail: f })));
          }

          if (response.ok) {
            setTimeout(() => {
              window.location.href = `/programs/${programSlug}`;
            }, 1500);
          }
        } catch (error) {
          console.error('Error:', error);
          window.dispatchEvent(new CustomEvent('flash', {
            detail: { level: 'danger', message: 'Error al guardar los cambios.' }
          }));
        }
      });
    }
  });

  // Exponer función de inicialización
  window.initializeProgramConfigEditors = initializeEditors;
})();

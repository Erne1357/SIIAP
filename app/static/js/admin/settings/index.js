(() => {
  const API = "/api/v1";
  const tblBody = document.getElementById("tbodyArchives");
  const alerts = document.getElementById("alerts");
  const search = document.getElementById("search");
  const btnReload = document.getElementById("btnReload");
  const btnNew = document.getElementById("btnNew");

  // Modal plantilla
  const modalTpl = new bootstrap.Modal(document.getElementById("modalTemplate"));
  const formTpl = document.getElementById("formTemplate");
  const tplArchiveId = document.getElementById("tplArchiveId");
  const tplFile = document.getElementById("tplFile");

  // Modal editar/crear
  const modalEdit = new bootstrap.Modal(document.getElementById("modalEdit"));
  const formEdit = document.getElementById("formEdit");
  const editTitle = document.getElementById("editTitle");
  const editId = document.getElementById("editId");
  const editName = document.getElementById("editName");
  const editDesc = document.getElementById("editDesc");
  const editStep = document.getElementById("editStep");
  const editIsUploadable = document.getElementById("editIsUploadable");
  const editIsDownloadable = document.getElementById("editIsDownloadable");
  const editAllowCoord = document.getElementById("editAllowCoord");
  const editAllowExt = document.getElementById("editAllowExt");

  // Modal eliminar
  const modalDel = new bootstrap.Modal(document.getElementById("modalDelete"));
  const formDel = document.getElementById("formDelete");
  const delId = document.getElementById("delId");
  const delForce = document.getElementById("delForce");

  let cached = [];
  let steps = [];

  // Función para disparar flash usando el sistema existente
  function flash(msg, type = "success") {
    window.dispatchEvent(new CustomEvent('flash', { 
      detail: { level: type, message: msg } 
    }));
  }

  // Función helper para obtener CSRF token
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  // Validación de archivos
  function validateFile(file) {
    const maxSize = 3 * 1024 * 1024; // 3MB
    const allowedTypes = ['application/pdf'];
    
    if (!file) {
      return { valid: false, error: 'No se ha seleccionado ningún archivo' };
    }
    
    if (!allowedTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.pdf')) {
      return { valid: false, error: 'Solo se permiten archivos PDF' };
    }
    
    if (file.size > maxSize) {
      return { valid: false, error: `El archivo excede el límite de 3MB (actual: ${(file.size / (1024 * 1024)).toFixed(2)}MB)` };
    }
    
    return { valid: true };
  }

  // Función helper para hacer peticiones con manejo de errores mejorado
  async function apiRequest(url, options = {}) {
    const defaultHeaders = {
      'X-CSRF-Token': getCsrfToken()
    };

    // Solo agregar Content-Type para JSON, no para FormData
    if (options.body && typeof options.body === 'string') {
      defaultHeaders['Content-Type'] = 'application/json';
    }

    const defaultOptions = {
      credentials: "same-origin",
      headers: {
        ...defaultHeaders,
        ...options.headers
      }
    };

    const finalOptions = { ...defaultOptions, ...options };

    try {
      const response = await fetch(url, finalOptions);
      
      // Verificar si la respuesta es HTML (redirección o error de permisos)
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('text/html')) {
        throw new Error('No tienes permisos para realizar esta acción o la sesión ha expirado');
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

  function stepName(step_id) {
    const s = steps.find(x => x.id === step_id);
    return s ? `${s.name} · ${s.phase_name}` : "";
  }

  function rowTemplate(a) {
    const tplUrl = a.template_url ? 
      `<a class="template-link" href="${a.template_url}" target="_blank" rel="noopener" title="${a.template_name || 'Descargar'}">${a.template_name || 'Ver plantilla'}</a>` : 
      `<span class="text-muted">—</span>`;
    const stepLabel = a.step_name || stepName(a.step_id) || "";
    
    return `
      <tr data-id="${a.id}" data-name="${(a.name||'').toLowerCase()}" data-step="${(stepLabel||'').toLowerCase()}">
        <td>
          <div class="fw-semibold">${a.name}</div>
          <div class="text-muted small">${a.description||''}</div>
        </td>
        <td>${stepLabel}</td>
        <td class="toggle-cell">
          <input class="form-check-input chk-uploadable" type="checkbox" ${a.is_uploadable ? 'checked':''}>
        </td>
        <td class="toggle-cell">
          <input class="form-check-input chk-downloadable" type="checkbox" ${a.is_downloadable ? 'checked':''}>
        </td>
        <td class="toggle-cell">
          <input class="form-check-input chk-allow-coord" type="checkbox" ${a.allow_coordinator_upload ? 'checked':''}>
        </td>
        <td class="toggle-cell">
          <input class="form-check-input chk-allow-ext" type="checkbox" ${a.allow_extension_request ? 'checked':''}>
        </td>
        <td>${tplUrl}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary btn-edit" title="Editar">
              <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-outline-primary btn-upload-template" title="Subir plantilla">
              <i class="fas fa-upload"></i>
            </button>
            <button class="btn btn-success btn-save" title="Guardar cambios">
              <i class="fas fa-save"></i>
            </button>
            <button class="btn btn-outline-danger btn-delete" title="Eliminar">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  async function loadSteps() {
    try {
      const { data } = await apiRequest(`${API}/archives/steps?scope=permitted`);
      steps = data.items || [];
      
      // Llenar select de steps para crear/editar
      editStep.innerHTML = steps.map(s => 
        `<option value="${s.id}">${s.name} (${s.phase_name})</option>`
      ).join('');
    } catch (err) {
      console.error('Error loading steps:', err);
      flash(`Error cargando steps: ${err.message}`, 'danger');
    }
  }

  async function loadArchives() {
    tblBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">Cargando archivos…</td></tr>`;
    try {
      const { data } = await apiRequest(`${API}/archives?include=step`);
      cached = data.items || [];
      render();
    } catch (err) {
      console.error('Error loading archives:', err);
      tblBody.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-4">${err.message}</td></tr>`;
      flash(`Error cargando archivos: ${err.message}`, 'danger');
    }
  }

  function render() {
    const q = (search.value || "").trim().toLowerCase();
    const items = !q ? cached : cached.filter(a =>
      (a.name || '').toLowerCase().includes(q) ||
      (a.step_name || '').toLowerCase().includes(q)
    );
    
    if (!items.length) {
      tblBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">Sin resultados</td></tr>`;
      return;
    }
    
    tblBody.innerHTML = items.map(rowTemplate).join("");
  }

  // ========= Eventos globales =========
  btnReload?.addEventListener("click", async () => { 
    await loadSteps(); 
    await loadArchives(); 
  });
  
  search?.addEventListener("input", render);

  btnNew?.addEventListener("click", () => {
    editTitle.textContent = "Nuevo archivo";
    editId.value = "";
    editName.value = "";
    editDesc.value = "";
    editIsUploadable.checked = false;
    editIsDownloadable.checked = false;
    editAllowCoord.checked = false;
    editAllowExt.checked = false;
    if (steps.length) editStep.value = steps[0].id;
    modalEdit.show();
  });

  tblBody?.addEventListener("click", async (ev) => {
    const tr = ev.target.closest("tr");
    if (!tr) return;
    const id = tr.getAttribute("data-id");
    if (!id) return;

    if (ev.target.closest(".btn-upload-template")) {
      tplArchiveId.value = id;
      tplFile.value = "";
      modalTpl.show();
      return;
    }

    if (ev.target.closest(".btn-save")) {
      const body = {
        is_uploadable: tr.querySelector(".chk-uploadable").checked,
        is_downloadable: tr.querySelector(".chk-downloadable").checked,
        allow_coordinator_upload: tr.querySelector(".chk-allow-coord").checked,
        allow_extension_request: tr.querySelector(".chk-allow-ext").checked
      };
      
      try {
        await apiRequest(`${API}/archives/${id}`, {
          method: "PUT",
          body: JSON.stringify(body)
        });
        
        flash("Configuración guardada correctamente", "success");
        await loadArchives();
      } catch (err) {
        flash(`Error al guardar: ${err.message}`, "danger");
      }
      return;
    }

    if (ev.target.closest(".btn-edit")) {
      const row = cached.find(x => String(x.id) === String(id));
      if (!row) return;
      
      editTitle.textContent = "Editar archivo";
      editId.value = row.id;
      editName.value = row.name || "";
      editDesc.value = row.description || "";
      editIsUploadable.checked = !!row.is_uploadable;
      editIsDownloadable.checked = !!row.is_downloadable;
      editAllowCoord.checked = !!row.allow_coordinator_upload;
      editAllowExt.checked = !!row.allow_extension_request;
      editStep.value = row.step_id;
      modalEdit.show();
      return;
    }

    if (ev.target.closest(".btn-delete")) {
      delId.value = id;
      delForce.checked = false;
      modalDel.show();
      return;
    }
  });

  // ========= Form plantilla =========
  formTpl?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = tplArchiveId.value;
    
    if (!tplFile.files.length) { 
      flash("Selecciona un archivo", "warning"); 
      return; 
    }
    
    // Validar archivo
    const validation = validateFile(tplFile.files[0]);
    if (!validation.valid) {
      flash(validation.error, "danger");
      return;
    }
    
    const fd = new FormData();
    fd.append("file", tplFile.files[0]);
    
    try {
      const { data } = await apiRequest(`${API}/archives/${id}/template`, {
        method: "POST",
        body: fd
      });
      
      flash("Plantilla actualizada correctamente", "success");
      modalTpl.hide();
      await loadArchives();
    } catch (err) {
      flash(`Error subiendo plantilla: ${err.message}`, "danger");
    }
  });

  // Validación en tiempo real para el input de archivo de plantilla
  tplFile?.addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    
    const validation = validateFile(file);
    const feedback = ev.target.parentElement.querySelector('.file-feedback') || 
                     document.createElement('div');
    
    if (!ev.target.parentElement.querySelector('.file-feedback')) {
      feedback.className = 'file-feedback small mt-1';
      ev.target.parentElement.appendChild(feedback);
    }
    
    if (!validation.valid) {
      feedback.className = 'file-feedback small mt-1 text-danger';
      feedback.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${validation.error}`;
    } else {
      feedback.className = 'file-feedback small mt-1 text-success';
      feedback.innerHTML = `<i class="fas fa-check"></i> Archivo válido (${(file.size / (1024 * 1024)).toFixed(2)}MB)`;
    }
  });

  // ========= Form editar/crear =========
  formEdit?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    
    const body = {
      name: editName.value.trim(),
      description: editDesc.value.trim(),
      step_id: Number(editStep.value),
      is_uploadable: editIsUploadable.checked,
      is_downloadable: editIsDownloadable.checked,
      allow_coordinator_upload: editAllowCoord.checked,
      allow_extension_request: editAllowExt.checked
    };
    
    if (!body.name) {
      flash("El nombre es requerido", "warning");
      return;
    }
    
    try {
      const isEdit = !!editId.value;
      const url = isEdit ? `${API}/archives/${editId.value}` : `${API}/archives`;
      const method = isEdit ? "PUT" : "POST";
      
      await apiRequest(url, {
        method,
        body: JSON.stringify(body)
      });
      
      flash(`Archivo ${isEdit ? 'actualizado' : 'creado'} correctamente`, "success");
      modalEdit.hide();
      await loadArchives();
    } catch (err) {
      flash(`Error al guardar: ${err.message}`, "danger");
    }
  });

  // ========= Form eliminar =========
  formDel?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = delId.value;
    const force = delForce.checked ? "?force=true" : "";
    
    try {
      const response = await fetch(`${API}/archives/${id}${force}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
          'X-CSRF-Token': getCsrfToken()
        }
      });

      // Verificar si es HTML en lugar de JSON
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('text/html')) {
        throw new Error('No tienes permisos para realizar esta acción');
      }

      const data = await response.json();
      
      if (response.status === 409 && data.requires_force) {
        flash(data.message || "Tiene submissions; marca 'Eliminar forzado' para continuar", "warning");
        return;
      }
      
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || "No se pudo eliminar");
      }
      
      flash("Archivo eliminado correctamente", "success");
      modalDel.hide();
      await loadArchives();
    } catch (err) {
      flash(`Error al eliminar: ${err.message}`, "danger");
    }
  });

  // Inicialización
  (async () => {
    try {
      await loadSteps();
      await loadArchives();
    } catch (err) {
      flash(`Error inicializando la página: ${err.message}`, 'danger');
    }
  })();
})();
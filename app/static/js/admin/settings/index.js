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
  let steps = []; // steps permitidos para el usuario actual
  let stepTabs = [];

  function flash(msg, type="success", target=alerts) {
    const el = document.createElement("div");
    el.className = `alert alert-${type} alert-dismissible fade show`;
    el.innerHTML = `<div>${msg}</div><button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    target.prepend(el);
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el).close(), 5000);
  }

  function stepName(step_id) {
    const s = steps.find(x => x.id === step_id);
    return s ? `${s.name} · ${s.phase_name}` : "";
  }

  function rowTemplate(a) {
    const tplUrl = a.template_url ? `<a class="template-link" href="${a.template_url}" target="_blank" rel="noopener">${a.template_name || 'Descargar'}</a>` : `<span class="text-muted">—</span>`;
    const stepLabel = a.step_name || stepName(a.step_id) || "";
    return `
      <tr data-id="${a.id}" data-name="${(a.name||'').toLowerCase()}" data-step="${(stepLabel||'').toLowerCase()}">
        <td><div class="fw-semibold">${a.name}</div><div class="text-muted small">${a.description||''}</div></td>
        <td>${stepLabel}</td>
        <td class="toggle-cell"><input class="form-check-input chk-uploadable" type="checkbox" ${a.is_uploadable ? 'checked':''}></td>
        <td class="toggle-cell"><input class="form-check-input chk-downloadable" type="checkbox" ${a.is_downloadable ? 'checked':''}></td>
        <td class="toggle-cell"><input class="form-check-input chk-allow-coord" type="checkbox" ${a.allow_coordinator_upload ? 'checked':''}></td>
        <td class="toggle-cell"><input class="form-check-input chk-allow-ext" type="checkbox" ${a.allow_extension_request ? 'checked':''}></td>
        <td>${tplUrl}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-secondary btn-edit">Editar</button>
          <button class="btn btn-sm btn-outline-danger btn-delete">Eliminar</button>
          <button class="btn btn-sm btn-outline-primary btn-upload-template">Subir plantilla</button>
          <button class="btn btn-sm btn-primary btn-save">Guardar toggles</button>
        </td>
      </tr>
    `;
  }

  async function loadSteps() {
    const res = await fetch(`${API}/archives/steps?scope=permitted`, { credentials: "same-origin" });
    const data = await res.json();
    steps = data.items || [];
    stepTabs = ["Admisión", "Permanencia", "Conclusión"];
    renderTabs(stepTabs);
  }

  function renderTabs(tabs) {
    const tabsContainer = document.getElementById('stepsTabContent');
    tabsContainer.innerHTML = "";
    tabs.forEach((tab, idx) => {
      const tabId = `tab-${idx}`;
      const tabPaneId = `pane-${idx}`;
      tabsContainer.innerHTML += `
        <ul class="nav nav-pills" id="${tabId}" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="btn-${tabId}" data-bs-toggle="pill" data-bs-target="#${tabPaneId}" type="button" role="tab">${tab}</button>
          </li>
        </ul>
        <div class="tab-pane fade show active" id="${tabPaneId}" role="tabpanel" aria-labelledby="btn-${tabId}">
          <div class="table-responsive" id="table-${tabPaneId}">
            <!-- Tabla para los pasos cargados -->
          </div>
        </div>`;
      renderStepTable(tab);
    });
  }

  function renderStepTable(tabName) {
    const tableId = `table-${tabName}`;
    const stepTable = document.getElementById(tableId);
    const filteredSteps = steps.filter(step => step.phase_name === tabName);
    stepTable.innerHTML = `
      <table class="table table-sm align-middle">
        <thead class="table-light">
          <tr>
            <th>Pasos</th>
            <th class="text-end">Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${filteredSteps.map(step => `
            <tr>
              <td>${step.name}</td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-primary btn-edit">Editar</button>
                <button class="btn btn-sm btn-outline-danger btn-delete">Eliminar</button>
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    `;
  }

  async function loadArchives() {
    tblBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">Cargando…</td></tr>`;
    try {
      const res = await fetch(`${API}/archives?include=step`, { credentials: "same-origin" });
      if (!res.ok) throw new Error("No se pudo cargar el catálogo de archivos");
      const data = await res.json();
      cached = (data.items || []);
      render();
    } catch (err) {
      tblBody.innerHTML = `<tr><td colspan="8" class="text-danger">${err.message}</td></tr>`;
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
  btnReload.addEventListener("click", async () => { await loadSteps(); await loadArchives(); });
  search.addEventListener("input", render);

  btnNew.addEventListener("click", () => {
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

  tblBody.addEventListener("click", async (ev) => {
    const tr = ev.target.closest("tr");
    if (!tr) return;
    const id = tr.getAttribute("data-id");

    if (ev.target.classList.contains("btn-upload-template")) {
      tplArchiveId.value = id;
      tplFile.value = "";
      modalTpl.show();
      return;
    }

    if (ev.target.classList.contains("btn-save")) {
      const body = {
        is_uploadable: tr.querySelector(".chk-uploadable").checked,
        is_downloadable: tr.querySelector(".chk-downloadable").checked,
        allow_coordinator_upload: tr.querySelector(".chk-allow-coord").checked,
        allow_extension_request: tr.querySelector(".chk-allow-ext").checked
      };
      try {
        const res = await fetch(`${API}/archives/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify(body)
        });
        const data = await res.json();
        if (!res.ok || data.ok === false) throw new Error(data.error || "Error al guardar");
        flash("Toggles guardados");
        await loadArchives();
      } catch (err) {
        flash(err.message, "danger");
      }
    }

    if (ev.target.classList.contains("btn-edit")) {
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
      if (!steps.find(s => s.id === row.step_id)) {
        const opt = document.createElement("option");
        opt.value = row.step_id;
        opt.textContent = row.step_name || `Step ${row.step_id}`;
        editStep.appendChild(opt);
      }
      editStep.value = row.step_id;
      modalEdit.show();
      return;
    }

    if (ev.target.classList.contains("btn-delete")) {
      delId.value = id;
      delForce.checked = false;
      modalDel.show();
      return;
    }
  });

  // ========= Form plantilla =========
  formTpl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = tplArchiveId.value;
    if (!tplFile.files.length) { flash("Selecciona un archivo.", "warning"); return; }
    const fd = new FormData();
    fd.append("file", tplFile.files[0]);
    try {
      const res = await fetch(`${API}/archives/${id}/template`, {
        method: "POST",
        body: fd,
        credentials: "same-origin"
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo subir la plantilla");
      flash("Plantilla actualizada");
      modalTpl.hide();
      await loadArchives();
    } catch (err) {
      flash(err.message, "danger");
    }
  });

  // ========= Form editar/crear =========
  formEdit.addEventListener("submit", async (ev) => {
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
    try {
      let res, data;
      if (editId.value) {
        res = await fetch(`${API}/archives/${editId.value}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify(body)
        });
      } else {
        res = await fetch(`${API}/archives`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify(body)
        });
      }
      data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo guardar");
      flash("Archivo guardado");
      modalEdit.hide();
      await loadArchives();
    } catch (err) {
      flash(err.message, "danger");
    }
  });

  // ========= Form eliminar =========
  formDel.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = delId.value;
    const force = delForce.checked ? "?force=true" : "";
    try {
      const res = await fetch(`${API}/archives/${id}${force}`, {
        method: "DELETE",
        credentials: "same-origin"
      });
      const data = await res.json();
      if (res.status === 409 && data.requires_force) {
        flash(data.message || "Tiene submissions; marca 'Eliminar forzado' para continuar.", "warning");
        return;
      }
      if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo eliminar");
      flash("Archivo eliminado");
      modalDel.hide();
      await loadArchives();
    } catch (err) {
      flash(err.message, "danger");
    }
  });

  // Inicialización
  (async () => {
    await loadSteps();
    await loadArchives();
  })();
})();

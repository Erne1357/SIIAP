(() => {
    const API = "/api/v1";
    const alerts = document.getElementById("alerts");
    const tbody = document.getElementById("tbodyPolicies");
    const form = document.getElementById("formPolicy");
    const polId = document.getElementById("polId");
    const polArchive = document.getElementById("polArchive");
    const polForever = document.getElementById("polForever");
    const polYears = document.getElementById("polYears");
    const polAfter = document.getElementById("polAfter");
    const btnReset = document.getElementById("btnReset");
    const btnDelete = document.getElementById("btnDelete");

    let archives = [];
    let policies = [];

    function flash(msg, type = "success") {
        const el = document.createElement("div");
        el.className = `alert alert-${type} alert-dismissible fade show`;
        el.innerHTML = `<div>${msg}</div><button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        alerts.prepend(el);
        setTimeout(() => bootstrap.Alert.getOrCreateInstance(el).close(), 5000);
    }

    function renderArchivesOptions() {
        polArchive.innerHTML = archives.map(a => `<option value="${a.id}">${a.name}</option>`).join("");
    }

    function renderPolicies() {
        if (!policies.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">Sin políticas</td></tr>`;
            return;
        }
        tbody.innerHTML = policies.map(p => {
            const a = archives.find(x => x.id === p.archive_id);
            return `
        <tr data-id="${p.id}">
          <td>${a ? a.name : p.archive_id}</td>
          <td class="text-center">${p.keep_forever ? "Sí" : "No"}</td>
          <td class="text-center">${p.keep_forever ? "—" : (p.keep_years ?? "—")}</td>
          <td>${p.apply_after}</td>
          <td class="text-end">
            <button class="btn btn-sm btn-outline-primary btn-edit">Editar</button>
          </td>
        </tr>
      `;
        }).join("");
    }

    async function loadAll() {
        // archivos (para selector y vista)
        const aRes = await fetch(`${API}/archives?include=step`, { credentials: "same-origin" });
        const aData = await aRes.json();
        archives = aData.items || [];
        renderArchivesOptions();

        // políticas
        const pRes = await fetch(`${API}/retention/policies`, { credentials: "same-origin" });
        const pData = await pRes.json();
        policies = pData.items || [];
        renderPolicies();
    }

    tbody.addEventListener("click", (ev) => {
        const tr = ev.target.closest("tr[data-id]");
        if (!tr) return;
        const id = Number(tr.getAttribute("data-id"));
        if (ev.target.classList.contains("btn-edit")) {
            const p = policies.find(x => x.id === id);
            if (!p) return;
            polId.value = p.id;
            polArchive.value = String(p.archive_id);
            polForever.checked = !!p.keep_forever;
            polYears.value = p.keep_years || "";
            polAfter.value = p.apply_after || "graduated";
            btnDelete.classList.remove("d-none");
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    });

    form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const body = {
            archive_id: Number(polArchive.value),
            keep_forever: polForever.checked,
            keep_years: polForever.checked ? null : Number(polYears.value || 0),
            apply_after: polAfter.value
        };
        try {
            let res, data;
            if (polId.value) {
                res = await fetch(`${API}/retention/policies/${polId.value}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    credentials: "same-origin",
                    body: JSON.stringify(body)
                });
            } else {
                res = await fetch(`${API}/retention/policies`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "same-origin",
                    body: JSON.stringify(body)
                });
            }
            data = await res.json();
            if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo guardar");
            flash("Política guardada");
            btnReset.click();
            await loadAll();
        } catch (err) {
            flash(err.message, "danger");
        }
    });

    btnReset.addEventListener("click", () => {
        polId.value = "";
        polArchive.selectedIndex = 0;
        polForever.checked = false;
        polYears.value = "";
        polAfter.value = "graduated";
        btnDelete.classList.add("d-none");
    });

    btnDelete.addEventListener("click", async () => {
        if (!polId.value) return;
        if (!confirm("¿Eliminar esta política? Esta acción no se puede deshacer.")) return;
        try {
            const res = await fetch(`${API}/retention/policies/${polId.value}`, {
                method: "DELETE",
                credentials: "same-origin"
            });
            const data = await res.json();
            if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo eliminar");
            flash("Política eliminada");
            btnReset.click();
            await loadAll();
        } catch (err) {
            flash(err.message, "danger");
        }
    });
    // al final de retention.js, agrega:
    const btnCandidates = document.getElementById("btnCandidates");
    if (btnCandidates) {
        btnCandidates.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/v1/retention/candidates", { credentials: "same-origin" });
                const data = await res.json();
                if (!res.ok || data.ok === false) throw new Error(data.error || "No se pudo traer candidatos");
                const count = data.count || (data.items ? data.items.length : 0);
                flash(`Candidatos a eliminación: ${count}`, "info");
                // si quieres mostrar el listado en modal, puedo pasarte un modal rápido
            } catch (err) {
                flash(err.message, "danger");
            }
        });
    }

    loadAll();
})();
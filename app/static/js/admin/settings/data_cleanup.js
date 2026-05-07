// app/static/js/admin/settings/data_cleanup.js
//
// Pantalla de limpieza con respaldo ZIP previo.
//
// Flujo por categoría:
//   1. listCandidates(category) → tabla con checkboxes
//   2. start(purge_type, ids)   → POST /start → run_id + archive_url
//   3. download(archive_url)    → cliente baja ZIP, backend marca downloaded
//   4. confirmPurge(run_id)     → POST /confirm → borrado físico
//
// Se apoya en window.PURGE_API definido por la plantilla.

(function () {
  'use strict';

  const CATEGORIES = [
    'admission_expired_with_files',
    'admission_delta3_plus',
    'retention_policy',
  ];

  const selectionByCategory = {};
  let currentRunId = null;

  // ── Utils ──────────────────────────────────────────────────────────────
  function getCsrf() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  }

  function flash(level, message) {
    if (typeof showFlash === 'function') showFlash(level, message);
    else console.log(`[${level}]`, message);
  }

  function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str == null ? '' : str);
    return div.innerHTML;
  }

  function formatBytes(bytes) {
    if (!bytes) return '—';
    const u = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let v = bytes;
    while (v >= 1024 && i < u.length - 1) {
      v /= 1024;
      i++;
    }
    return `${v.toFixed(1)} ${u[i]}`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-MX', {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  }

  // ── Render tabla candidatos ────────────────────────────────────────────
  function renderTable(category, items) {
    const container = document.querySelector(
      `[data-table-container="${category}"]`
    );
    if (!container) return;

    document.getElementById(`badge-${badgeKey(category)}`).textContent = items.length;

    if (!items.length) {
      container.innerHTML = `
        <div class="cleanup-empty">
          <i class="bi bi-check-circle me-1"></i>
          No hay candidatos en esta categoría.
        </div>`;
      updateStartButton(category);
      return;
    }

    selectionByCategory[category] = new Set();

    const rows = items.map(it => `
      <tr>
        <td>
          <input type="checkbox" class="form-check-input cleanup-row-check"
                 data-up-id="${it.user_program_id}">
        </td>
        <td>${escHtml(it.name || '')}</td>
        <td>${escHtml(it.email || '')}</td>
        <td>${escHtml(it.program_name || '')}</td>
        <td>${escHtml(it.admission_status || '')}</td>
        <td>${escHtml(it.admission_period || '—')}</td>
        <td class="files-badge">${it.files_count || 0}</td>
        <td class="files-badge">${formatBytes(it.total_size_bytes)}</td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm cleanup-table align-middle">
          <thead>
            <tr>
              <th style="width:40px;">
                <input type="checkbox" class="form-check-input cleanup-select-all">
              </th>
              <th>Nombre</th>
              <th>Email</th>
              <th>Programa</th>
              <th>Estado</th>
              <th>Periodo admisión</th>
              <th>Archivos</th>
              <th>Tamaño</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;

    container.querySelector('.cleanup-select-all')?.addEventListener('change', (e) => {
      const checked = e.target.checked;
      container.querySelectorAll('.cleanup-row-check').forEach(cb => {
        cb.checked = checked;
        const id = parseInt(cb.dataset.upId, 10);
        if (checked) selectionByCategory[category].add(id);
        else selectionByCategory[category].delete(id);
      });
      updateStartButton(category);
    });

    container.querySelectorAll('.cleanup-row-check').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(e.target.dataset.upId, 10);
        if (e.target.checked) selectionByCategory[category].add(id);
        else selectionByCategory[category].delete(id);
        updateStartButton(category);
      });
    });

    updateStartButton(category);
  }

  function badgeKey(category) {
    if (category === 'admission_expired_with_files') return 'expired-files';
    if (category === 'admission_delta3_plus') return 'delta3';
    if (category === 'retention_policy') return 'retention';
    return category;
  }

  function updateStartButton(category) {
    const btn = document.querySelector(
      `[data-action="start-purge"][data-category="${category}"]`
    );
    if (!btn) return;
    const count = (selectionByCategory[category] || new Set()).size;
    btn.disabled = count === 0;
    btn.innerHTML = `<i class="bi bi-file-earmark-zip me-1"></i>` +
      (count ? `Generar respaldo de ${count} seleccionado(s)` : `Generar respaldo de seleccionados`);
  }

  // ── Cargar candidatos ──────────────────────────────────────────────────
  async function loadCandidates(category) {
    try {
      const res = await fetch(`${window.PURGE_API.candidates}?category=${category}`, {
        headers: { 'Accept': 'application/json' },
      });
      const json = await res.json();
      if (!res.ok) {
        flash('danger', json?.error?.message || 'Error al cargar candidatos');
        return;
      }
      renderTable(category, json.data || []);
    } catch (e) {
      flash('danger', `Error de red: ${e.message}`);
    }
  }

  // ── Generar respaldo ZIP ───────────────────────────────────────────────
  async function startPurge(category, purgeType) {
    const ids = Array.from(selectionByCategory[category] || []);
    if (!ids.length) {
      flash('warning', 'Selecciona al menos un registro.');
      return;
    }

    const btn = document.querySelector(
      `[data-action="start-purge"][data-category="${category}"]`
    );
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Generando ZIP...`;
    }

    try {
      const res = await fetch(window.PURGE_API.start, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify({
          user_program_ids: ids,
          purge_type: purgeType,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        flash('danger', json?.error?.message || 'Error al generar respaldo');
        return;
      }

      (json.flash || []).forEach(f => flash(f.level, f.message));

      const run = json.data?.run;
      if (run) {
        currentRunId = run.run_id;
        triggerDownload(json.data.archive_url, `purge_${run.run_id}.zip`);
        // Mostrar modal de confirmación tras pequeño delay para asegurar que descarga inició
        setTimeout(() => openConfirmModal(run.run_id), 800);
        await loadCandidates(category);
        await loadRuns();
      }
    } catch (e) {
      flash('danger', `Error de red: ${e.message}`);
    } finally {
      updateStartButton(category);
    }
  }

  function triggerDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || '';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1000);
  }

  // ── Confirmar purga física ─────────────────────────────────────────────
  function openConfirmModal(run_id) {
    currentRunId = run_id;
    document.getElementById('confirmRunId').textContent = run_id;
    const check = document.getElementById('confirmDownloadedCheck');
    if (check) check.checked = false;
    const btn = document.getElementById('btnDoConfirmPurge');
    if (btn) btn.disabled = true;
    const modal = bootstrap.Modal.getOrCreateInstance(
      document.getElementById('modalConfirmPurge')
    );
    modal.show();
  }

  async function doConfirmPurge() {
    if (!currentRunId) return;
    const btn = document.getElementById('btnDoConfirmPurge');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Borrando...`;
    try {
      const res = await fetch(window.PURGE_API.confirm(currentRunId), {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf() },
      });
      const json = await res.json();
      (json.flash || []).forEach(f => flash(f.level, f.message));
      if (res.ok) {
        const modal = bootstrap.Modal.getInstance(
          document.getElementById('modalConfirmPurge')
        );
        modal?.hide();
        CATEGORIES.forEach(c => loadCandidates(c));
        loadRuns();
      } else {
        flash('danger', json?.error?.message || 'Error al confirmar purga');
      }
    } catch (e) {
      flash('danger', `Error de red: ${e.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-trash me-1"></i>Borrar archivos del servidor`;
    }
  }

  // ── Cancelar run ───────────────────────────────────────────────────────
  async function cancelRun(run_id) {
    if (!confirm(`¿Cancelar el respaldo ${run_id}? Se borrará el ZIP del servidor sin purgar datos.`)) {
      return;
    }
    try {
      const res = await fetch(window.PURGE_API.cancel(run_id), {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf() },
      });
      const json = await res.json();
      (json.flash || []).forEach(f => flash(f.level, f.message));
      loadRuns();
    } catch (e) {
      flash('danger', `Error: ${e.message}`);
    }
  }

  // ── Lista de runs ──────────────────────────────────────────────────────
  async function loadRuns() {
    try {
      const res = await fetch(window.PURGE_API.runs);
      const json = await res.json();
      const container = document.getElementById('runsTableContainer');
      if (!container) return;

      const runs = json.data || [];
      if (!runs.length) {
        container.innerHTML = `<div class="cleanup-empty">No hay respaldos generados.</div>`;
        return;
      }

      const rows = runs.map(r => {
        const actions = [];
        if (r.status === 'pending_download' || r.status === 'downloaded') {
          actions.push(`<a class="btn btn-sm btn-outline-primary"
                           href="${window.PURGE_API.archive(r.run_id)}"
                           download="purge_${r.run_id}.zip">
                          <i class="bi bi-download"></i></a>`);
        }
        if (r.status === 'downloaded' && r.purge_type !== 'transition_snapshot') {
          actions.push(`<button class="btn btn-sm btn-danger"
                                data-action="open-confirm" data-run-id="${r.run_id}">
                          <i class="bi bi-trash"></i></button>`);
        }
        if (r.status === 'pending_download' || r.status === 'downloaded') {
          actions.push(`<button class="btn btn-sm btn-outline-secondary"
                                data-action="cancel-run" data-run-id="${r.run_id}">
                          <i class="bi bi-x-lg"></i></button>`);
        }
        return `
          <tr>
            <td><code>${escHtml(r.run_id.slice(0, 8))}</code></td>
            <td>${escHtml(r.purge_type)}</td>
            <td>${r.item_count}</td>
            <td>${formatBytes(r.archive_size_bytes)}</td>
            <td>${fmtDate(r.initiated_at)}</td>
            <td>${fmtDate(r.expires_at)}</td>
            <td><span class="status-pill ${r.status}">${escHtml(r.status)}</span></td>
            <td class="actions-col">${actions.join(' ')}</td>
          </tr>`;
      }).join('');

      container.innerHTML = `
        <div class="table-responsive">
          <table class="table table-sm runs-table align-middle">
            <thead>
              <tr>
                <th>Run</th>
                <th>Tipo</th>
                <th>Items</th>
                <th>Tamaño</th>
                <th>Generado</th>
                <th>Expira</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    } catch (e) {
      flash('danger', `Error al cargar respaldos: ${e.message}`);
    }
  }

  // ── Bindings ───────────────────────────────────────────────────────────
  function bindGlobalActions() {
    document.body.addEventListener('click', (e) => {
      const reload = e.target.closest('[data-action="reload"]');
      if (reload) {
        loadCandidates(reload.dataset.category);
        return;
      }
      const reloadRuns = e.target.closest('[data-action="reload-runs"]');
      if (reloadRuns) {
        loadRuns();
        return;
      }
      const start = e.target.closest('[data-action="start-purge"]');
      if (start) {
        startPurge(start.dataset.category, start.dataset.purgeType);
        return;
      }
      const openConfirm = e.target.closest('[data-action="open-confirm"]');
      if (openConfirm) {
        openConfirmModal(openConfirm.dataset.runId);
        return;
      }
      const cancel = e.target.closest('[data-action="cancel-run"]');
      if (cancel) {
        cancelRun(cancel.dataset.runId);
        return;
      }
    });

    document.getElementById('confirmDownloadedCheck')?.addEventListener('change', (e) => {
      const btn = document.getElementById('btnDoConfirmPurge');
      if (btn) btn.disabled = !e.target.checked;
    });

    document.getElementById('btnDoConfirmPurge')?.addEventListener('click', doConfirmPurge);
  }

  // ── Init ───────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    bindGlobalActions();
    CATEGORIES.forEach(c => loadCandidates(c));
    loadRuns();
  });
})();

/* app/static/js/admin/settings/permissions.js
 * Gestión de permisos por rol (catálogo, seed, overrides, auditoría, toast).
 */
(function () {
  'use strict';

  function getCsrf() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  }

  let currentRoleId = null;
  let catalogAll = [];

  // ── Inicialización ──────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    loadCatalog();

    // Delegación: botones de rol, botones de acción
    document.getElementById('roleList')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.list-group-item[data-role-id]');
      if (btn) loadRole(parseInt(btn.dataset.roleId), btn.dataset.roleName);
    });

    document.getElementById('btnRefreshAudit')?.addEventListener('click', loadAudit);
    document.getElementById('filterResource')?.addEventListener('change', filterCatalog);
    document.getElementById('btnSubmitOverride')?.addEventListener('click', submitOverride);
    document.getElementById('seedFilter')?.addEventListener('input', (e) =>
      filterTable(e.target.value, 'seedTable')
    );

    document.getElementById('overridesBody')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.js-revert-override');
      if (btn) revertOverride(btn.dataset.codename);
    });

    // Cargar primer rol por defecto
    const firstBtn = document.querySelector('#roleList .list-group-item');
    if (firstBtn) loadRole(parseInt(firstBtn.dataset.roleId), firstBtn.dataset.roleName);

    // Tiempo real: otro postgrad_admin agregó/revirtió un override
    window.addEventListener('siiap:role_permission:changed', (e) => {
      const d = e.detail || {};
      const verb = d.action === 'grant' ? 'agregado' : 'revertido';
      showToast(`Override ${verb} en rol "${d.role_name}": ${d.codename}. Actualizando...`, 'info');
      // Si el rol afectado es el actualmente cargado, refrescar su panel
      if (currentRoleId && d.role_id === currentRoleId) {
        loadRole(currentRoleId, document.getElementById('currentRoleName').textContent);
      } else {
        loadAudit();
      }
    });
  });

  // ── Catálogo ────────────────────────────────────────────────────────────
  async function loadCatalog() {
    const res = await fetch('/api/v1/permissions/catalog');
    const { data } = await res.json();
    catalogAll = data || [];
    populateCatalogSelect(catalogAll);
  }

  function populateCatalogSelect(perms) {
    const sel = document.getElementById('selectCodename');
    if (!sel) return;
    sel.innerHTML = perms.length
      ? perms.map(p => `<option value="${p.codename}">${p.codename} — ${p.display_name}</option>`).join('')
      : '<option disabled>Sin resultados</option>';
  }

  function filterCatalog() {
    const resource = document.getElementById('filterResource').value;
    const filtered = resource ? catalogAll.filter(p => p.resource === resource) : catalogAll;
    populateCatalogSelect(filtered);
  }

  // ── Cargar permisos de un rol ───────────────────────────────────────────
  async function loadRole(roleId, roleName) {
    currentRoleId = roleId;
    document.getElementById('currentRoleName').textContent = roleName;
    document.getElementById('btnAddOverride').disabled = false;

    document.querySelectorAll('#roleList .list-group-item').forEach(b => {
      b.classList.toggle('active', parseInt(b.dataset.roleId) === roleId);
    });

    const res = await fetch(`/api/v1/permissions/roles/${roleId}`);
    const { data } = await res.json();

    renderSeed(data.seed_permissions || []);
    renderOverrides(data.overrides || []);
    loadAudit();
  }

  function renderSeed(perms) {
    document.getElementById('seedCount').textContent = perms.length;
    const tbody = document.getElementById('seedBody');
    if (!perms.length) {
      tbody.innerHTML = '<tr><td colspan="3" class="text-muted text-center py-2">Sin permisos base.</td></tr>';
      return;
    }
    tbody.innerHTML = perms.map(p => `
      <tr>
        <td><code class="small">${p.codename}</code></td>
        <td class="text-muted small">${p.display_name}</td>
        <td><span class="badge bg-light text-secondary border">${p.perm_type}</span></td>
      </tr>
    `).join('');
  }

  function renderOverrides(overrides) {
    const active = overrides.filter(o => o.is_active);
    document.getElementById('overrideCount').textContent = active.length;
    const tbody = document.getElementById('overridesBody');
    if (!overrides.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center py-2">Sin overrides registrados.</td></tr>';
      return;
    }
    tbody.innerHTML = overrides.map(o => `
      <tr class="${o.is_active ? '' : 'table-secondary text-muted'}">
        <td><code class="small">${o.permission_codename}</code>
          ${o.is_seed_duplicate ? '<span class="badge bg-info ms-1 small">ya en seed</span>' : ''}
        </td>
        <td>
          ${o.is_active
            ? '<span class="badge bg-success">Activo</span>'
            : '<span class="badge bg-secondary">Revertido</span>'}
        </td>
        <td class="small">${o.created_at ? new Date(o.created_at).toLocaleDateString() : '—'}</td>
        <td class="small">${o.revoked_at ? new Date(o.revoked_at).toLocaleDateString() : '—'}</td>
        <td>
          ${o.is_active
            ? `<button class="btn btn-sm btn-outline-danger js-revert-override" data-codename="${o.permission_codename}">
                 <i class="fas fa-undo"></i>
               </button>`
            : ''}
        </td>
      </tr>
    `).join('');
  }

  // ── Overrides (agregar / revertir) ──────────────────────────────────────
  async function submitOverride() {
    const codename = document.getElementById('selectCodename').value;
    const reason   = document.getElementById('overrideReason').value.trim();
    if (!codename) { showToast('Selecciona un permiso.', 'warning'); return; }

    const res = await fetch(`/api/v1/permissions/roles/${currentRoleId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      body: JSON.stringify({ codename, reason: reason || null }),
    });
    const body = await res.json();
    if (res.ok) {
      bootstrap.Modal.getInstance(document.getElementById('addOverrideModal')).hide();
      showToast(body.flash?.[0]?.[0] ?? 'Override agregado.', 'success');
      loadRole(currentRoleId, document.getElementById('currentRoleName').textContent);
    } else {
      showToast(body.error ?? 'Error al agregar override.', 'danger');
    }
  }

  async function revertOverride(codename) {
    const ok = await siiapConfirm({
      type: 'warning',
      title: 'Revertir override',
      message: `¿Revertir el override de "${codename}" para este rol?`,
      confirmLabel: 'Sí, revertir',
    });
    if (!ok) return;
    const res = await fetch(`/api/v1/permissions/roles/${currentRoleId}/override/${codename}`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrf() },
    });
    const body = await res.json();
    if (res.ok) {
      showToast(body.flash?.[0]?.[0] ?? 'Override revertido.', 'success');
      loadRole(currentRoleId, document.getElementById('currentRoleName').textContent);
    } else {
      showToast(body.error ?? 'Error al revertir.', 'danger');
    }
  }

  // ── Auditoría ───────────────────────────────────────────────────────────
  async function loadAudit() {
    const params = currentRoleId ? `?role_id=${currentRoleId}&per_page=20` : '?per_page=20';
    const res = await fetch(`/api/v1/permissions/audit${params}`);
    const { data } = await res.json();
    const container = document.getElementById('auditLog');
    if (!data || !data.length) {
      container.innerHTML = '<p class="text-muted small text-center py-2">Sin registros.</p>';
      return;
    }
    container.innerHTML = data.map(e => `
      <div class="border-bottom py-1 px-1 small">
        <span class="badge ${e.action === 'grant' ? 'bg-success' : 'bg-warning text-dark'}">${e.action}</span>
        <code class="ms-1">${e.permission_codename}</code>
        <div class="text-muted audit-meta">${e.performed_by_name} · ${new Date(e.performed_at).toLocaleString()}</div>
        ${e.reason ? `<div class="fst-italic audit-meta">"${e.reason}"</div>` : ''}
      </div>
    `).join('');
  }

  // ── Filtrar tabla ───────────────────────────────────────────────────────
  function filterTable(query, tableId) {
    const q = query.toLowerCase();
    document.querySelectorAll(`#${tableId} tbody tr`).forEach(tr => {
      tr.classList.toggle('d-none', !tr.textContent.toLowerCase().includes(q));
    });
  }

  // ── Toast ───────────────────────────────────────────────────────────────
  function showToast(msg, type = 'info') {
    const el = document.getElementById('permToast');
    el.className = `toast align-items-center text-bg-${type} border-0`;
    document.getElementById('permToastBody').textContent = msg;
    bootstrap.Toast.getOrCreateInstance(el).show();
  }
})();

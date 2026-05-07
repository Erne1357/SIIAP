/* app/static/js/coordinator/photo_requests.js
 * Coordinator UI to handle profile photo change requests:
 *  - List pending requests (GET /api/v1/users/photo-requests)
 *  - Approve / reject (POST /api/v1/users/<id>/photo/enable-change)
 *  - Upload photo on behalf of student (POST /api/v1/users/<id>/photo)
 */
(function () {
  'use strict';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmt(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-MX', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function flashMsg(level, msg) {
    if (typeof showFlash === 'function') showFlash(level, msg);
  }

  async function loadPhotoRequests() {
    const tbody = document.getElementById('photoRequestsTbody');
    if (!tbody) return;

    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-4 text-muted small">
          <div class="spinner-border spinner-border-sm me-1" role="status"></div>
          Cargando solicitudes...
        </td>
      </tr>`;

    try {
      const res = await fetch('/api/v1/users/photo-requests');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderRequests(json.data || []);
    } catch (e) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-4 text-danger small">
            ${escHtml(e.message)}
          </td>
        </tr>`;
    }
  }

  function renderRequests(items) {
    const tbody = document.getElementById('photoRequestsTbody');
    const badge = document.getElementById('photoRequestsCount');
    if (!tbody) return;

    if (badge) {
      if (items.length > 0) {
        badge.textContent = items.length;
        badge.classList.remove('d-none');
      } else {
        badge.classList.add('d-none');
      }
    }

    if (!items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5">
            <div class="empty-state empty-state--compact">
              <i class="empty-state__icon bi bi-camera"></i>
              <h3 class="empty-state__title">Sin solicitudes pendientes</h3>
              <p class="empty-state__description">
                No hay estudiantes esperando autorización para cambiar su foto de perfil.
              </p>
            </div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = items.map(it => `
      <tr data-user-id="${it.user_id}">
        <td>
          <img src="${escHtml(it.avatar_url)}" alt="Avatar"
               class="rounded-circle border" style="width:42px;height:42px;object-fit:cover">
        </td>
        <td>
          <div class="fw-semibold">${escHtml(it.full_name)}</div>
          ${window.siiapStudentRecordBtn ? `
            <a href="/students/${it.user_id}/record" class="small text-decoration-none">
              <i class="bi bi-folder2-open me-1"></i>Expediente
            </a>` : ''}
        </td>
        <td class="small text-muted">${escHtml(it.email)}</td>
        <td class="text-center small">${escHtml(fmt(it.requested_at))}</td>
        <td class="text-center">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-success" data-action="approve" data-user-id="${it.user_id}">
              <i class="bi bi-check-lg"></i> Habilitar
            </button>
            <button class="btn btn-outline-danger" data-action="reject" data-user-id="${it.user_id}">
              <i class="bi bi-x-lg"></i> Rechazar
            </button>
            <button class="btn btn-outline-primary" data-action="upload" data-user-id="${it.user_id}">
              <i class="bi bi-upload"></i> Subir foto
            </button>
          </div>
        </td>
      </tr>
    `).join('');

    bindActionButtons();
  }

  function bindActionButtons() {
    document.querySelectorAll('#photoRequestsTbody [data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const action = btn.dataset.action;
        const userId = parseInt(btn.dataset.userId, 10);
        if (!userId) return;
        if (action === 'approve') await decide(userId, true);
        else if (action === 'reject') await decide(userId, false);
        else if (action === 'upload') openUploadModal(userId);
      });
    });
  }

  async function decide(userId, approve) {
    const reason = approve
      ? null
      : (prompt('Motivo del rechazo (opcional):') || null);

    try {
      const res = await fetch(`/api/v1/users/${userId}/photo/enable-change`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ approve, reason }),
      });
      const json = await res.json();
      if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
      if (res.ok && !json.error) loadPhotoRequests();
    } catch (e) {
      flashMsg('danger', 'Error al procesar la solicitud.');
    }
  }

  function openUploadModal(userId) {
    document.getElementById('coordPhotoTargetUserId').value = userId;
    document.getElementById('coordPhotoFile').value = '';
    new bootstrap.Modal(document.getElementById('coordPhotoUploadFromListModal')).show();
  }

  function bindUploadForm() {
    const form = document.getElementById('coordPhotoUploadFromListForm');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const userId = parseInt(document.getElementById('coordPhotoTargetUserId').value, 10);
      const file = document.getElementById('coordPhotoFile').files?.[0];
      if (!userId || !file) return;

      const fd = new FormData();
      fd.append('photo', file);

      try {
        const res = await fetch(`/api/v1/users/${userId}/photo`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: fd,
        });
        const json = await res.json();
        if (json.flash) json.flash.forEach(f => flashMsg(f.level, f.message));
        if (res.ok && !json.error) {
          bootstrap.Modal.getInstance(
            document.getElementById('coordPhotoUploadFromListModal')
          )?.hide();
          form.reset();
          loadPhotoRequests();
        }
      } catch (err) {
        flashMsg('danger', 'Error de red al subir foto.');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindUploadForm();
    document.getElementById('btnRefreshPhotoRequests')
      ?.addEventListener('click', loadPhotoRequests);
    // Lazy load when tab opens
    const tabBtn = document.getElementById('photo-requests-tab');
    if (tabBtn) {
      let loaded = false;
      tabBtn.addEventListener('shown.bs.tab', () => {
        if (!loaded) { loadPhotoRequests(); loaded = true; }
      });
    }
    // Initial badge fetch
    fetch('/api/v1/users/photo-requests')
      .then(r => r.ok ? r.json() : null)
      .then(json => {
        const count = (json?.data || []).length;
        const badge = document.getElementById('photoRequestsCount');
        if (badge && count > 0) {
          badge.textContent = count;
          badge.classList.remove('d-none');
        }
      })
      .catch(() => {});
  });
})();

// static/js/admin/admin_review.js - Versión con gestión de prórrogas
document.addEventListener('DOMContentLoaded', () => {
  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  const csrf = getCsrf();

  function emitFlash(level, message) {
    window.dispatchEvent(new CustomEvent('flash', { detail: { level, message } }));
  }
  
  function persistFlashes(flashes) {
    try { sessionStorage.setItem('flashQueue', JSON.stringify(flashes || [])); } catch (_) {}
  }

  // ==================== REVISIÓN DE DOCUMENTOS ====================
  const reviewForm = document.querySelector('[data-review-form="true"]');
  if (reviewForm) {
    let pendingAction = null;

    // Captura qué botón se pulsó (approve/reject)
    reviewForm.querySelectorAll('button[type="submit"][data-action]').forEach(btn => {
      btn.addEventListener('click', () => { pendingAction = btn.getAttribute('data-action'); });
    });

    reviewForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const subId = reviewForm.getAttribute('data-sub-id');
      const nextUrl = reviewForm.getAttribute('data-next-url') || window.location.href;
      const comment = reviewForm.comment?.value?.trim() || '';

      if (!pendingAction) return;

      if (pendingAction === 'reject') {
        const ok = confirm('¿Estás seguro de rechazar este documento?');
        if (!ok) return;
      }

      try {
        const res = await fetch(`/api/v1/admin/review/submissions/${subId}/decision`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          },
          body: JSON.stringify({ action: pendingAction, comment })
        });
        const json = await res.json().catch(() => ({}));

        if (!res.ok) {
          const msg = json?.error?.message || 'No se pudo aplicar la acción.';
          if (Array.isArray(json.flash) && json.flash.length) {
            json.flash.forEach(f => emitFlash(f.level || 'danger', f.message || msg));
          } else {
            emitFlash('danger', msg);
          }
          return;
        }

        const flashes = Array.isArray(json.flash) && json.flash.length
          ? json.flash
          : [{ level: 'success', message: 'Acción realizada correctamente.' }];

        persistFlashes(flashes);
        window.location.href = nextUrl;

      } catch (err) {
        console.error('review decision error:', err);
        emitFlash('danger', 'Error de red. Intenta de nuevo.');
      }
    });
  }

  // ==================== GESTIÓN DE PRÓRROGAS ====================
  const extensionsTab = document.getElementById('extensions-tab');
  const extensionsTableBody = document.getElementById('extensionsTableBody');
  const extensionReviewModal = document.getElementById('extensionReviewModal');
  
  let extensionRequests = [];
  let currentExtension = null;

  if (extensionsTab) {
    // Cargar prórrogas cuando se activa la pestaña
    extensionsTab.addEventListener('shown.bs.tab', loadExtensions);
    
    // Si la pestaña ya está activa al cargar
    if (extensionsTab.classList.contains('active')) {
      loadExtensions();
    }
  }

  // Botón de filtrar
  document.getElementById('filterExtensionsBtn')?.addEventListener('click', loadExtensions);

  async function loadExtensions() {
    if (!extensionsTableBody) return;

    extensionsTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">Cargando...</td></tr>';

    try {
      const params = new URLSearchParams();
      const status = document.getElementById('extensionStatusFilter')?.value;
      const programId = document.getElementById('extensionProgramFilter')?.value;
      const userId = document.getElementById('extensionStudentFilter')?.value;

      if (status) params.append('status', status);
      if (programId) params.append('program_id', programId);
      if (userId) params.append('user_id', userId);

      const res = await fetch(`/api/v1/extensions/requests?${params}`, {
        credentials: 'same-origin'
      });

      if (!res.ok) throw new Error('Error al cargar solicitudes');

      const json = await res.json();
      extensionRequests = json.items || [];

      renderExtensions();
      updateExtensionCounts();

    } catch (err) {
      console.error('Error loading extensions:', err);
      extensionsTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-3">Error al cargar solicitudes</td></tr>';
    }
  }

  function renderExtensions() {
    if (!extensionsTableBody) return;

    if (extensionRequests.length === 0) {
      extensionsTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No hay solicitudes de prórroga</td></tr>';
      return;
    }

    extensionsTableBody.innerHTML = extensionRequests.map(ext => {
      const requestedDate = new Date(ext.requested_until);
      const createdDate = new Date(ext.created_at);
      
      const statusBadge = {
        'pending': '<span class="badge bg-warning">Pendiente</span>',
        'granted': '<span class="badge bg-success">Concedida</span>',
        'rejected': '<span class="badge bg-danger">Rechazada</span>',
        'cancelled': '<span class="badge bg-secondary">Cancelada</span>'
      }[ext.status] || '<span class="badge bg-secondary">Desconocido</span>';

      return `
        <tr data-extension-id="${ext.id}">
          <td>${ext.id}</td>
          <td>
            <div class="fw-semibold">${ext.user_name || 'N/A'}</div>
            <small class="text-muted">${ext.user_email || ''}</small>
          </td>
          <td>${ext.archive_name}</td>
          <td>${requestedDate.toLocaleDateString('es-MX')}</td>
          <td>${createdDate.toLocaleDateString('es-MX')}</td>
          <td>${statusBadge}</td>
          <td>
            ${ext.status === 'pending' ? `
              <button class="btn btn-sm btn-outline-primary btn-review-extension" 
                      data-extension-id="${ext.id}">
                <i class="fas fa-eye me-1"></i>Revisar
              </button>
            ` : `
              <button class="btn btn-sm btn-outline-secondary btn-view-extension" 
                      data-extension-id="${ext.id}">
                <i class="fas fa-info-circle me-1"></i>Ver
              </button>
            `}
          </td>
        </tr>
      `;
    }).join('');

    // Event listeners para botones
    document.querySelectorAll('.btn-review-extension, .btn-view-extension').forEach(btn => {
      btn.addEventListener('click', () => {
        const extId = parseInt(btn.getAttribute('data-extension-id'));
        openExtensionModal(extId);
      });
    });
  }

  function updateExtensionCounts() {
    const pendingCount = extensionRequests.filter(e => e.status === 'pending').length;
    document.getElementById('pendingExtensionsCount').textContent = pendingCount;
  }

  function openExtensionModal(extId) {
    const ext = extensionRequests.find(e => e.id === extId);
    if (!ext) return;

    currentExtension = ext;

    // Llenar datos del modal
    document.getElementById('reviewExtensionId').value = ext.id;
    document.getElementById('extensionStudentName').textContent = ext.user_name || 'N/A';
    document.getElementById('extensionStudentEmail').textContent = ext.user_email || '';
    document.getElementById('extensionArchiveName').textContent = ext.archive_name;
    document.getElementById('extensionRequestedUntil').textContent = 
      new Date(ext.requested_until).toLocaleDateString('es-MX');
    document.getElementById('extensionReason').textContent = ext.reason || 'Sin motivo especificado';

    // Pre-llenar fecha concedida con la solicitada
    const requestedDate = new Date(ext.requested_until);
    document.getElementById('extensionGrantedUntil').value = requestedDate.toISOString().split('T')[0];

    // Si ya fue revisada, mostrar decisión
    if (ext.status !== 'pending') {
      document.getElementById('extensionConditions').value = ext.condition_text || '';
      document.getElementById('extensionConditions').disabled = true;
      document.getElementById('extensionGrantedUntil').disabled = true;
      document.getElementById('approveExtensionBtn').style.display = 'none';
      document.getElementById('rejectExtensionBtn').style.display = 'none';
    } else {
      document.getElementById('extensionConditions').disabled = false;
      document.getElementById('extensionGrantedUntil').disabled = false;
      document.getElementById('approveExtensionBtn').style.display = 'inline-block';
      document.getElementById('rejectExtensionBtn').style.display = 'inline-block';
    }

    const modal = new bootstrap.Modal(extensionReviewModal);
    modal.show();
  }

  // Aprobar prórroga
  document.getElementById('approveExtensionBtn')?.addEventListener('click', async () => {
    const extId = document.getElementById('reviewExtensionId').value;
    const grantedUntil = document.getElementById('extensionGrantedUntil').value;
    const conditions = document.getElementById('extensionConditions').value.trim();

    if (!grantedUntil) {
      emitFlash('warning', 'Debes especificar una fecha');
      return;
    }

    await decideExtension(extId, 'granted', grantedUntil, conditions);
  });

  // Rechazar prórroga
  document.getElementById('rejectExtensionBtn')?.addEventListener('click', async () => {
    if (!confirm('¿Estás seguro de rechazar esta solicitud?')) return;

    const extId = document.getElementById('reviewExtensionId').value;
    const conditions = document.getElementById('extensionConditions').value.trim() || 
                      'Solicitud rechazada';

    await decideExtension(extId, 'rejected', null, conditions);
  });

  async function decideExtension(extId, status, grantedUntil, conditions) {
    try {
      const payload = {
        status,
        condition_text: conditions
      };

      if (status === 'granted' && grantedUntil) {
        payload.granted_until = grantedUntil;
      }

      const res = await fetch(`/api/v1/extensions/requests/${extId}/decision`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf
        },
        body: JSON.stringify(payload)
      });

      const json = await res.json();

      if (!res.ok || !json.ok) {
        emitFlash('danger', json.error || 'No se pudo procesar la decisión');
        return;
      }

      emitFlash('success', json.message || 'Decisión registrada correctamente');

      // Cerrar modal y recargar
      const modal = bootstrap.Modal.getInstance(extensionReviewModal);
      modal.hide();
      
      await loadExtensions();

    } catch (err) {
      console.error('Extension decision error:', err);
      emitFlash('danger', 'Error al procesar la decisión');
    }
  }
});
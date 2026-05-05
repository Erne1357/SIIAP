/* app/static/js/user/profile_activity.js
 * Carga "Actividad Reciente", "Próximos Eventos" y la pestaña de Documentos
 * históricos del perfil. Usa endpoints en /api/v1/users/me/*.
 */
(function () {
  'use strict';

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatRelativeOrDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.round(diffMs / 60000);
    if (diffMin < 1) return 'Hace unos segundos';
    if (diffMin < 60) return `Hace ${diffMin} min`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `Hace ${diffHr} h`;
    const diffDays = Math.round(diffHr / 24);
    if (diffDays < 7) return `Hace ${diffDays} día${diffDays === 1 ? '' : 's'}`;
    return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function formatEventDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleString('es-MX', {
      day: '2-digit', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  // ── Actividad Reciente ─────────────────────────────────────────────────
  async function loadActivity() {
    const container = document.getElementById('profileActivityContainer');
    if (!container) return;

    container.innerHTML = `<div class="text-center py-3 text-muted small">
      <div class="spinner-border spinner-border-sm me-1" role="status"></div>
      Cargando actividad...
    </div>`;

    try {
      const res = await fetch('/api/v1/users/me/activity?limit=6');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderActivity(json.data || []);
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger small mb-0">Error al cargar actividad: ${escHtml(e.message)}</div>`;
    }
  }

  function renderActivity(items) {
    const container = document.getElementById('profileActivityContainer');
    if (!container) return;

    if (!items.length) {
      container.innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-clock-history"></i>
          <h3 class="empty-state__title">Sin actividad reciente</h3>
          <p class="empty-state__description">Tus acciones aparecerán aquí.</p>
        </div>`;
      return;
    }

    const rows = items.map(it => {
      const url = it.url ? `<a href="${escHtml(it.url)}" class="text-reset text-decoration-none">` : '';
      const closeUrl = it.url ? `</a>` : '';
      return `
        <div class="d-flex mb-3">
          <div class="bg-${escHtml(it.icon_color || 'primary')} bg-opacity-10 p-2 rounded-circle me-3 flex-shrink-0">
            <i class="bi ${escHtml(it.icon || 'bi-clock-history')} text-${escHtml(it.icon_color || 'primary')}"></i>
          </div>
          <div class="flex-grow-1">
            ${url}<p class="mb-0 fw-medium">${escHtml(it.title)}</p>${closeUrl}
            ${it.description ? `<small class="text-muted d-block">${escHtml(it.description)}</small>` : ''}
            <small class="text-muted">${escHtml(formatRelativeOrDate(it.timestamp))}</small>
          </div>
        </div>`;
    }).join('');

    container.innerHTML = rows;
  }

  // ── Próximos Eventos ──────────────────────────────────────────────────
  async function loadUpcoming() {
    const container = document.getElementById('profileUpcomingEventsContainer');
    if (!container) return;

    container.innerHTML = `<div class="text-center py-3 text-muted small">
      <div class="spinner-border spinner-border-sm me-1" role="status"></div>
      Cargando eventos...
    </div>`;

    try {
      const res = await fetch('/api/v1/users/me/upcoming-events?limit=5');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderUpcoming(json.data || []);
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger small mb-0">Error al cargar eventos: ${escHtml(e.message)}</div>`;
    }
  }

  function renderUpcoming(items) {
    const container = document.getElementById('profileUpcomingEventsContainer');
    if (!container) return;

    if (!items.length) {
      container.innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-calendar-x"></i>
          <h3 class="empty-state__title">Sin eventos próximos</h3>
          <p class="empty-state__description">No estás inscrito a eventos futuros.</p>
        </div>`;
      return;
    }

    const rows = items.map(ev => `
      <div class="d-flex mb-3">
        <div class="bg-primary bg-opacity-10 p-2 rounded-circle me-3 flex-shrink-0">
          <i class="bi bi-calendar-event text-primary"></i>
        </div>
        <div class="flex-grow-1">
          <a href="${escHtml(ev.url)}" class="text-reset text-decoration-none">
            <p class="mb-0 fw-medium">${escHtml(ev.title)}</p>
          </a>
          <small class="text-muted d-block">${escHtml(formatEventDate(ev.event_date))}</small>
          ${ev.location ? `<small class="text-muted"><i class="bi bi-geo-alt me-1"></i>${escHtml(ev.location)}</small>` : ''}
        </div>
      </div>
    `).join('');

    container.innerHTML = rows;
  }

  // ── Documentos históricos por fase ─────────────────────────────────────
  async function loadDocumentsHistory() {
    const container = document.getElementById('profileDocumentsHistoryContainer');
    if (!container) return;

    container.innerHTML = `<div class="text-center py-3 text-muted small">
      <div class="spinner-border spinner-border-sm me-1" role="status"></div>
      Cargando documentos...
    </div>`;

    try {
      const res = await fetch('/api/v1/users/me/documents-history');
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json.error?.message || 'Error');
      renderDocumentsHistory(json.data || {});
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger small mb-0">Error al cargar documentos: ${escHtml(e.message)}</div>`;
    }
  }

  function statusBadge(status) {
    const map = {
      review: ['warning', 'En revisión'],
      approved: ['success', 'Aprobado'],
      rejected: ['danger', 'Rechazado'],
      pending: ['secondary', 'Pendiente'],
    };
    const [color, label] = map[status] || ['secondary', status || '—'];
    return `<span class="status-badge status-badge--${escHtml(status || 'pending')}">${escHtml(label)}</span>`;
  }

  function renderDocList(docs) {
    if (!docs || !docs.length) {
      return `<div class="text-muted small px-3 py-2">No hay documentos en esta fase.</div>`;
    }
    return `
      <ul class="list-group list-group-flush">
        ${docs.map(d => `
          <li class="list-group-item d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div>
              <div class="fw-medium">${escHtml(d.archive_name || 'Documento')}</div>
              <small class="text-muted">
                ${d.upload_date ? new Date(d.upload_date).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' }) : ''}
                ${d.semester ? ` · Semestre ${escHtml(String(d.semester))}` : ''}
              </small>
            </div>
            <div class="d-flex align-items-center gap-2">
              ${statusBadge(d.status)}
              ${d.file_url ? `<a href="${escHtml(d.file_url)}" target="_blank" class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-eye"></i>
              </a>` : ''}
            </div>
          </li>
        `).join('')}
      </ul>`;
  }

  function renderDocumentsHistory(grouped) {
    const container = document.getElementById('profileDocumentsHistoryContainer');
    if (!container) return;

    const admission = grouped.admission || [];
    const conclusion = grouped.conclusion || [];
    const permanence = grouped.permanence || {};
    const other = grouped.other || [];

    const semesters = Object.keys(permanence).sort((a, b) => {
      const na = parseInt(a, 10);
      const nb = parseInt(b, 10);
      if (isNaN(na) || isNaN(nb)) return String(a).localeCompare(String(b));
      return na - nb;
    });

    const isEmpty = !admission.length && !conclusion.length && !semesters.length && !other.length;
    if (isEmpty) {
      container.innerHTML = `
        <div class="empty-state empty-state--compact">
          <i class="empty-state__icon bi bi-folder-x"></i>
          <h3 class="empty-state__title">Sin documentos históricos</h3>
          <p class="empty-state__description">Aún no has subido documentos en ninguna fase.</p>
        </div>`;
      return;
    }

    const permanenceCount = semesters.reduce((acc2, k) => acc2 + (permanence[k]?.length || 0), 0);

    const permanenceBody = semesters.length
      ? semesters.map(sem => {
          const docs = permanence[sem] || [];
          const semLabel = sem === 'sin_semestre' ? 'Sin semestre asignado' : `Semestre ${sem}`;
          return `
            <div class="border-bottom">
              <div class="px-3 py-2 bg-body-tertiary fw-semibold small">${escHtml(semLabel)} · ${docs.length} documento(s)</div>
              ${renderDocList(docs)}
            </div>`;
        }).join('')
      : `<div class="text-muted small px-3 py-2">No hay documentos en permanencia.</div>`;

    const tabBtn = (id, title, count, active) => `
      <li class="nav-item" role="presentation">
        <button class="nav-link ${active ? 'active' : ''}" type="button"
                data-bs-toggle="tab" data-bs-target="#docHist-${id}-pane"
                role="tab" aria-controls="docHist-${id}-pane">
          <i class="bi bi-folder2-open me-1"></i>${escHtml(title)}
          <span class="badge bg-secondary ms-2">${count}</span>
        </button>
      </li>`;

    const tabPane = (id, body, active) => `
      <div class="tab-pane fade ${active ? 'show active' : ''}" id="docHist-${id}-pane" role="tabpanel">
        ${body}
      </div>`;

    container.innerHTML = `
      <ul class="nav nav-tabs mb-3" role="tablist">
        ${tabBtn('admission', 'Admisión', admission.length, true)}
        ${tabBtn('permanence', 'Permanencia', permanenceCount, false)}
        ${tabBtn('conclusion', 'Conclusión', conclusion.length, false)}
        ${other.length ? tabBtn('other', 'Otros', other.length, false) : ''}
      </ul>
      <div class="tab-content">
        ${tabPane('admission', renderDocList(admission), true)}
        ${tabPane('permanence', permanenceBody, false)}
        ${tabPane('conclusion', renderDocList(conclusion), false)}
        ${other.length ? tabPane('other', renderDocList(other), false) : ''}
      </div>`;
  }

  // ── Init ───────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('profileActivityContainer')) loadActivity();
    if (document.getElementById('profileUpcomingEventsContainer')) loadUpcoming();
    if (document.getElementById('profileDocumentsHistoryContainer')) loadDocumentsHistory();

    document.getElementById('btnRefreshActivity')?.addEventListener('click', loadActivity);
    document.getElementById('btnRefreshUpcoming')?.addEventListener('click', loadUpcoming);

    // Lazy-load documents tab when first opened
    const docsTab = document.getElementById('documents-tab');
    if (docsTab) {
      docsTab.addEventListener('shown.bs.tab', () => {
        if (document.getElementById('profileDocumentsHistoryContainer')) loadDocumentsHistory();
      });
    }
  });
})();

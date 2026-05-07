/* app/static/js/base.js
 * Lógica global del layout: dropdowns del sidebar, offcanvas móvil y logout.
 * Depende de `window.SIIAP_BASE` (definido inline en base.html con url_for/csrf).
 */
(function () {
  'use strict';

  const CFG = window.SIIAP_BASE || {};

  function getCsrf() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  }

  // ── Dropdowns del sidebar ──────────────────────────────────────────────
  function initDropdownMenus() {
    document.querySelectorAll('[data-dropdown]').forEach(trigger => {
      const newTrigger = trigger.cloneNode(true);
      trigger.parentNode.replaceChild(newTrigger, trigger);

      newTrigger.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();

        const targetId = this.getAttribute('data-dropdown');
        const submenu = document.getElementById(targetId);
        if (!submenu) return;

        const isShowing = submenu.classList.contains('show');

        document.querySelectorAll('.dropdown-submenu.show').forEach(m => {
          if (m !== submenu) m.classList.remove('show');
        });
        document.querySelectorAll('.dropdown-toggle-custom.expanded').forEach(t => {
          if (t !== this) t.classList.remove('expanded');
        });

        submenu.classList.toggle('show', !isShowing);
        this.classList.toggle('expanded', !isShowing);
      });
    });
  }

  // ── Offcanvas móvil ────────────────────────────────────────────────────
  function initOffcanvasLinks() {
    const offcanvasElement = document.getElementById('mobileSidebar');
    if (!offcanvasElement) return;

    const links = offcanvasElement.querySelectorAll(
      'a[href]:not(.dropdown-toggle-custom):not(.js-api-logout)'
    );

    links.forEach(link => {
      link.addEventListener('click', function () {
        const href = this.getAttribute('href');
        if (href && href !== '#' && href !== '') {
          const bsOffcanvas = bootstrap.Offcanvas.getInstance(offcanvasElement);
          if (bsOffcanvas) bsOffcanvas.hide();
        }
      });
    });
  }

  // ── Body class para el offcanvas (permite ocultar el footer vía CSS) ─
  function initOffcanvasBodyClass() {
    const offcanvasElement = document.getElementById('mobileSidebar');
    if (!offcanvasElement) return;

    offcanvasElement.addEventListener('show.bs.offcanvas', () =>
      document.body.classList.add('offcanvas-open')
    );
    offcanvasElement.addEventListener('hidden.bs.offcanvas', () =>
      document.body.classList.remove('offcanvas-open')
    );
  }

  // ── Cerrar dropdowns al click fuera ────────────────────────────────────
  function initCloseOnOutsideClick() {
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.dropdown-menu-container')) {
        document.querySelectorAll('.dropdown-submenu.show').forEach(m =>
          m.classList.remove('show')
        );
        document.querySelectorAll('.dropdown-toggle-custom.expanded').forEach(t =>
          t.classList.remove('expanded')
        );
      }
    });
  }

  // ── Logout vía API ─────────────────────────────────────────────────────
  function wireLogout() {
    document.querySelectorAll('.js-api-logout').forEach(el => {
      el.addEventListener('click', async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();

        // Cerrar offcanvas si está abierto
        const offcanvas = document.getElementById('mobileSidebar');
        if (offcanvas) {
          const bsOffcanvas = bootstrap.Offcanvas.getInstance(offcanvas);
          if (bsOffcanvas) bsOffcanvas.hide();
        }

        try {
          const res = await fetch(CFG.logoutUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCsrf() },
          });
          const json = await res.json().catch(() => ({}));
          if (json.flash) {
            json.flash.forEach(f =>
              window.dispatchEvent(new CustomEvent('flash', { detail: f }))
            );
          }
          if (!res.ok) throw new Error('Error al cerrar sesión');
        } catch (e) {
          console.error(e);
        } finally {
          window.location.href = CFG.loginUrl;
        }
      });
    });
  }

  function init() {
    initDropdownMenus();
    initOffcanvasLinks();
    initOffcanvasBodyClass();
    initCloseOnOutsideClick();
    wireLogout();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

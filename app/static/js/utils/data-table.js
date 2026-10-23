/*
 * SIIAP — Helper para tablas con scroll hint indicator.
 * Auto-aplica a todos los .siiap-table-wrapper en DOMContentLoaded.
 */

(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});

  // Idiomorph drops attributes the server did not emit, so data-dt-init alone
  // is not a safe guard: a morph would erase it and every re-init would stack
  // another scroll listener and ResizeObserver. Identity survives a morph.
  const initialised = new WeakSet();

  function initDataTable(wrapper) {
    if (!wrapper || initialised.has(wrapper)) return;
    initialised.add(wrapper);
    wrapper.dataset.dtInit = '1';

    const update = () => {
      const overflow = wrapper.scrollWidth > wrapper.clientWidth + 1;
      const atEnd = wrapper.scrollLeft + wrapper.clientWidth >= wrapper.scrollWidth - 1;
      wrapper.classList.toggle('has-overflow', overflow);
      wrapper.classList.toggle('scrolled-end', atEnd);
    };

    update();
    wrapper.addEventListener('scroll', update, { passive: true });

    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(update).observe(wrapper);
    } else {
      window.addEventListener('resize', update, { passive: true });
    }
  }

  SIIAP.initDataTable = initDataTable;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.siiap-table-wrapper').forEach(initDataTable);
  });

})(window);

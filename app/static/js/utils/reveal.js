/*
 * SIIAP — Reveal-on-scroll con IntersectionObserver.
 * Sustitucion ligera de AOS. Aplica a elementos con [data-reveal].
 *
 * Uso en HTML:
 *   <div data-reveal>...</div>
 *   <div data-reveal="fade-up" data-reveal-delay="200">...</div>
 *
 * Tipos soportados: fade-up (default), fade-down, fade-left, fade-right.
 *
 * API: SIIAP.initReveal(root?) — idempotente. Observa los [data-reveal] aún no
 * revelados bajo `root` (por defecto, el documento). El puente de htmx
 * (utils/htmx-bridge.js) la llama en cada htmx:load, así un fragmento recién
 * intercambiado no queda con opacity: 0 para siempre.
 */

(function (global) {
  'use strict';

  const SIIAP = global.SIIAP || (global.SIIAP = {});

  const reduceMotion = !!(global.matchMedia &&
    global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const instantReveal = typeof IntersectionObserver === 'undefined' || reduceMotion;

  let io = null;

  function getObserver() {
    if (io) return io;
    io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const delay = parseInt(el.dataset.revealDelay || '0', 10);
          if (delay > 0) {
            setTimeout(() => el.classList.add('revealed'), delay);
          } else {
            el.classList.add('revealed');
          }
          io.unobserve(el);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
    return io;
  }

  function initReveal(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const nodes = Array.from(scope.querySelectorAll('[data-reveal]:not(.revealed)'));
    if (scope !== document && scope.matches && scope.matches('[data-reveal]:not(.revealed)')) {
      nodes.unshift(scope);
    }
    if (instantReveal) {
      nodes.forEach(el => el.classList.add('revealed'));
      return;
    }
    // observe() on an element that is already observed is a no-op.
    const observer = getObserver();
    nodes.forEach(el => observer.observe(el));
  }

  SIIAP.initReveal = initReveal;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initReveal(document));
  } else {
    initReveal(document);
  }
})(window);

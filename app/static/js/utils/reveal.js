/*
 * SIIAP — Reveal-on-scroll con IntersectionObserver.
 * Sustitucion ligera de AOS. Aplica a elementos con [data-reveal].
 *
 * Uso en HTML:
 *   <div data-reveal>...</div>
 *   <div data-reveal="fade-up" data-reveal-delay="200">...</div>
 *
 * Tipos soportados: fade-up (default), fade-down, fade-left, fade-right.
 */

(function () {
  'use strict';

  if (typeof IntersectionObserver === 'undefined') {
    document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('revealed'));
    return;
  }

  const reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (reduceMotion) {
    document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('revealed'));
    return;
  }

  const io = new IntersectionObserver((entries) => {
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

  function init() {
    document.querySelectorAll('[data-reveal]:not(.revealed)').forEach(el => io.observe(el));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

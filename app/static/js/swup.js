
// Obtenemos las posiciones del menú para saber si “subimos” o “bajamos”
const navLinks = [...document.querySelectorAll('aside .nav-link')];

const swup = new Swup({
    containers: ['#main-content'],
    animationSelector: "#main-content",
    animateHistoryBrowsing: true
});

// --- Elegir dirección de animación según el orden en la sidebar ---
swup.hooks.on('link:click', (link) => {
    const current = navLinks.findIndex(a => a.classList.contains('active'));
    const target = navLinks.findIndex(a => a.href === link.href);
    document.documentElement.dataset.swupDir =
        target > current ? 'down' : 'up';
});

swup.hooks.on('content:replace', () => {
    navLinks.forEach(a => a.classList.toggle(
      'active',
      a.pathname === window.location.pathname
    ));
  });
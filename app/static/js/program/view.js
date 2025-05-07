/* cambia el icono flecha arriba/abajo si usas FontAwesome 5+ */
document.addEventListener('shown.bs.collapse', e => {
    e.target.previousElementSibling
            .querySelector('.accordion-button')
            ?.classList.add('open');
  });
  document.addEventListener('hidden.bs.collapse', e => {
    e.target.previousElementSibling
            .querySelector('.accordion-button')
            ?.classList.remove('open');
  });
  
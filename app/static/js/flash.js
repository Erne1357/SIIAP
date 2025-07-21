// static/js/flash.js
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash-toast').forEach(toast => {
    toast.addEventListener('animationend', e => {
      if (e.animationName === 'slideOutRight') {
        toast.remove();        // evita que se acumulen en el DOM
      }
    });
  });
});

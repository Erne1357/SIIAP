document.addEventListener('DOMContentLoaded', function() {
  // Confirmar antes de rechazar
  document.querySelectorAll('.btn-reject').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      if (!confirm('¿Estás seguro de rechazar este documento?')) {
        e.preventDefault();
      }
    });
  });
});

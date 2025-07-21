// static/js/program/admission.js
document.addEventListener('DOMContentLoaded', () => {
  const uploadModal = document.getElementById('uploadModal');

  uploadModal.addEventListener('show.bs.modal', event => {
    const btn = event.relatedTarget;                 // botón que disparó el modal
    const archId = btn?.getAttribute('data-archive');
    uploadModal.querySelector('[name="archive_id"]').value = archId || '';
  });
});

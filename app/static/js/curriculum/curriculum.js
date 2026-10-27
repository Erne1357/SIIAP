// app/static/js/curriculum/curriculum.js
// Fills the shared subject modal from the button that opened it and closes it
// after a successful save. The modal lives outside the swapped workspace.
(function () {
  'use strict';

  var modal = document.getElementById('modalSubject');
  if (!modal) return;
  var form = document.getElementById('curriculumSubjectForm');

  function setValue(id, value) {
    var field = document.getElementById(id);
    if (field) field.value = value || '';
  }

  modal.addEventListener('show.bs.modal', function (evt) {
    var btn = evt.relatedTarget;
    if (!btn) return;
    var data = btn.dataset;
    form.setAttribute('hx-post', data.subjectUrl);
    if (window.htmx) window.htmx.process(form);
    modal.querySelector('.modal-title').textContent = data.subjectTitle || 'Materia';
    setValue('subjectKey', data.subjectKey);
    setValue('subjectName', data.subjectName);
    setValue('subjectCredits', data.subjectCredits);
    setValue('subjectSemester', data.subjectSemester);
    setValue('subjectKind', data.subjectKind || 'required');
  });

  form.addEventListener('htmx:afterRequest', function (evt) {
    if (evt.target !== form || !evt.detail.successful) return;
    var instance = window.bootstrap && window.bootstrap.Modal.getOrCreateInstance(modal);
    if (instance) instance.hide();
  });
})();

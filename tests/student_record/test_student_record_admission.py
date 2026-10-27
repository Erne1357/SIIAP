# tests/student_record/test_student_record_admission.py
"""
The record page's admission tab (HTML fragment) and the cross-program summary
page, which replaced the dashboard's "student detail" modal.

Covers GET /students/<id>/record (deep link + breadcrumb),
GET /students/<id>/record/admission (HX vs non-HX, scope 404),
POST /students/<id>/record/admission/upload and GET /students/<id>/summary
(the reduced cross-program tier).
"""
import io
import unittest

from flask import g

from app import create_app, db
from app.models.archive import Archive
from app.models.phase import Phase
from app.models.program_step import ProgramStep
from app.models.step import Step
from app.models.submission import Submission
from app.models.user import User
from app.utils.uuid7 import uuid7

from tests.student_record.conftest import (
    make_test_config, make_role, make_user, make_program, make_period,
    grant_permission, make_user_program,
)

HX = {'HX-Request': 'true'}
UNKNOWN_ID = str(uuid7())
SECRET_PHONE = '5551234567'
SECRET_CURP = 'ABCD800101HJCXXX01'


class AdmissionFragmentTest(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        r_student = make_role('student')
        r_admin = make_role('program_admin')
        r_other = make_role('social_service')
        for codename in ('students.page.view_record', 'students.api.view_record',
                         'coordinator.api.list_students',
                         'coordinator.api.upload_for_student', 'coordinator.page.view'):
            grant_permission(r_admin, codename)
        # Holds the record capabilities but NOT the cross-program tier.
        for codename in ('students.page.view_record', 'students.api.view_record'):
            grant_permission(r_other, codename)

        self.coord_a = make_user(r_admin, suffix='_a')
        self.coord_b = make_user(r_admin, suffix='_b')
        self.no_tier = make_user(r_other, suffix='_nt')
        self.student_b = make_user(r_student, suffix='_sb')
        self.student_b.phone = SECRET_PHONE
        self.student_b.curp = SECRET_CURP
        self.student_b.first_name = '<b>Ana</b>'

        self.program_a = make_program(self.coord_a, slug='prog-a')
        self.program_b = make_program(self.coord_b, slug='prog-b')
        period = make_period()
        make_user_program(self.student_b, self.program_b, period, status='in_progress')

        phase = Phase(name='admission', description='Admisión')
        db.session.add(phase)
        db.session.flush()
        step = Step(name='Documentos', description='', phase_id=phase.id)
        db.session.add(step)
        db.session.flush()
        self.archive = Archive(name='Acta <i>de nacimiento</i>', description='',
                               file_path=None, step_id=step.id)
        self.archive.allow_coordinator_upload = True
        db.session.add(self.archive)
        db.session.flush()
        db.session.add(ProgramStep(sequence=1, program_id=self.program_b.id,
                                   step_id=step.id))
        db.session.commit()

        uid = str(self.student_b.uuid)
        self.page_url = f'/students/{uid}/record'
        self.frag_url = f'{self.page_url}/admission'
        self.upload_url = f'{self.frag_url}/upload'
        self.summary_url = f'/students/{uid}/summary'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login_as(self, user):
        g.pop('_login_user', None)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
            sess['_csrf_token'] = 'test-csrf-token'

    # ── Page: deep link + breadcrumb ───────────────────────────────────────
    def test_page_has_admission_tab_lazy_fragment_and_breadcrumb(self):
        self._login_as(self.coord_b)
        html = self.client.get(self.page_url + '?tab=admision').get_data(as_text=True)
        self.assertIn('id="tab-admission-btn"', html)
        self.assertIn('hx-history="false"', html)
        self.assertIn(self.frag_url, html)
        self.assertIn('initialTab: "admision"', html)
        self.assertIn('Expedientes', html)
        self.assertIn('aria-current="page">&lt;b&gt;Ana&lt;/b&gt; User', html)
        self.assertIn('Estudiantes', html)

    # ── Fragment ───────────────────────────────────────────────────────────
    def test_htmx_fragment_shows_sections_and_escapes(self):
        self._login_as(self.coord_b)
        res = self.client.get(self.frag_url, headers=HX)
        self.assertEqual(res.status_code, 200)
        self.assertIn('HX-Request', res.headers.get('Vary', ''))
        html = res.get_data(as_text=True)
        self.assertNotIn('<html', html)
        for label in ('Progreso general', 'Documentos pendientes',
                      'Documentos por etapa', 'Entrevista', 'Estado del perfil'):
            self.assertIn(label, html)
        self.assertIn('Acta &lt;i&gt;de nacimiento&lt;/i&gt;', html)
        self.assertNotIn('<i>de nacimiento</i>', html)
        self.assertIn('data-bs-target="#admissionUploadModal"', html)

    def test_non_htmx_request_redirects_to_the_page_tab(self):
        self._login_as(self.coord_b)
        res = self.client.get(self.frag_url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers['Location'].endswith(self.page_url + '?tab=admision'))

    def test_out_of_scope_coordinator_gets_404_like_unknown_id(self):
        self._login_as(self.coord_a)
        denied = self.client.get(self.frag_url, headers=HX)
        unknown = self.client.get(f'/students/{UNKNOWN_ID}/record/admission', headers=HX)
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(denied.get_data(), unknown.get_data())
        self.assertEqual(denied.headers.get('HX-Reswap'), 'none')
        # Same answer without HX: no redirect that would confirm existence.
        self.assertEqual(self.client.get(self.frag_url).status_code, 404)

    # ── Upload ─────────────────────────────────────────────────────────────
    def _upload(self, **over):
        data = {'archive_id': str(self.archive.uuid), 'decision': 'approve',
                'notes': 'Validado en persona'}
        data.update(over)
        return self.client.post(self.upload_url, data=data, headers={**HX, 'X-CSRFToken': 'test-csrf-token'},
                                content_type='multipart/form-data')

    def test_upload_without_file_registers_submission_and_returns_fragment(self):
        self._login_as(self.coord_b)
        res = self._upload()
        self.assertEqual(res.status_code, 200)
        self.assertIn('siiap:flash', res.headers.get('HX-Trigger', ''))
        sub = Submission.query.filter_by(user_id=self.student_b.id,
                                         archive_id=self.archive.id).one()
        self.assertEqual(sub.status, 'approved')
        self.assertIn('Aprobado', res.get_data(as_text=True))

    def test_upload_requires_a_comment_when_there_is_no_file(self):
        self._login_as(self.coord_b)
        res = self._upload(notes='')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Submission.query.count(), 0)

    def test_upload_rejects_non_pdf(self):
        self._login_as(self.coord_b)
        res = self.client.post(
            self.upload_url,
            data={'archive_id': str(self.archive.uuid), 'notes': 'x',
                  'file': (io.BytesIO(b'GIF89a'), 'a.gif')},
            headers={**HX, 'X-CSRFToken': 'test-csrf-token'},
            content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Submission.query.count(), 0)

    def test_out_of_scope_coordinator_cannot_upload(self):
        self._login_as(self.coord_a)
        res = self._upload()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(Submission.query.count(), 0)

    # ── Cross-program summary tier ─────────────────────────────────────────
    def test_summary_shows_only_the_reduced_tier(self):
        self._login_as(self.coord_a)
        res = self.client.get(self.summary_url)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Información limitada', html)
        self.assertIn('Test Program', html)
        self.assertIn(self.student_b.email, html)
        for forbidden in (SECRET_PHONE, SECRET_CURP, 'Acta', '/files/'):
            self.assertNotIn(forbidden, html)

    def test_summary_without_tier_permission_or_unknown_is_404(self):
        self._login_as(self.no_tier)
        self.assertEqual(self.client.get(self.summary_url).status_code, 404)
        self._login_as(self.coord_a)
        self.assertEqual(
            self.client.get(f'/students/{UNKNOWN_ID}/summary').status_code, 404)

    def test_summary_of_a_staff_account_is_404(self):
        self._login_as(self.coord_a)
        res = self.client.get(f'/students/{self.coord_b.uuid}/summary')
        self.assertEqual(res.status_code, 404)

    def test_summary_redirects_a_managed_student_to_the_record(self):
        self._login_as(self.coord_b)
        res = self.client.get(self.summary_url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers['Location'].endswith(self.page_url))

    def test_user_not_changed_by_reads(self):
        self._login_as(self.coord_b)
        self.client.get(self.frag_url, headers=HX)
        db.session.expire_all()
        self.assertEqual(db.session.get(User, self.student_b.id).phone, SECRET_PHONE)


if __name__ == '__main__':
    unittest.main()

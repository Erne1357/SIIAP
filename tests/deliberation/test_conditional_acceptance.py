# tests/deliberation/test_conditional_acceptance.py
"""
Sprint 2 Fase 3 — accept_applicant supports `is_conditional` and `dictamen_file`.
On conditional acceptance, an AcceptanceDocument with type='acceptance_opinion'
is created and the user_history records 'admission_accepted_conditional'.
"""

import io
import unittest
from werkzeug.datastructures import FileStorage

from app import create_app, db
from app.models.acceptance_document import AcceptanceDocument
from app.models.user_history import UserHistory
from app.services import deliberation_service as svc

from tests.deliberation.conftest import (
    make_test_config, make_role, make_user, make_program, make_period,
    make_user_program,
)


def _file(name='dictamen.pdf'):
    return FileStorage(
        stream=io.BytesIO(b'%PDF-1.4 dictamen'),
        filename=name,
        content_type='application/pdf',
    )


class TestConditionalAcceptance(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_app = make_role('applicant')
        self.role_coord = make_role('program_admin')
        self.coord = make_user(self.role_coord, suffix='_coord')
        self.applicant = make_user(self.role_app, suffix='_app')
        self.period = make_period()
        self.program = make_program(self.coord)
        self.up = make_user_program(
            self.applicant, self.program, self.period, status='deliberation',
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_conditional_without_file_raises(self):
        with self.assertRaises(ValueError) as ctx:
            svc.accept_applicant(
                self.applicant.id, self.program.id, self.coord.id,
                notes='Aceptación condicionada',
                is_conditional=True,
                dictamen_file=None,
            )
        self.assertIn('dictamen', str(ctx.exception).lower())

    def test_conditional_with_file_creates_document(self):
        svc.accept_applicant(
            self.applicant.id, self.program.id, self.coord.id,
            notes='Cumple cursos remediales en primer semestre',
            is_conditional=True,
            dictamen_file=_file('dictamen.pdf'),
        )
        dictamen = AcceptanceDocument.query.filter_by(
            user_program_id=self.up.id,
            document_type='acceptance_opinion',
        ).first()
        self.assertIsNotNone(dictamen)
        self.assertEqual(dictamen.status, 'uploaded')
        self.assertIsNotNone(dictamen.file_path)

    def test_conditional_logs_specific_action(self):
        svc.accept_applicant(
            self.applicant.id, self.program.id, self.coord.id,
            notes='condicionado',
            is_conditional=True,
            dictamen_file=_file('dictamen.pdf'),
        )
        h = UserHistory.query.filter_by(
            user_id=self.applicant.id,
            action='admission_accepted_conditional',
        ).count()
        self.assertEqual(h, 1)

    def test_unconditional_does_not_create_dictamen(self):
        svc.accept_applicant(
            self.applicant.id, self.program.id, self.coord.id,
            notes='aceptado',
            is_conditional=False,
        )
        dictamen = AcceptanceDocument.query.filter_by(
            user_program_id=self.up.id,
            document_type='acceptance_opinion',
        ).first()
        self.assertIsNone(dictamen)
        h = UserHistory.query.filter_by(
            user_id=self.applicant.id,
            action='admission_accepted',
        ).count()
        self.assertEqual(h, 1)


class TestMarkInterviewCompleted(unittest.TestCase):
    """Sprint 1 Fase 7.2 — mark_interview_completed must log to user_history."""

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_app = make_role('applicant')
        self.role_coord = make_role('program_admin')
        self.coord = make_user(self.role_coord, suffix='_coord')
        self.applicant = make_user(self.role_app, suffix='_app')
        self.period = make_period()
        self.program = make_program(self.coord)
        self.up = make_user_program(
            self.applicant, self.program, self.period, status='in_progress',
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_mark_interview_logs_history_with_coordinator_id(self):
        svc.mark_interview_completed(
            self.applicant.id, self.program.id, coordinator_id=self.coord.id,
        )
        h = UserHistory.query.filter_by(
            user_id=self.applicant.id,
            action='interview_completed',
        ).first()
        self.assertIsNotNone(h)
        self.assertEqual(h.admin_id, self.coord.id)


if __name__ == '__main__':
    unittest.main()

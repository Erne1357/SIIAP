# tests/acceptance/test_per_doc_notification.py
"""
Sprint 1 Fase 1.1 — coordinator uploads each acceptance document independently.
Verifies that:
  - upload of acceptance_letter alone notifies the applicant once
  - upload of course_schedule (after letter) notifies the applicant again,
    and additionally fires the "docs_ready" notification
  - re-uploading does NOT re-notify (was_pending guard)
"""

import io
import unittest
from werkzeug.datastructures import FileStorage

from app import create_app, db
from app.models.notification import Notification
from app.models.acceptance_document import AcceptanceDocument
from app.services import acceptance_service as svc

from tests.acceptance.conftest import (
    make_test_config, make_role, make_user, make_program, make_period,
    make_accepted_user_program,
)


def _file(name='doc.pdf'):
    return FileStorage(
        stream=io.BytesIO(b'%PDF-1.4 fake'),
        filename=name,
        content_type='application/pdf',
    )


class TestPerDocNotification(unittest.TestCase):

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
        self.up = make_accepted_user_program(self.applicant, self.program, self.period)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _notification_count(self, type_):
        return Notification.query.filter_by(
            user_id=self.applicant.id, type=type_,
        ).count()

    def test_letter_upload_creates_individual_notification(self):
        svc.upload_coordinator_doc(
            user_id=self.applicant.id,
            program_id=self.program.id,
            document_type='acceptance_letter',
            file_storage=_file('carta.pdf'),
            coordinator_id=self.coord.id,
        )
        self.assertEqual(
            self._notification_count('acceptance_acceptance_letter_uploaded'), 1,
        )
        # docs_ready should NOT fire yet (only one doc)
        self.assertEqual(self._notification_count('acceptance_docs_ready'), 0)

    def test_schedule_after_letter_fires_individual_and_ready(self):
        svc.upload_coordinator_doc(
            user_id=self.applicant.id, program_id=self.program.id,
            document_type='acceptance_letter',
            file_storage=_file('carta.pdf'), coordinator_id=self.coord.id,
        )
        svc.upload_coordinator_doc(
            user_id=self.applicant.id, program_id=self.program.id,
            document_type='course_schedule',
            file_storage=_file('tira.pdf'), coordinator_id=self.coord.id,
        )
        self.assertEqual(
            self._notification_count('acceptance_acceptance_letter_uploaded'), 1,
        )
        self.assertEqual(
            self._notification_count('acceptance_course_schedule_uploaded'), 1,
        )
        self.assertEqual(self._notification_count('acceptance_docs_ready'), 1)

    def test_reupload_does_not_renotify(self):
        # First upload
        svc.upload_coordinator_doc(
            user_id=self.applicant.id, program_id=self.program.id,
            document_type='acceptance_letter',
            file_storage=_file('carta.pdf'), coordinator_id=self.coord.id,
        )
        # Re-upload of the same document
        svc.upload_coordinator_doc(
            user_id=self.applicant.id, program_id=self.program.id,
            document_type='acceptance_letter',
            file_storage=_file('carta_v2.pdf'), coordinator_id=self.coord.id,
        )
        # Still only one notification (was_pending guard)
        self.assertEqual(
            self._notification_count('acceptance_acceptance_letter_uploaded'), 1,
        )

    def test_document_record_persisted(self):
        svc.upload_coordinator_doc(
            user_id=self.applicant.id, program_id=self.program.id,
            document_type='acceptance_letter',
            file_storage=_file('carta.pdf'), coordinator_id=self.coord.id,
        )
        doc = AcceptanceDocument.query.filter_by(
            user_program_id=self.up.id, document_type='acceptance_letter',
        ).first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, 'uploaded')


if __name__ == '__main__':
    unittest.main()

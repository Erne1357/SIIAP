# tests/permanence/test_confirm_semester_enrollment.py
"""
Sprint 1 Fase 1.2 — bug fix: confirm_semester_enrollment now closes the
previous SemesterEnrollment and validates that the destination period is
the immediate next one (or force=True).
"""

import unittest
from datetime import date

from app import create_app, db
from app.models.semester_enrollment import SemesterEnrollment
from app.services import permanence_service as svc

from tests.permanence.conftest import (
    make_test_config, make_role, make_user, make_program, make_period,
    make_user_program, make_enrollment,
)


class TestConfirmSemesterEnrollment(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_student = make_role('student')
        self.role_coord = make_role('program_admin')
        self.coord = make_user(self.role_coord, suffix='_coord')
        self.student = make_user(self.role_student, suffix='_st')
        self.program = make_program(self.coord)

        # Create three sequential periods
        self.p1 = make_period('20251', date(2025, 1, 15))
        self.p2 = make_period('20253', date(2025, 8, 1))
        self.p3 = make_period('20261', date(2026, 1, 15))

        self.up = make_user_program(self.student, self.program, self.p1, semester=1)
        # Existing active SE in p1 (semester 1)
        self.se1 = make_enrollment(self.up, self.p1, 1, status='active', confirmed=True)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_advance_to_immediate_next_period_succeeds(self):
        svc.confirm_semester_enrollment(
            user_program_id=self.up.id,
            academic_period_id=self.p2.id,
            coordinator_id=self.coord.id,
        )
        # Previous SE must be marked completed
        db.session.refresh(self.se1)
        self.assertEqual(self.se1.status, 'completed')

        # New SE must exist and be active
        new_se = SemesterEnrollment.query.filter_by(
            user_program_id=self.up.id,
            academic_period_id=self.p2.id,
        ).first()
        self.assertIsNotNone(new_se)
        self.assertEqual(new_se.semester_number, 2)
        self.assertEqual(new_se.status, 'active')
        self.assertTrue(new_se.enrollment_confirmed)

    def test_skip_period_blocked_without_force(self):
        with self.assertRaises(svc.InvalidStateTransition) as ctx:
            svc.confirm_semester_enrollment(
                user_program_id=self.up.id,
                academic_period_id=self.p3.id,  # Skips p2
                coordinator_id=self.coord.id,
            )
        msg = str(ctx.exception).lower()
        self.assertIn('rezago', msg)

    def test_skip_period_allowed_with_force(self):
        svc.confirm_semester_enrollment(
            user_program_id=self.up.id,
            academic_period_id=self.p3.id,
            coordinator_id=self.coord.id,
            force=True,
        )
        db.session.refresh(self.se1)
        self.assertEqual(self.se1.status, 'completed')
        new_se = SemesterEnrollment.query.filter_by(
            user_program_id=self.up.id,
            academic_period_id=self.p3.id,
        ).first()
        self.assertIsNotNone(new_se)
        self.assertEqual(new_se.status, 'active')

    def test_no_previous_enrollment_works(self):
        # Wipe the existing SE
        db.session.delete(self.se1)
        db.session.commit()
        svc.confirm_semester_enrollment(
            user_program_id=self.up.id,
            academic_period_id=self.p1.id,
            coordinator_id=self.coord.id,
        )
        new_se = SemesterEnrollment.query.filter_by(
            user_program_id=self.up.id,
            academic_period_id=self.p1.id,
        ).first()
        self.assertIsNotNone(new_se)
        self.assertEqual(new_se.semester_number, 1)
        self.assertEqual(new_se.status, 'active')

    def test_confirm_already_existing_se_does_not_close_previous(self):
        # If the SE for the destination period already exists (not confirmed),
        # confirming it should activate it, not duplicate.
        existing = make_enrollment(self.up, self.p2, 2, status='pending', confirmed=False)
        db.session.commit()
        svc.confirm_semester_enrollment(
            user_program_id=self.up.id,
            academic_period_id=self.p2.id,
            coordinator_id=self.coord.id,
        )
        db.session.refresh(existing)
        self.assertEqual(existing.status, 'active')
        self.assertTrue(existing.enrollment_confirmed)
        # se1 not affected
        db.session.refresh(self.se1)
        self.assertEqual(self.se1.status, 'active')


if __name__ == '__main__':
    unittest.main()

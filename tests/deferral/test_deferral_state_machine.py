# tests/deferral/test_deferral_state_machine.py
"""
Deferral flows go through the admission state machine: a refused transition
raises DeferralNotAllowed before any side effect, reactivation returns the
applicant `accepted`, and the expiry task never rewrites the status of an
applicant who is no longer `deferred`.
"""
import unittest
from datetime import date, timedelta

from app import create_app, db
from app.models.academic_period import AcademicPeriod
from app.models.acceptance_document import AcceptanceDocument
from app.models.enrollment_deferral import EnrollmentDeferral
from app.models.user_program import UserProgram
from app.services import deferral_service as dsvc

from tests.program_scope.conftest import (
    make_test_config, make_role, make_user, make_program, make_period,
    make_user_program,
)


class DeferralStateMachineTest(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.coord = make_user(make_role('program_admin'), suffix='_c')
        self.applicant = make_user(make_role('applicant'), suffix='_a')
        self.period = make_period(code='20261')
        today = date.today()
        self.next_period = AcademicPeriod(
            code='20262', name='Period 20262',
            start_date=today + timedelta(days=150),
            end_date=today + timedelta(days=300),
            admission_start_date=today + timedelta(days=120),
            admission_end_date=today + timedelta(days=145),
            is_active=False, status='planned',
        )
        self.past_period = AcademicPeriod(
            code='20251', name='Period 20251',
            start_date=today - timedelta(days=400),
            end_date=today - timedelta(days=30),
            admission_start_date=today - timedelta(days=450),
            admission_end_date=today - timedelta(days=410),
            is_active=False, status='completed',
        )
        db.session.add_all([self.next_period, self.past_period])
        db.session.flush()
        self.program = make_program(self.coord, slug='prog-sm')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _deferral(self, up, status, to_period, number=1):
        d = EnrollmentDeferral(
            user_program_id=up.id, original_period_id=self.period.id,
            deferred_to_period_id=to_period.id, deferral_number=number,
            status=status, requested_by='applicant',
        )
        db.session.add(d)
        db.session.commit()
        return d

    def test_approve_refuses_when_not_accepted_without_side_effects(self):
        up = make_user_program(self.applicant, self.program, self.period, status='enrolled')
        db.session.add(AcceptanceDocument(
            user_program_id=up.id, document_type='course_schedule',
            file_path='x/y.pdf', status='uploaded', uploaded_by_id=self.coord.id,
        ))
        d = self._deferral(up, 'pending', self.next_period)

        with self.assertRaises(dsvc.DeferralNotAllowed):
            dsvc.approve_deferral(d.id, self.coord.id, notes='n')

        db.session.rollback()
        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'enrolled')
        self.assertEqual(EnrollmentDeferral.query.get(d.id).status, 'pending')
        self.assertEqual(AcceptanceDocument.query.filter_by(user_program_id=up.id).count(), 1)

    def test_approve_works_when_accepted(self):
        up = make_user_program(self.applicant, self.program, self.period, status='accepted')
        d = self._deferral(up, 'pending', self.next_period)

        dsvc.approve_deferral(d.id, self.coord.id)

        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'deferred')
        self.assertEqual(EnrollmentDeferral.query.get(d.id).status, 'active')

    def test_reactivate_returns_accepted(self):
        up = make_user_program(self.applicant, self.program, self.period, status='deferred')
        d = self._deferral(up, 'active', self.next_period)

        dsvc.reactivate_deferred(self.applicant.id, self.program.id, self.coord.id)

        up = UserProgram.query.get(up.id)
        self.assertEqual(up.admission_status, 'accepted')
        self.assertEqual(up.admission_period_id, self.next_period.id)
        self.assertEqual(EnrollmentDeferral.query.get(d.id).status, 'used')

    def test_expiry_task_does_not_touch_non_deferred_applicant(self):
        up = make_user_program(self.applicant, self.program, self.period, status='accepted')
        self._deferral(up, 'used', self.past_period, number=1)
        d = self._deferral(up, 'active', self.past_period, number=2)

        result = dsvc.check_and_expire_deferrals()

        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'accepted')
        self.assertEqual(EnrollmentDeferral.query.get(d.id).status, 'expired')
        self.assertEqual(result['expired'], 1)

    def test_expiry_task_still_expires_deferred_applicant_out_of_deferrals(self):
        up = make_user_program(self.applicant, self.program, self.period, status='deferred')
        self._deferral(up, 'used', self.past_period, number=1)
        self._deferral(up, 'active', self.past_period, number=2)

        dsvc.check_and_expire_deferrals()

        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'expired')

    def test_defer_applicant_skips_summer_period(self):
        today = date.today()
        regular = AcademicPeriod(
            code='20271', name='Period 20271',
            start_date=today + timedelta(days=400),
            end_date=today + timedelta(days=550),
            admission_start_date=today + timedelta(days=370),
            admission_end_date=today + timedelta(days=395),
            is_active=False, status='planned',
        )
        db.session.add(regular)
        db.session.flush()
        up = make_user_program(self.applicant, self.program, self.period, status='accepted')

        d = dsvc.defer_applicant(self.applicant.id, self.program.id, self.coord.id)

        # 20262 (summer) sits between 20261 and 20271 and must be skipped.
        self.assertEqual(d.deferred_to_period_id, regular.id)
        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'deferred')

    def test_defer_applicant_refuses_when_only_summer_period_follows(self):
        up = make_user_program(self.applicant, self.program, self.period, status='accepted')
        db.session.commit()

        with self.assertRaises(dsvc.DeferralNotAllowed):
            dsvc.defer_applicant(self.applicant.id, self.program.id, self.coord.id)

        db.session.rollback()
        self.assertEqual(UserProgram.query.get(up.id).admission_status, 'accepted')
        self.assertEqual(EnrollmentDeferral.query.filter_by(user_program_id=up.id).count(), 0)


if __name__ == '__main__':
    unittest.main()

"""
acceptance_service beyond scope: document workflow, receipt review, control-number
assignment (the accepted -> enrolled transition) and document debt.
"""

import io
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step, Submission
from app.models.acceptance_document import AcceptanceDocument
from app.models.notification import Notification
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user import User
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.services import acceptance_service as svc
from app.utils.datetime_utils import now_local
from tests.support.factories import (
    enroll, get_or_create_role, make_academic_period, make_program, make_user,
)


def _file(name='doc.pdf'):
    return FileStorage(stream=io.BytesIO(b'%PDF-1.4 x'), filename=name,
                       content_type='application/pdf')


def _hist(user_id, action=None):
    q = UserHistory.query.filter_by(user_id=user_id)
    return q.filter_by(action=action).all() if action else q.all()


def _notifs(user_id, type_=None):
    q = Notification.query.filter_by(user_id=user_id)
    return q.filter_by(type=type_).all() if type_ else q.all()


@pytest.fixture
def acc(app):
    get_or_create_role('student')
    coord = make_user('program_admin')
    program = make_program(coord)
    applicant = make_user('applicant')
    period = make_academic_period('20261')
    up = enroll(applicant, program, 'accepted')
    up.admission_period_id = period.id
    db.session.commit()
    return type('A', (), dict(coord=coord, program=program, applicant=applicant, up=up, period=period))


def _upload_both(a):
    svc.upload_coordinator_doc(a.applicant.id, a.program.id, 'acceptance_letter', _file(), a.coord.id)
    svc.upload_coordinator_doc(a.applicant.id, a.program.id, 'course_schedule', _file(), a.coord.id)


def _approved_receipt(a):
    _upload_both(a)
    doc = svc.submit_enrollment_receipt(a.applicant.id, a.program.id, _file(), a.applicant.id)
    svc.review_enrollment_receipt(doc.id, a.coord.id, 'approved')
    return doc


class TestStatusAndStats:
    def test_status_defaults_to_pending_for_all_types(self, acc):
        s = svc.get_acceptance_status(acc.up.id)
        assert set(s) == svc.VALID_DOC_TYPES
        assert all(v['status'] == 'pending' and v['id'] is None for v in s.values())

    def test_status_reflects_uploaded_doc(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                   _file(), acc.coord.id)
        assert svc.get_acceptance_status(acc.up.id)['acceptance_letter']['status'] == 'uploaded'

    def test_status_unknown_user_program(self, acc):
        with pytest.raises(svc.ApplicantNotFound):
            svc.get_acceptance_status(99999)

    def test_stats_progression(self, acc):
        assert svc.get_acceptance_stats(acc.program.id) == {
            'total_accepted': 1, 'pending_docs': 1, 'receipt_submitted': 0, 'completed': 0}
        _upload_both(acc)
        assert svc.get_acceptance_stats(acc.program.id)['pending_docs'] == 1   # letter+schedule, no receipt
        doc = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        assert svc.get_acceptance_stats(acc.program.id)['receipt_submitted'] == 1
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved')
        s = svc.get_acceptance_stats(acc.program.id)
        assert s['completed'] == 1 and s['receipt_submitted'] == 0

    def test_stats_only_count_accepted(self, acc):
        other = make_user('applicant')
        enroll(other, acc.program, 'in_progress')
        db.session.commit()
        assert svc.get_acceptance_stats(acc.program.id)['total_accepted'] == 1

    def test_accepted_list_excludes_inactive_and_other_states(self, acc):
        inactive = make_user('applicant', is_active=False)
        enroll(inactive, acc.program, 'accepted')
        enroll(make_user('applicant'), acc.program, 'rejected')
        db.session.commit()
        rows = svc.get_accepted_applicants(acc.program.id)
        assert [r['user']['email'] for r in rows] == [acc.applicant.email]

    def test_accepted_list_exposes_uuid_not_integer_id(self, acc):
        row = svc.get_accepted_applicants(acc.program.id)[0]
        assert row['user']['id'] == str(acc.applicant.uuid)
        assert set(row['acceptance_docs']) == svc.VALID_DOC_TYPES


class TestUploadCoordinatorDoc:
    def test_creates_document_file_history_and_notification(self, acc):
        doc = svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                         _file(), acc.coord.id)
        assert doc.status == 'uploaded' and doc.uploaded_by_id == acc.coord.id
        assert doc.file_path.startswith(f'{acc.applicant.id}/acceptance/')
        assert len(_hist(acc.applicant.id, 'acceptance_acceptance_letter_uploaded')) == 1
        assert len(_notifs(acc.applicant.id)) == 1

    @pytest.mark.parametrize('doc_type', ['enrollment_receipt', 'nonsense'])
    def test_type_not_allowed_for_coordinator(self, acc, doc_type):
        with pytest.raises(svc.InvalidDocumentType):
            svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, doc_type, _file(), acc.coord.id)

    @pytest.mark.parametrize('status', ['in_progress', 'deliberation', 'rejected', 'enrolled'])
    def test_requires_accepted_state(self, acc, status):
        acc.up.admission_status = status
        db.session.commit()
        with pytest.raises(svc.InvalidStateTransition):
            svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                       _file(), acc.coord.id)
        assert AcceptanceDocument.query.count() == 0

    def test_unknown_applicant(self, acc):
        with pytest.raises(svc.ApplicantNotFound):
            svc.upload_coordinator_doc(99999, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)

    def test_docs_ready_only_after_both(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        assert _notifs(acc.applicant.id, 'acceptance_docs_ready') == []
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'course_schedule', _file(), acc.coord.id)
        assert len(_notifs(acc.applicant.id, 'acceptance_docs_ready')) == 1
        assert len(_hist(acc.applicant.id, 'acceptance_docs_uploaded')) == 1

    def test_reupload_replaces_without_renotifying(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        before = len(_notifs(acc.applicant.id))
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        assert len(_notifs(acc.applicant.id)) == before
        assert AcceptanceDocument.query.filter_by(document_type='acceptance_letter').count() == 1

    def test_disallowed_extension_aborts(self, acc):
        from werkzeug.exceptions import BadRequest
        with pytest.raises(BadRequest):
            svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                       _file('x.exe'), acc.coord.id)

    # Regression: the generated action 'acceptance_acceptance_opinion_uploaded' was unregistered, so log_action raised ValueError.
    def test_acceptance_opinion_upload(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_opinion',
                                   _file(), acc.coord.id)
        assert AcceptanceDocument.query.filter_by(document_type='acceptance_opinion').count() == 1
        assert len(_hist(acc.applicant.id, 'acceptance_acceptance_opinion_uploaded')) == 1


class TestSubmitEnrollmentReceipt:
    def test_requires_coordinator_docs_first(self, acc):
        with pytest.raises(svc.InvalidStateTransition, match='coordinador'):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_only_letter_is_not_enough(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        with pytest.raises(svc.InvalidStateTransition):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_requires_accepted(self, acc):
        _upload_both(acc)
        acc.up.admission_status = 'enrolled'
        db.session.commit()
        with pytest.raises(svc.InvalidStateTransition, match='aceptados'):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_success_notifies_coordinator_and_logs(self, acc):
        _upload_both(acc)
        doc = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        assert doc.status == 'uploaded'
        n = _notifs(acc.coord.id, 'enrollment_receipt_submitted')
        assert len(n) == 1 and n[0].is_actionable
        assert len(_hist(acc.applicant.id, 'enrollment_receipt_submitted')) == 1

    def test_cannot_replace_pending_review(self, acc):
        _upload_both(acc)
        svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        with pytest.raises(svc.InvalidStateTransition, match="'uploaded'"):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_cannot_replace_approved(self, acc):
        _approved_receipt(acc)
        with pytest.raises(svc.InvalidStateTransition, match="'approved'"):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_resubmit_after_rejection_clears_review(self, acc):
        _upload_both(acc)
        doc = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'rejected', 'borrosa')
        again = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        assert again.id == doc.id and again.status == 'uploaded'
        assert again.review_notes is None and again.reviewed_by_id is None


class TestReviewReceipt:
    def _submitted(self, acc):
        _upload_both(acc)
        return svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)

    def test_approve(self, acc):
        doc = self._submitted(acc)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved', 'ok')
        assert doc.status == 'approved' and doc.reviewed_by_id == acc.coord.id
        assert doc.reviewed_at is not None
        assert len(_notifs(acc.applicant.id, 'enrollment_receipt_approved')) == 1
        assert len(_hist(acc.applicant.id, 'enrollment_receipt_approved')) == 1

    def test_reject_carries_reason(self, acc):
        doc = self._submitted(acc)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'rejected', 'ilegible')
        n = _notifs(acc.applicant.id, 'enrollment_receipt_rejected')[0]
        assert 'ilegible' in n.message and n.is_actionable
        assert len(_hist(acc.applicant.id, 'enrollment_receipt_rejected')) == 1

    def test_reject_without_notes_has_default_reason(self, acc):
        doc = self._submitted(acc)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'rejected')
        assert 'Sin especificar' in _notifs(acc.applicant.id, 'enrollment_receipt_rejected')[0].message

    @pytest.mark.parametrize('bad', ['pending', 'uploaded', '', None])
    def test_invalid_status(self, acc, bad):
        doc = self._submitted(acc)
        with pytest.raises(ValueError):
            svc.review_enrollment_receipt(doc.id, acc.coord.id, bad)

    def test_unknown_doc(self, acc):
        with pytest.raises(svc.ApplicantNotFound):
            svc.review_enrollment_receipt(99999, acc.coord.id, 'approved')

    def test_only_receipts_reviewable(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        letter = AcceptanceDocument.query.filter_by(document_type='acceptance_letter').one()
        with pytest.raises(svc.InvalidDocumentType):
            svc.review_enrollment_receipt(letter.id, acc.coord.id, 'approved')

    def test_cannot_review_twice(self, acc):
        doc = self._submitted(acc)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved')
        with pytest.raises(svc.InvalidStateTransition):
            svc.review_enrollment_receipt(doc.id, acc.coord.id, 'rejected', 'x')
        assert doc.status == 'approved'

    def test_review_queues_email_to_applicant(self, acc):
        from app.models.email_queue import EmailQueue
        doc = self._submitted(acc)
        before = EmailQueue.query.filter_by(user_id=acc.applicant.id).count()
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved')
        assert EmailQueue.query.filter_by(user_id=acc.applicant.id).count() == before + 1


class TestDeleteCoordinatorDoc:
    def test_deletes_and_logs(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        doc = AcceptanceDocument.query.one()
        svc.delete_coordinator_doc(doc.id, acc.coord.id)
        assert AcceptanceDocument.query.count() == 0
        assert len(_hist(acc.applicant.id, 'acceptance_doc_deleted')) == 1

    def test_unknown(self, acc):
        with pytest.raises(svc.ApplicantNotFound):
            svc.delete_coordinator_doc(99999, acc.coord.id)

    def test_receipt_not_deletable_by_coordinator(self, acc):
        doc = _approved_receipt(acc)
        with pytest.raises(svc.InvalidDocumentType):
            svc.delete_coordinator_doc(doc.id, acc.coord.id)
        assert AcceptanceDocument.query.get(doc.id) is not None

    def test_deleted_doc_can_be_uploaded_again_and_renotifies(self, acc):
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        svc.delete_coordinator_doc(AcceptanceDocument.query.one().id, acc.coord.id)
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter', _file(), acc.coord.id)
        assert len(_hist(acc.applicant.id, 'acceptance_acceptance_letter_uploaded')) == 2


class TestAssignControlNumber:
    def test_full_transition(self, acc):
        _approved_receipt(acc)
        up = svc.assign_control_number(acc.applicant.id, acc.program.id, ' M21111182 ', acc.coord.id)
        user = User.query.get(acc.applicant.id)
        assert up.admission_status == 'enrolled' and up.current_semester == 1
        assert up.academic_status == 'active'
        assert user.control_number == 'M21111182' and user.username == 'M21111182'
        assert user.role.name == 'student'
        assert user.control_number_assigned_at is not None

    def test_creates_confirmed_first_semester_enrollment(self, acc):
        _approved_receipt(acc)
        svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
        se = SemesterEnrollment.query.filter_by(user_program_id=acc.up.id).one()
        assert se.semester_number == 1 and se.enrollment_confirmed is True
        assert se.academic_period_id == acc.period.id and se.confirmed_by == acc.coord.id

    def test_falls_back_to_active_period(self, acc):
        _approved_receipt(acc)
        acc.up.admission_period_id = None
        db.session.commit()
        svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
        assert SemesterEnrollment.query.one().academic_period_id == acc.period.id

    def test_history_and_notification(self, acc):
        _approved_receipt(acc)
        svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
        assert len(_hist(acc.applicant.id, 'control_number_assigned')) == 1
        assert len(_notifs(acc.applicant.id, 'control_number_assigned')) == 1

    @pytest.mark.parametrize('bad', ['', '   ', None])
    def test_empty_number(self, acc, bad):
        with pytest.raises(ValueError, match='vacío'):
            svc.assign_control_number(acc.applicant.id, acc.program.id, bad, acc.coord.id)

    def test_collision_uses_uniform_message_without_number(self, acc):
        other = make_user('student')
        other.assign_control_number('M777')
        db.session.commit()
        _approved_receipt(acc)
        with pytest.raises(ValueError) as ei:
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M777', acc.coord.id)
        assert str(ei.value) == svc.CONTROL_NUMBER_REJECTED_MESSAGE
        assert 'M777' not in str(ei.value)
        assert User.query.get(acc.applicant.id).control_number is None

    def test_same_user_may_reassign_own_number(self, acc):
        _approved_receipt(acc)
        acc.applicant.assign_control_number('M5')
        db.session.commit()
        assert svc.assign_control_number(acc.applicant.id, acc.program.id, 'M5',
                                         acc.coord.id).admission_status == 'enrolled'

    def test_requires_approved_receipt(self, acc):
        _upload_both(acc)
        svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        with pytest.raises(svc.InvalidStateTransition, match='aprobada'):
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)

    def test_requires_a_receipt_at_all(self, acc):
        with pytest.raises(svc.InvalidStateTransition):
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)

    @pytest.mark.parametrize('status', ['in_progress', 'deliberation', 'rejected', 'enrolled'])
    def test_requires_accepted(self, acc, status):
        acc.up.admission_status = status
        db.session.commit()
        with pytest.raises(svc.InvalidStateTransition):
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)

    def test_failure_leaves_user_unchanged(self, acc):
        with pytest.raises(svc.InvalidStateTransition):
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
        user = User.query.get(acc.applicant.id)
        assert user.control_number is None and user.role.name == 'applicant'

    def test_missing_student_role(self, acc):
        from app.models.role import Role
        _approved_receipt(acc)
        Role.query.filter_by(name='student').delete()
        db.session.commit()
        with pytest.raises(ValueError, match='student'):
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)

    def test_unknown_applicant(self, acc):
        with pytest.raises(svc.ApplicantNotFound):
            svc.assign_control_number(99999, acc.program.id, 'M1', acc.coord.id)


class TestDocumentDebt:
    def _extension(self, acc, *, granted_until, with_submission=None):
        ph = Phase('admission', 'd')
        db.session.add(ph)
        db.session.flush()
        st = Step('s', 'd', ph.id)
        db.session.add(st)
        db.session.flush()
        ps = ProgramStep(program_id=acc.program.id, step_id=st.id, sequence=2)
        db.session.add(ps)
        db.session.flush()
        ar = Archive('Constancia', 'd', None, st.id)
        db.session.add(ar)
        db.session.flush()
        ext = ExtensionRequest(user_id=acc.applicant.id, archive_id=ar.id, program_step_id=ps.id,
                               requested_by=acc.applicant.id, role='student', reason='r',
                               requested_until=granted_until)
        ext.status = 'granted'
        ext.granted_until = granted_until
        db.session.add(ext)
        if with_submission:
            db.session.add(Submission('f.pdf', with_submission, acc.applicant.id, ar.id, ps.id, None))
        db.session.commit()

    def test_expired_extension_without_document_blocks(self, acc):
        _approved_receipt(acc)
        self._extension(acc, granted_until=now_local() - timedelta(days=2))
        with pytest.raises(svc.DocumentDebtError) as ei:
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
        assert ei.value.debts[0]['archive_name'] == 'Constancia'
        assert User.query.get(acc.applicant.id).control_number is None
        assert UserProgram.query.get(acc.up.id).admission_status == 'accepted'

    def test_running_extension_does_not_block(self, acc):
        _approved_receipt(acc)
        self._extension(acc, granted_until=now_local() + timedelta(days=5))
        assert svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1',
                                         acc.coord.id).admission_status == 'enrolled'

    @pytest.mark.parametrize('status', ['approved', 'review'])
    def test_expired_extension_with_delivered_document_ok(self, acc, status):
        _approved_receipt(acc)
        self._extension(acc, granted_until=now_local() - timedelta(days=2), with_submission=status)
        svc._check_document_debt(acc.applicant.id, acc.program.id)

    @pytest.mark.parametrize('status', ['pending', 'rejected'])
    def test_expired_extension_with_unaccepted_document_still_debt(self, acc, status):
        self._extension(acc, granted_until=now_local() - timedelta(days=2), with_submission=status)
        with pytest.raises(svc.DocumentDebtError):
            svc._check_document_debt(acc.applicant.id, acc.program.id)

    def test_no_extensions_no_debt(self, acc):
        svc._check_document_debt(acc.applicant.id, acc.program.id)


class TestAssignControlNumberAdmin:
    # Regression: the action 'control_number_assigned_admin' was unregistered, so log_action raised ValueError.
    def test_admin_assignment_completes(self, acc):
        up = svc.assign_control_number_admin(acc.applicant.id, acc.program.id, 'L1', acc.coord.id)
        assert up.admission_status == 'enrolled'
        assert User.query.get(acc.applicant.id).control_number == 'L1'
        assert len(_hist(acc.applicant.id, 'control_number_assigned_admin')) == 1


def _spy_notifications(monkeypatch):
    """Record any control-number notification or queued email attempt."""
    from app.services.email_service import EmailService
    from app.services.notification_service import NotificationService
    seen = []
    monkeypatch.setattr(
        NotificationService, 'notify_control_number_assigned',
        staticmethod(lambda *a, **k: seen.append(('notify', a, k))),
    )
    monkeypatch.setattr(
        EmailService, 'queue_email',
        staticmethod(lambda *a, **k: seen.append(('email', a, k))),
    )
    return seen


class TestAssignControlNumberRaces:
    def test_integrity_error_gives_friendly_error_and_rolls_back(self, acc, monkeypatch):
        _approved_receipt(acc)
        real_commit = db.session.commit
        calls = {'n': 0}

        def boom():
            calls['n'] += 1
            if calls['n'] == 1:
                raise IntegrityError('INSERT', {}, Exception('uq_user_control_number'))
            return real_commit()

        emitted = []
        notified = _spy_notifications(monkeypatch)
        monkeypatch.setattr(svc, '_emit_acceptance_updated', lambda *a, **k: emitted.append(a))
        monkeypatch.setattr(db.session, 'commit', boom)
        with pytest.raises(ValueError) as ei:
            svc.assign_control_number(acc.applicant.id, acc.program.id, 'M900', acc.coord.id)
        assert str(ei.value) == svc.CONTROL_NUMBER_REJECTED_MESSAGE
        assert emitted == []
        assert notified == []
        monkeypatch.undo()
        assert _notifs(acc.applicant.id, 'control_number_assigned') == []
        assert UserProgram.query.get(acc.up.id).admission_status == 'accepted'
        assert User.query.get(acc.applicant.id).control_number is None

    def test_socket_emitted_only_after_commit(self, acc, monkeypatch):
        _approved_receipt(acc)
        order = []
        real_commit = db.session.commit

        def commit():
            order.append('commit')
            return real_commit()

        monkeypatch.setattr(db.session, 'commit', commit)
        monkeypatch.setattr(svc, '_emit_acceptance_updated',
                            lambda *a, **k: order.append('emit'))
        svc.assign_control_number(acc.applicant.id, acc.program.id, 'M901', acc.coord.id)
        assert order[-2:] == ['commit', 'emit']


class TestAssignControlNumberAdminOverride:
    def test_from_rejected_enrolls_by_override(self, acc):
        acc.up.admission_status = 'rejected'
        db.session.commit()
        up = svc.assign_control_number_admin(acc.applicant.id, acc.program.id, 'L100', acc.coord.id)
        assert up.admission_status == 'enrolled'
        user = User.query.get(acc.applicant.id)
        assert user.control_number == 'L100' and user.role.name == 'student'
        assert len(_hist(acc.applicant.id, 'control_number_assigned_admin')) == 1

    def test_already_enrolled_keeps_status_and_reassigns_number(self, acc):
        acc.up.admission_status = 'enrolled'
        acc.up.current_semester = 3
        db.session.commit()
        up = svc.assign_control_number_admin(acc.applicant.id, acc.program.id, 'L200', acc.coord.id)
        assert up.admission_status == 'enrolled' and up.current_semester == 3
        assert User.query.get(acc.applicant.id).control_number == 'L200'

    def test_integrity_error_is_friendly(self, acc, monkeypatch):
        def boom():
            raise IntegrityError('INSERT', {}, Exception('uq_user_control_number'))

        emitted = []
        notified = _spy_notifications(monkeypatch)
        monkeypatch.setattr(svc, '_emit_acceptance_updated', lambda *a, **k: emitted.append(a))
        monkeypatch.setattr(db.session, 'commit', boom)
        with pytest.raises(ValueError) as ei:
            svc.assign_control_number_admin(acc.applicant.id, acc.program.id, 'L300', acc.coord.id)
        assert str(ei.value) == svc.CONTROL_NUMBER_REJECTED_MESSAGE
        assert emitted == []
        assert notified == []


class TestEmitsAfterCommit:
    """`acceptance:updated` emits for upload/submit/review must follow the commit."""

    @staticmethod
    def _spy_emitters(monkeypatch, log):
        """Record only the `acceptance:updated` emits (other services emit too)."""
        from app.extensions import socketio
        from app.sockets import emitters

        def record(event, *a, **k):
            if event == 'acceptance:updated':
                log.append('emit')

        monkeypatch.setattr(socketio, 'emit', record)
        monkeypatch.setattr(emitters, 'emit_to_coordinators', record)

    @staticmethod
    def _fail_service_commit(monkeypatch, module=None):
        """Make only the commit issued by `module` (default acceptance_service) fail."""
        import sys
        real_commit = db.session.commit
        module = module or svc.__name__

        def commit():
            if sys._getframe(1).f_globals.get('__name__') == module:
                raise RuntimeError('commit failed')
            return real_commit()

        monkeypatch.setattr(db.session, 'commit', commit)

    @staticmethod
    def _track_commits(monkeypatch, log):
        real_commit = db.session.commit

        def commit():
            log.append('commit')
            return real_commit()

        monkeypatch.setattr(db.session, 'commit', commit)

    @staticmethod
    def _assert_emit_after_last_commit(log):
        assert 'emit' in log
        last_commit = len(log) - 1 - log[::-1].index('commit')
        assert log.index('emit') > last_commit

    def test_upload_coordinator_doc_no_emit_when_commit_fails(self, acc, monkeypatch):
        log = []
        self._spy_emitters(monkeypatch, log)
        self._fail_service_commit(monkeypatch)
        with pytest.raises(RuntimeError):
            svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                       _file(), acc.coord.id)
        assert log == []

    def test_upload_coordinator_doc_emits_after_commit(self, acc, monkeypatch):
        log = []
        self._spy_emitters(monkeypatch, log)
        self._track_commits(monkeypatch, log)
        svc.upload_coordinator_doc(acc.applicant.id, acc.program.id, 'acceptance_letter',
                                   _file(), acc.coord.id)
        self._assert_emit_after_last_commit(log)

    def test_submit_enrollment_receipt_no_emit_when_commit_fails(self, acc, monkeypatch):
        _upload_both(acc)
        log = []
        self._spy_emitters(monkeypatch, log)
        self._fail_service_commit(monkeypatch)
        with pytest.raises(RuntimeError):
            svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        assert log == []

    def test_submit_enrollment_receipt_emits_after_commit(self, acc, monkeypatch):
        _upload_both(acc)
        log = []
        self._spy_emitters(monkeypatch, log)
        self._track_commits(monkeypatch, log)
        svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        self._assert_emit_after_last_commit(log)

    def test_review_enrollment_receipt_no_emit_when_commit_fails(self, acc, monkeypatch):
        _upload_both(acc)
        doc = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        log = []
        self._spy_emitters(monkeypatch, log)
        # 6D: the review engine issues the decision's commit.
        self._fail_service_commit(monkeypatch, 'app.services.review_engine.engine')
        with pytest.raises(RuntimeError):
            svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved')
        assert log == []

    def test_review_enrollment_receipt_emits_after_commit(self, acc, monkeypatch):
        _upload_both(acc)
        doc = svc.submit_enrollment_receipt(acc.applicant.id, acc.program.id, _file(), acc.applicant.id)
        log = []
        self._spy_emitters(monkeypatch, log)
        self._track_commits(monkeypatch, log)
        svc.review_enrollment_receipt(doc.id, acc.coord.id, 'approved')
        self._assert_emit_after_last_commit(log)

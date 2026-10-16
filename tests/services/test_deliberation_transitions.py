"""
admission_status state machine driven by deliberation_service.

Every mutation must leave a UserHistory row; every decision the applicant must
hear about must leave a Notification (CLAUDE.md: history + notification on
every state change).
"""

import json

import pytest

from app import db
from app.models.email_queue import EmailQueue
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.services import deliberation_service as ds
from app.services.deliberation_service import ApplicantNotFound, InvalidStateTransition
from tests.support.factories import enroll, make_program, make_user


def _history(user_id, action=None):
    q = UserHistory.query.filter_by(user_id=user_id).order_by(UserHistory.id)
    if action:
        q = q.filter_by(action=action)
    return q.all()


def _notifs(user_id, type_=None):
    q = Notification.query.filter_by(user_id=user_id)
    if type_:
        q = q.filter_by(type=type_)
    return q.all()


def _set(adm, status):
    adm.up.admission_status = status
    db.session.commit()


class TestMarkInterviewCompleted:
    def test_in_progress_moves_to_interview_completed(self, admission):
        a = admission
        ds.mark_interview_completed(a.applicant.id, a.program.id, a.coordinator.id)
        assert UserProgram.query.get(a.up.id).admission_status == 'interview_completed'

    def test_logs_history_with_coordinator(self, admission):
        a = admission
        ds.mark_interview_completed(a.applicant.id, a.program.id, a.coordinator.id)
        rows = _history(a.applicant.id, 'interview_completed')
        assert len(rows) == 1 and rows[0].admin_id == a.coordinator.id

    # Regression: mark_interview_completed changed admission_status without notifying the applicant.
    def test_notifies_applicant(self, admission):
        a = admission
        ds.mark_interview_completed(a.applicant.id, a.program.id, a.coordinator.id)
        rows = _notifs(a.applicant.id)
        assert [n.type for n in rows] == ['interview_completed']

    @pytest.mark.parametrize('status', [
        'interview_completed', 'deliberation', 'accepted', 'rejected', 'deferred', 'enrolled'])
    def test_invalid_from_other_states(self, admission, status):
        _set(admission, status)
        with pytest.raises(InvalidStateTransition):
            ds.mark_interview_completed(admission.applicant.id, admission.program.id)
        assert UserProgram.query.get(admission.up.id).admission_status == status

    def test_invalid_transition_writes_no_history(self, admission):
        _set(admission, 'accepted')
        with pytest.raises(InvalidStateTransition):
            ds.mark_interview_completed(admission.applicant.id, admission.program.id)
        assert _history(admission.applicant.id) == []

    def test_unknown_applicant(self, admission):
        with pytest.raises(ApplicantNotFound):
            ds.mark_interview_completed(999999, admission.program.id)

    def test_not_in_this_program(self, admission):
        stranger = make_user('applicant')
        db.session.commit()
        with pytest.raises(ApplicantNotFound):
            ds.mark_interview_completed(stranger.id, admission.program.id)

    def test_not_found_message_does_not_leak_ids(self, admission):
        with pytest.raises(ApplicantNotFound) as ei:
            ds.mark_interview_completed(424242, admission.program.id)
        assert '424242' not in str(ei.value)
        assert str(ei.value) == ds.APPLICANT_NOT_FOUND_MESSAGE

    def test_history_falls_back_to_applicant_when_no_coordinator(self, admission):
        a = admission
        ds.mark_interview_completed(a.applicant.id, a.program.id)
        assert _history(a.applicant.id, 'interview_completed')[0].admin_id == a.applicant.id


class TestStartDeliberation:
    def test_from_interview_completed(self, admission):
        _set(admission, 'interview_completed')
        up = ds.start_deliberation(admission.applicant.id, admission.program.id,
                                   admission.coordinator.id)
        assert up.admission_status == 'deliberation'
        assert up.deliberation_started_at is not None

    def test_history_and_notification(self, admission):
        a = admission
        _set(a, 'interview_completed')
        ds.start_deliberation(a.applicant.id, a.program.id, a.coordinator.id)
        assert len(_history(a.applicant.id, 'deliberation_started')) == 1
        n = _notifs(a.applicant.id, 'deliberation_started')
        assert len(n) == 1 and a.program.name in n[0].message

    @pytest.mark.parametrize('status', [
        'in_progress', 'deliberation', 'accepted', 'rejected', 'deferred', 'enrolled'])
    def test_invalid_from_other_states(self, admission, status):
        _set(admission, status)
        with pytest.raises(InvalidStateTransition):
            ds.start_deliberation(admission.applicant.id, admission.program.id,
                                  admission.coordinator.id)

    def test_invalid_leaves_no_side_effects(self, admission):
        with pytest.raises(InvalidStateTransition):
            ds.start_deliberation(admission.applicant.id, admission.program.id,
                                  admission.coordinator.id)
        assert _notifs(admission.applicant.id) == []
        assert _history(admission.applicant.id) == []


class TestAcceptApplicant:
    @pytest.mark.parametrize('status', ['deliberation', 'interview_completed'])
    def test_accept_from_valid_states(self, admission, status):
        _set(admission, status)
        up = ds.accept_applicant(admission.applicant.id, admission.program.id,
                                 admission.coordinator.id, notes='Bien')
        assert up.admission_status == 'accepted'
        assert up.decision_by == admission.coordinator.id
        assert up.decision_notes == 'Bien'
        assert up.decision_at is not None

    @pytest.mark.parametrize('status', [
        'in_progress', 'accepted', 'rejected', 'deferred', 'enrolled'])
    def test_accept_invalid_states(self, admission, status):
        _set(admission, status)
        with pytest.raises(InvalidStateTransition):
            ds.accept_applicant(admission.applicant.id, admission.program.id,
                                admission.coordinator.id)

    def test_accept_logs_history_and_notifies(self, admission):
        a = admission
        _set(a, 'deliberation')
        ds.accept_applicant(a.applicant.id, a.program.id, a.coordinator.id)
        assert len(_history(a.applicant.id, 'admission_accepted')) == 1
        assert len(_notifs(a.applicant.id, 'deliberation_accepted')) == 1

    def test_accept_notification_is_actionable(self, admission):
        _set(admission, 'deliberation')
        ds.accept_applicant(admission.applicant.id, admission.program.id,
                            admission.coordinator.id)
        assert _notifs(admission.applicant.id, 'deliberation_accepted')[0].is_actionable

    def test_accept_queues_email(self, admission):
        _set(admission, 'deliberation')
        ds.accept_applicant(admission.applicant.id, admission.program.id,
                            admission.coordinator.id)
        mails = EmailQueue.query.filter_by(user_id=admission.applicant.id).all()
        assert len(mails) == 1 and mails[0].status == 'pending'

    def test_accept_clears_previous_rejection_data(self, admission):
        _set(admission, 'deliberation')
        admission.up.rejection_type = 'partial'
        admission.up.correction_required = 'x'
        db.session.commit()
        up = ds.accept_applicant(admission.applicant.id, admission.program.id,
                                 admission.coordinator.id)
        assert up.rejection_type is None and up.correction_required is None

    def test_conditional_without_dictamen_rejected_and_state_kept(self, admission):
        _set(admission, 'deliberation')
        with pytest.raises(ValueError):
            ds.accept_applicant(admission.applicant.id, admission.program.id,
                                admission.coordinator.id, is_conditional=True)
        db.session.rollback()
        assert UserProgram.query.get(admission.up.id).admission_status == 'deliberation'


class TestRejectApplicant:
    def test_full_rejection(self, admission):
        a = admission
        _set(a, 'deliberation')
        up = ds.reject_applicant(a.applicant.id, a.program.id, a.coordinator.id,
                                 rejection_type='full', notes='No cumple')
        assert up.admission_status == 'rejected' and up.rejection_type == 'full'
        assert len(_history(a.applicant.id, 'admission_rejected')) == 1
        assert len(_notifs(a.applicant.id, 'deliberation_rejected')) == 1

    def test_partial_rejection_is_correction_request(self, admission):
        a = admission
        _set(a, 'interview_completed')
        ds.reject_applicant(a.applicant.id, a.program.id, a.coordinator.id,
                            rejection_type='partial', notes='Falta CV',
                            correction_required='Subir CV')
        assert len(_history(a.applicant.id, 'correction_requested')) == 1
        assert len(_notifs(a.applicant.id, 'deliberation_corrections')) == 1
        assert _history(a.applicant.id, 'admission_rejected') == []

    def test_bad_rejection_type(self, admission):
        _set(admission, 'deliberation')
        with pytest.raises(ValueError):
            ds.reject_applicant(admission.applicant.id, admission.program.id,
                                admission.coordinator.id, rejection_type='maybe')
        db.session.rollback()
        assert UserProgram.query.get(admission.up.id).admission_status == 'deliberation'

    @pytest.mark.parametrize('status', [
        'in_progress', 'accepted', 'rejected', 'deferred', 'enrolled'])
    def test_invalid_states(self, admission, status):
        _set(admission, status)
        with pytest.raises(InvalidStateTransition):
            ds.reject_applicant(admission.applicant.id, admission.program.id,
                                admission.coordinator.id)

    def test_partial_with_json_marks_approved_submission_rejected(self, admission):
        from app.models import Archive, Phase, ProgramStep, Step, Submission
        a = admission
        phase = Phase('admission', 'd')
        db.session.add(phase)
        db.session.flush()
        step = Step('s', 'd', phase.id)
        db.session.add(step)
        db.session.flush()
        ps = ProgramStep(program_id=a.program.id, step_id=step.id, sequence=1)
        db.session.add(ps)
        db.session.flush()
        arch = Archive('CV', 'd', None, step.id)
        db.session.add(arch)
        db.session.flush()
        sub = Submission('x.pdf', 'approved', a.applicant.id, arch.id, ps.id, None)
        db.session.add(sub)
        _set(a, 'deliberation')
        ds.reject_applicant(a.applicant.id, a.program.id, a.coordinator.id,
                            rejection_type='partial', notes='n',
                            correction_required=json.dumps(
                                {'archive_id': arch.id, 'notes': 'ilegible'}))
        sub = Submission.query.get(sub.id)
        assert sub.status == 'rejected' and sub.reviewer_comment == 'ilegible'
        assert sub.reviewer_id == a.coordinator.id

    def test_partial_with_plain_text_correction_is_tolerated(self, admission):
        _set(admission, 'deliberation')
        up = ds.reject_applicant(admission.applicant.id, admission.program.id,
                                 admission.coordinator.id, rejection_type='partial',
                                 correction_required='texto libre, no JSON')
        assert up.admission_status == 'rejected'


class TestResets:
    def _reject(self, adm, rtype):
        _set(adm, 'deliberation')
        ds.reject_applicant(adm.applicant.id, adm.program.id, adm.coordinator.id,
                            rejection_type=rtype, notes='n')

    def test_reset_after_partial_rejection(self, admission):
        a = admission
        self._reject(a, 'partial')
        up = ds.reset_to_in_progress(a.applicant.id, a.program.id, a.coordinator.id, 'ok')
        assert up.admission_status == 'in_progress'
        assert up.decision_at is None and up.rejection_type is None
        assert up.correction_required is None and up.decision_by is None
        assert len(_history(a.applicant.id, 'admission_reset')) == 1
        assert len(_notifs(a.applicant.id, 'deliberation_reset')) == 1

    def test_reset_after_full_rejection_is_refused(self, admission):
        self._reject(admission, 'full')
        with pytest.raises(InvalidStateTransition):
            ds.reset_to_in_progress(admission.applicant.id, admission.program.id,
                                    admission.coordinator.id)

    @pytest.mark.parametrize('status', ['in_progress', 'deliberation', 'accepted', 'enrolled'])
    def test_reset_only_from_rejected(self, admission, status):
        _set(admission, status)
        with pytest.raises(InvalidStateTransition):
            ds.reset_to_in_progress(admission.applicant.id, admission.program.id,
                                    admission.coordinator.id)

    @pytest.mark.parametrize('status', [
        'interview_completed', 'deliberation', 'accepted', 'rejected', 'deferred', 'enrolled'])
    def test_force_reset_from_any_state(self, admission, status):
        a = admission
        _set(a, status)
        up = ds.force_reset_applicant(a.applicant.id, a.program.id, a.coordinator.id, 'x')
        assert up.admission_status == 'in_progress'
        assert up.deliberation_started_at is None
        assert len(_history(a.applicant.id, 'admission_reset')) == 1
        assert len(_notifs(a.applicant.id, 'deliberation_reset')) == 1

    def test_force_reset_records_previous_state_in_history(self, admission):
        _set(admission, 'accepted')
        ds.force_reset_applicant(admission.applicant.id, admission.program.id,
                                 admission.coordinator.id)
        assert 'accepted' in _history(admission.applicant.id, 'admission_reset')[0].details


class TestFullLifecycle:
    def test_in_progress_to_accepted_trail(self, admission):
        a = admission
        ds.mark_interview_completed(a.applicant.id, a.program.id, a.coordinator.id)
        ds.start_deliberation(a.applicant.id, a.program.id, a.coordinator.id)
        ds.accept_applicant(a.applicant.id, a.program.id, a.coordinator.id)
        actions = [h.action for h in _history(a.applicant.id)]
        assert actions == ['interview_completed', 'deliberation_started', 'admission_accepted']

    def test_cannot_accept_twice(self, admission):
        a = admission
        _set(a, 'deliberation')
        ds.accept_applicant(a.applicant.id, a.program.id, a.coordinator.id)
        with pytest.raises(InvalidStateTransition):
            ds.accept_applicant(a.applicant.id, a.program.id, a.coordinator.id)
        assert len(_history(a.applicant.id, 'admission_accepted')) == 1


class TestQueries:
    def test_stats_counts_each_status(self, admission):
        a = admission
        other = make_user('applicant')
        enroll(other, a.program, 'accepted')
        db.session.commit()
        s = ds.get_deliberation_stats(a.program.id)
        assert s['in_progress'] == 1 and s['accepted'] == 1 and s['total'] == 2

    def test_stats_ignore_unknown_status(self, admission):
        other = make_user('applicant')
        enroll(other, admission.program, 'expired')
        db.session.commit()
        assert ds.get_deliberation_stats(admission.program.id)['total'] == 1

    def test_stats_scoped_to_program(self, admission):
        other_prog = make_program()
        db.session.commit()
        assert ds.get_deliberation_stats(other_prog.id)['total'] == 0

    def test_deliberation_list_excludes_inactive_users(self, admission):
        a = admission
        _set(a, 'deliberation')
        assert len(ds.get_applicants_for_deliberation(a.program.id)) == 1
        a.applicant.is_active = False
        db.session.commit()
        assert ds.get_applicants_for_deliberation(a.program.id) == []

    def test_by_status_filters(self, admission):
        a = admission
        assert len(ds.get_applicants_by_status(a.program.id, 'in_progress')) == 1
        assert ds.get_applicants_by_status(a.program.id, 'accepted') == []

    def test_pending_interview_empty_without_appointment(self, admission):
        assert ds.get_applicants_with_pending_interview(admission.program.id) == []

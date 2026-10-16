"""admission_service.get_admission_state: the applicant's admission dashboard model."""

import json
from datetime import date, datetime, time, timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step, Submission
from app.models.acceptance_document import AcceptanceDocument
from app.models.appointment import Appointment
from app.models.event import Event, EventSlot, EventWindow
from app.services import admission_service as adm
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user

NOW = datetime(2026, 4, 1, 12, 0, 0)


@pytest.fixture
def env(app):
    """Program with steps 0 (info), 1, 2, 3, 4 (interview, last); one archive each."""
    coord = make_user('program_admin')
    program = make_program(coord)
    phase = Phase('admission', 'd')
    db.session.add(phase)
    db.session.flush()
    steps, archives = {}, {}
    for seq in (0, 1, 2, 3, 4):
        st = Step(f'Paso {seq}', 'd', phase.id)
        db.session.add(st)
        db.session.flush()
        ps = ProgramStep(program_id=program.id, step_id=st.id, sequence=seq)
        db.session.add(ps)
        db.session.flush()
        ar = Archive(f'Doc {seq}', 'd', None, st.id)
        db.session.add(ar)
        db.session.flush()
        steps[seq], archives[seq] = ps, ar
    user = make_user('applicant')
    up = enroll(user, program, 'in_progress')
    db.session.commit()
    return type('E', (), dict(coord=coord, program=program, steps=steps, archives=archives,
                              user=user, up=up))


def _sub(env, seq, status='approved', upload=None):
    s = Submission('f.pdf', status, env.user.id, env.archives[seq].id, env.steps[seq].id, None)
    if upload:
        s.upload_date = upload
    db.session.add(s)
    db.session.commit()
    return s


def _state(env):
    db.session.expire_all()
    return adm.get_admission_state(env.user.id, env.program.id, env.up)


def _extension(env, seq, until, status='granted'):
    e = ExtensionRequest(user_id=env.user.id, archive_id=env.archives[seq].id,
                         program_step_id=env.steps[seq].id, requested_by=env.user.id,
                         role='student', reason='motivo', requested_until=until)
    e.status = status
    e.granted_until = until
    db.session.add(e)
    db.session.commit()
    return e


def _interview(env):
    ev = Event(program_id=env.program.id, type='interview', title='Entrevista', description='',
               location='', created_by=env.coord.id, capacity_type='single',
               requires_registration=True, status='published')
    db.session.add(ev)
    db.session.flush()
    w = EventWindow(event_id=ev.id, date=date(2026, 5, 1), start_time=time(9), end_time=time(10),
                    slot_minutes=30)
    db.session.add(w)
    db.session.flush()
    sl = EventSlot(event_window_id=w.id, starts_at=datetime(2026, 5, 1, 9),
                   ends_at=datetime(2026, 5, 1, 9, 30), status='booked')
    db.session.add(sl)
    db.session.flush()
    ap = Appointment(event_id=ev.id, slot_id=sl.id, applicant_id=env.user.id,
                     assigned_by=env.coord.id, status='scheduled')
    db.session.add(ap)
    db.session.commit()
    return ap


class TestAddMonths:
    @pytest.mark.parametrize('start,months,expected', [
        (datetime(2026, 1, 31), 1, datetime(2026, 2, 28)),
        (datetime(2024, 1, 31), 1, datetime(2024, 2, 29)),
        (datetime(2026, 11, 15), 3, datetime(2027, 2, 15)),
        (datetime(2026, 12, 31), 12, datetime(2027, 12, 31)),
        (datetime(2026, 5, 10), 0, datetime(2026, 5, 10)),
        (datetime(2026, 3, 31), 6, datetime(2026, 9, 30)),
    ])
    def test_clamps_day(self, start, months, expected):
        assert adm._add_months(start, months) == expected


class TestProgress:
    def test_empty_state(self, env):
        s = _state(env)
        assert s['progress_pct'] == 0 and s['total_docs'] == 4     # step 0 is informative
        assert s['status_count'] == {'approved': 0, 'rejected': 0, 'review': 0,
                                     'pending': 4, 'extended': 0}
        assert s['admission_status'] == 'in_progress'

    def test_informative_step_excluded_from_counts(self, env):
        _sub(env, 0, 'approved')
        s = _state(env)
        assert s['total_docs'] == 4 and s['status_count']['approved'] == 0

    def test_progress_percentage(self, env):
        _sub(env, 1)
        s = _state(env)
        assert s['progress_pct'] == 25 and s['status_count']['approved'] == 1

    def test_all_approved_is_100(self, env):
        for seq in (1, 2, 3, 4):
            _sub(env, seq)
        assert _state(env)['progress_pct'] == 100

    def test_segments_sum_to_100(self, env):
        _sub(env, 1)
        _sub(env, 2, 'rejected')
        _sub(env, 3, 'review')
        segs = _state(env)['progress_segments']
        assert round(sum(x['pct'] for x in segs)) == 100
        assert {x['class'] for x in segs} == {'success', 'danger', 'warning', 'secondary'}

    def test_pending_items_list_pending_and_rejected(self, env):
        _sub(env, 1)
        _sub(env, 2, 'rejected')
        names = {i['name']: i['status'] for i in _state(env)['pending_items']}
        assert names == {'Doc 2': 'rejected', 'Doc 3': 'pending', 'Doc 4': 'pending'}

    def test_other_users_submissions_ignored(self, env):
        other = make_user('applicant')
        s = Submission('f.pdf', 'approved', other.id, env.archives[1].id, env.steps[1].id, None)
        db.session.add(s)
        db.session.commit()
        assert _state(env)['status_count']['approved'] == 0

    # Regression: status_count[sub.status] raised KeyError for 'expired'/'purged' submissions.
    @pytest.mark.parametrize('status', ['expired', 'purged'])
    def test_unexpected_submission_status_does_not_crash(self, env, status):
        _sub(env, 1, status)
        st = _state(env)
        assert st['status_count']['approved'] == 0
        names = {i['name']: i['status'] for i in st['pending_items']}
        assert names['Doc 1'] == 'pending'


class TestStepStates:
    def test_regular_step_approved_only_when_all_archives_approved(self, env):
        _sub(env, 1)
        s = _state(env)
        assert s['step_states'][env.steps[1].step_id] == 'approved'
        assert s['step_states'][env.steps[2].step_id] == 'pending'

    def test_rejected_dominates(self, env):
        _sub(env, 2, 'rejected')
        assert _state(env)['step_states'][env.steps[2].step_id] == 'rejected'

    def test_review_state(self, env):
        _sub(env, 2, 'review')
        assert _state(env)['step_states'][env.steps[2].step_id] == 'review'

    def test_active_extension_counts_as_extended(self, env):
        _extension(env, 2, now_local() + timedelta(days=5))
        s = _state(env)
        assert s['step_states'][env.steps[2].step_id] == 'extended'
        assert s['status_count']['extended'] == 1 and s['extended_docs'] == 1
        item = [i for i in s['pending_items'] if i['name'] == 'Doc 2'][0]
        assert item['status'] == 'extended' and item['extension_reason'] == 'motivo'

    def test_expired_extension_is_ignored(self, env):
        _extension(env, 2, now_local() - timedelta(days=1))
        s = _state(env)
        assert s['status_count']['extended'] == 0
        assert env.archives[2].id in s['all_extensions']
        assert env.archives[2].id not in s['extensions']

    @pytest.mark.parametrize('status', ['pending', 'rejected', 'cancelled'])
    def test_non_granted_extension_ignored(self, env, status):
        _extension(env, 2, now_local() + timedelta(days=5), status)
        assert _state(env)['status_count']['extended'] == 0

    def test_last_step_pending_until_interview_assigned(self, env):
        assert _state(env)['step_states'][env.steps[4].step_id] == 'pending'

    def test_last_step_approved_when_interview_assigned(self, env):
        _interview(env)
        assert _state(env)['step_states'][env.steps[4].step_id] == 'approved'

    def test_cancelled_interview_does_not_count(self, env):
        ap = _interview(env)
        ap.status = 'cancelled'
        db.session.commit()
        assert _state(env)['step_states'][env.steps[4].step_id] == 'pending'

    def test_steps_2_and_3_are_merged(self, env):
        ps = _state(env)['processed_steps']
        combined = [p for p in ps if p['is_combined']]
        assert len(combined) == 1 and combined[0]['name'] == 'Requisitos Específicos'
        assert [p['sequence'] for p in ps] == [0, 1, 2, 4]

    def test_combined_approved_when_both_approved(self, env):
        _sub(env, 2)
        _sub(env, 3)
        combined = [p for p in _state(env)['processed_steps'] if p['is_combined']][0]
        assert combined['state'] == 'approved'

    def test_combined_rejected_when_either_rejected(self, env):
        _sub(env, 2)
        _sub(env, 3, 'rejected')
        combined = [p for p in _state(env)['processed_steps'] if p['is_combined']][0]
        assert combined['state'] == 'rejected'


class TestLocking:
    def test_early_steps_never_locked(self, env):
        s = _state(env)
        for seq in (0, 1):
            assert s['lock_info'][env.steps[seq].step_id] is False

    def test_middle_steps_never_locked(self, env):
        s = _state(env)
        assert s['lock_info'][env.steps[2].step_id] is False
        assert s['lock_info'][env.steps[3].step_id] is False

    def test_last_step_locked_until_previous_approved(self, env):
        assert _state(env)['lock_info'][env.steps[4].step_id] is True

    def test_last_step_unlocked_when_all_previous_approved(self, env):
        for seq in (1, 2, 3):
            _sub(env, seq)
        assert _state(env)['lock_info'][env.steps[4].step_id] is False

    def test_informative_step_does_not_lock(self, env):
        for seq in (1, 2, 3):
            _sub(env, seq)
        # no submission for step 0
        assert _state(env)['lock_info'][env.steps[4].step_id] is False

    def test_extension_unlocks(self, env):
        _sub(env, 1)
        _sub(env, 2)
        _extension(env, 3, now_local() + timedelta(days=3))
        assert _state(env)['lock_info'][env.steps[4].step_id] is False

    def test_review_status_still_locks(self, env):
        _sub(env, 1)
        _sub(env, 2)
        _sub(env, 3, 'review')
        assert _state(env)['lock_info'][env.steps[4].step_id] is True

    def test_non_uploadable_archives_ignored_by_lock(self, env):
        env.archives[3].is_uploadable = False
        for seq in (1, 2):
            _sub(env, seq)
        assert _state(env)['lock_info'][env.steps[4].step_id] is False


class TestValidityExpiry:
    @freeze_time(NOW)
    def test_expired_when_validity_months_passed(self, env):
        env.archives[1].validity_months = 3
        _sub(env, 1, upload=NOW - timedelta(days=120))
        assert env.archives[1].id in _state(env)['expired_archive_ids']

    @freeze_time(NOW)
    def test_not_expired_within_validity(self, env):
        env.archives[1].validity_months = 6
        _sub(env, 1, upload=NOW - timedelta(days=30))
        assert _state(env)['expired_archive_ids'] == set()

    @freeze_time(NOW)
    def test_no_validity_never_expires(self, env):
        _sub(env, 1, upload=NOW - timedelta(days=4000))
        assert _state(env)['expired_archive_ids'] == set()


class TestTimeline:
    def _tl(self, env):
        return {t['label']: t for t in _state(env)['timeline']}

    def test_initial(self, env):
        t = self._tl(env)
        assert t['Registro completado']['state'] == 'done'
        assert t['Documentos enviados']['state'] == 'pending'
        assert t['Revisión de documentos']['state'] == 'pending'
        assert t['Entrevista']['state'] == 'pending'
        assert t['Decisión final']['state'] == 'pending'

    def test_docs_sent_and_review_inprogress(self, env):
        _sub(env, 1, 'review')
        t = self._tl(env)
        assert t['Documentos enviados']['state'] == 'done'
        assert t['Documentos enviados']['date'] is not None
        assert t['Revisión de documentos']['state'] == 'inprogress'

    def test_review_done_when_everything_reviewed(self, env):
        for seq in (1, 2, 3, 4):
            _sub(env, seq)
        t = self._tl(env)
        assert t['Revisión de documentos']['state'] == 'done'
        assert t['Entrevista']['state'] == 'inprogress'

    def test_interview_done_when_assigned(self, env):
        _interview(env)
        t = self._tl(env)
        assert t['Entrevista']['state'] == 'done' and t['Decisión final']['state'] == 'inprogress'

    @pytest.mark.parametrize('status,expected', [
        ('in_progress', 'pending'),
        ('interview_completed', 'inprogress'),
        ('deliberation', 'inprogress'),
        ('accepted', 'done'),
        ('enrolled', 'done'),
        ('rejected', 'rejected'),
    ])
    def test_final_decision_by_admission_status(self, env, status, expected):
        env.up.admission_status = status
        db.session.commit()
        assert self._tl(env)['Decisión final']['state'] == expected

    def test_registration_date_formatted(self, env):
        env.up.enrollment_date = datetime(2026, 2, 3)
        db.session.commit()
        assert self._tl(env)['Registro completado']['date'] == '03/02/2026'


class TestDeliberationFields:
    def test_exposes_decision_data(self, env):
        env.up.admission_status = 'rejected'
        env.up.rejection_type = 'partial'
        env.up.decision_notes = 'Falta CV'
        env.up.correction_required = json.dumps({'archive_id': env.archives[1].id, 'notes': 'n'})
        db.session.commit()
        s = _state(env)
        assert s['rejection_type'] == 'partial' and s['decision_notes'] == 'Falta CV'
        assert json.loads(s['correction_required'])['archive_id'] == str(env.archives[1].uuid)

    def test_plain_text_correction_untouched(self, env):
        env.up.correction_required = 'texto'
        db.session.commit()
        assert _state(env)['correction_required'] == 'texto'

    def test_acceptance_docs_only_when_accepted(self, env):
        db.session.add(AcceptanceDocument(user_program_id=env.up.id,
                                          document_type='acceptance_letter', status='uploaded'))
        db.session.commit()
        assert _state(env)['acceptance_docs'] == {}
        env.up.admission_status = 'accepted'
        db.session.commit()
        docs = _state(env)['acceptance_docs']
        assert docs['acceptance_letter']['status'] == 'uploaded'
        assert docs['course_schedule'] is None and set(docs) == {
            'acceptance_letter', 'course_schedule', 'enrollment_receipt', 'acceptance_opinion'}

    def test_user_program_id_exposed(self, env):
        assert _state(env)['user_program_id'] == env.up.id

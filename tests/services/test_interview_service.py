"""InterviewEligibilityService: eligibility rules and mark_profile_complete."""

from datetime import date, timedelta

import pytest

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step, Submission
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.services.interview_service import InterviewEligibilityService as IES
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user


def _profile(user):
    user.phone = '6561234567'
    user.address = 'Calle 1'
    user.curp = 'XEXX010101HNEXXXA4'
    user.birth_date = date(1995, 1, 1)
    user.emergency_contact_name = 'Mamá'
    user.emergency_contact_phone = '6560000000'
    user.emergency_contact_relationship = 'Madre'
    user.profile_completed = True


@pytest.fixture
def prog(app):
    """Program with 4 admission steps; only steps 2 and 3 are checked (first and last excluded)."""
    coord = make_user('program_admin')
    program = make_program(coord)
    phase = Phase('admission', 'd')
    db.session.add(phase)
    db.session.flush()
    steps, archives = [], {}
    for seq in (1, 2, 3, 4):
        st = Step(f'Paso {seq}', 'd', phase.id)
        db.session.add(st)
        db.session.flush()
        ps = ProgramStep(program_id=program.id, step_id=st.id, sequence=seq)
        db.session.add(ps)
        db.session.flush()
        ar = Archive(f'Doc {seq}', 'd', None, st.id)
        db.session.add(ar)
        db.session.flush()
        steps.append(ps)
        archives[seq] = ar
    db.session.commit()
    return type('P', (), dict(program=program, coord=coord, steps=steps, archives=archives))


def _applicant(prog, *, profile=True, enrolled=True):
    u = make_user('applicant')
    if profile:
        _profile(u)
    if enrolled:
        enroll(u, prog.program)
    db.session.commit()
    return u


def _sub(prog, user, seq, status='approved'):
    ps = prog.steps[seq - 1]
    s = Submission('f.pdf', status, user.id, prog.archives[seq].id, ps.id, None)
    db.session.add(s)
    db.session.commit()
    return s


def _approve_all_checked(prog, user):
    _sub(prog, user, 2)
    _sub(prog, user, 3)


class TestEligibility:
    def test_unknown_student(self, prog):
        r = IES.check_student_eligibility(99999, prog.program.id)
        assert r == {'eligible': False, 'reason': 'Estudiante no encontrado'}

    def test_not_enrolled_in_program_yields_no_document_detail(self, prog):
        u = _applicant(prog, enrolled=False)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is False and 'no está inscrito' in r['reason']
        assert 'documents_status' not in r

    def test_program_without_steps(self, app):
        coord = make_user('program_admin')
        program = make_program(coord)
        u = make_user('applicant')
        _profile(u)
        enroll(u, program)
        db.session.commit()
        r = IES.check_student_eligibility(u.id, program.id)
        assert r == {'eligible': False, 'reason': 'Programa sin pasos configurados'}

    def test_eligible_when_profile_and_documents_ok(self, prog):
        u = _applicant(prog)
        _approve_all_checked(prog, u)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is True and r['missing_items'] == []
        assert r['total_steps_checked'] == 2
        assert r['last_step_excluded'] == 'Paso 4'

    def test_first_and_last_step_documents_not_required(self, prog):
        u = _applicant(prog)
        _approve_all_checked(prog, u)   # nothing uploaded for steps 1 and 4
        assert IES.check_student_eligibility(u.id, prog.program.id)['eligible'] is True

    def test_missing_document_blocks(self, prog):
        u = _applicant(prog)
        _sub(prog, u, 2)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is False
        assert r['missing_items'] == [{
            'type': 'document', 'step': 'Paso 3', 'archive': 'Doc 3', 'current_status': 'missing'}]

    @pytest.mark.parametrize('status', ['pending', 'review', 'rejected', 'expired'])
    def test_non_approved_submission_blocks(self, prog, status):
        u = _applicant(prog)
        _sub(prog, u, 2)
        _sub(prog, u, 3, status)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is False
        assert r['missing_items'][0]['current_status'] == status

    def test_extended_submission_counts(self, prog):
        u = _applicant(prog)
        _sub(prog, u, 2)
        _sub(prog, u, 3, 'extended')
        assert IES.check_student_eligibility(u.id, prog.program.id)['eligible'] is True

    def _extension(self, prog, user, seq, status):
        ps = prog.steps[seq - 1]
        e = ExtensionRequest(user_id=user.id, archive_id=prog.archives[seq].id,
                             program_step_id=ps.id, requested_by=user.id, role='student',
                             reason='r', requested_until=now_local() + timedelta(days=5))
        e.status = status
        db.session.add(e)
        db.session.commit()

    def test_granted_extension_replaces_missing_submission(self, prog):
        u = _applicant(prog)
        _sub(prog, u, 2)
        self._extension(prog, u, 3, 'granted')
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is True
        entry = r['documents_status'][1]['archives'][0]
        assert entry['has_granted_extension'] is True and entry['status'] == 'extension_granted'

    @pytest.mark.parametrize('status', ['pending', 'rejected', 'cancelled'])
    def test_non_granted_extension_does_not_count(self, prog, status):
        u = _applicant(prog)
        _sub(prog, u, 2)
        self._extension(prog, u, 3, status)
        assert IES.check_student_eligibility(u.id, prog.program.id)['eligible'] is False

    def test_incomplete_profile_blocks_even_with_documents(self, prog):
        u = _applicant(prog, profile=False)
        _approve_all_checked(prog, u)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert r['eligible'] is False
        assert {'type': 'profile', 'description': 'Perfil de usuario incompleto'} in r['missing_items']
        assert r['profile_status'] == {'complete': False, 'required': True}

    def test_reports_all_problems_at_once(self, prog):
        u = _applicant(prog, profile=False)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        assert len(r['missing_items']) == 3   # 2 documents + profile

    def test_non_uploadable_archives_ignored(self, prog):
        prog.archives[3].is_uploadable = False
        u = _applicant(prog)
        _sub(prog, u, 2)
        db.session.commit()
        assert IES.check_student_eligibility(u.id, prog.program.id)['eligible'] is True

    def test_other_users_submissions_do_not_leak(self, prog):
        a, b = _applicant(prog), _applicant(prog)
        _approve_all_checked(prog, a)
        assert IES.check_student_eligibility(b.id, prog.program.id)['eligible'] is False

    def test_archive_ids_are_public_uuids(self, prog):
        u = _applicant(prog)
        r = IES.check_student_eligibility(u.id, prog.program.id)
        ids = [a['archive_id'] for s in r['documents_status'] for a in s['archives']]
        assert all(i and '-' in i for i in ids)
        assert str(prog.archives[2].id) not in ids

    def test_is_enrolled_in_program(self, prog):
        u = _applicant(prog)
        out = _applicant(prog, enrolled=False)
        assert IES.is_enrolled_in_program(u.id, prog.program.id) is True
        assert IES.is_enrolled_in_program(out.id, prog.program.id) is False


class TestEligibleLists:
    def test_lists_only_eligible_applicants(self, prog):
        ok, bad = _applicant(prog), _applicant(prog)
        _approve_all_checked(prog, ok)
        res = IES.get_eligible_students(prog.program.id)
        assert [r['email'] for r in res] == [ok.email]
        assert res[0]['id'] == str(ok.uuid)

    def test_students_role_excluded(self, prog):
        s = make_user('student')
        _profile(s)
        enroll(s, prog.program)
        db.session.commit()
        _approve_all_checked(prog, s)
        assert IES.get_eligible_students(prog.program.id) == []

    def test_by_programs_none_and_empty_mean_nothing(self, prog):
        _approve_all_checked(prog, _applicant(prog))
        assert IES.get_eligible_students_by_programs(None) == []
        assert IES.get_eligible_students_by_programs([]) == []

    def test_by_programs_normalises_junk_ids(self, prog):
        u = _applicant(prog)
        _approve_all_checked(prog, u)
        res = IES.get_eligible_students_by_programs([str(prog.program.id), 'x', None, prog.program.id])
        assert len(res) == 1 and res[0]['eligible_count'] == 1
        assert res[0]['program_slug'] == prog.program.slug

    def test_by_programs_unknown_program(self, prog):
        assert IES.get_eligible_students_by_programs([99999]) == []

    def test_all_program_ids_sorted(self, prog):
        other = make_program()
        db.session.commit()
        assert IES.all_program_ids() == sorted([prog.program.id, other.id])

    def test_normalize_ids(self):
        assert IES._normalize_ids(['3', 3, 'a', None, 4.0]) == [3, 4]
        assert IES._normalize_ids(None) == []


class TestMarkProfileComplete:
    def test_ok_sets_flag_history_and_notification(self, prog):
        u = _applicant(prog, profile=True)
        u.profile_completed = False
        db.session.commit()
        r = IES.mark_profile_complete(u.id, prog.coord.id)
        assert r['status'] == 'ok'
        db.session.expire_all()
        assert u.profile_completed is True
        h = UserHistory.query.filter_by(user_id=u.id, action='profile_completed').one()
        assert h.admin_id == prog.coord.id
        n = Notification.query.filter_by(user_id=u.id, type='profile_completed').one()
        assert n.priority == 'low'

    def test_unknown_user(self, prog):
        assert IES.mark_profile_complete(99999, prog.coord.id)['status'] == 'not_found'

    @pytest.mark.parametrize('role', ['program_admin', 'postgraduate_admin', 'social_service'])
    def test_staff_accounts_are_invalid_targets(self, prog, role):
        staff = make_user(role)
        db.session.commit()
        assert IES.mark_profile_complete(staff.id, prog.coord.id)['status'] == 'invalid_target'
        assert staff.profile_completed is False

    @pytest.mark.parametrize('role', ['applicant', 'student'])
    def test_valid_target_roles(self, prog, role):
        u = make_user(role)
        _profile(u)
        u.profile_completed = False
        db.session.commit()
        assert IES.mark_profile_complete(u.id, prog.coord.id)['status'] == 'ok'

    def test_already_complete_is_idempotent_and_silent(self, prog):
        u = _applicant(prog)
        assert IES.mark_profile_complete(u.id, prog.coord.id)['status'] == 'already_complete'
        assert UserHistory.query.count() == 0 and Notification.query.count() == 0

    def test_incomplete_profile_cannot_be_forced(self, prog):
        u = _applicant(prog, profile=False)
        r = IES.mark_profile_complete(u.id, prog.coord.id)
        assert r['status'] == 'incomplete'
        assert u.profile_completed is False
        assert UserHistory.query.count() == 0 and Notification.query.count() == 0

    def test_whitespace_only_field_counts_as_missing(self, prog):
        u = _applicant(prog)
        u.profile_completed = False
        u.address = '   '
        db.session.commit()
        assert IES.mark_profile_complete(u.id, prog.coord.id)['status'] == 'incomplete'

    def test_second_call_does_not_duplicate_history(self, prog):
        u = _applicant(prog)
        u.profile_completed = False
        db.session.commit()
        IES.mark_profile_complete(u.id, prog.coord.id)
        IES.mark_profile_complete(u.id, prog.coord.id)
        assert UserHistory.query.filter_by(action='profile_completed').count() == 1

    def test_messages_are_spanish(self, prog):
        r = IES.mark_profile_complete(99999, prog.coord.id)
        assert r['message'] == 'Usuario no encontrado'

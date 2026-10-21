"""Backfill of migration n9i0j1k2l3m4 (academic_status + user_program links)."""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import db
from app.models.archive import Archive
from app.models.phase import Phase
from app.models.program_step import ProgramStep
from app.models.semester_enrollment import SemesterEnrollment
from app.models.step import Step
from app.models.submission import Submission
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.services.user_history_service import UserHistoryService
from app.services.user_program_links import resolve_user_program_id
from tests.support.factories import enroll, make_academic_period, make_program, make_user

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 'n9i0j1k2l3m4_academic_status_and_up_links.py')


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_n9i0', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _period(offset_days: int):
    period = make_academic_period(is_active=False)
    period.start_date = date(2024, 1, 1) + timedelta(days=offset_days)
    period.end_date = period.start_date + timedelta(days=120)
    return period


def _se(up, period, number, status):
    se = SemesterEnrollment(user_program_id=up.id, academic_period_id=period.id,
                            semester_number=number, status=status)
    db.session.add(se)
    db.session.flush()
    return se


def _student(program, statuses):
    """Enrolled student with one enrollment per status, oldest first."""
    up = enroll(make_user('student'), program, admission_status='enrolled')
    for i, status in enumerate(statuses):
        _se(up, _period(i * 180), i + 1, status)
    return up


def test_backfill_maps_last_enrollment_to_academic_status(app, migration):
    program = make_program(duration_semesters=4)
    dropped = _student(program, ['completed', 'dropped'])
    on_leave = _student(program, ['completed', 'on_leave'])
    graduated = _student(program, ['completed'] * 4)
    active = _student(program, ['completed', 'active'])
    repeating = _student(program, ['completed'] * 4 + ['active'])
    no_enrollments = _student(program, [])
    applicant = enroll(make_user('applicant'), program)

    counts = migration.backfill_academic_status(db.session.connection())
    db.session.expire_all()

    assert counts == {'active': 3, 'on_leave': 1, 'withdrawn': 1, 'graduated': 1}
    assert db.session.get(UserProgram, dropped.id).academic_status == 'withdrawn'
    assert db.session.get(UserProgram, dropped.id).withdrawn_at is not None
    assert db.session.get(UserProgram, on_leave.id).academic_status == 'on_leave'
    grad = db.session.get(UserProgram, graduated.id)
    assert grad.academic_status == 'graduated'
    last_period_end = (date(2024, 1, 1) + timedelta(days=3 * 180 + 120))
    assert grad.graduated_at == last_period_end
    assert db.session.get(UserProgram, active.id).academic_status == 'active'
    assert db.session.get(UserProgram, repeating.id).academic_status == 'active'
    assert db.session.get(UserProgram, no_enrollments.id).academic_status == 'active'
    assert db.session.get(UserProgram, applicant.id).academic_status is None


def _submission_setup():
    phase = Phase(name='permanence', description='')
    db.session.add(phase)
    db.session.flush()
    step = Step(name='Permanencia', description='', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    archive = Archive(name='Reinscripción', description='', file_path=None, step_id=step.id)
    db.session.add(archive)
    db.session.flush()
    return step, archive


def _submission(user, archive, program_step):
    sub = Submission(user_id=user.id, archive_id=archive.id,
                     program_step_id=program_step.id, status='review',
                     file_path=None, semester=None)
    db.session.add(sub)
    db.session.flush()
    return sub


def test_backfill_links_submission_by_program_step(app, migration):
    step, archive = _submission_setup()
    master, doctorate = make_program(), make_program()
    ps_master = ProgramStep(sequence=1, program_id=master.id, step_id=step.id)
    ps_doct = ProgramStep(sequence=1, program_id=doctorate.id, step_id=step.id)
    db.session.add_all([ps_master, ps_doct])
    db.session.flush()
    user = make_user('student')
    up_master = enroll(user, master, admission_status='enrolled')
    up_doct = enroll(user, doctorate)
    sub_master = _submission(user, archive, ps_master)
    sub_doct = _submission(user, archive, ps_doct)

    left = migration.backfill_user_program_links(db.session.connection())
    db.session.expire_all()

    assert db.session.get(Submission, sub_master.id).user_program_id == up_master.id
    assert db.session.get(Submission, sub_doct.id).user_program_id == up_doct.id
    assert left == {'submission': 0, 'extension_request': 0}
    assert resolve_user_program_id(user.id, ps_doct.id) == up_doct.id


def test_backfill_leaves_null_when_no_matching_user_program(app, migration):
    step, archive = _submission_setup()
    program = make_program()
    ps = ProgramStep(sequence=1, program_id=program.id, step_id=step.id)
    db.session.add(ps)
    db.session.flush()
    stranger = make_user('student')
    sub = _submission(stranger, archive, ps)

    left = migration.backfill_user_program_links(db.session.connection())
    db.session.expire_all()

    assert db.session.get(Submission, sub.id).user_program_id is None
    assert left['submission'] == 1
    assert resolve_user_program_id(stranger.id, ps.id) is None


def test_log_action_stores_user_program_id(app):
    program = make_program()
    user = make_user('student')
    up = enroll(user, program, admission_status='enrolled')

    entry = UserHistoryService.log_action(
        user_id=user.id, action='semester_enrollment_status_updated',
        details={'x': 1}, admin_id=None, user_program_id=up.id)
    db.session.flush()

    assert db.session.get(UserHistory, entry.id).user_program_id == up.id

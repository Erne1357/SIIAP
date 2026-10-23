# tests/purge/test_retention_graduated.py
"""
Phase 6A: "graduated" in history retention comes from
UserProgram.academic_status == 'graduated' (reference date: graduated_at),
no longer from the semester_number >= duration_semesters heuristic.
"""

from datetime import date

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_program import UserProgram
from app.services.history_retention_service import HistoryRetentionService


def _up(user, program, status='enrolled'):
    up = UserProgram(user_id=user.id, program_id=program.id,
                     admission_status=status, has_conacyt_scholarship=False)
    db.session.add(up)
    db.session.flush()
    return up


def test_graduated_academic_status_is_classified_graduated(
        app, roles, program, applicant_user_factory):
    user = applicant_user_factory()
    up = _up(user, program)
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'graduated', 'graduated_at': date(2024, 6, 30)})
    db.session.flush()

    result = HistoryRetentionService._classify_users()

    assert user.id in result['graduated']
    assert user.id not in result['active']


def test_completed_last_semester_without_graduated_status_is_not_graduated(
        app, roles, program, periods, applicant_user_factory):
    user = applicant_user_factory()
    up = _up(user, program)
    UserProgram.query.filter_by(id=up.id).update({'academic_status': 'active'})
    se = SemesterEnrollment(
        user_program_id=up.id, academic_period_id=periods['20251'].id,
        semester_number=program.duration_semesters, status='completed')
    db.session.add(se)
    db.session.flush()

    result = HistoryRetentionService._classify_users()

    assert user.id not in result['graduated']
    assert user.id in result['active']

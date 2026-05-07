# tests/transition/test_preview.py
"""
Tests de preview_program y preview_global — verifica clasificación correcta
de estudiantes y aspirantes sin mutar datos.
"""

from datetime import datetime
import pytest

from app import db
from app.models.user import User
from app.models.user_program import UserProgram
from app.models.semester_enrollment import SemesterEnrollment
from app.models.submission import Submission
from app.models.enrollment_deferral import EnrollmentDeferral
from app.services import semester_transition_service as tsvc


def test_preview_classifies_student_will_advance(app, periods, program, archives,
                                                 deadlines_source, student_factory,
                                                 make_submission):
    """Estudiante elegible aparece en will_advance."""
    user, up, se = student_factory(suffix='adv', semester=2)
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids_advance = [r['user_program']['id'] for r in out['will_advance']]
    assert up.id in ids_advance
    assert out['stats']['will_advance'] == 1
    # next_semester_number = max+1
    row = next(r for r in out['will_advance'] if r['user_program']['id'] == up.id)
    assert row['next_semester_number'] == 3


def test_preview_classifies_will_block(app, periods, program, deadlines_source,
                                       student_factory):
    """Estudiante con SE no confirmado aparece en will_block."""
    user, up, se = student_factory(suffix='blk', enrollment_confirmed=False)
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids_block = [r['user_program']['id'] for r in out['will_block']]
    assert up.id in ids_block
    assert out['stats']['will_block'] >= 1


def test_preview_classifies_on_leave(app, periods, program, student_factory):
    """Estudiante on_leave aparece en categoría 'on_leave', no en will_block."""
    user, up, se = student_factory(suffix='leave', se_status='on_leave')
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids_leave = [r['user_program']['id'] for r in out['on_leave']]
    ids_block = [r['user_program']['id'] for r in out['will_block']]
    assert up.id in ids_leave
    assert up.id not in ids_block


def test_preview_classifies_admission_migrate(app, periods, program, roles, student_factory):
    """
    Aspirante con admission_period_id = 1 atrás del target → admission_migrate.
    Target=20271, admission_period=20263 → Δ=1 → migrate.
    """
    u = User(
        first_name='Asp', last_name='Migrate', mother_last_name='',
        username='asp_mig', password='Test1234!', email='aspmig@t.local',
        is_internal=True, role_id=roles['applicant'].id,
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='in_progress',
        admission_period_id=periods['20263'].id,
    )
    db.session.add(up)
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids = [r['user_program']['id'] for r in out['admission_migrate']]
    assert up.id in ids


def test_preview_classifies_admission_expire(app, periods, program, roles):
    """
    Aspirante con admission_period_id = 2 atrás del target → admission_expire.
    Target=20271, admission_period=20253 → Δ=2 → expire.
    """
    u = User(
        first_name='Asp', last_name='Expire', mother_last_name='',
        username='asp_exp', password='Test1234!', email='aspexp@t.local',
        is_internal=True, role_id=roles['applicant'].id,
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='in_progress',
        admission_period_id=periods['20253'].id,
    )
    db.session.add(up)
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids = [r['user_program']['id'] for r in out['admission_expire']]
    assert up.id in ids


def test_preview_classifies_admission_cleanup(app, periods, program, roles):
    """
    Aspirante con admission_period_id = 3 atrás del target → admission_to_cleanup.
    Target=20271, admission_period=20251 → Δ=3 → cleanup (informativo).
    """
    u = User(
        first_name='Asp', last_name='Cleanup', mother_last_name='',
        username='asp_cln', password='Test1234!', email='aspcln@t.local',
        is_internal=True, role_id=roles['applicant'].id,
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='in_progress',
        admission_period_id=periods['20251'].id,
    )
    db.session.add(up)
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids = [r['user_program']['id'] for r in out['admission_to_cleanup']]
    assert up.id in ids


def test_preview_classifies_deferred_reactivate(app, periods, program, roles):
    """
    Aspirante con EnrollmentDeferral activo cuyo target == nuevo periodo
    aparece en deferred_reactivate (no en migrate/expire).
    """
    u = User(
        first_name='Asp', last_name='Defer', mother_last_name='',
        username='asp_def', password='Test1234!', email='aspdef@t.local',
        is_internal=True, role_id=roles['applicant'].id,
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='deferred',
        admission_period_id=periods['20253'].id,  # 2 atrás
    )
    db.session.add(up)
    db.session.flush()
    deferral = EnrollmentDeferral(
        user_program_id=up.id,
        original_period_id=periods['20253'].id,
        deferred_to_period_id=periods['20271'].id,
        deferral_number=1,
        status='active',
        requested_by='applicant',
    )
    db.session.add(deferral)
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    ids_def = [r['user_program']['id'] for r in out['deferred_reactivate']]
    ids_exp = [r['user_program']['id'] for r in out['admission_expire']]
    assert up.id in ids_def
    assert up.id not in ids_exp


def test_preview_does_not_mutate(app, periods, program, deadlines_source, student_factory):
    """preview_program no debe alterar nada."""
    user, up, se = student_factory(suffix='nomut', enrollment_confirmed=False)
    db.session.commit()
    initial_status = se.status
    initial_confirmed = se.enrollment_confirmed

    tsvc.preview_program(program.id, periods['20263'].id, periods['20271'].id)
    db.session.expire_all()
    se_re = SemesterEnrollment.query.get(se.id)
    assert se_re.status == initial_status
    assert se_re.enrollment_confirmed == initial_confirmed


def test_preview_global_aggregates_programs(app, periods, program, deadlines_source,
                                            student_factory, archives,
                                            make_submission):
    """preview_global suma stats de todos los programas activos."""
    user, up, se = student_factory(suffix='glob1')
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    out = tsvc.preview_global(periods['20263'].id, periods['20271'].id)
    assert out['stats']['will_advance'] >= 1
    assert any(p['program_id'] == program.id for p in out['programs'])

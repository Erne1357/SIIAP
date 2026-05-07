# tests/transition/test_execute.py
"""
Tests de execute_program_transition — verifica mutaciones, idempotencia y
atomicidad.
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


def test_execute_advances_eligible_student(app, periods, program, archives,
                                           deadlines_source, student_factory,
                                           postgrad_admin, permissions, make_submission):
    """Estudiante elegible: SE actual completed, SE nuevo en target con pending."""
    user, up, se = student_factory(suffix='exec_adv', semester=2)
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['advanced'] == 1
    assert stats['errors'] == []

    db.session.expire_all()
    se_old = SemesterEnrollment.query.get(se.id)
    assert se_old.status == 'completed'

    se_new = SemesterEnrollment.query.filter_by(
        user_program_id=up.id, academic_period_id=periods['20271'].id,
    ).first()
    assert se_new is not None
    assert se_new.status == 'pending'
    assert se_new.enrollment_confirmed is False
    assert se_new.semester_number == 3

    up_re = UserProgram.query.get(up.id)
    assert up_re.current_semester == 3


def test_execute_skips_blocked_student(app, periods, program, deadlines_source,
                                       student_factory, postgrad_admin, permissions):
    """Estudiante bloqueado: SE actual NO cambia, no se crea nuevo SE."""
    user, up, se = student_factory(suffix='exec_blk', enrollment_confirmed=False)
    db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['blocked'] == 1
    assert stats['advanced'] == 0
    db.session.expire_all()

    se_re = SemesterEnrollment.query.get(se.id)
    # No se modifica
    assert se_re.status == 'active'
    assert se_re.enrollment_confirmed is False

    new_se = SemesterEnrollment.query.filter_by(
        user_program_id=up.id, academic_period_id=periods['20271'].id,
    ).first()
    assert new_se is None


def test_execute_counts_on_leave_separately(app, periods, program, student_factory,
                                            postgrad_admin, permissions):
    """on_leave se cuenta en su propio bucket, no en blocked ni advanced."""
    user, up, se = student_factory(suffix='exec_leave', se_status='on_leave')
    db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['on_leave'] == 1
    assert stats['advanced'] == 0
    assert stats['blocked'] == 0


def test_execute_idempotent(app, periods, program, archives, deadlines_source,
                            student_factory, postgrad_admin, permissions, make_submission):
    """Ejecutar dos veces no crea SE duplicado."""
    user, up, se = student_factory(suffix='idem')
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )
    # Segunda ejecución
    tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    count = SemesterEnrollment.query.filter_by(
        user_program_id=up.id, academic_period_id=periods['20271'].id,
    ).count()
    assert count == 1


def test_execute_migrates_admission_period(app, periods, program, roles,
                                           postgrad_admin, permissions):
    """Aspirante Δ=1: admission_period_id se actualiza al target."""
    u = User(
        first_name='Asp', last_name='Migr', mother_last_name='',
        username='asp_migr_exec', password='Test1234!',
        email='aspmigexec@t.local', is_internal=True,
        role_id=roles['applicant'].id, must_change_password=False,
    )
    db.session.add(u); db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='in_progress',
        admission_period_id=periods['20263'].id,
    )
    db.session.add(up); db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['admission_migrated'] == 1
    db.session.expire_all()
    up_re = UserProgram.query.get(up.id)
    assert up_re.admission_period_id == periods['20271'].id
    assert up_re.admission_status == 'in_progress'


def test_execute_expires_admission(app, periods, program, roles, postgrad_admin, permissions):
    """Aspirante Δ=2: admission_status='expired'."""
    u = User(
        first_name='Asp', last_name='Exp', mother_last_name='',
        username='asp_exp_exec', password='Test1234!',
        email='aspexpexec@t.local', is_internal=True,
        role_id=roles['applicant'].id, must_change_password=False,
    )
    db.session.add(u); db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='in_progress',
        admission_period_id=periods['20253'].id,
    )
    db.session.add(up); db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['admission_expired'] == 1
    db.session.expire_all()
    up_re = UserProgram.query.get(up.id)
    assert up_re.admission_status == 'expired'
    # admission_period_id NO se cambia para los expirados
    assert up_re.admission_period_id == periods['20253'].id


def test_execute_reactivates_deferred(app, periods, program, roles, postgrad_admin, permissions):
    """Diferido cuyo target_period == nuevo periodo activo: in_progress + status='used'."""
    u = User(
        first_name='Asp', last_name='Defer', mother_last_name='',
        username='asp_def_exec', password='Test1234!',
        email='aspdefexec@t.local', is_internal=True,
        role_id=roles['applicant'].id, must_change_password=False,
    )
    db.session.add(u); db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status='deferred',
        admission_period_id=periods['20253'].id,
    )
    db.session.add(up); db.session.flush()
    deferral = EnrollmentDeferral(
        user_program_id=up.id,
        original_period_id=periods['20253'].id,
        deferred_to_period_id=periods['20271'].id,
        deferral_number=1, status='active', requested_by='applicant',
    )
    db.session.add(deferral); db.session.commit()

    stats = tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )

    assert stats['deferred_reactivated'] == 1
    db.session.expire_all()
    up_re = UserProgram.query.get(up.id)
    assert up_re.admission_status == 'in_progress'
    assert up_re.admission_period_id == periods['20271'].id
    deferral_re = EnrollmentDeferral.query.get(deferral.id)
    assert deferral_re.status == 'used'


def test_execute_atomicity_rollback_on_error(app, periods, program, archives,
                                             deadlines_source, student_factory,
                                             postgrad_admin, permissions, monkeypatch,
                                             make_submission):
    """Si una operación interna falla fatalmente, se hace rollback completo."""
    user, up, se = student_factory(suffix='atom')
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    # Forzar fallo en commit final monkeypatching
    original_commit = db.session.commit
    def boom(*args, **kw):
        raise RuntimeError('forced commit failure')
    monkeypatch.setattr(db.session, 'commit', boom)

    with pytest.raises(RuntimeError):
        tsvc.execute_program_transition(
            program.id, periods['20263'].id, periods['20271'].id,
            coordinator_id=postgrad_admin.id,
        )

    # Restaurar commit y verificar que no quedó SE nuevo
    monkeypatch.setattr(db.session, 'commit', original_commit)
    db.session.rollback()
    db.session.expire_all()
    new_se = SemesterEnrollment.query.filter_by(
        user_program_id=up.id, academic_period_id=periods['20271'].id,
    ).first()
    assert new_se is None


def test_execute_activates_target_period(app, periods, program, postgrad_admin, permissions):
    """Tras execute, target queda is_active=True y source is_active=False."""
    from app.models.academic_period import AcademicPeriod
    src = AcademicPeriod.query.get(periods['20263'].id)
    tgt = AcademicPeriod.query.get(periods['20271'].id)
    assert src.is_active is True
    assert tgt.is_active is False

    tsvc.execute_program_transition(
        program.id, periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )
    db.session.expire_all()
    assert AcademicPeriod.query.get(periods['20263'].id).is_active is False
    assert AcademicPeriod.query.get(periods['20271'].id).is_active is True


def test_execute_global_iterates_all_programs(app, periods, program, archives,
                                              deadlines_source, student_factory,
                                              postgrad_admin, permissions, make_submission):
    """execute_global_transition retorna un dict 'total' + lista 'programs'."""
    user, up, se = student_factory(suffix='glob_exec')
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    out = tsvc.execute_global_transition(
        periods['20263'].id, periods['20271'].id,
        coordinator_id=postgrad_admin.id,
    )
    assert 'total' in out
    assert 'programs' in out
    assert out['total']['advanced'] >= 1
    assert any(p['program_id'] == program.id for p in out['programs'])

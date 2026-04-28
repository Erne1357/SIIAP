# tests/transition/test_evaluate_student.py
"""
Tests de evaluate_student — verifica todas las ramas de bloqueo.
"""

from datetime import datetime
import pytest

from app import db
from app.models.submission import Submission
from app.services import semester_transition_service as tsvc


def test_can_advance_happy_path(app, periods, program, archives, deadlines_source,
                                student_factory, make_submission):
    """Estudiante con SE confirmado, sin ventanas pendientes → can_advance=True."""
    user, up, se = student_factory(suffix='happy', semester=1)
    make_submission(user.id, archives['boleta'].id, archives['ps9'].id,
                    deadline_id=deadlines_source.id, status='approved')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    assert result['can_advance'] is True
    assert result['blockers'] == []


def test_blocks_when_enrollment_not_confirmed(app, periods, program, deadlines_source, student_factory):
    """SE existe pero enrollment_confirmed=False → bloquea."""
    user, up, se = student_factory(suffix='unconfirmed', enrollment_confirmed=False)
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert result['can_advance'] is False
    assert 'enrollment_not_confirmed' in codes


def test_blocks_when_no_se_in_source(app, periods, program, student_factory):
    """No existe SE en periodo origen → not_enrolled."""
    user, up, se = student_factory(suffix='nosource', period=periods['20253'])
    # Cambiar el SE para que sea de OTRO periodo distinto al source
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert 'not_enrolled' in codes


def test_blocks_when_on_leave(app, periods, program, student_factory):
    """SE.status='on_leave' → bloquea."""
    user, up, se = student_factory(suffix='leave', se_status='on_leave')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert 'on_leave' in codes


def test_blocks_when_dropped(app, periods, program, student_factory):
    """SE.status='dropped' → bloquea."""
    user, up, se = student_factory(suffix='drop', se_status='dropped')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert 'dropped' in codes


def test_blocks_missing_documents(app, periods, program, archives, deadlines_source, student_factory):
    """Ventana cerrada sin submission aprobada → missing_documents."""
    user, up, se = student_factory(suffix='nodoc')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    blocker_codes = [b['code'] for b in result['blockers']]
    assert 'missing_documents' in blocker_codes
    miss = next(b for b in result['blockers'] if b['code'] == 'missing_documents')
    assert len(miss['deadlines']) == 1
    assert miss['deadlines'][0]['label'] == 'Boleta Inscripcion'


def test_does_not_block_when_deadline_open(app, periods, program, archives, periods_no_close, student_factory):
    """
    Se omite verificación si el deadline NO ha cerrado todavía.
    Recibimos la fixture con closes_at futuro.
    """
    user, up, se = student_factory(suffix='open')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert 'missing_documents' not in codes


@pytest.fixture
def periods_no_close(app, program, archives, periods):
    """Deadline que aún NO ha cerrado (closes_at en el futuro)."""
    from app.models.document_deadline import DocumentDeadline
    dl = DocumentDeadline(
        archive_id=archives['boleta'].id,
        program_id=program.id,
        academic_period_id=periods['20263'].id,
        sequence=1, label='Boleta Inscripcion (abierta)',
        opens_at=datetime(2026, 8, 1),
        closes_at=datetime(2099, 12, 31),  # futuro
        is_open=True,
    )
    db.session.add(dl)
    db.session.flush()
    return dl


def test_conacyt_blocks_only_when_scholarship(app, periods, program, archives,
                                              conacyt_deadline_source, student_factory):
    """
    Becario CONACyT con Formato mensual cerrado sin entrega → bloquea.
    No-becario con misma situación NO bloquea por CONACyT.
    """
    # Becario
    u1, up1, se1 = student_factory(suffix='conacyt_yes', has_conacyt=True)
    # No becario
    u2, up2, se2 = student_factory(suffix='conacyt_no', has_conacyt=False)
    db.session.commit()

    r1 = tsvc.evaluate_student(up1.id, periods['20263'].id, periods['20271'].id)
    r2 = tsvc.evaluate_student(up2.id, periods['20263'].id, periods['20271'].id)

    codes1 = [b['code'] for b in r1['blockers']]
    codes2 = [b['code'] for b in r2['blockers']]

    assert 'missing_conacyt_months' in codes1
    assert 'missing_conacyt_months' not in codes2


def test_conacyt_passes_when_submission_approved(app, periods, program, archives,
                                                 conacyt_deadline_source, student_factory,
                                                 make_submission):
    """Becario con submission aprobada para la ventana CONACyT → no bloquea."""
    user, up, se = student_factory(suffix='conacyt_ok', has_conacyt=True)
    make_submission(user.id, archives['conacyt'].id, archives['ps12'].id,
                    deadline_id=conacyt_deadline_source.id, status='approved')
    db.session.commit()

    result = tsvc.evaluate_student(up.id, periods['20263'].id, periods['20271'].id)
    codes = [b['code'] for b in result['blockers']]
    assert 'missing_conacyt_months' not in codes


def test_returns_not_enrolled_for_invalid_up(app, periods):
    """user_program_id inválido → blocker not_enrolled."""
    result = tsvc.evaluate_student(999999, periods['20263'].id, periods['20271'].id)
    assert result['can_advance'] is False
    assert any(b['code'] == 'not_enrolled' for b in result['blockers'])

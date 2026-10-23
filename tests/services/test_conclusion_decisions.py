"""
Phase 6C QA follow-up: owner's decisions 6-8 and the deliberation/coordinator
bugs found in the scenario QA.

- 6: "No aplica" override per student and requirement.
- 7: validity (`validity_months`) of a reused admission document.
- 8: a condition born against an already satisfied requirement is met.
- Bug 1: graduated/titled students are in the dashboard's Conclusión phase.
- Bug 2: deliberation conditions only link requirements of the applicant's program.
- Bug 4: a user on a thesis committee/board cannot be deleted (409, no write).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import db
from app.models.admission_condition import AdmissionCondition
from app.models.conclusion_requirement_override import ConclusionRequirementOverride
from app.models.user import User
from app.models.user_history import UserHistory
from app.services import conclusion_service as svc
from app.services import deliberation_service
from app.services.errors import ConflictError, DomainError
from app.utils.datetime_utils import now_local
from tests.services.test_conclusion_service import (  # noqa: F401  (fixture)
    _archive, _by_key, _pdf, _ready_for_exam, _set_status, _step, _submit, ctx,
)
from tests.support.factories import enroll, make_program, make_user


def _actions(user_id):
    return [h.action for h in UserHistory.query.filter_by(user_id=user_id)]


def _age(sub, months):
    """Move a submission's upload date `months` (approx.) into the past."""
    sub.upload_date = now_local().replace(tzinfo=None) - timedelta(days=31 * months)
    db.session.commit()


# ─── Decision 6: «No aplica» ─────────────────────────────────────────────────

def test_not_applicable_counts_as_satisfied_and_can_be_undone(ctx):
    _set_status(ctx.up, 'graduated')
    db.session.commit()
    with pytest.raises(DomainError, match='motivo'):
        svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                     'not_applicable', '  ')

    svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                 'not_applicable', 'Programa en español nativo')
    item = _by_key(svc.requirements(ctx.up))['conclusion_second_language']
    assert item['status'] == 'not_applicable' and item['satisfied']
    assert item['note'] == 'Programa en español nativo'
    assert not any('Constancia de Segundo Idioma' in b for b in svc.exam_blockers(ctx.up))
    with pytest.raises(ConflictError):
        svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                     'not_applicable', 'Otra vez')
    with pytest.raises(DomainError, match='no aplica'):
        svc.upload_requirement(ctx.student, ctx.language.uuid, ctx.up.id, _pdf())

    svc.remove_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                    'not_applicable')
    assert _by_key(svc.requirements(ctx.up))['conclusion_second_language']['status'] == 'missing'
    actions = _actions(ctx.student.id)
    assert 'conclusion_requirement_override_set' in actions
    assert 'conclusion_requirement_override_removed' in actions


def test_not_applicable_refused_when_satisfied_or_read_only(ctx):
    _submit(ctx.up, ctx.thesis_doc)
    db.session.commit()
    with pytest.raises(DomainError, match='ya está cumplido'):
        svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.thesis_doc.uuid,
                                     'not_applicable', 'x')
    _set_status(ctx.up, 'titled')
    db.session.commit()
    with pytest.raises(DomainError, match='titulado'):
        svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                     'not_applicable', 'x')
    assert ConclusionRequirementOverride.query.count() == 0


def test_not_applicable_out_of_scope_is_not_found(ctx):
    outsider = make_user('program_admin')
    db.session.commit()
    with pytest.raises(DomainError) as err:
        svc.set_requirement_override(outsider, ctx.up.id, ctx.language.uuid,
                                     'not_applicable', 'x')
    assert err.value.status_code == 404


# ─── Decision 7: validity of a reused admission document ─────────────────────

def test_expired_reuse_is_not_satisfied_until_accepted(ctx):
    ctx.title_ms.validity_months = 6
    title = _submit(ctx.up, ctx.title_ms)
    _age(title, 2)
    assert _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']['status'] == 'reused'

    _age(title, 12)
    item = _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']
    assert item['status'] == 'reused_expired' and not item['satisfied']
    assert item['reuse_expires_at'] is not None
    assert any('Título del Grado Anterior' in b for b in svc.exam_blockers(ctx.up))

    svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.prev_degree.uuid,
                                 'accept_expired', 'Título vigente en el registro nacional')
    item = _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']
    assert item['status'] == 'reused' and item['satisfied']
    assert item['note'] == svc.EXPIRED_ACCEPTED_NOTE


def test_accept_expired_only_for_expired_reuse(ctx):
    _submit(ctx.up, ctx.title_ms)  # no validity configured: never expires
    db.session.commit()
    with pytest.raises(DomainError, match='vigencia vencida'):
        svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.prev_degree.uuid,
                                     'accept_expired', 'x')


def test_student_may_upload_over_an_expired_reuse(ctx):
    ctx.title_ms.validity_months = 1
    _age(_submit(ctx.up, ctx.title_ms), 6)
    _set_status(ctx.up, 'graduated')
    db.session.commit()
    sub = svc.upload_requirement(ctx.student, ctx.prev_degree.uuid, ctx.up.id, _pdf())
    item = _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']
    assert item['status'] == 'pending' and item['submission'].id == sub.id


# ─── Decision 8: a condition on an already satisfied requirement ─────────────

def test_condition_on_satisfied_requirement_is_born_met(ctx):
    _submit(ctx.up, ctx.title_ms)  # reusable → previous degree satisfied
    db.session.commit()
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Entregar título',
                                archive_uuid=ctx.prev_degree.uuid)
    assert cond.status == 'met'
    assert cond.resolution_note == svc.ALREADY_MET_NOTE
    assert cond.resolved_by == ctx.coordinator.id
    assert 'admission_condition_resolved' in _actions(ctx.student.id)
    assert _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']['status'] == 'reused'


def test_condition_on_not_applicable_requirement_is_born_met(ctx):
    svc.set_requirement_override(ctx.coordinator, ctx.up.id, ctx.language.uuid,
                                 'not_applicable', 'Exento')
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Idioma',
                                archive_uuid=ctx.language.uuid)
    assert cond.status == 'met'


def test_condition_on_unsatisfied_requirement_stays_pending(ctx):
    _submit(ctx.up, ctx.thesis_doc, status='rejected')
    db.session.commit()
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Tesis',
                                archive_uuid=ctx.thesis_doc.uuid)
    assert cond.status == 'pending'


def test_deliberation_condition_on_satisfied_requirement_is_born_met(ctx, monkeypatch):
    applicant = make_user('applicant')
    up = enroll(applicant, ctx.program, 'deliberation')
    _submit(up, ctx.title_ms)
    db.session.commit()
    monkeypatch.setattr('app.utils.files.save_user_doc', lambda *a, **k: 'x.pdf')
    deliberation_service.accept_applicant(
        applicant.id, ctx.program.id, ctx.coordinator.id, None,
        is_conditional=True, dictamen_file=_pdf(),
        conditions=[{'description': 'Título', 'archive_key': 'conclusion_previous_degree'}])
    cond = AdmissionCondition.query.filter_by(user_program_id=up.id).one()
    assert cond.status == 'met' and cond.resolution_note == svc.ALREADY_MET_NOTE


def test_resolve_condition_refused_when_titled(ctx):
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Curso')
    _set_status(ctx.up, 'titled')
    db.session.commit()
    with pytest.raises(DomainError, match='resolver condiciones'):
        svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'met')


# ─── Bug 2: deliberation requirements are per program ────────────────────────

@pytest.fixture
def other_program(ctx):
    program = make_program(ctx.coordinator)
    step = _step('conclusion', 'Requisitos de Doctorado', program, 2)
    letter = _archive(step, 'Carta de Usuario', 'conclusion_user_letter')
    db.session.commit()
    return SimpleNamespace(program=program, letter=letter)


def test_deliberation_rejects_requirement_of_another_program(ctx, other_program, monkeypatch):
    applicant = make_user('applicant')
    up = enroll(applicant, ctx.program, 'deliberation')
    db.session.commit()
    monkeypatch.setattr('app.utils.files.save_user_doc', lambda *a, **k: 'x.pdf')
    with pytest.raises(DomainError, match='no existe'):
        deliberation_service.accept_applicant(
            applicant.id, ctx.program.id, ctx.coordinator.id, None,
            is_conditional=True, dictamen_file=_pdf(),
            conditions=[{'description': 'X', 'archive_key': 'conclusion_user_letter'}])
    db.session.rollback()
    assert db.session.get(type(up), up.id).admission_status == 'deliberation'
    assert AdmissionCondition.query.count() == 0


def test_stage_condition_rejects_archive_of_another_program(ctx, other_program):
    with pytest.raises(DomainError, match='del programa'):
        svc.stage_condition(ctx.up, 'X', archive_id=other_program.letter.id)


def test_conclusion_requirement_options_are_per_program(ctx, other_program):
    options = deliberation_service.list_conclusion_requirements(
        [ctx.program.id, other_program.program.id])
    keys = {pid: [o['key'] for o in rows] for pid, rows in options.items()}
    assert 'conclusion_user_letter' not in keys[ctx.program.id]
    assert 'conclusion_previous_degree' in keys[ctx.program.id]
    assert keys[other_program.program.id] == ['conclusion_user_letter']


# ─── Bug 1: dashboard phase ──────────────────────────────────────────────────

@pytest.mark.parametrize('academic_status, completed, expected', [
    ('graduated', 1, 'conclusion'),
    ('titled', 0, 'conclusion'),
    ('active', 1, 'permanence'),
    ('active', 4, 'conclusion'),
])
def test_dashboard_phase_follows_academic_status(app, academic_status, completed, expected):
    from app.routes.api.coordinator_api import _determine_current_phase

    up = SimpleNamespace(admission_status='enrolled', academic_status=academic_status)
    perm = {'completed_semesters': completed, 'total_semesters': 4}
    assert _determine_current_phase({}, up, perm) == expected


# ─── Bug 4: deleting a committee member ──────────────────────────────────────

def test_delete_user_on_committee_is_refused_before_any_write(ctx):
    from app.services import user_admin_service

    teacher = make_user('teacher')
    db.session.commit()
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'director', user_id=teacher.id)
    before = UserHistory.query.filter_by(action='deleted').count()

    with pytest.raises(ConflictError, match='comité/sínodo de 1 tesis') as err:
        user_admin_service.delete_user_account(teacher, 'Docente')
    assert err.value.status_code == 409
    assert 'Reemplázalo primero' in str(err.value)
    db.session.rollback()
    assert db.session.get(User, teacher.id) is not None
    assert UserHistory.query.filter_by(action='deleted').count() == before


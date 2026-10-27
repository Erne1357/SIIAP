"""Phase 6D, task 4: the review engine over `ExtensionRequest` (kind `extension`)."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.services import admission_debt_service as debt
from app.services.extensions_service import ExtensionsService, record_decision
from app.services.review_engine import (
    KINDS, ReviewConflict, ReviewForbidden, ReviewNotFound, decide, get_kind,
)
from app.utils.datetime_utils import now_local
from tests.support.factories import (
    enroll, get_or_create_role, grant, make_program, make_user,
)


def _naive_now():
    return now_local().replace(tzinfo=None)


@pytest.fixture
def w(app):
    role = get_or_create_role('program_admin')
    grant(role, 'extensions.api.decide')
    coord = make_user('program_admin')
    other_coord = make_user('program_admin')
    program = make_program(coord)
    other_program = make_program(other_coord)

    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    up.academic_status = 'active'
    other_student = make_user('student')
    other_up = enroll(other_student, other_program, 'enrolled')

    phase = Phase.query.filter_by(name='admission').first()
    if phase is None:
        phase = Phase(name='admission', description='admission')
        db.session.add(phase)
        db.session.flush()
    step = Step(name='Requisitos', description='r', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    ps = ProgramStep(sequence=1, program_id=program.id, step_id=step.id)
    other_ps = ProgramStep(sequence=1, program_id=other_program.id, step_id=step.id)
    db.session.add_all([ps, other_ps])
    archive = Archive(name='Título de Licenciatura', description='t', file_path=None,
                      step_id=step.id)
    db.session.add(archive)
    db.session.flush()

    def make_request(owner=None, step_=None, status='pending', **kw):
        owner = owner or up
        er = ExtensionRequest(user_id=owner.user_id, archive_id=archive.id,
                              program_step_id=(step_ or ps).id,
                              requested_by=owner.user_id, reason='Título en trámite',
                              requested_until=_naive_now() + timedelta(days=30),
                              user_program_id=owner.id)
        er.status = status
        for k, v in kw.items():
            setattr(er, k, v)
        db.session.add(er)
        db.session.commit()
        return er

    db.session.commit()
    return SimpleNamespace(coord=coord, other_coord=other_coord, program=program,
                           student=student, up=up, other_up=other_up, archive=archive,
                           ps=ps, other_ps=other_ps, make_request=make_request)


def _reload(er):
    db.session.expire_all()
    return db.session.get(ExtensionRequest, er.id)


def _future():
    return _naive_now() + timedelta(days=15)


def test_kind_is_registered(app):
    assert 'extension' in KINDS
    kind = get_kind('extension')
    assert kind.permission == 'extensions.api.decide'
    assert kind.status_for('approve') == 'granted'
    assert kind.status_for('reject') == 'rejected'


def test_grant_needs_granted_until(w):
    er = w.make_request()
    with pytest.raises(ReviewConflict, match='fecha límite'):
        decide(w.coord, 'extension', er.uuid, 'approve')
    assert _reload(er).status == 'pending'


def test_grant(w):
    er = w.make_request()
    until = _future()
    result = decide(w.coord, 'extension', er.uuid, 'approve',
                    extra={'granted_until': until, 'condition_text': 'Entregar el acta'})
    assert result.status == 'granted' and not result.reverted
    er = _reload(er)
    assert er.status == 'granted' and er.granted_until == until
    assert er.decided_by == w.coord.id and er.decided_at is not None
    assert er.condition_text == 'Entregar el acta'
    assert Notification.query.filter_by(user_id=w.student.id).count() >= 1
    assert UserHistory.query.filter_by(user_id=w.coord.id, action='extension_decided').count() == 1


def test_reject(w):
    er = w.make_request()
    result = decide(w.coord, 'extension', er.uuid, 'reject', extra={'condition_text': 'No procede'})
    assert result.status == 'rejected'
    er = _reload(er)
    assert er.status == 'rejected' and er.granted_until is None
    assert er.decided_by == w.coord.id


def test_redecide_without_reason_is_a_conflict(w):
    er = w.make_request()
    decide(w.coord, 'extension', er.uuid, 'reject')
    with pytest.raises(ReviewConflict):
        decide(w.coord, 'extension', er.uuid, 'approve', extra={'granted_until': _future()})
    assert _reload(er).status == 'rejected'


def test_revert_with_reason(w):
    er = w.make_request()
    decide(w.coord, 'extension', er.uuid, 'reject')
    result = decide(w.coord, 'extension', er.uuid, 'approve', revert_reason='Presentó el oficio',
                    extra={'granted_until': _future()})
    assert result.reverted and result.status == 'granted'
    assert _reload(er).status == 'granted'
    assert UserHistory.query.filter_by(
        user_id=w.student.id, action='document_review_reverted').count() == 1


def test_out_of_scope_is_not_found(w):
    er = w.make_request(owner=w.other_up, step_=w.other_ps)
    with pytest.raises(ReviewNotFound):
        decide(w.coord, 'extension', er.uuid, 'reject')
    assert _reload(er).status == 'pending'


def test_unknown_request_is_not_found(w):
    with pytest.raises(ReviewNotFound):
        decide(w.coord, 'extension', 'not-a-uuid', 'reject')


def test_actor_without_permission_is_forbidden(w):
    er = w.make_request()
    with pytest.raises(ReviewForbidden):
        decide(w.student, 'extension', er.uuid, 'reject')


def test_program_falls_back_to_program_step(w):
    er = w.make_request()
    er.user_program_id = None
    db.session.commit()
    kind = get_kind('extension')
    assert kind.program_id(er) == w.program.id
    assert decide(w.coord, 'extension', er.uuid, 'reject').status == 'rejected'


def test_row_and_queries(w):
    er = w.make_request()
    kind = get_kind('extension')
    assert [r.id for r in kind.pending_query({w.program.id}).all()] == [er.id]
    assert kind.pending_query({-1}).all() == []
    row = kind.row(er)
    assert row['uuid'] == str(er.uuid) and row['kind'] == 'extension'
    assert row['title'] == 'Título de Licenciatura' and row['file_url'] is None
    assert row['program_id'] == w.program.id
    decide(w.coord, 'extension', er.uuid, 'reject')
    since = now_local().replace(tzinfo=None) - timedelta(minutes=5)
    assert [r.id for r in kind.decided_query(None, since).all()] == [er.id]


def test_revert_granted_reblocks_enrollment(w):
    # Owner's decision: a rejected extension on an undelivered document blocks.
    er = w.make_request()
    decide(w.coord, 'extension', er.uuid, 'approve', extra={'granted_until': _future()})
    assert debt.overdue_admission_documents(w.up) == []

    decide(w.coord, 'extension', er.uuid, 'reject', revert_reason='Se canceló el trámite')
    docs = debt.overdue_admission_documents(w.up)
    assert [d['archive'].id for d in docs] == [w.archive.id]
    assert docs[0]['rejected'] and docs[0]['granted_until'] is None


def test_revert_of_a_lapsed_grant_keeps_the_block(w):
    er = w.make_request()
    decide(w.coord, 'extension', er.uuid, 'approve',
           extra={'granted_until': _naive_now() - timedelta(days=1)})
    assert len(debt.overdue_admission_documents(w.up)) == 1
    decide(w.coord, 'extension', er.uuid, 'reject', revert_reason='Error de captura')
    assert len(debt.overdue_admission_documents(w.up)) == 1


# ─── Legacy wrapper ──────────────────────────────────────────────────────────

def test_wrapper_grant_keeps_contract(w):
    er = w.make_request()
    until = _future()
    out = ExtensionsService.decide_request(er.id, 'granted', w.coord.id,
                                           granted_until=until, condition_text='x')
    assert out.id == er.id and out.status == 'granted' and out.granted_until == until
    # The route's follow-up must not log twice.
    record_decision(out, 'granted', until, 'x', w.coord.id)
    assert UserHistory.query.filter_by(user_id=w.coord.id, action='extension_decided').count() == 1


def test_wrapper_reject(w):
    er = w.make_request()
    out = ExtensionsService.decide_request(er.id, 'rejected', w.coord.id)
    assert out.status == 'rejected'


def test_wrapper_redecision_is_a_value_error(w):
    er = w.make_request()
    ExtensionsService.decide_request(er.id, 'rejected', w.coord.id)
    with pytest.raises(ValueError, match='motivo'):
        ExtensionsService.decide_request(er.id, 'granted', w.coord.id, granted_until=_future())


def test_wrapper_grant_without_date_is_a_value_error(w):
    er = w.make_request()
    with pytest.raises(ValueError, match='fecha límite'):
        ExtensionsService.decide_request(er.id, 'granted', w.coord.id)


def test_wrapper_out_of_scope_is_a_value_error(w):
    er = w.make_request(owner=w.other_up, step_=w.other_ps)
    with pytest.raises(ValueError):
        ExtensionsService.decide_request(er.id, 'rejected', w.coord.id)


def test_wrapper_unknown_and_invalid(w):
    with pytest.raises(ValueError, match='no encontrada'):
        ExtensionsService.decide_request(999999, 'rejected', w.coord.id)
    er = w.make_request()
    with pytest.raises(ValueError, match='inválido'):
        ExtensionsService.decide_request(er.id, 'maybe', w.coord.id)


def test_cancel_is_unchanged(w):
    er = w.make_request()
    out = ExtensionsService.decide_request(er.id, 'cancelled', w.coord.id)
    assert out.status == 'cancelled' and out.decided_by == w.coord.id
    assert out.decided_at is not None and out.granted_until is None
    # A cancelled request cannot be revived through the engine.
    with pytest.raises(ReviewConflict):
        decide(w.coord, 'extension', er.uuid, 'reject', revert_reason='x')

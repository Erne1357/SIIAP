# ruff: noqa: F811  (pytest fixtures imported from the sibling module)
"""
Phase 6D, task 1: a condition met automatically remembers the submission
whose approval met it, so reverting that approval reopens it — and only it.
"""
from app import db
from app.models.admission_condition import AdmissionCondition
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.services import conclusion_service as svc
from tests.services.test_conclusion_service import (  # noqa: F401  (fixture)
    _set_status, _submit, ctx,
)


def _condition(ctx, archive=None, description='Entregar tesis final'):
    _set_status(ctx.up, 'graduated')
    db.session.commit()
    return svc.create_condition(ctx.coordinator, ctx.up.id, description,
                                archive_uuid=archive.uuid if archive else None)


def _approved(ctx, archive):
    sub = _submit(ctx.up, archive, status='approved')
    svc.on_requirement_approved(sub, ctx.coordinator.id)
    db.session.commit()
    return sub


def test_auto_met_records_submission(ctx):
    cond = _condition(ctx, ctx.thesis_doc)
    sub = _approved(ctx, ctx.thesis_doc)

    db.session.expire_all()
    cond = db.session.get(AdmissionCondition, cond.id)
    assert cond.status == 'met'
    assert cond.resolved_by_submission_id == sub.id


def test_reopen_returns_condition_to_pending(ctx):
    cond = _condition(ctx, ctx.thesis_doc)
    sub = _approved(ctx, ctx.thesis_doc)

    reopened = svc.reopen_conditions_for_submission(sub, ctx.coordinator.id)
    db.session.commit()

    assert [c.id for c in reopened] == [cond.id]
    db.session.expire_all()
    cond = db.session.get(AdmissionCondition, cond.id)
    assert cond.status == 'pending'
    assert cond.resolved_at is None and cond.resolved_by is None
    assert cond.resolution_note is None and cond.resolved_by_submission_id is None
    history = UserHistory.query.filter_by(user_id=ctx.student.id,
                                          action='admission_condition_reopened').one()
    assert history.user_program_id == ctx.up.id
    assert Notification.query.filter_by(
        user_id=ctx.student.id, type='admission_condition_reopened').count() == 1


def test_manual_resolution_not_reopened(ctx):
    cond = _condition(ctx, ctx.thesis_doc)
    svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'met', 'Entregada en físico')
    # The requirement is approved afterwards: the condition is no longer
    # pending, so this approval does not own it.
    sub = _approved(ctx, ctx.thesis_doc)

    assert svc.reopen_conditions_for_submission(sub, ctx.coordinator.id) == []
    db.session.commit()
    db.session.expire_all()
    cond = db.session.get(AdmissionCondition, cond.id)
    assert cond.status == 'met'
    assert cond.resolution_note == 'Entregada en físico'
    assert cond.resolved_by_submission_id is None


def test_reopen_ignores_waived(ctx):
    cond = _condition(ctx, ctx.thesis_doc)
    sub = _approved(ctx, ctx.thesis_doc)
    # Defensive: a condition linked to the submission but waived later by hand.
    row = db.session.get(AdmissionCondition, cond.id)
    row.status = 'waived'
    db.session.commit()

    assert svc.reopen_conditions_for_submission(sub, ctx.coordinator.id) == []
    db.session.expire_all()
    assert db.session.get(AdmissionCondition, cond.id).status == 'waived'


def test_reopen_without_submission_is_noop(ctx):
    assert svc.reopen_conditions_for_submission(None, ctx.coordinator.id) == []

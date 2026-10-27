"""Phase 6D, task 3: the `enrollment_receipt` kind over AcceptanceDocument."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import db
from app.models.acceptance_document import AcceptanceDocument
from app.models.email_queue import EmailQueue
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.services import acceptance_service as svc
from app.services.review_engine import (
    KINDS, ReviewConflict, ReviewNotFound, decide, get_kind,
)
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, get_or_create_role, grant, make_user


@pytest.fixture
def rx(world):
    grant(get_or_create_role('program_admin'), 'acceptance.api.review_doc')
    applicant = make_user('applicant')
    up = enroll(applicant, world.program, 'accepted')
    other_applicant = make_user('applicant')
    other_up = enroll(other_applicant, world.other_program, 'accepted')
    db.session.commit()

    def receipt(owner=up, doc_type='enrollment_receipt', status='uploaded'):
        doc = AcceptanceDocument(user_program_id=owner.id, document_type=doc_type,
                                 file_path=f'{owner.user_id}/x.pdf', status=status,
                                 uploaded_by_id=owner.user_id, uploaded_at=now_local())
        db.session.add(doc)
        db.session.commit()
        return doc

    return SimpleNamespace(world=world, applicant=applicant, up=up, other_up=other_up,
                           receipt=receipt)


def _reload(doc):
    db.session.expire_all()
    return db.session.get(AcceptanceDocument, doc.id)


def test_registered(app):
    kind = get_kind('enrollment_receipt')
    assert 'enrollment_receipt' in KINDS
    assert kind.permission == 'acceptance.api.review_doc'
    assert kind.label == 'Recibo de inscripción'


def test_approve_pending_keeps_side_effects(rx):
    doc = rx.receipt()
    result = decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'approve', 'ok')
    assert result.status == 'approved' and not result.reverted
    doc = _reload(doc)
    assert doc.status == 'approved' and doc.reviewed_by_id == rx.world.coordinator.id
    assert doc.reviewed_at is not None and doc.review_notes == 'ok'
    uid = rx.applicant.id
    assert Notification.query.filter_by(user_id=uid, type='enrollment_receipt_approved').count() == 1
    assert UserHistory.query.filter_by(user_id=uid, action='enrollment_receipt_approved').count() == 1
    assert EmailQueue.query.filter_by(user_id=uid).count() == 1


def test_reject_pending_carries_reason(rx):
    doc = rx.receipt()
    decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'reject', 'ilegible')
    assert _reload(doc).status == 'rejected'
    note = Notification.query.filter_by(user_id=rx.applicant.id,
                                        type='enrollment_receipt_rejected').one()
    assert 'ilegible' in note.message
    assert UserHistory.query.filter_by(user_id=rx.applicant.id,
                                       action='enrollment_receipt_rejected').count() == 1


def test_redecide_without_reason_is_conflict(rx):
    doc = rx.receipt()
    decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'approve')
    with pytest.raises(ReviewConflict):
        decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'reject')
    assert _reload(doc).status == 'approved'


def test_revert_with_reason(rx):
    doc = rx.receipt()
    decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'approve')
    result = decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'reject',
                    revert_reason='Era de otro aspirante')
    assert result.reverted and _reload(doc).status == 'rejected'
    assert UserHistory.query.filter_by(user_id=rx.applicant.id,
                                       action='document_review_reverted').count() == 1


def test_revert_approval_when_enrolled_is_conflict(rx):
    doc = rx.receipt()
    decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'approve')
    rx.up.admission_status = 'enrolled'
    db.session.commit()
    with pytest.raises(ReviewConflict, match='ya está inscrito'):
        decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'reject',
               revert_reason='Error')
    assert _reload(doc).status == 'approved'


def test_out_of_scope_is_not_found(rx):
    doc = rx.receipt(owner=rx.other_up)
    with pytest.raises(ReviewNotFound):
        decide(rx.world.coordinator, 'enrollment_receipt', doc.uuid, 'approve')
    assert _reload(doc).status == 'uploaded'


def test_other_document_type_is_not_matched(rx):
    letter = rx.receipt(doc_type='acceptance_letter', status='approved')
    kind = get_kind('enrollment_receipt')
    assert not kind.matches(letter)
    with pytest.raises(ReviewNotFound):
        decide(rx.world.coordinator, 'enrollment_receipt', letter.uuid, 'reject',
               revert_reason='x')


def test_queries_and_row(rx):
    kind = get_kind('enrollment_receipt')
    pending = rx.receipt()
    rx.receipt(doc_type='acceptance_letter')
    foreign = rx.receipt(owner=rx.other_up)
    assert [d.id for d in kind.pending_query({rx.world.program.id}).all()] == [pending.id]
    assert {d.id for d in kind.pending_query(None).all()} == {pending.id, foreign.id}
    decide(rx.world.coordinator, 'enrollment_receipt', pending.uuid, 'approve')
    since = now_local() - timedelta(minutes=5)
    decided = kind.decided_query({rx.world.program.id}, since).all()
    assert [d.id for d in decided] == [pending.id]
    row = kind.row(_reload(pending))
    assert row['kind'] == 'enrollment_receipt' and row['status'] == 'approved'
    assert row['program_id'] == rx.world.program.id and row['uuid'] == str(pending.uuid)


def test_wrapper_keeps_contract(rx):
    doc = rx.receipt()
    out = svc.review_enrollment_receipt(doc.id, rx.world.coordinator.id, 'rejected', 'borrosa')
    assert out.id == doc.id and out.status == 'rejected' and out.review_notes == 'borrosa'
    with pytest.raises(svc.InvalidStateTransition):
        svc.review_enrollment_receipt(doc.id, rx.world.coordinator.id, 'approved')
    with pytest.raises(ValueError):
        svc.review_enrollment_receipt(doc.id, rx.world.coordinator.id, 'pending')
    with pytest.raises(svc.ApplicantNotFound):
        svc.review_enrollment_receipt(999999, rx.world.coordinator.id, 'approved')
    letter = rx.receipt(doc_type='acceptance_letter')
    with pytest.raises(svc.InvalidDocumentType):
        svc.review_enrollment_receipt(letter.id, rx.world.coordinator.id, 'approved')


def test_wrapper_translates_engine_refusals(rx, monkeypatch):
    # Out of the coordinator's scope: the engine's 404 becomes the service's own.
    foreign = rx.receipt(owner=rx.other_up)
    with pytest.raises(svc.ApplicantNotFound):
        svc.review_enrollment_receipt(foreign.id, rx.world.coordinator.id, 'approved')
    assert _reload(foreign).status == 'uploaded'

    # Any other engine refusal is an InvalidStateTransition (400), never a 500.
    from app.services import review_engine

    def refuse(*_a, **_k):
        raise ReviewConflict('El estado cambió.')

    monkeypatch.setattr(review_engine, 'decide_item', refuse)
    doc = rx.receipt()
    with pytest.raises(svc.InvalidStateTransition, match='El estado cambió.'):
        svc.review_enrollment_receipt(doc.id, rx.world.coordinator.id, 'approved')

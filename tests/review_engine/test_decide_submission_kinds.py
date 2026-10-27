"""Phase 6D, task 2: the review engine over the four Submission kinds."""
from datetime import timedelta

import pytest

from app import db
from app.models import Submission
from app.models.admission_condition import AdmissionCondition
from app.models.notification import Notification
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.services import conclusion_service, permanence_service, review_engine, review_service
from app.services.review_engine import (
    KINDS, ReviewConflict, ReviewError, ReviewForbidden, ReviewNotFound, decide, get_kind,
)
from app.services.review_engine.submission_kinds import kind_key_for_submission
from app.utils.datetime_utils import now_local
from tests.support.factories import make_user

SUBMISSION_KINDS = ('admission_doc', 'permanence_doc', 'leave_request', 'conclusion_doc')


def _reload(sub):
    db.session.expire_all()
    return db.session.get(Submission, sub.id)


# ─── Registry ────────────────────────────────────────────────────────────────

def test_registry_has_the_submission_kinds(app):
    assert set(SUBMISSION_KINDS) <= set(KINDS)
    for key in SUBMISSION_KINDS:
        kind = get_kind(key)
        assert kind.key == key and kind.label and kind.permission


def test_unknown_kind_is_not_found(world):
    with pytest.raises(ReviewNotFound):
        decide(world.coordinator, 'nope', 'x', 'approve')


def test_kind_key_follows_archive_and_phase(world):
    for key in SUBMISSION_KINDS:
        assert kind_key_for_submission(world.submit(world.archives[key])) == key


# ─── Pending decisions, per kind ─────────────────────────────────────────────

@pytest.mark.parametrize('key', SUBMISSION_KINDS)
def test_kind_approve_pending(world, key):
    sub = world.submit(world.archives[key])
    result = decide(world.coordinator, key, sub.uuid, 'approve', 'Todo en orden')

    assert result.status == 'approved' and not result.reverted
    assert result.kind.key == key and result.item.id == sub.id
    sub = _reload(sub)
    assert sub.status == 'approved'
    assert sub.reviewer_id == world.coordinator.id
    assert sub.reviewer_comment == 'Todo en orden'
    assert sub.review_date is not None


@pytest.mark.parametrize('key', SUBMISSION_KINDS)
def test_kind_reject_pending(world, key):
    sub = world.submit(world.archives[key])
    result = decide(world.coordinator, key, sub.uuid, 'reject', 'Falta firma')

    assert result.status == 'rejected'
    assert _reload(sub).status == 'rejected'
    assert Notification.query.filter_by(user_id=world.student.id).count() >= 1


def test_invalid_decision_is_rejected(world):
    sub = world.submit(world.archives['admission_doc'])
    with pytest.raises(ReviewError) as err:
        decide(world.coordinator, 'admission_doc', sub.uuid, 'maybe')
    assert err.value.status_code == 400


def test_kind_mismatch_is_not_found(world):
    sub = world.submit(world.archives['admission_doc'])
    with pytest.raises(ReviewNotFound):
        decide(world.coordinator, 'leave_request', sub.uuid, 'approve')


# ─── Re-deciding ─────────────────────────────────────────────────────────────

def test_second_decision_without_reason_conflicts(world):
    """Review focus 1: a double click / second reviewer gets 409 and writes nothing."""
    sub = world.submit(world.archives['admission_doc'])
    decide(world.coordinator, 'admission_doc', sub.uuid, 'approve')

    with pytest.raises(ReviewConflict) as err:
        decide(world.postgrad, 'admission_doc', sub.uuid, 'reject', 'Otra opinión')
    assert err.value.status_code == 409
    assert 'motivo' in err.value.message
    sub = _reload(sub)
    assert sub.status == 'approved' and sub.reviewer_id == world.coordinator.id


def test_revert_with_reason_flips_and_logs(world):
    sub = world.submit(world.archives['permanence_doc'])
    decide(world.coordinator, 'permanence_doc', sub.uuid, 'approve')

    result = decide(world.coordinator, 'permanence_doc', sub.uuid, 'reject',
                    revert_reason='El documento era de otro periodo')

    assert result.reverted and result.previous_status == 'approved'
    sub = _reload(sub)
    assert sub.status == 'rejected'
    assert sub.reviewer_comment == 'El documento era de otro periodo'
    entry = UserHistory.query.filter_by(user_id=world.student.id,
                                        action='document_review_reverted').one()
    assert entry.user_program_id == world.up.id
    assert entry.admin_id == world.coordinator.id
    assert 'El documento era de otro periodo' in entry.details
    assert Notification.query.filter_by(user_id=world.student.id,
                                        type='permanence_doc_rejected').count() == 1


def test_same_decision_is_conflict(world):
    """Review focus 2: 'reverting' to the current decision is 409 without writing."""
    sub = world.submit(world.archives['admission_doc'])
    decide(world.coordinator, 'admission_doc', sub.uuid, 'reject', 'Ilegible')
    before = UserHistory.query.count()

    with pytest.raises(ReviewConflict):
        decide(world.coordinator, 'admission_doc', sub.uuid, 'reject', revert_reason='Otra vez')
    sub = _reload(sub)
    assert sub.status == 'rejected' and sub.reviewer_comment == 'Ilegible'
    assert UserHistory.query.count() == before


def test_reverting_twice_to_the_same_status_conflicts(world):
    sub = world.submit(world.archives['admission_doc'])
    decide(world.coordinator, 'admission_doc', sub.uuid, 'approve')
    decide(world.coordinator, 'admission_doc', sub.uuid, 'reject', revert_reason='Error')
    with pytest.raises(ReviewConflict):
        decide(world.coordinator, 'admission_doc', sub.uuid, 'reject', revert_reason='Error')


# ─── Permission and scope ────────────────────────────────────────────────────

def test_out_of_scope_is_not_found(world):
    sub = world.submit(world.archives['admission_doc'], owner=world.other_up)
    with pytest.raises(ReviewNotFound) as err:
        decide(world.coordinator, 'admission_doc', sub.uuid, 'approve')
    assert err.value.status_code == 404
    assert _reload(sub).status == 'pending'


def test_unknown_item_is_not_found_with_the_same_message(world):
    sub = world.submit(world.archives['admission_doc'], owner=world.other_up)
    with pytest.raises(ReviewNotFound) as foreign:
        decide(world.coordinator, 'admission_doc', sub.uuid, 'approve')
    with pytest.raises(ReviewNotFound) as unknown:
        decide(world.coordinator, 'admission_doc', '00000000-0000-7000-8000-000000000000',
               'approve')
    assert foreign.value.message == unknown.value.message


def test_kind_permission_required(world):
    sub = world.submit(world.archives['admission_doc'])
    outsider = make_user('social_service')
    db.session.commit()
    with pytest.raises(ReviewForbidden) as err:
        decide(outsider, 'admission_doc', sub.uuid, 'approve')
    assert err.value.status_code == 403
    assert _reload(sub).status == 'pending'


def test_postgrad_decides_any_program(world):
    sub = world.submit(world.archives['admission_doc'], owner=world.other_up)
    assert decide(world.postgrad, 'admission_doc', sub.uuid, 'approve').status == 'approved'


# ─── Reversion effects ───────────────────────────────────────────────────────

def test_revert_approval_of_titled_is_conflict(world):
    sub = world.submit(world.archives['conclusion_doc'])
    decide(world.coordinator, 'conclusion_doc', sub.uuid, 'approve')
    UserProgram.query.filter_by(id=world.up.id).update({'academic_status': 'titled'})
    db.session.commit()

    with pytest.raises(ReviewConflict) as err:
        decide(world.coordinator, 'conclusion_doc', sub.uuid, 'reject', revert_reason='Error')
    assert 'titulado' in err.value.message
    assert _reload(sub).status == 'approved'


def test_revert_conclusion_doc_reopens_condition(world):
    up = world.up
    archive = world.archives['conclusion_doc']
    cond = AdmissionCondition(user_program_id=up.id, description='Entregar tesis final',
                              archive_id=archive.id, status='pending')
    db.session.add(cond)
    db.session.commit()
    sub = world.submit(archive)

    decide(world.coordinator, 'conclusion_doc', sub.uuid, 'approve')
    db.session.expire_all()
    cond = db.session.get(AdmissionCondition, cond.id)
    assert cond.status == 'met' and cond.resolved_by_submission_id == sub.id

    decide(world.coordinator, 'conclusion_doc', sub.uuid, 'reject', revert_reason='Archivo erróneo')
    db.session.expire_all()
    cond = db.session.get(AdmissionCondition, cond.id)
    assert cond.status == 'pending' and cond.resolved_by_submission_id is None
    assert conclusion_service.exam_blockers(db.session.get(UserProgram, up.id))


def test_approve_leave_puts_enrollment_on_leave(world):
    sub = world.submit(world.archives['leave_request'])
    decide(world.coordinator, 'leave_request', sub.uuid, 'approve')
    db.session.expire_all()
    assert db.session.get(SemesterEnrollment, world.enrollment.id).status == 'on_leave'
    assert db.session.get(UserProgram, world.up.id).academic_status == 'on_leave'
    assert Notification.query.filter_by(user_id=world.student.id,
                                        type='leave_request_approved').count() == 1


def test_revert_leave_restores_active(world):
    sub = world.submit(world.archives['leave_request'])
    decide(world.coordinator, 'leave_request', sub.uuid, 'approve')
    decide(world.coordinator, 'leave_request', sub.uuid, 'reject',
           revert_reason='Se aprobó por error')
    db.session.expire_all()
    assert db.session.get(SemesterEnrollment, world.enrollment.id).status == 'active'
    assert db.session.get(UserProgram, world.up.id).academic_status == 'active'


def test_revert_leave_after_period_changed_conflicts(world):
    sub = world.submit(world.archives['leave_request'])
    decide(world.coordinator, 'leave_request', sub.uuid, 'approve')
    SemesterEnrollment.query.filter_by(id=world.enrollment.id).update({'status': 'dropped'})
    db.session.commit()

    with pytest.raises(ReviewConflict) as err:
        decide(world.coordinator, 'leave_request', sub.uuid, 'reject', revert_reason='Error')
    assert 'periodo' in err.value.message
    assert _reload(sub).status == 'approved'


# ─── History ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('key, action, owner_is_student', [
    ('admission_doc', 'document_reviewed', False),
    ('conclusion_doc', 'document_reviewed', False),
    ('permanence_doc', 'permanence_document_approved', True),
    ('leave_request', 'leave_request_approved', True),
])
def test_history_has_user_program_id(world, key, action, owner_is_student):
    sub = world.submit(world.archives[key])
    decide(world.coordinator, key, sub.uuid, 'approve')
    owner = world.student.id if owner_is_student else world.coordinator.id
    entry = UserHistory.query.filter_by(user_id=owner, action=action).one()
    assert entry.user_program_id == world.up.id


# ─── Legacy wrappers keep their contracts ────────────────────────────────────

def test_decide_submission_wrapper(world):
    sub = world.submit(world.archives['admission_doc'])
    result = review_service.decide_submission(world.coordinator, sub.id, 'approve', 'ok')
    assert isinstance(result, Submission) and result.status == 'approved'
    with pytest.raises(ReviewConflict):
        # 6D: re-deciding needs a reason
        review_service.decide_submission(world.coordinator, sub.id, 'reject')
    with pytest.raises(review_service.InvalidReviewAction):
        review_service.decide_submission(world.coordinator, sub.id, 'maybe')
    other = world.submit(world.archives['admission_doc'], owner=world.other_up)
    with pytest.raises(review_service.SubmissionNotFound):
        review_service.decide_submission(world.coordinator, other.id, 'approve')


def test_review_permanence_document_wrapper(world):
    sub = world.submit(world.archives['permanence_doc'])
    data = permanence_service.review_permanence_document(sub.id, world.coordinator.id,
                                                         'rejected', 'Borroso')
    assert data['status'] == 'rejected' and data['reviewer_comment'] == 'Borroso'
    assert data['id'] == str(sub.uuid)
    with pytest.raises(permanence_service.InvalidStateTransition):
        # 6D: re-deciding needs a reason
        permanence_service.review_permanence_document(sub.id, world.coordinator.id, 'approved')
    with pytest.raises(permanence_service.StudentNotFound):
        permanence_service.review_permanence_document(999999, world.coordinator.id, 'approved')


def test_process_leave_request_wrapper(world):
    sub = world.submit(world.archives['leave_request'])
    result = permanence_service.process_leave_request(sub.id, world.coordinator.id, True)
    assert result['new_enrollment_status'] == 'on_leave'
    assert result['submission']['status'] == 'approved'
    with pytest.raises(permanence_service.InvalidStateTransition):
        permanence_service.process_leave_request(sub.id, world.coordinator.id, False)
    doc = world.submit(world.archives['permanence_doc'])
    with pytest.raises(permanence_service.InvalidStateTransition):
        permanence_service.process_leave_request(doc.id, world.coordinator.id, True)


def test_admin_review_route_redecision_is_409(world, client):
    from tests.support.fixtures import login_as

    sub = world.submit(world.archives['admission_doc'])
    api = login_as(client, world.coordinator)
    url = f'/api/v1/admin/review/submissions/{sub.uuid}/decision'
    assert api.post(url, json={'action': 'approve'}).status_code == 200
    resp = api.post(url, json={'action': 'reject'})
    assert resp.status_code == 409
    assert resp.get_json()['error']['code'] == 'CONFLICT'


# ─── Inbox queries ───────────────────────────────────────────────────────────

def test_pending_query_is_per_kind_and_scoped(world):
    mine = {key: world.submit(world.archives[key]) for key in SUBMISSION_KINDS}
    foreign = world.submit(world.archives['admission_doc'], owner=world.other_up)
    for key in SUBMISSION_KINDS:
        kind = get_kind(key)
        assert [s.id for s in kind.pending_query({world.program.id})] == [mine[key].id]
    everything = get_kind('admission_doc').pending_query(None).all()
    assert {s.id for s in everything} == {mine['admission_doc'].id, foreign.id}
    assert get_kind('admission_doc').pending_query(set()).all() == []


def test_decided_query_since(world):
    old = world.submit(world.archives['permanence_doc'])
    new = world.submit(world.archives['permanence_doc'])
    decide(world.coordinator, 'permanence_doc', old.uuid, 'approve')
    decide(world.coordinator, 'permanence_doc', new.uuid, 'reject', 'No')
    Submission.query.filter_by(id=old.id).update(
        {'review_date': now_local() - timedelta(days=40)})
    db.session.commit()

    kind = get_kind('permanence_doc')
    since = now_local() - timedelta(days=30)
    assert [s.id for s in kind.decided_query({world.program.id}, since)] == [new.id]
    assert kind.pending_query({world.program.id}).all() == []


def test_row_and_submitted_at(world):
    sub = world.submit(world.archives['permanence_doc'])
    kind = get_kind('permanence_doc')
    row = kind.row(sub)
    for key in ('student_name', 'student_uuid', 'program_name', 'kind_label', 'title',
                'uploaded_at', 'file_url', 'uuid'):
        assert key in row
    assert row['uuid'] == str(sub.uuid)
    assert row['kind_label'] == kind.label
    assert row['title'] == 'Constancia de calificaciones'
    assert row['program_name'] == world.program.name
    assert kind.submitted_at(sub) == sub.upload_date
    assert get_kind('leave_request').row(world.submit(world.archives['leave_request']))[
        'title'] == 'Solicitud de baja temporal'


def test_engine_exports(app):
    for name in ('decide', 'get_kind', 'KINDS', 'register', 'ReviewKind', 'Decision',
                 'ReviewError', 'ReviewNotFound', 'ReviewConflict', 'ReviewForbidden'):
        assert hasattr(review_engine, name)

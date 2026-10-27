"""Regressions of the phase 6D review + QA findings (engine, inbox, legacy routes)."""
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from app import db
from app.models import ExtensionRequest, Submission
from app.models.notification import Notification
from app.services import file_access_service, permanence_service, review_inbox_service
from app.services.review_engine import ReviewConflict, decide, get_kind
from app.utils.datetime_utils import now_local
from tests.review_engine.conftest import world  # noqa: F401  (fixture used by `inbox`)
from tests.review_inbox.conftest import inbox  # noqa: F401  (fixture)
from tests.support.factories import get_or_create_role, grant

HX = {'HX-Request': 'true'}
INBOX_JS = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'js' / 'review' / 'inbox.js'


@pytest.fixture
def staff(inbox):  # noqa: F811
    inbox.grant_all()
    for role in ('program_admin', 'postgraduate_admin'):
        grant(get_or_create_role(role), 'review.page.inbox', 'admin_review.page.view',
              'admin_review.api.detail_submission')
    db.session.commit()
    return inbox


def _doc_notices(user_id):
    return Notification.query.filter(
        Notification.user_id == user_id,
        Notification.type.in_(('document_approved', 'document_rejected')),
    ).count()


# ── 1. Extension grant date: engine refusal + modal `min` ────────────────

def test_inbox_grant_with_past_date_is_400(staff, login):
    er = staff.extension()
    yesterday = (now_local() - timedelta(days=1)).date().isoformat()
    res = login(staff.world.postgrad).post(
        f'/review/extension/{er.uuid}/decide', headers=HX,
        data={'decision': 'approve', 'granted_until': yesterday})
    assert res.status_code == 400
    flash = json.loads(res.headers['HX-Trigger'])['siiap:flash']
    assert flash['message'] == 'La fecha de la prórroga debe ser futura'
    db.session.refresh(er)
    assert er.status == 'pending' and er.granted_until is None


def test_modal_date_input_has_min_tomorrow(staff, login):
    er = staff.extension()
    html = login(staff.world.postgrad).get(
        f'/review/extension/{er.uuid}/decide?decision=approve', headers=HX).get_data(as_text=True)
    tomorrow = (now_local().date() + timedelta(days=1)).isoformat()
    tag = re.search(r'<input[^>]*name="granted_until"[^>]*>', html).group(0)
    assert f'min="{tomorrow}"' in tag


def test_inbox_reject_extension_stores_comment(staff, login):
    er = staff.extension()
    res = login(staff.world.postgrad).post(
        f'/review/extension/{er.uuid}/decide', headers=HX,
        data={'decision': 'reject', 'comment': 'Sin documento probatorio'})
    assert res.status_code == 200
    db.session.refresh(er)
    assert er.status == 'rejected' and er.condition_text == 'Sin documento probatorio'


# ── 3. One student notice per admission/conclusion decision ──────────────

@pytest.mark.parametrize('key', ['admission_doc', 'conclusion_doc'])
@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_one_notice_per_first_decision(world, key, decision):  # noqa: F811
    sub = world.submit(world.archives[key])
    decide(world.coordinator, key, sub.uuid, decision, 'Motivo')
    assert _doc_notices(world.student.id) == 1
    notice = Notification.query.filter(
        Notification.user_id == world.student.id,
        Notification.type.in_(('document_approved', 'document_rejected')),
    ).one()
    data = notice.data if isinstance(notice.data, dict) else json.loads(notice.data or '{}')
    assert data.get('submission_id') == sub.id


def test_one_notice_per_change_of_decision(world):  # noqa: F811
    sub = world.submit(world.archives['admission_doc'])
    decide(world.coordinator, 'admission_doc', sub.uuid, 'approve')
    decide(world.coordinator, 'admission_doc', sub.uuid, 'reject', revert_reason='Ilegible')
    assert _doc_notices(world.student.id) == 2


def test_log_document_review_still_notifies_by_default(world):  # noqa: F811
    from app.services.user_history_service import UserHistoryService

    UserHistoryService.log_document_review(
        user_id=world.student.id, archive_name='Acta', status='approved',
        admin_id=world.coordinator.id)
    db.session.commit()
    assert _doc_notices(world.student.id) == 1


# ── 4. The modal GET loads without a row lock ────────────────────────────

def test_get_row_does_not_lock(staff, monkeypatch):
    sub = staff.submission('admission_doc')
    kind = get_kind('admission_doc')

    def boom(*_a, **_k):
        raise AssertionError('get_row must not take a row lock')

    monkeypatch.setattr(kind, 'load_for_update', boom)
    row = review_inbox_service.get_row(staff.world.postgrad, 'admission_doc', sub.uuid)
    assert row['uuid'] == str(sub.uuid) and row['pending'] is True


def test_get_row_kind_mismatch_is_not_found(staff):
    from app.services.review_engine import ReviewNotFound

    sub = staff.submission('admission_doc')
    with pytest.raises(ReviewNotFound):
        review_inbox_service.get_row(staff.world.postgrad, 'permanence_doc', sub.uuid)


# ── 5. Permanence / leave: only `review` is decidable ────────────────────

@pytest.mark.parametrize('key', ['permanence_doc', 'leave_request'])
def test_permanence_pending_status_is_not_decidable(world, key):  # noqa: F811
    sub = world.submit(world.archives[key], status='pending')
    kind = get_kind(key)
    assert kind.pending_statuses == ('review',)
    assert sub.id not in [s.id for s in kind.pending_query(None).all()]
    for reason in (None, 'Cambio'):
        with pytest.raises(ReviewConflict):
            decide(world.coordinator, key, sub.uuid, 'approve', revert_reason=reason)
    db.session.expire_all()
    assert db.session.get(Submission, sub.id).status == 'pending'


def test_permanence_wrappers_refuse_pending(world):  # noqa: F811
    doc = world.submit(world.archives['permanence_doc'], status='pending')
    with pytest.raises(permanence_service.InvalidStateTransition):
        permanence_service.review_permanence_document(doc.id, world.coordinator.id, 'approved')
    leave = world.submit(world.archives['leave_request'], status='pending')
    with pytest.raises(permanence_service.InvalidStateTransition):
        permanence_service.process_leave_request(leave.id, world.coordinator.id, True)


def test_admission_kind_keeps_pending_and_review(world):  # noqa: F811
    assert get_kind('admission_doc').pending_statuses == ('pending', 'review')
    assert get_kind('conclusion_doc').pending_statuses == ('pending', 'review')


# ── 6. Legacy admin/review decide: route envelope for a conflict ─────────

def test_admin_review_conflict_uses_route_envelope(world, client):  # noqa: F811
    from tests.support.fixtures import login_as

    sub = world.submit(world.archives['admission_doc'])
    api = login_as(client, world.coordinator)
    url = f'/api/v1/admin/review/submissions/{sub.uuid}/decision'
    assert api.post(url, json={'action': 'approve'}).status_code == 200
    resp = api.post(url, json={'action': 'reject'})
    body = resp.get_json()
    assert resp.status_code == 409
    assert body['data'] is None and body['meta'] == {}
    assert body['error']['code'] == 'CONFLICT'
    assert 'motivo' in body['error']['message']
    assert body['flash'] == [{'level': 'warning', 'message': body['error']['message']}]


# ── 9. Legacy list links that carry a submission / applicant filter ──────

def test_admin_review_submission_filter_goes_to_detail(staff, login):
    sub = staff.submission('admission_doc')
    res = login(staff.world.coordinator).get(
        f'/admin/review/submissions?submission_id={sub.uuid}')
    assert res.status_code == 302
    assert res.headers['Location'].endswith(f'/admin/review/submission/{sub.uuid}')


def test_admin_review_applicant_filter_keeps_legacy_list(staff, login):
    res = login(staff.world.coordinator).get(
        f'/admin/review/submissions?applicant_id={staff.world.student.uuid}')
    assert res.status_code == 200


def test_admin_review_bad_submission_filter_keeps_legacy_list(staff, login):
    res = login(staff.world.coordinator).get('/admin/review/submissions?submission_id=nope')
    assert res.status_code == 200


# ── 10. inbox.js handles `siiap:review-count` once ───────────────────────

def test_inbox_js_listens_to_review_count_once():
    source = INBOX_JS.read_text(encoding='utf-8')
    assert len(re.findall(r"addEventListener\('siiap:review-count'", source)) == 1


# ── 11. A cancelled extension says so, even with a reason ────────────────

def test_cancelled_extension_message_comes_first(staff):
    er = staff.extension(status='cancelled')
    for reason in (None, 'Cambio'):
        with pytest.raises(ReviewConflict, match='cancelada'):
            decide(staff.world.postgrad, 'extension', er.uuid, 'reject', revert_reason=reason)
    assert db.session.get(ExtensionRequest, er.id).status == 'cancelled'


# ── 12. stored_file_exists stays inside the documents folder ─────────────

def test_stored_file_exists_refuses_paths_outside_base(app, tmp_path):
    base = tmp_path / 'docs'
    (base / '1' / 'admission').mkdir(parents=True)
    (base / '1' / 'admission' / 'a.pdf').write_bytes(b'%PDF')
    (tmp_path / 'secret.txt').write_text('x')
    app.config['USER_DOCS_FOLDER'] = str(base)

    assert file_access_service.stored_file_exists('1/admission/a.pdf')
    assert file_access_service.stored_file_exists('documents/1/admission/a.pdf')
    assert not file_access_service.stored_file_exists('../secret.txt')
    assert not file_access_service.stored_file_exists('1/../../secret.txt')
    assert not file_access_service.stored_file_exists('1/admission/missing.pdf')

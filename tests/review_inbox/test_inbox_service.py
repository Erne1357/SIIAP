"""Phase 6D, task 6: `review_inbox_service` (the "Por revisar" inbox)."""
from contextlib import contextmanager

from sqlalchemy import event

from app import db
from app.services import review_inbox_service as inbox_svc
from app.services.review_engine import KINDS
from tests.review_inbox.conftest import ago
from tests.support.factories import enroll, make_program, make_user

ALL_KINDS = tuple(KINDS)


@contextmanager
def count_queries():
    statements = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', _count)
    try:
        yield statements
    finally:
        event.remove(db.engine, 'before_cursor_execute', _count)


def _uuids(result):
    return [item['uuid'] for item in result['items']]


def test_visible_kinds_in_registry_order(inbox):
    inbox.grant_all()
    keys = [k.key for k in inbox_svc.visible_kinds(inbox.world.postgrad)]
    assert keys == list(ALL_KINDS)
    assert inbox_svc.visible_kinds(None) == []


def test_coordinator_sees_only_own_programs(inbox):
    inbox.grant_all()
    w = inbox.world
    own = [inbox.submission('admission_doc'), inbox.receipt(), inbox.extension()]
    foreign = [inbox.submission('admission_doc', owner=w.other_up),
               inbox.receipt(owner=w.other_up), inbox.extension(owner=w.other_up)]

    result = inbox_svc.list_items(w.coordinator)
    assert set(_uuids(result)) == {str(x.uuid) for x in own}
    assert result['total'] == 3
    assert result['counts']['admission_doc'] == 1
    assert {item['program_id'] for item in result['items']} == {w.program.id}

    other = inbox_svc.list_items(w.other_coordinator)
    assert set(_uuids(other)) == {str(x.uuid) for x in foreign}

    # A program outside the scope gives an empty result, not an error.
    denied = inbox_svc.list_items(w.coordinator, program_id=w.other_program.id)
    assert denied['items'] == [] and denied['total'] == 0
    assert set(denied['counts'].values()) == {0}


def test_postgrad_sees_all(inbox):
    inbox.grant_all()
    w = inbox.world
    made = [inbox.submission('admission_doc'), inbox.submission('permanence_doc'),
            inbox.submission('leave_request'), inbox.submission('conclusion_doc'),
            inbox.receipt(), inbox.extension(),
            inbox.submission('admission_doc', owner=w.other_up),
            inbox.receipt(owner=w.other_up), inbox.extension(owner=w.other_up)]

    result = inbox_svc.list_items(w.postgrad)
    assert set(_uuids(result)) == {str(x.uuid) for x in made}
    assert result['counts'] == {'admission_doc': 2, 'permanence_doc': 1, 'leave_request': 1,
                                'conclusion_doc': 1, 'enrollment_receipt': 2, 'extension': 2}
    assert [key for key, _label in result['kinds']] == list(ALL_KINDS)
    assert result['view'] == 'pending'


def test_kind_hidden_without_permission(inbox):
    """Review focus #3: a coordinator with two programs, no receipt/extension permission."""
    w = inbox.world
    second = make_program(w.coordinator)
    applicant = make_user('applicant')
    second_up = enroll(applicant, second, 'accepted')
    db.session.commit()

    doc = inbox.submission('admission_doc')
    inbox.receipt()
    inbox.receipt(owner=second_up)
    inbox.extension()

    kinds = [k.key for k in inbox_svc.visible_kinds(w.coordinator)]
    assert 'enrollment_receipt' not in kinds and 'extension' not in kinds

    result = inbox_svc.list_items(w.coordinator)
    assert _uuids(result) == [str(doc.uuid)]
    assert 'enrollment_receipt' not in result['counts']
    assert 'extension' not in result['counts']
    assert ('enrollment_receipt', 'Recibo de inscripción') not in result['kinds']
    assert inbox_svc.list_items(w.coordinator, kind='enrollment_receipt')['items'] == []
    assert inbox_svc.pending_total(w.coordinator) == 1


def test_oldest_first_and_overdue_flag(inbox):
    inbox.grant_all()
    seven = inbox.receipt(days=7)
    eight = inbox.submission('admission_doc', days=8)
    fresh = inbox.extension(days=0)
    twenty = inbox.submission('permanence_doc', days=20)

    items = inbox_svc.list_items(inbox.world.coordinator)['items']
    assert [i['uuid'] for i in items] == [str(x.uuid) for x in (twenty, eight, seven, fresh)]
    by_uuid = {i['uuid']: i for i in items}
    assert by_uuid[str(eight.uuid)]['days_waiting'] == 8
    assert by_uuid[str(eight.uuid)]['overdue'] is True
    assert by_uuid[str(seven.uuid)]['days_waiting'] == 7
    assert by_uuid[str(seven.uuid)]['overdue'] is False
    assert by_uuid[str(fresh.uuid)]['days_waiting'] == 0
    assert by_uuid[str(twenty.uuid)]['kind'] == 'permanence_doc'
    assert by_uuid[str(seven.uuid)]['kind'] == 'enrollment_receipt'


def test_filters(inbox):
    inbox.grant_all()
    w = inbox.world
    own_doc = inbox.submission('admission_doc')
    own_receipt = inbox.receipt()
    foreign_doc = inbox.submission('admission_doc', owner=w.other_up)
    inbox.extension(owner=w.other_up)

    by_program = inbox_svc.list_items(w.postgrad, program_id=w.program.id)
    assert set(_uuids(by_program)) == {str(own_doc.uuid), str(own_receipt.uuid)}
    # Counts follow the program filter...
    assert by_program['counts']['admission_doc'] == 1
    assert by_program['counts']['extension'] == 0

    by_kind = inbox_svc.list_items(w.postgrad, kind='admission_doc')
    assert set(_uuids(by_kind)) == {str(own_doc.uuid), str(foreign_doc.uuid)}
    # ...but not the kind filter: every tab keeps its backlog.
    assert by_kind['counts']['enrollment_receipt'] == 1
    assert by_kind['total'] == 2

    both = inbox_svc.list_items(w.postgrad, program_id=str(w.other_program.id),
                                kind='admission_doc')
    assert _uuids(both) == [str(foreign_doc.uuid)]

    assert inbox_svc.list_items(w.postgrad, kind='nope')['items'] == []
    assert inbox_svc.list_items(w.postgrad, program_id='x')['items'] == []


def test_pagination(inbox):
    inbox.grant_all()
    made = []
    for n in range(10):
        made.append(inbox.submission('admission_doc', days=3 * n))
        made.append(inbox.receipt(days=3 * n + 1))
        made.append(inbox.extension(days=3 * n + 2))
    expected = [str(x.uuid) for x in reversed(made)]  # oldest first

    first = inbox_svc.list_items(inbox.world.coordinator, page=1, per_page=25)
    second = inbox_svc.list_items(inbox.world.coordinator, page=2, per_page=25)
    assert (first['total'], first['pages'], first['per_page']) == (30, 2, 25)
    assert len(first['items']) == 25 and len(second['items']) == 5
    assert _uuids(first) + _uuids(second) == expected
    assert first['counts'] == {'admission_doc': 10, 'permanence_doc': 0, 'leave_request': 0,
                               'conclusion_doc': 0, 'enrollment_receipt': 10, 'extension': 10}

    # A page past the end is clamped to the last one.
    beyond = inbox_svc.list_items(inbox.world.coordinator, page=9, per_page=25)
    assert beyond['page'] == 2 and _uuids(beyond) == _uuids(second)

    only_receipts = inbox_svc.list_items(inbox.world.coordinator, kind='enrollment_receipt',
                                         per_page=4, page=3)
    assert only_receipts['total'] == 10 and only_receipts['pages'] == 3
    assert len(only_receipts['items']) == 2


def test_decided_view_last_30_days(inbox):
    inbox.grant_all()
    w = inbox.world
    recent_doc = inbox.submission('admission_doc', status='approved', review_date=ago(5))
    old_doc = inbox.submission('admission_doc', status='rejected', review_date=ago(31))
    recent_receipt = inbox.receipt(status='rejected', reviewed_at=ago(1))
    recent_ext = inbox.extension(status='granted', decided_at=ago(10))
    pending = inbox.submission('admission_doc')

    result = inbox_svc.list_items(w.coordinator, view='decided')
    assert result['view'] == 'decided'
    assert _uuids(result) == [str(recent_receipt.uuid), str(recent_doc.uuid),
                              str(recent_ext.uuid)]
    assert str(old_doc.uuid) not in _uuids(result)
    assert str(pending.uuid) not in _uuids(result)
    assert all(i['days_waiting'] is None and i['overdue'] is False for i in result['items'])
    assert result['items'][0]['status'] == 'rejected'
    # Counts stay pending counts in every view.
    assert result['counts']['admission_doc'] == 1
    assert result['counts']['enrollment_receipt'] == 0


def test_pending_total(inbox):
    inbox.grant_all()
    w = inbox.world
    inbox.submission('admission_doc')
    inbox.submission('leave_request')
    inbox.receipt()
    inbox.extension()
    inbox.submission('admission_doc', status='approved')
    inbox.extension(owner=w.other_up)

    assert inbox_svc.pending_total(w.coordinator) == 4
    assert inbox_svc.pending_total(w.other_coordinator) == 1
    assert inbox_svc.pending_total(w.postgrad) == 5
    assert inbox_svc.pending_total(w.student) == 0


def test_page_of_mixed_items_has_bounded_queries(inbox):
    inbox.grant_all()
    w = inbox.world
    second_student = make_user('student')
    second_up = enroll(second_student, w.program, 'enrolled')
    db.session.commit()
    kinds = ('admission_doc', 'permanence_doc', 'leave_request', 'conclusion_doc')
    for n in range(5):
        owner = w.up if n % 2 else second_up
        for kind in kinds:
            inbox.submission(kind, owner=owner, days=n)
        inbox.receipt(owner=owner, days=n)
        inbox.extension(owner=owner, days=n)
    db.session.expire_all()
    inbox_svc.visible_kinds(w.postgrad)  # permission cache, as in a real request

    with count_queries() as statements:
        result = inbox_svc.list_items(w.postgrad, per_page=25)

    assert len(result['items']) == 25 and result['total'] == 30
    assert all(i['student_name'] and i['program_name'] for i in result['items'])
    # 6 key queries + one bulk load per kind + the extensions' student programs
    # (+ scope lookup): independent of how many rows the page holds.
    assert len(statements) <= 16, statements

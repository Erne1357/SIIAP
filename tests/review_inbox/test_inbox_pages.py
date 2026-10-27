"""Phase 6D, task 7: the "Por revisar" inbox pages (page, rows fragment, modal, decide)."""
import json
from pathlib import Path

import pytest

from app import db
from app.models.submission import Submission
from tests.review_inbox.conftest import inbox  # noqa: F401  (fixture)
from tests.review_engine.conftest import world  # noqa: F401  (fixture used by `inbox`)
from tests.support.factories import get_or_create_role, grant, make_user

HX = {'HX-Request': 'true'}


@pytest.fixture
def staff(inbox):  # noqa: F811
    """Inbox permission on both staff roles + every decision permission."""
    inbox.grant_all()
    for role in ('program_admin', 'postgraduate_admin'):
        grant(get_or_create_role(role), 'review.page.inbox', 'admin_review.page.view',
              'admin_review.api.detail_submission')
    db.session.commit()
    return inbox


def _flash(res):
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']


def _html(res):
    return res.get_data(as_text=True)


# ── Access ───────────────────────────────────────────────────────────────

def test_page_200_for_coordinator_and_postgrad(staff, login):
    w = staff.world
    staff.submission('admission_doc')
    for user in (w.coordinator, w.postgrad):
        res = login(user).get('/review/')
        assert res.status_code == 200
        html = _html(res)
        assert 'Por revisar' in html
        assert 'Pendientes' in html and 'Decididos recientemente' in html
        assert 'Acta de nacimiento' in html


def test_page_403_without_permission(staff, login):
    student = make_user('student')
    # A full-page denial redirects (app convention); an HTMX request gets the real 403.
    assert login(student).get('/review/').status_code in (302, 403)
    assert login(student).get('/review/rows', headers=HX).status_code == 403
    assert login(student).get('/review/', headers=HX).status_code == 403


# ── Rows fragment ────────────────────────────────────────────────────────

def test_rows_fragment_filters_by_kind_and_program(staff, login):
    w = staff.world
    staff.submission('admission_doc')
    staff.submission('permanence_doc')
    staff.submission('admission_doc', owner=w.other_up)
    client = login(w.postgrad)

    html = _html(client.get('/review/rows?kind=permanence_doc', headers=HX))
    assert 'Constancia de calificaciones' in html
    assert 'Acta de nacimiento' not in html

    html = _html(client.get(f'/review/rows?program={w.program.id}', headers=HX))
    assert html.count('id="review-row-') == 2
    assert 'Todos los tipos (2)' in html


def test_coordinator_only_sees_own_programs(staff, login):
    w = staff.world
    staff.submission('admission_doc', owner=w.other_up)
    html = _html(login(w.coordinator).get('/review/rows', headers=HX))
    assert 'id="review-row-' not in html
    assert 'No hay nada por revisar' in html
    assert 'empty-state' in html


def test_overdue_badge_has_text(staff, login):
    staff.submission('admission_doc', days=9)
    staff.submission('permanence_doc', days=1)
    html = _html(login(staff.world.postgrad).get('/review/rows', headers=HX))
    assert html.count('status-badge--warning') == 1
    assert 'Más de 7 días' in html
    assert '9 días' in html and '1 día' in html


def test_table_markup(staff, login):
    staff.submission('admission_doc')
    html = _html(login(staff.world.postgrad).get('/review/rows', headers=HX))
    assert '<caption class="visually-hidden">' in html
    assert 'scope="col"' in html


# ── Missing file ─────────────────────────────────────────────────────────

def test_row_with_missing_file(staff, login):
    """The file is gone from disk: the row is still listed and decidable."""
    w = staff.world
    sub = staff.submission('admission_doc')
    html = _html(login(w.postgrad).get('/review/rows', headers=HX))
    assert 'Archivo no disponible' in html
    assert 'Ver archivo' not in html

    res = login(w.postgrad).post(f'/review/admission_doc/{sub.uuid}/decide', headers=HX,
                                 data={'decision': 'approve'})
    assert res.status_code == 200
    assert db.session.get(Submission, sub.id).status == 'approved'


def test_row_with_existing_file_links_it(staff, login, app):
    sub = staff.submission('admission_doc')
    path = Path(app.config['USER_DOCS_FOLDER']) / sub.file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'%PDF-1.4')
    html = _html(login(staff.world.postgrad).get('/review/rows', headers=HX))
    assert 'Ver archivo' in html
    assert f'/files/doc/{sub.uuid}' in html
    assert 'Archivo no disponible' not in html


def test_extension_row_has_no_file_message(staff, login):
    staff.extension()
    html = _html(login(staff.world.postgrad).get('/review/rows', headers=HX))
    assert 'Archivo no disponible' not in html
    assert 'Título en trámite' in html or 'Prórroga' in html


# ── Modal ────────────────────────────────────────────────────────────────

def test_modal_prefilled_and_required_reason(staff, login):
    sub = staff.submission('admission_doc')
    res = login(staff.world.postgrad).get(
        f'/review/admission_doc/{sub.uuid}/decide?decision=reject&view=pending&page=1', headers=HX)
    html = _html(res)
    assert res.status_code == 200
    assert 'name="decision" value="reject"' in html
    assert 'Motivo del rechazo' in html
    assert 'required' in html
    assert 'Acta de nacimiento' in html


def test_modal_out_of_scope_is_404(staff, login):
    sub = staff.submission('admission_doc', owner=staff.world.other_up)
    res = login(staff.world.coordinator).get(f'/review/admission_doc/{sub.uuid}/decide', headers=HX)
    assert res.status_code == 404


# ── Decide ───────────────────────────────────────────────────────────────

def test_post_approve_removes_row_and_flashes(staff, login):
    sub = staff.submission('admission_doc')
    keep = staff.submission('permanence_doc')
    res = login(staff.world.postgrad).post(
        f'/review/admission_doc/{sub.uuid}/decide', headers=HX,
        data={'decision': 'approve', 'view': 'pending', 'page': '1'})
    assert res.status_code == 200
    html = _html(res)
    assert f'review-row-{sub.uuid}' not in html
    assert f'review-row-{keep.uuid}' in html
    assert _flash(res) == {'level': 'success', 'message': 'Elemento aprobado.'}
    assert json.loads(res.headers['HX-Trigger'])['siiap:review-count'] == {'count': 1}
    assert db.session.get(Submission, sub.id).status == 'approved'


def test_post_change_without_reason_is_conflict_flash(staff, login):
    sub = staff.submission('admission_doc', status='approved')
    res = login(staff.world.postgrad).post(
        f'/review/admission_doc/{sub.uuid}/decide', headers=HX, data={'decision': 'reject'})
    assert res.status_code == 409
    assert res.headers.get('HX-Reswap') == 'none'
    assert 'motivo' in _flash(res)['message']
    assert db.session.get(Submission, sub.id).status == 'approved'


def test_post_change_with_reason_in_decided_view(staff, login):
    sub = staff.submission('admission_doc', status='approved', days=2)
    sub.review_date = sub.upload_date
    db.session.commit()
    client = login(staff.world.postgrad)
    assert 'Cambiar decisión' in _html(client.get('/review/rows?view=decided', headers=HX))
    res = client.post(f'/review/admission_doc/{sub.uuid}/decide', headers=HX,
                      data={'decision': 'reject', 'revert_reason': 'Documento ilegible',
                            'view': 'decided'})
    assert res.status_code == 200
    assert 'Decisión cambiada' in _flash(res)['message']
    assert db.session.get(Submission, sub.id).status == 'rejected'


def test_post_without_kind_permission_is_403(staff, login):
    sub = staff.submission('admission_doc')
    user = make_user('teacher')
    grant(user.role, 'review.page.inbox')
    db.session.commit()
    res = login(user).post(f'/review/admission_doc/{sub.uuid}/decide', headers=HX,
                           data={'decision': 'approve'})
    assert res.status_code == 403
    assert db.session.get(Submission, sub.id).status == 'pending'


def test_post_out_of_scope_is_404(staff, login):
    sub = staff.submission('admission_doc', owner=staff.world.other_up)
    res = login(staff.world.coordinator).post(
        f'/review/admission_doc/{sub.uuid}/decide', headers=HX, data={'decision': 'approve'})
    assert res.status_code == 404


def test_extension_approve_with_granted_until(staff, login):
    er = staff.extension()
    client = login(staff.world.postgrad)
    html = _html(client.get(f'/review/extension/{er.uuid}/decide?decision=approve', headers=HX))
    assert 'name="granted_until"' in html

    res = client.post(f'/review/extension/{er.uuid}/decide', headers=HX,
                      data={'decision': 'approve', 'granted_until': '2030-01-31',
                            'condition_text': 'Entregar el título'})
    assert res.status_code == 200
    db.session.refresh(er)
    assert er.status == 'granted'
    assert er.granted_until.date().isoformat() == '2030-01-31'
    assert er.condition_text == 'Entregar el título'


def test_extension_approve_without_date_is_refused(staff, login):
    er = staff.extension()
    res = login(staff.world.postgrad).post(
        f'/review/extension/{er.uuid}/decide', headers=HX, data={'decision': 'approve'})
    assert res.status_code == 409
    db.session.refresh(er)
    assert er.status == 'pending'


def test_extension_bad_date_is_400(staff, login):
    er = staff.extension()
    res = login(staff.world.postgrad).post(
        f'/review/extension/{er.uuid}/decide', headers=HX,
        data={'decision': 'approve', 'granted_until': 'mañana'})
    assert res.status_code == 400


# ── Legacy admin/review ──────────────────────────────────────────────────

@pytest.mark.parametrize('query, expected', [
    ('', '/review/'),
    ('?phase=admission', '/review/?kind=admission_doc'),
    ('?phase=permanence', '/review/?kind=permanence_doc'),
    ('?phase=conclusion', '/review/?kind=conclusion_doc'),
])
def test_admin_review_redirects_to_inbox(staff, login, query, expected):
    client = login(staff.world.coordinator)
    for path in ('/admin/review/', '/admin/review/submissions'):
        res = client.get(path + query)
        assert res.status_code == 302
        assert res.headers['Location'].endswith(expected)


def test_submission_detail_still_works_and_links_back(staff, login):
    sub = staff.submission('admission_doc')
    res = login(staff.world.postgrad).get(f'/admin/review/submission/{sub.uuid}')
    assert res.status_code == 200
    assert 'Volver a Por revisar' in _html(res)


def test_sidebar_badge_counts_pending(staff, login):
    staff.submission('admission_doc')
    staff.submission('permanence_doc')
    html = _html(login(staff.world.postgrad).get('/review/'))
    assert 'data-role="review-badge"' in html

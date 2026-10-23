"""Phase 6C QA follow-up on "Mi conclusión": titled is read-only; new requirement states."""

from app import db
from app.services import conclusion_service as svc
from tests.conclusion.test_conclusion_pages import _status, world  # noqa: F401  (fixture)


def _page(world, login):
    res = login(world['student']).get('/conclusion/')
    assert res.status_code == 200
    return res.get_data(as_text=True)


def test_titled_student_sees_titulado_and_no_upload(world, login):
    _status(world['up'], 'titled')
    db.session.commit()
    html = _page(world, login)
    assert 'Titulado' in html
    assert 'Los requisitos se abren al egreso' not in html
    assert 'conclusion-upload' not in html


def test_graduated_student_can_upload(world, login):
    _status(world['up'], 'graduated')
    db.session.commit()
    html = _page(world, login)
    assert 'conclusion-upload' in html
    assert 'Titulado.' not in html


def test_student_sees_not_applicable_without_upload(world, login):
    _status(world['up'], 'graduated')
    db.session.commit()
    svc.set_requirement_override(world['coord'], world['up'].id, world['thesis_doc'].uuid,
                                 'not_applicable', 'Exento por acuerdo')
    html = _page(world, login)
    assert 'No aplica' in html
    assert f'req-file-{world["thesis_doc"].id}' not in html

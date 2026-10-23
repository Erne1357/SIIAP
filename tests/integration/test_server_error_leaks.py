"""A 500 on /api never carries the exception text (table names, paths, SQL)."""

import pytest

from app.services import acceptance_service, permanence_service
from tests.support.factories import enroll, get_or_create_role, grant, make_program, make_user

GENERIC = 'Ocurrió un error interno. Intenta de nuevo más tarde.'
SECRET = 'secret-table-name'


def _boom(*args, **kwargs):
    raise RuntimeError(SECRET)


def _setup(login, codename):
    coordinator = make_user('program_admin')
    program = make_program(coordinator)
    enroll(make_user('applicant'), program, 'accepted')
    grant(get_or_create_role('program_admin'), codename)
    return login(coordinator), program


@pytest.mark.parametrize('module, func, codename, path', [
    (permanence_service, 'get_enrolled_students', 'permanence.api.list_students',
     '/api/v1/permanence/program/{id}/students'),
    (acceptance_service, 'get_accepted_applicants', 'acceptance.api.list_applicants',
     '/api/v1/acceptance/program/{id}/applicants'),
])
def test_unexpected_error_does_not_leak_exception_text(app, login, monkeypatch,
                                                       module, func, codename, path):
    client, program = _setup(login, codename)
    monkeypatch.setattr(module, func, _boom)

    resp = client.get(path.format(id=program.id))

    assert resp.status_code == 500
    body = resp.get_json()
    assert body['error']['code'] == 'SERVER_ERROR'
    assert body['error']['message'] == GENERIC
    assert body['data'] is None
    assert SECRET not in resp.get_data(as_text=True)

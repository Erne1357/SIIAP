# tests/bulk_import/test_api.py
"""Tests de los endpoints de student-bulk."""

from io import BytesIO
import pytest
from app import db
from app.services import student_bulk_service as svc


def _login(client, user, password='Test1234!'):
    resp = client.post('/api/v1/auth/login',
                       json={'username': user.username, 'password': password})
    try:
        from flask import g as _g
        if hasattr(_g, '_login_user'):
            del _g._login_user
    except RuntimeError:
        pass
    try:
        return resp.get_json().get('data', {}).get('csrf_token', '')
    except Exception:
        return ''


def _csrf(token):
    return {'X-CSRFToken': token}


# ---------------------------------------------------------------------------
# /validate
# ---------------------------------------------------------------------------

def test_validate_endpoint_postgrad_ok(app, client, periods, program, permissions,
                                        postgrad_admin, valid_payload):
    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/validate',
        json=valid_payload,
        headers=_csrf(token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['data']['valid'] is True


def test_validate_endpoint_applicant_403(app, client, periods, program, permissions,
                                          applicant_user, valid_payload):
    """Applicant no tiene permiso → 403."""
    token = _login(client, applicant_user)
    resp = client.post(
        '/api/v1/student-bulk/validate',
        json=valid_payload,
        headers=_csrf(token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /create
# ---------------------------------------------------------------------------

def test_create_endpoint_creates_student(app, client, periods, program, permissions,
                                         postgrad_admin, valid_payload):
    from app.models.user import User
    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/create',
        json=valid_payload,
        headers=_csrf(token),
    )
    assert resp.status_code in (200, 201)
    body = resp.get_json()
    assert body.get('error') is None
    assert User.query.filter_by(email=valid_payload['email']).first() is not None


def test_create_endpoint_validation_error_400(app, client, periods, program, permissions,
                                              postgrad_admin, valid_payload):
    valid_payload['email'] = ''
    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/create',
        json=valid_payload,
        headers=_csrf(token),
    )
    assert resp.status_code == 400


def test_create_endpoint_social_service_with_perm_ok(app, client, periods, program,
                                                     permissions, social_user,
                                                     valid_payload):
    """social_service con permiso de rol asignado puede crear."""
    token = _login(client, social_user)
    resp = client.post(
        '/api/v1/student-bulk/create',
        json=valid_payload,
        headers=_csrf(token),
    )
    assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# /csv/preview
# ---------------------------------------------------------------------------

def test_csv_preview_endpoint(app, client, periods, program, permissions,
                              postgrad_admin):
    csv_text = '\n'.join([
        ','.join(svc.CSV_HEADERS),
        'Ana,Soto,M,ana@test.local,M22110001,' + program.slug + ',2,20223,no',
    ])
    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/csv/preview',
        data={'csv_file': (BytesIO(csv_text.encode('utf-8')), 'students.csv')},
        content_type='multipart/form-data',
        headers=_csrf(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['summary']['total'] == 1
    assert data['summary']['valid'] == 1


def test_csv_preview_missing_file_400(app, client, periods, program, permissions,
                                      postgrad_admin):
    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/csv/preview',
        data={},
        content_type='multipart/form-data',
        headers=_csrf(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /csv/execute
# ---------------------------------------------------------------------------

def test_csv_execute_endpoint(app, client, periods, program, permissions,
                              postgrad_admin):
    csv_text = '\n'.join([
        ','.join(svc.CSV_HEADERS),
        'Eli,Rios,X,eli@test.local,M22110010,' + program.slug + ',2,20223,no',
    ])
    preview = svc.validate_csv(csv_text)

    token = _login(client, postgrad_admin)
    resp = client.post(
        '/api/v1/student-bulk/csv/execute',
        json={'rows': preview['rows']},
        headers=_csrf(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['created'] == 1


# ---------------------------------------------------------------------------
# /csv/template
# ---------------------------------------------------------------------------

def test_csv_template_download(app, client, permissions, postgrad_admin):
    _login(client, postgrad_admin)
    resp = client.get('/api/v1/student-bulk/csv/template')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for h in svc.CSV_HEADERS:
        assert h in body


def test_csv_template_requires_perm(app, client, permissions, applicant_user):
    _login(client, applicant_user)
    resp = client.get('/api/v1/student-bulk/csv/template')
    assert resp.status_code == 403

"""Unit tests: api_response helpers, pydantic validation and the DomainError handler."""

from datetime import date

import pytest
from pydantic import BaseModel, Field, field_validator

from app.services.errors import ConflictError, DomainError, NotFoundError, ValidationFailed
from app.utils.api_response import (
    SERVER_ERROR_MESSAGE, api_error, api_not_found, api_ok, api_server_error,
)
from app.utils.validation import parse_json, parse_model


# ── api_response ─────────────────────────────────────────────────────────────

def test_api_ok_envelope(app):
    with app.test_request_context():
        resp, status = api_ok({'x': 1}, meta={'count': 1})
    assert status == 200
    assert resp.get_json() == {'data': {'x': 1}, 'error': None, 'meta': {'count': 1}}


def test_api_ok_with_flash_and_status(app):
    with app.test_request_context():
        resp, status = api_ok(None, status=201, flash=[{'level': 'success', 'message': 'Listo'}])
    assert status == 201
    assert resp.get_json()['flash'] == [{'level': 'success', 'message': 'Listo'}]


def test_api_error_envelope(app):
    with app.test_request_context():
        resp, status = api_error('BUSINESS_ERROR', 'No se puede', fields={'a': 'b'})
    body = resp.get_json()
    assert status == 400
    assert body['data'] is None and body['meta'] == {}
    assert body['error'] == {'code': 'BUSINESS_ERROR', 'message': 'No se puede', 'fields': {'a': 'b'}}
    assert body['flash'] == [{'level': 'warning', 'message': 'No se puede'}]


def test_api_not_found(app):
    with app.test_request_context():
        resp, status = api_not_found('No existe')
    assert status == 404 and resp.get_json()['error']['code'] == 'NOT_FOUND'


def test_api_server_error_hides_exception_and_logs_it(app, caplog):
    with app.test_request_context():
        resp, status = api_server_error(RuntimeError('relation "user" leaked'), context='t')
    text = resp.get_data(as_text=True)
    assert status == 500
    assert 'leaked' not in text
    assert resp.get_json()['error'] == {'code': 'SERVER_ERROR', 'message': SERVER_ERROR_MESSAGE}
    assert any('leaked' in r.getMessage() or (r.exc_info and 'leaked' in str(r.exc_info[1]))
               for r in caplog.records)


# ── domain errors ────────────────────────────────────────────────────────────

def test_domain_error_defaults():
    e = DomainError('Mensaje')
    assert (e.status_code, e.code, e.message, e.fields) == (400, 'BUSINESS_ERROR', 'Mensaje', None)
    assert NotFoundError('x').status_code == 404
    assert ConflictError('x').status_code == 409
    assert ValidationFailed('x').code == 'VALIDATION_ERROR'
    assert DomainError('x', code='CUSTOM').code == 'CUSTOM'


@pytest.fixture
def raising_app(app):
    def boom_api():
        raise NotFoundError('Evento no encontrado.')

    def boom_page():
        raise DomainError('No permitido.')

    app.add_url_rule('/api/v1/_t/domain', 't_domain_api', boom_api)
    app.add_url_rule('/_t/domain', 't_domain_page', boom_page)
    return app


def test_uncaught_domain_error_becomes_envelope(raising_app):
    resp = raising_app.test_client().get('/api/v1/_t/domain')
    assert resp.status_code == 404
    assert resp.get_json()['error'] == {'code': 'NOT_FOUND', 'message': 'Evento no encontrado.'}


def test_uncaught_domain_error_on_a_page_flashes_and_redirects(raising_app):
    client = raising_app.test_client()
    resp = client.get('/_t/domain')
    assert resp.status_code == 303
    with client.session_transaction() as sess:
        assert ('warning', 'No permitido.') in sess.get('_flashes', [])


# ── validation ───────────────────────────────────────────────────────────────

class _WindowIn(BaseModel):
    date: date
    slot_minutes: int = Field(ge=5, le=240)
    title: str = Field(min_length=3)

    @field_validator('title')
    @classmethod
    def no_placeholder(cls, v):
        if v.lower() == 'xxx':
            raise ValueError('El título no puede ser un marcador.')
        return v


def test_parse_model_ok():
    m = parse_model(_WindowIn, {'date': '2026-10-19', 'slot_minutes': '30', 'title': 'Entrevistas'})
    assert m.date == date(2026, 10, 19) and m.slot_minutes == 30


def test_parse_model_spanish_field_messages():
    with pytest.raises(ValidationFailed) as e:
        parse_model(_WindowIn, {'slot_minutes': 2, 'title': 'ab'})
    fields = e.value.fields
    assert fields['date'] == 'Este campo es obligatorio.'
    assert fields['slot_minutes'] == 'Debe ser mayor o igual que 5.'
    assert fields['title'] == 'Debe tener al menos 3 caracteres.'
    assert e.value.code == 'VALIDATION_ERROR' and e.value.status_code == 400


def test_custom_validator_message_is_kept():
    with pytest.raises(ValidationFailed) as e:
        parse_model(_WindowIn, {'date': '2026-10-19', 'slot_minutes': 30, 'title': 'xxx'})
    assert e.value.fields['title'] == 'El título no puede ser un marcador.'


def test_parse_json_rejects_non_object_body(app):
    with app.test_request_context(json=[1, 2]):
        with pytest.raises(ValidationFailed) as e:
            parse_json(_WindowIn)
    assert 'objeto JSON' in e.value.message


def test_parse_json_missing_body_reports_required_fields(app):
    with app.test_request_context():
        with pytest.raises(ValidationFailed) as e:
            parse_json(_WindowIn)
    assert set(e.value.fields) == {'date', 'slot_minutes', 'title'}


def test_validation_failure_through_a_route(app):
    def create():
        parse_json(_WindowIn)
        return 'ok'

    app.add_url_rule('/api/v1/_t/validate', 't_validate', create, methods=['GET'])
    resp = app.test_client().get('/api/v1/_t/validate', json={'slot_minutes': 'x'})
    body = resp.get_json()
    assert resp.status_code == 400
    assert body['error']['code'] == 'VALIDATION_ERROR'
    assert body['error']['fields']['slot_minutes'] == 'Debe ser un número entero.'


# ── api_server_error classification ─────────────────────────────────────────

def test_api_server_error_keeps_business_value_errors(app):
    with app.test_request_context():
        resp, status = api_server_error(ValueError('El archivo no está disponible.'))
    assert status == 400
    assert resp.get_json()['error'] == {'code': 'BUSINESS_ERROR', 'message': 'El archivo no está disponible.'}


def test_api_server_error_renders_domain_errors(app):
    with app.test_request_context():
        resp, status = api_server_error(NotFoundError('Periodo no encontrado.'))
    assert status == 404 and resp.get_json()['error']['code'] == 'NOT_FOUND'


def test_api_server_error_maps_integrity_errors_to_conflict(app):
    from sqlalchemy.exc import IntegrityError
    exc = IntegrityError('INSERT ...', {}, Exception('duplicate key value violates "uq_secret"'))
    with app.test_request_context():
        resp, status = api_server_error(exc)
    text = resp.get_data(as_text=True)
    assert status == 409
    assert resp.get_json()['error']['code'] == 'CONFLICT'
    assert 'uq_secret' not in text


def test_api_server_error_empty_value_error_is_a_server_error(app):
    with app.test_request_context():
        _, status = api_server_error(ValueError())
    assert status == 500

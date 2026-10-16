"""Unit tests for app/utils/csrf.py and app/utils/urls.py."""

import pytest
from flask import session
from werkzeug.exceptions import BadRequest

from app.utils.csrf import (
    CSRF_HEADER, CSRF_SESSION_KEY, generate_csrf_token, validate_csrf_for_api,
)
from app.utils.urls import DEFAULT_BASE_URL, external_url, get_base_url


# --- generate_csrf_token ----------------------------------------------------

def test_generate_creates_and_stores(app):
    with app.test_request_context():
        t = generate_csrf_token()
        assert t and session[CSRF_SESSION_KEY] == t
        assert len(t) >= 32


def test_generate_is_stable(app):
    with app.test_request_context():
        assert generate_csrf_token() == generate_csrf_token()


def test_generate_force_new_rotates(app):
    with app.test_request_context():
        a = generate_csrf_token()
        b = generate_csrf_token(force_new=True)
        assert a != b and session[CSRF_SESSION_KEY] == b


def test_generate_replaces_empty_token(app):
    with app.test_request_context():
        session[CSRF_SESSION_KEY] = ''
        assert generate_csrf_token()


# --- validate_csrf_for_api --------------------------------------------------

def run(app, method, path, header=None, saved=None):
    headers = {CSRF_HEADER: header} if header is not None else {}
    with app.test_request_context(path, method=method, headers=headers):
        if saved is not None:
            session[CSRF_SESSION_KEY] = saved
        return validate_csrf_for_api()


@pytest.mark.parametrize('method', ['GET', 'HEAD', 'OPTIONS'])
def test_safe_methods_not_checked(app, method):
    assert run(app, method, '/api/v1/x') is None


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_mutating_methods_valid_token(app, method):
    assert run(app, method, '/api/v1/x', header='tok', saved='tok') is None


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_mutating_methods_missing_header(app, method):
    with pytest.raises(BadRequest) as e:
        run(app, method, '/api/v1/x', saved='tok')
    assert 'no enviado' in e.value.description


def test_wrong_token(app):
    with pytest.raises(BadRequest) as e:
        run(app, 'POST', '/api/v1/x', header='nope', saved='tok')
    assert 'inválido' in e.value.description


def test_no_session_token_expired_message(app):
    with pytest.raises(BadRequest) as e:
        run(app, 'POST', '/api/v1/x', header='tok')
    assert 'expirada' in e.value.description


def test_no_session_token_and_no_header_still_expired(app):
    with pytest.raises(BadRequest) as e:
        run(app, 'DELETE', '/api/v1/x')
    assert 'expirada' in e.value.description


def test_non_api_path_not_checked(app):
    assert run(app, 'POST', '/login') is None
    assert run(app, 'POST', '/apix/v1') is None
    assert run(app, 'POST', '/api') is None


@pytest.mark.parametrize('path', ['/api/v1/auth/login', '/api/v1/auth/register'])
def test_exempt_paths(app, path):
    assert run(app, 'POST', path) is None


def test_exempt_is_exact_match(app):
    with pytest.raises(BadRequest):
        run(app, 'POST', '/api/v1/auth/login/extra', header='x', saved='y')
    with pytest.raises(BadRequest):
        run(app, 'POST', '/api/v1/auth/logout', header='x', saved='y')


def test_token_comparison_case_sensitive(app):
    with pytest.raises(BadRequest):
        run(app, 'POST', '/api/v1/x', header='TOK', saved='tok')


def test_prefix_token_rejected(app):
    with pytest.raises(BadRequest):
        run(app, 'POST', '/api/v1/x', header='to', saved='tok')


def test_generates_token_when_missing_for_next_request(app):
    with app.test_request_context('/api/v1/x', method='POST', headers={CSRF_HEADER: 'a'}):
        with pytest.raises(BadRequest):
            validate_csrf_for_api()
        assert session.get(CSRF_SESSION_KEY)


# --- urls -------------------------------------------------------------------

def test_base_url_from_config(app):
    app.config['APP_BASE_URL'] = 'https://siiap.example.org/'
    assert get_base_url() == 'https://siiap.example.org'


def test_base_url_strips_multiple_slashes(app):
    app.config['APP_BASE_URL'] = 'https://x.org///'
    assert get_base_url() == 'https://x.org'


def test_base_url_falls_back_to_env(app, monkeypatch):
    app.config['APP_BASE_URL'] = ''
    monkeypatch.setenv('APP_BASE_URL', 'https://env.example.org/')
    assert get_base_url() == 'https://env.example.org'


def test_base_url_falls_back_to_default(app, monkeypatch):
    app.config['APP_BASE_URL'] = ''
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    assert get_base_url() == DEFAULT_BASE_URL.rstrip('/')


def test_base_url_without_app_context(monkeypatch):
    monkeypatch.setenv('APP_BASE_URL', 'https://noctx.org')
    assert get_base_url() == 'https://noctx.org'
    monkeypatch.delenv('APP_BASE_URL')
    assert get_base_url() == DEFAULT_BASE_URL.rstrip('/')


def test_external_url_uses_config_not_request_host(app):
    app.config['APP_BASE_URL'] = 'https://siiap.example.org'
    with app.test_request_context('/', base_url='http://evil.test', headers={'X-Forwarded-Host': 'evil.test'}):
        url = external_url('static', filename='css/a.css')
    assert url == 'https://siiap.example.org/static/css/a.css'


def test_external_url_without_request_context(app):
    app.config['APP_BASE_URL'] = 'https://siiap.example.org'
    assert external_url('static', filename='x.js') == 'https://siiap.example.org/static/x.js'


def test_external_url_honors_subpath(app):
    app.config['APP_BASE_URL'] = 'https://host.org/siiap'
    assert external_url('static', filename='x.js') == 'https://host.org/siiap/static/x.js'


def test_external_url_bare_host_defaults_to_http(app):
    app.config['APP_BASE_URL'] = 'example.org'
    assert external_url('static', filename='x.js') == 'http://example.org/static/x.js'


def test_external_url_unknown_endpoint_raises(app):
    from werkzeug.routing import BuildError
    with pytest.raises(BuildError):
        external_url('no.such.endpoint')

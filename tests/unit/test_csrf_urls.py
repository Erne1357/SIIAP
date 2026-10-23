"""Unit tests for app/utils/csrf.py and app/utils/urls.py."""

import pytest
from flask import session
from flask_wtf.csrf import CSRFError, validate_csrf

from app.utils.csrf import (
    CSRF_EXEMPT_VIEWS, CSRF_SESSION_KEY, csrf, csrf_error_message, generate_csrf_token,
)
from app.utils.urls import DEFAULT_BASE_URL, external_url, get_base_url


# --- generate_csrf_token ----------------------------------------------------

def test_generate_stores_raw_token_and_returns_signed_copy(app):
    with app.test_request_context():
        signed = generate_csrf_token()
        raw = session[CSRF_SESSION_KEY]
        assert raw and signed and signed != raw
        validate_csrf(signed)  # does not raise


def test_generate_is_stable_within_a_request(app):
    with app.test_request_context():
        assert generate_csrf_token() == generate_csrf_token()


def test_generate_force_new_rotates_session_token(app):
    with app.test_request_context():
        old_signed = generate_csrf_token()
        old_raw = session[CSRF_SESSION_KEY]
        new_signed = generate_csrf_token(force_new=True)
        assert session[CSRF_SESSION_KEY] != old_raw
        validate_csrf(new_signed)
        with pytest.raises(Exception):
            validate_csrf(old_signed)


def test_generate_replaces_empty_token(app):
    with app.test_request_context():
        session[CSRF_SESSION_KEY] = ''
        assert generate_csrf_token()
        assert session[CSRF_SESSION_KEY]


# --- init_csrf / messages ---------------------------------------------------

def test_tokens_do_not_expire_within_the_session(app):
    assert app.config['WTF_CSRF_TIME_LIMIT'] is None


def test_login_view_is_the_only_exemption():
    assert CSRF_EXEMPT_VIEWS == ('app.routes.api.auth_api.api_login',)
    assert set(CSRF_EXEMPT_VIEWS) <= csrf._exempt_views


@pytest.mark.parametrize('reason, fragment', [
    ('The CSRF token is missing.', 'no enviado'),
    ('The CSRF session token is missing.', 'Sesión expirada'),
    ('The CSRF token has expired.', 'Sesión expirada'),
    ('The CSRF token is invalid.', 'inválido'),
    ('The CSRF tokens do not match.', 'inválido'),
    ('The referrer header is missing.', 'origen'),
    ('The referrer does not match the host.', 'origen'),
    ('Something new in a future Flask-WTF.', 'inválido'),
])
def test_csrf_error_message_is_spanish(reason, fragment):
    assert fragment in csrf_error_message(CSRFError(reason))


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

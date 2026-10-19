"""Unit tests: app/utils/logging_config.py (request id, log filter, Sentry gate)."""

import logging

import pytest
from flask import Flask, g

from app.utils.logging_config import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    init_error_tracking,
    init_request_id,
)


@pytest.fixture
def mini_app():
    application = Flask(__name__)
    init_request_id(application)

    @application.get('/ping')
    def ping():
        return g.request_id

    return application


def test_generates_request_id_and_echoes_it(mini_app):
    resp = mini_app.test_client().get('/ping')
    rid = resp.headers[REQUEST_ID_HEADER]
    assert rid and rid == resp.get_data(as_text=True)


def test_reuses_safe_upstream_request_id(mini_app):
    resp = mini_app.test_client().get('/ping', headers={REQUEST_ID_HEADER: 'abc-123.x_Y'})
    assert resp.headers[REQUEST_ID_HEADER] == 'abc-123.x_Y'


@pytest.mark.parametrize('bad', ['a b', 'x' * 65, 'id;Injected=1','<script>'])
def test_replaces_unsafe_upstream_request_id(mini_app, bad):
    resp = mini_app.test_client().get('/ping', headers={REQUEST_ID_HEADER: bad})
    assert resp.headers[REQUEST_ID_HEADER] != bad
    assert len(resp.headers[REQUEST_ID_HEADER]) == 16


def _record():
    return logging.LogRecord('t', logging.INFO, __file__, 1, 'msg', None, None)


def test_filter_outside_request_uses_dash():
    record = _record()
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == '-'


def test_filter_inside_request_uses_current_id(mini_app):
    with mini_app.test_request_context('/'):
        g.request_id = 'req-1'
        record = _record()
        RequestIdFilter().filter(record)
    assert record.request_id == 'req-1'


def test_error_tracking_disabled_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    assert init_error_tracking(Flask(__name__)) is False


def test_error_tracking_disabled_under_testing(monkeypatch):
    monkeypatch.setenv('SENTRY_DSN', 'https://public@example.invalid/1')
    application = Flask(__name__)
    application.testing = True
    assert init_error_tracking(application) is False

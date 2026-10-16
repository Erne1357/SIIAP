"""
Fixtures shared by new tests (registered from the root conftest).

Package conftests that predate this module keep their own helpers; new tests
should use these instead of copying another `make_test_config`.
"""

import os
import time

import pytest

from app import create_app, db
from app.utils.csrf import CSRF_HEADER, CSRF_SESSION_KEY


# CI's PostgreSQL job sets this so the same tests run on the production engine
# (FK enforcement, row locks, timezone types) instead of SQLite.
TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'


def make_test_config(tmp_path, **overrides) -> dict:
    uploads = tmp_path / 'uploads'
    cfg = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': TEST_DATABASE_URL,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'CELERY_BROKER_URL': 'memory://',
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        'REDIS_URL': 'redis://127.0.0.1:1/0',
        'APP_BASE_URL': 'http://localhost.test',
        'PREFERRED_URL_SCHEME': 'http',
        'MAX_CONTENT_LENGTH': 5 * 1024 * 1024,
        'MAX_EVENT_IMAGE_BYTES': 5 * 1024 * 1024,
        'ALLOWED_IMAGE_EXT': {'jpg', 'jpeg', 'png', 'webp'},
        'ALLOWED_DOC_EXT': {'pdf', 'doc', 'docx'},
        'UPLOAD_FOLDER': uploads,
        'AVATAR_FOLDER': uploads / 'avatars',
        'USER_DOCS_FOLDER': uploads / 'documents',
        'EVENTS_FOLDER': uploads / 'events',
        'TEMPLATE_STORE': uploads / 'templates_sys',
    }
    cfg.update(overrides)
    return cfg


@pytest.fixture
def app(tmp_path):
    application = create_app(make_test_config(tmp_path))
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


class ApiClient:
    """Test client logged in as one user; sends the CSRF header on mutations."""

    def __init__(self, flask_client, csrf_token: str):
        self.raw = flask_client
        self.csrf_token = csrf_token

    def _headers(self, headers):
        merged = {CSRF_HEADER: self.csrf_token}
        merged.update(headers or {})
        return merged

    def get(self, *a, **kw):
        return self.raw.get(*a, **kw)

    def post(self, *a, headers=None, **kw):
        return self.raw.post(*a, headers=self._headers(headers), **kw)

    def put(self, *a, headers=None, **kw):
        return self.raw.put(*a, headers=self._headers(headers), **kw)

    def patch(self, *a, headers=None, **kw):
        return self.raw.patch(*a, headers=self._headers(headers), **kw)

    def delete(self, *a, headers=None, **kw):
        return self.raw.delete(*a, headers=self._headers(headers), **kw)


def login_as(flask_client, user, csrf_token: str = 'test-csrf-token') -> ApiClient:
    """Open an authenticated session for `user` without going through /login."""
    with flask_client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        sess[CSRF_SESSION_KEY] = csrf_token
        sess['last_activity'] = time.time()
    return ApiClient(flask_client, csrf_token)


@pytest.fixture
def login(app):
    """`login(user)` → ApiClient on a fresh test client logged in as `user`."""

    def _login(user):
        db.session.commit()
        return login_as(app.test_client(), user)

    return _login

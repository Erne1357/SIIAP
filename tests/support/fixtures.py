"""
Fixtures shared by new tests (registered from the root conftest).

Package conftests that predate this module keep their own helpers; new tests
should use these instead of copying another `make_test_config`.
"""

import os
import time

import pytest
from itsdangerous import URLSafeTimedSerializer

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
        # CSRFProtect stays on: login_as() hands out a real signed token.
        'WTF_CSRF_ENABLED': True,
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


_PG_SCHEMA_BUILT = False


def prepare_database() -> None:
    """
    Empty database with the full schema, ready for one test (or one module).

    SQLite :memory: is fresh per app, so create_all() is all it needs. On the
    CI PostgreSQL rebuilding 43 tables per test cost ~1.5 s each, so the schema
    is built once per process and later tests only TRUNCATE. Tables outside
    the models (a test creates alembic_version by hand) are dropped.
    """
    global _PG_SCHEMA_BUILT
    if db.engine.dialect.name == 'sqlite':
        db.create_all()
        return
    with db.engine.begin() as conn:
        if not _PG_SCHEMA_BUILT:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE')
            conn.exec_driver_sql('CREATE SCHEMA public')
        else:
            conn.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
            names = ', '.join(f'"{t.name}"' for t in db.metadata.sorted_tables)
            conn.exec_driver_sql(f'TRUNCATE {names} RESTART IDENTITY CASCADE')
    if not _PG_SCHEMA_BUILT:
        db.create_all()
        _PG_SCHEMA_BUILT = True


def release_database() -> None:
    db.session.remove()
    if db.engine.dialect.name == 'sqlite':
        db.drop_all()
    else:
        # One engine per test app: without this each test leaves its pool open
        # and PostgreSQL runs out of connections a hundred tests in.
        db.engine.dispose()


@pytest.fixture
def app(tmp_path):
    application = create_app(make_test_config(tmp_path))
    with application.app_context():
        prepare_database()
        yield application
        release_database()


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


def signed_csrf_token(flask_app, raw_token: str) -> str:
    """The value Flask-WTF expects in X-CSRFToken for session token `raw_token`."""
    serializer = URLSafeTimedSerializer(flask_app.secret_key, salt='wtf-csrf-token')
    return serializer.dumps(raw_token)


def seed_csrf(flask_client, raw_token: str = 'test-csrf-token') -> str:
    """Store `raw_token` in the client's session; return the header value for it."""
    with flask_client.session_transaction() as sess:
        sess[CSRF_SESSION_KEY] = raw_token
    return signed_csrf_token(flask_client.application, raw_token)


def login_as(flask_client, user, csrf_token: str = 'test-csrf-token') -> ApiClient:
    """Open an authenticated session for `user` without going through /login."""
    with flask_client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        sess[CSRF_SESSION_KEY] = csrf_token
        sess['last_activity'] = time.time()
    return ApiClient(flask_client, signed_csrf_token(flask_client.application, csrf_token))


@pytest.fixture
def login(app):
    """`login(user)` → ApiClient on a fresh test client logged in as `user`."""

    def _login(user):
        db.session.commit()
        return login_as(app.test_client(), user)

    return _login

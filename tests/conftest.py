"""
Root test configuration, loaded before every package conftest.

Two process-wide adjustments happen at import time, before `app` is imported
anywhere, because `app/__init__.py` builds a module-level app on import:

1. Environment defaults. Redis points at a closed loopback port so the one
   real-config app built on import fails its ping instantly instead of waiting
   on DNS for the compose host `redis`. CI overrides REDIS_URL / DATABASE_URL
   when it provides real services.
2. Cheap password hashing. Production hashes with scrypt (~100 ms by design);
   every factory user paid that, which made the suite several times slower.
   Hashes produced here are still real werkzeug hashes, so
   check_password_hash() verifies them unchanged.
"""

import os

os.environ.setdefault('REDIS_URL', 'redis://127.0.0.1:1/0')
os.environ.setdefault('CELERY_BROKER_URL', 'memory://')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'cache+memory://')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('FLASK_DEBUG', 'False')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

import werkzeug.security as _ws  # noqa: E402

_real_generate_password_hash = _ws.generate_password_hash


def _fast_generate_password_hash(password, method='pbkdf2:sha256:1000', salt_length=8):
    return _real_generate_password_hash(password, method=method, salt_length=salt_length)


_ws.generate_password_hash = _fast_generate_password_hash

pytest_plugins = ['tests.support.fixtures']

# The browser suite runs only in the Playwright container of
# docker/docker-compose.e2e.yml, which loads tests/e2e/conftest.py alone
# (--confcutdir). Here it would fail to import playwright.
collect_ignore = ['e2e']

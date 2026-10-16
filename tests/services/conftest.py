"""
Shared fixtures for the domain-service tests.

Everything that could reach the outside world is neutralised here so every test
is deterministic: Celery dispatch is recorded instead of sent, and Microsoft
Graph is replaced by a scriptable fake.
"""

from types import SimpleNamespace

import pytest

from app import db
from tests.support.factories import enroll, make_program, make_user


@pytest.fixture(autouse=True)
def celery_dispatch(monkeypatch):
    """Record `send_email_async.apply_async` calls instead of hitting a broker."""
    from app.tasks import notifications as tasks

    calls = []

    def fake_apply_async(*args, **kwargs):
        calls.append({'args': args, 'kwargs': kwargs})

    monkeypatch.setattr(tasks.send_email_async, 'apply_async', fake_apply_async)
    return calls


class FakeGraph:
    """Scriptable replacement for the Microsoft Graph helpers."""

    def __init__(self):
        self.connected = True
        self.token = 'tok'
        self.status_codes = []          # popped per send; default 202
        self.sent = []                  # (subject, to_list)
        self.raise_exc = None

    def is_connected(self):
        return self.connected

    def acquire_token_silent(self):
        return self.token

    def graph_send_mail(self, access_token, subject, content_html, to_list, save_to_sent=True):
        if self.raise_exc:
            raise self.raise_exc
        code = self.status_codes.pop(0) if self.status_codes else 202
        self.sent.append((subject, tuple(to_list)))
        return SimpleNamespace(status_code=code, text='fake-body')


@pytest.fixture
def graph(monkeypatch):
    fake = FakeGraph()
    from app.services import email_service
    from app.utils import ms_graph

    monkeypatch.setattr(email_service, 'is_connected', fake.is_connected)
    monkeypatch.setattr(email_service, 'acquire_token_silent', fake.acquire_token_silent)
    monkeypatch.setattr(email_service, 'graph_send_mail', fake.graph_send_mail)
    # The Celery tasks import `is_connected` from the module at call time.
    monkeypatch.setattr(ms_graph, 'is_connected', fake.is_connected)
    return fake


@pytest.fixture
def admission(app):
    """A coordinator, a program and one applicant enrolled `in_progress`."""
    coordinator = make_user('program_admin')
    program = make_program(coordinator)
    applicant = make_user('applicant')
    up = enroll(applicant, program, 'in_progress')
    db.session.commit()
    return SimpleNamespace(coordinator=coordinator, program=program,
                           applicant=applicant, up=up)

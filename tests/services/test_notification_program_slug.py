"""Notification e-mails link to the right program when a user holds several."""

from datetime import timedelta

from app import db
from app.models.email_queue import EmailQueue
from app.models.user_program import UserProgram
from app.services.notification_service import NotificationService as NS
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user


def _two_programs():
    user = make_user('applicant')
    old_prog, new_prog = make_program(slug='maestria-vieja'), make_program(slug='doctorado-nuevo')
    old = enroll(user, old_prog, 'enrolled')
    new = enroll(user, new_prog, 'in_progress')
    UserProgram.query.filter_by(id=old.id).update(
        {'academic_status': 'graduated', 'enrollment_date': now_local() - timedelta(days=900)})
    db.session.commit()
    return user


def _last_html(user):
    row = EmailQueue.query.filter_by(user_id=user.id).order_by(EmailQueue.id.desc()).first()
    assert row is not None
    return row.html_content


def test_default_slug_is_current_program(app):
    user = _two_programs()
    NS.notify_document_approved(user.id, 'CV', 1)
    html = _last_html(user)
    assert 'doctorado-nuevo' in html and 'maestria-vieja' not in html


def test_explicit_slug_wins(app):
    user = _two_programs()
    NS.notify_document_rejected(user.id, 'CV', 1, reason='x', program_slug='maestria-vieja')
    assert 'maestria-vieja' in _last_html(user)


def test_program_changed_accepts_slug(app):
    user = _two_programs()
    NS.notify_program_changed(user.id, 'A', 'B', program_slug='maestria-vieja')
    assert 'maestria-vieja' in _last_html(user)


def test_no_program_uses_general(app):
    user = make_user('applicant')
    db.session.commit()
    NS.notify_document_approved(user.id, 'CV', 1)
    assert '/general' in _last_html(user)

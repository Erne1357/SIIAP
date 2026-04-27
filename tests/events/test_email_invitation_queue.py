# tests/events/test_email_invitation_queue.py
"""
Tests that invite_students creates EmailQueue rows (via notify_event_invitation)
and that the broadcast (notify_event_published) does NOT enqueue emails.
"""

import unittest
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventInvitation
from app.models.email_queue import EmailQueue
from app.models.notification import Notification
from app.services.events_service import EventsService
from app.services.notification_service import NotificationService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
)


def _make_event(admin_id, prog_id=None):
    ev = Event(
        program_id=prog_id,
        type='conference',
        title='Email Queue Test',
        description='',
        location='',
        created_by=admin_id,
        visible_to_students=True,
        capacity_type='multiple',
        max_capacity=50,
        requires_registration=True,
        allows_attendance_tracking=False,
        reminders_enabled=True,
        status='published',
        visibility='private',
    )
    db.session.add(ev)
    db.session.flush()
    return ev


class TestEmailQueueOnInvitation(unittest.TestCase):
    """
    invite_students -> notify_event_invitation -> EmailService.queue_email
    should create an EmailQueue row for the invited user.
    """

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role_admin = make_role('program_admin')
        self.admin = make_user(role_admin, suffix='_adm')
        self.prog = make_program(self.admin)
        role_student = make_role('student')
        self.student = make_user(role_student, suffix='_stu')
        db.session.commit()

        self.ev = _make_event(self.admin.id)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_creates_email_queue_row(self, mock_log):
        """
        When invite_students succeeds, an EmailQueue row should exist
        for the invited user. We do NOT mock EmailService — we let the real
        notify_event_invitation run so we can verify the EmailQueue insert.

        Note: url_for for 'pages_events_public.view_event' may not be
        registered in the test app. notify_event_invitation falls back to
        '/events/{id}' when RuntimeError is raised — so this should still work.
        """
        mock_log.return_value = None

        with self.app.test_request_context('/'):
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.student.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.student.id, results['invited'],
                      "Expected student to be in 'invited' list")

        # Verify EmailQueue row exists for student
        eq = EmailQueue.query.filter_by(user_id=self.student.id).first()
        self.assertIsNotNone(eq, "Expected EmailQueue row for invited student")
        self.assertEqual(eq.status, 'pending')

    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_does_not_create_email_for_non_invited(self, mock_log):
        """Users not actually invited should get no EmailQueue row."""
        mock_log.return_value = None
        before_count = EmailQueue.query.count()
        # Send empty list
        with self.app.test_request_context('/'):
            EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[],
                invited_by=self.admin.id,
            )
        after_count = EmailQueue.query.count()
        self.assertEqual(before_count, after_count)


class TestNotifyEventPublishedNoEmailQueue(unittest.TestCase):
    """
    notify_event_published should create N Notification rows
    but NOT create EmailQueue rows (broadcast = no email).
    """

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role_student = make_role('student')
        self.s1 = make_user(role_student, suffix='_s1')
        self.s2 = make_user(role_student, suffix='_s2')
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_notify_event_published_creates_notifications(self):
        count = NotificationService.notify_event_published(
            user_ids=[self.s1.id, self.s2.id],
            event_title='Broadcast Event',
            event_id=1,
        )
        db.session.commit()
        self.assertEqual(count, 2)
        notifs = Notification.query.filter_by(type='event_published').all()
        self.assertEqual(len(notifs), 2)

    def test_notify_event_published_does_not_create_email_queue(self):
        before = EmailQueue.query.count()
        NotificationService.notify_event_published(
            user_ids=[self.s1.id, self.s2.id],
            event_title='No Email',
            event_id=2,
        )
        db.session.commit()
        after = EmailQueue.query.count()
        self.assertEqual(before, after,
                         "notify_event_published must NOT create EmailQueue rows")

    def test_notify_event_published_empty_list_returns_zero(self):
        count = NotificationService.notify_event_published(
            user_ids=[],
            event_title='Empty',
            event_id=3,
        )
        self.assertEqual(count, 0)

    def test_notify_event_published_skips_invalid_user(self):
        # user_id 99999 does not exist
        count = NotificationService.notify_event_published(
            user_ids=[99999],
            event_title='Ghost',
            event_id=4,
        )
        # Should not raise; invalid users are skipped or cause 0 successful creates
        self.assertIsInstance(count, int)

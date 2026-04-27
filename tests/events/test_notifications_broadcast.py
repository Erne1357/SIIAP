# tests/events/test_notifications_broadcast.py
"""
Tests for broadcast notifications on event creation and archival:

  - notify_event_published: creates N notifications, NO emails
  - create_event with status='published' + visible_to_students + capacity_type='multiple'
    + visibility='public' => triggers broadcast to students/applicants (excl. creator)
  - create_event with visibility='private' => NO broadcast
  - create_event with capacity_type='single' => NO broadcast
  - create_event with status='draft' => NO broadcast
  - archive_event: notify_event_archived to registered users
"""

import unittest
from unittest.mock import patch

from app import create_app, db
from app.models.event import Event, EventAttendance
from app.models.notification import Notification
from app.models.email_queue import EmailQueue
from app.services.events_service import EventsService
from app.services.notification_service import NotificationService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program, make_academic_period,
)


class TestNotifyEventPublished(unittest.TestCase):
    """Unit tests for NotificationService.notify_event_published."""

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('student')
        self.s1 = make_user(role, suffix='_s1')
        self.s2 = make_user(role, suffix='_s2')
        self.s3 = make_user(role, suffix='_s3')
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_creates_n_notifications(self):
        count = NotificationService.notify_event_published(
            user_ids=[self.s1.id, self.s2.id, self.s3.id],
            event_title='Big Conference',
            event_id=1,
        )
        db.session.commit()
        self.assertEqual(count, 3)
        notifs = Notification.query.filter_by(type='event_published').all()
        self.assertEqual(len(notifs), 3)

    def test_does_not_enqueue_emails(self):
        before = EmailQueue.query.count()
        NotificationService.notify_event_published(
            user_ids=[self.s1.id, self.s2.id],
            event_title='No Mail',
            event_id=2,
        )
        db.session.commit()
        after = EmailQueue.query.count()
        self.assertEqual(before, after)

    def test_empty_user_list_creates_zero_notifications(self):
        before = Notification.query.count()
        count = NotificationService.notify_event_published(
            user_ids=[],
            event_title='Nobody',
            event_id=3,
        )
        db.session.commit()
        self.assertEqual(count, 0)
        self.assertEqual(Notification.query.count(), before)


class TestCreateEventBroadcast(unittest.TestCase):
    """
    create_event side-effect: broadcast fires only under specific conditions.
    Uses role seeding to confirm students/applicants receive notifications.
    """

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        self.admin = make_user(self.role_admin, suffix='_adm')
        self.prog = make_program(self.admin)

        # Seed student + applicant roles and users for broadcast
        self.role_student = make_role('student')
        self.role_app = make_role('applicant')
        self.student = make_user(self.role_student, suffix='_stu')
        self.applicant = make_user(self.role_app, suffix='_app')
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_public_published_multiple_triggers_broadcast(self):
        before = Notification.query.count()
        EventsService.create_event(
            program_id=None,
            type_='conference',
            title='Broadcast',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='multiple',
            max_capacity=100,
            status='published',
            visibility='public',
            visible_to_students=True,
        )
        db.session.commit()
        after = Notification.query.filter_by(type='event_published').count()
        self.assertGreater(after, before)

    def test_broadcast_excludes_creator(self):
        EventsService.create_event(
            program_id=None,
            type_='conference',
            title='No Self Notify',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='multiple',
            max_capacity=100,
            status='published',
            visibility='public',
            visible_to_students=True,
        )
        db.session.commit()
        # Admin should have no 'event_published' notification
        admin_notifs = Notification.query.filter_by(
            user_id=self.admin.id, type='event_published'
        ).all()
        self.assertEqual(len(admin_notifs), 0)

    def test_private_event_no_broadcast(self):
        before = Notification.query.filter_by(type='event_published').count()
        EventsService.create_event(
            program_id=None,
            type_='conference',
            title='Private No Broadcast',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='multiple',
            max_capacity=100,
            status='published',
            visibility='private',  # private!
            visible_to_students=True,
        )
        db.session.commit()
        after = Notification.query.filter_by(type='event_published').count()
        self.assertEqual(before, after)

    def test_single_capacity_no_broadcast(self):
        before = Notification.query.filter_by(type='event_published').count()
        EventsService.create_event(
            program_id=None,
            type_='interview',
            title='Single No Broadcast',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='single',  # single!
            status='published',
            visibility='public',
            visible_to_students=True,
        )
        db.session.commit()
        after = Notification.query.filter_by(type='event_published').count()
        self.assertEqual(before, after)

    def test_draft_event_no_broadcast(self):
        before = Notification.query.filter_by(type='event_published').count()
        EventsService.create_event(
            program_id=None,
            type_='conference',
            title='Draft No Broadcast',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='multiple',
            max_capacity=50,
            status='draft',  # draft!
            visibility='public',
            visible_to_students=True,
        )
        db.session.commit()
        after = Notification.query.filter_by(type='event_published').count()
        self.assertEqual(before, after)

    def test_not_visible_to_students_no_broadcast(self):
        before = Notification.query.filter_by(type='event_published').count()
        EventsService.create_event(
            program_id=None,
            type_='conference',
            title='Hidden No Broadcast',
            description=None,
            location=None,
            created_by=self.admin.id,
            capacity_type='multiple',
            max_capacity=50,
            status='published',
            visibility='public',
            visible_to_students=False,  # hidden!
        )
        db.session.commit()
        after = Notification.query.filter_by(type='event_published').count()
        self.assertEqual(before, after)


class TestNotifyEventArchivedToRegistered(unittest.TestCase):
    """archive_event notifies registered attendees via notify_event_archived."""

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        self.admin = make_user(self.role_admin, suffix='_adm')
        self.prog = make_program(self.admin)
        self.role_student = make_role('student')
        self.student = make_user(self.role_student, suffix='_stu')

        self.ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='Archive Notify',
            description='',
            location='',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=50,
            requires_registration=True,
            allows_attendance_tracking=False,
            reminders_enabled=True,
            status='published',
            visibility='public',
        )
        db.session.add(self.ev)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_notifies_registered_users(self, mock_purge):
        mock_purge.return_value = {}
        att = EventAttendance(
            event_id=self.ev.id,
            user_id=self.student.id,
            status='registered',
        )
        db.session.add(att)
        db.session.commit()

        with self.app.test_request_context('/'):
            EventsService.archive_event(self.ev.id, self.admin.id)

        notif = Notification.query.filter_by(
            user_id=self.student.id, type='event_archived'
        ).first()
        self.assertIsNotNone(notif)

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_does_not_notify_non_registered(self, mock_purge):
        mock_purge.return_value = {}
        before = Notification.query.filter_by(type='event_archived').count()
        with self.app.test_request_context('/'):
            EventsService.archive_event(self.ev.id, self.admin.id)
        after = Notification.query.filter_by(type='event_archived').count()
        self.assertEqual(before, after)

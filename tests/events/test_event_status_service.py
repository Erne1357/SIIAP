# tests/events/test_event_status_service.py
"""
Unit tests for status-transition methods:
  - conclude_event
  - archive_event
  - unarchive_event
"""

import unittest
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventInvitation, EventAttendance
from app.services.events_service import EventsService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
)


def _make_full_event(admin_id, prog_id):
    ev = Event(
        program_id=prog_id,
        type='conference',
        title='Status Event',
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
        visibility='public',
    )
    db.session.add(ev)
    db.session.flush()
    return ev


class TestConcludeEvent(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('program_admin')
        self.admin = make_user(role)
        self.prog = make_program(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_conclude_sets_status_completed(self, mock_purge):
        mock_purge.return_value = {}
        ev = _make_full_event(self.admin.id, self.prog.id)
        db.session.commit()
        with self.app.test_request_context('/'):
            result = EventsService.conclude_event(ev.id, self.admin.id)
        self.assertEqual(result.status, 'completed')

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_conclude_cancels_pending_invitations(self, mock_purge):
        mock_purge.return_value = {}

        role_s = make_role('student')
        student = make_user(role_s, suffix='_stu')
        db.session.commit()

        ev = _make_full_event(self.admin.id, self.prog.id)
        inv = EventInvitation(
            event_id=ev.id,
            user_id=student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        with self.app.test_request_context('/'):
            EventsService.conclude_event(ev.id, self.admin.id)
        db.session.refresh(inv)
        self.assertEqual(inv.status, 'cancelled')

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_conclude_already_completed_raises(self, mock_purge):
        mock_purge.return_value = {}
        ev = _make_full_event(self.admin.id, self.prog.id)
        ev.status = 'completed'
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.conclude_event(ev.id, self.admin.id)

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_conclude_event_not_found_raises(self, mock_purge):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.conclude_event(99999, self.admin.id)


class TestArchiveEvent(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('program_admin')
        self.admin = make_user(role)
        self.prog = make_program(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_sets_status_archived(self, mock_purge):
        mock_purge.return_value = {}
        ev = _make_full_event(self.admin.id, self.prog.id)
        db.session.commit()
        with self.app.test_request_context('/'):
            result = EventsService.archive_event(ev.id, self.admin.id)
        self.assertEqual(result.status, 'archived')

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_already_archived_raises(self, mock_purge):
        mock_purge.return_value = {}
        ev = _make_full_event(self.admin.id, self.prog.id)
        ev.status = 'archived'
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.archive_event(ev.id, self.admin.id)

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_cancels_pending_invitations(self, mock_purge):
        mock_purge.return_value = {}
        role_s = make_role('student')
        student = make_user(role_s, suffix='_stu2')
        db.session.commit()

        ev = _make_full_event(self.admin.id, self.prog.id)
        inv = EventInvitation(
            event_id=ev.id,
            user_id=student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        with self.app.test_request_context('/'):
            EventsService.archive_event(ev.id, self.admin.id)
        db.session.refresh(inv)
        self.assertEqual(inv.status, 'cancelled')

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_event_not_found_raises(self, mock_purge):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.archive_event(99999, self.admin.id)


class TestUnarchiveEvent(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('program_admin')
        self.admin = make_user(role)
        self.prog = make_program(self.admin)
        self.ev = _make_full_event(self.admin.id, self.prog.id)
        self.ev.status = 'archived'
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_unarchive_sets_published(self):
        with self.app.test_request_context('/'):
            result = EventsService.unarchive_event(self.ev.id, self.admin.id)
        self.assertEqual(result.status, 'published')

    def test_unarchive_sets_draft(self):
        with self.app.test_request_context('/'):
            result = EventsService.unarchive_event(self.ev.id, self.admin.id, new_status='draft')
        self.assertEqual(result.status, 'draft')

    def test_unarchive_invalid_new_status_raises(self):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.unarchive_event(self.ev.id, self.admin.id, new_status='cancelled')

    def test_unarchive_non_archived_event_raises(self):
        self.ev.status = 'published'
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.unarchive_event(self.ev.id, self.admin.id)

    def test_unarchive_not_found_raises(self):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.unarchive_event(99999, self.admin.id)

# tests/events/test_invitations_service.py
"""
Unit tests for EventsService invitation methods:
  - invite_students (single, batch, already invited, already registered, wrong program)
  - respond_to_invitation (accept, reject, reconsider, cancelled)
  - cancel_invitation
  - get_my_invitations
  - get_event_invitations
"""

import unittest
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventInvitation, EventAttendance
from app.models.user_program import UserProgram
from app.services.events_service import EventsService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
)


def _make_event(admin_id, prog_id, capacity_type='multiple', max_capacity=50):
    ev = Event(
        program_id=prog_id,
        type='conference',
        title='Invitation Event',
        description='',
        location='',
        created_by=admin_id,
        visible_to_students=True,
        capacity_type=capacity_type,
        max_capacity=max_capacity,
        requires_registration=True,
        allows_attendance_tracking=False,
        reminders_enabled=True,
        status='published',
        visibility='private',
    )
    db.session.add(ev)
    db.session.flush()
    return ev


class TestInviteStudents(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role_admin = make_role('program_admin')
        self.admin = make_user(role_admin, suffix='_adm')
        self.prog = make_program(self.admin)

        role_student = make_role('student')
        self.s1 = make_user(role_student, suffix='_s1')
        self.s2 = make_user(role_student, suffix='_s2')
        db.session.commit()

        self.ev = _make_event(self.admin.id, None)  # global event
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('app.services.events_service.EventsService.get_my_invitations')
    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_single_student(self, mock_log, mock_notif, mock_get_my):
        mock_notif.return_value = MagicMock(id=1)
        with self.app.test_request_context('/'):
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.s1.id, results['invited'])

    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_already_invited_returns_already_invited(self, mock_log, mock_notif):
        mock_notif.return_value = MagicMock(id=1)
        with self.app.test_request_context('/'):
            # First invite
            EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
            # Second invite (pending status)
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.s1.id, results['already_invited'])

    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_already_registered_returns_already_registered(self, mock_log, mock_notif):
        # Register first
        att = EventAttendance(
            event_id=self.ev.id,
            user_id=self.s1.id,
            status='registered',
        )
        db.session.add(att)
        db.session.commit()

        with self.app.test_request_context('/'):
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.s1.id, results['already_registered'])

    def test_invite_to_single_event_raises(self):
        self.ev.capacity_type = 'single'
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.invite_students(
                    event_id=self.ev.id,
                    user_ids=[self.s1.id],
                    invited_by=self.admin.id,
                )

    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_invite_wrong_program_returns_wrong_program(self, mock_log, mock_notif):
        """Student not enrolled in event's program goes to wrong_program."""
        # Assign event to a specific program but don't link student to that program
        self.ev.program_id = self.prog.id
        db.session.commit()

        with self.app.test_request_context('/'):
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.s1.id, results['wrong_program'])

    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    def test_reinvite_rejected_becomes_pending(self, mock_log, mock_notif):
        mock_notif.return_value = MagicMock(id=1)
        # Seed a rejected invitation
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.s1.id,
            invited_by=self.admin.id,
            status='rejected',
        )
        db.session.add(inv)
        db.session.commit()

        with self.app.test_request_context('/'):
            results = EventsService.invite_students(
                event_id=self.ev.id,
                user_ids=[self.s1.id],
                invited_by=self.admin.id,
            )
        self.assertIn(self.s1.id, results['invited'])
        db.session.refresh(inv)
        self.assertEqual(inv.status, 'pending')

    def test_invite_nonexistent_event_raises(self):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.invite_students(
                    event_id=99999,
                    user_ids=[self.s1.id],
                    invited_by=self.admin.id,
                )


class TestRespondToInvitation(unittest.TestCase):

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

        self.ev = _make_event(self.admin.id, None)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _make_invitation(self, status='pending'):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status=status,
        )
        db.session.add(inv)
        db.session.commit()
        return inv

    def test_accept_invitation_creates_attendance(self):
        inv = self._make_invitation()
        with self.app.test_request_context('/'):
            result = EventsService.respond_to_invitation(inv.id, self.student.id, accept=True)
        self.assertEqual(result.status, 'accepted')
        att = EventAttendance.query.filter_by(
            event_id=self.ev.id, user_id=self.student.id
        ).first()
        self.assertIsNotNone(att)

    def test_reject_invitation(self):
        inv = self._make_invitation()
        with self.app.test_request_context('/'):
            result = EventsService.respond_to_invitation(inv.id, self.student.id, accept=False)
        self.assertEqual(result.status, 'rejected')

    def test_accept_already_accepted_returns_same(self):
        inv = self._make_invitation(status='accepted')
        # Pre-create attendance so register_to_event does not fail
        att = EventAttendance(
            event_id=self.ev.id,
            user_id=self.student.id,
            status='registered',
        )
        db.session.add(att)
        db.session.commit()
        with self.app.test_request_context('/'):
            result = EventsService.respond_to_invitation(inv.id, self.student.id, accept=True)
        self.assertEqual(result.status, 'accepted')

    def test_respond_to_cancelled_invitation_raises(self):
        inv = self._make_invitation(status='cancelled')
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.respond_to_invitation(inv.id, self.student.id, accept=True)

    def test_respond_wrong_user_raises(self):
        inv = self._make_invitation()
        role_other = make_role('student2')
        other = make_user(role_other, suffix='_oth')
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.respond_to_invitation(inv.id, other.id, accept=True)

    def test_respond_invitation_not_found_raises(self):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.respond_to_invitation(99999, self.student.id, accept=True)

    def test_reconsider_rejected_to_accepted(self):
        inv = self._make_invitation(status='rejected')
        with self.app.test_request_context('/'):
            result = EventsService.respond_to_invitation(inv.id, self.student.id, accept=True)
        self.assertEqual(result.status, 'accepted')


class TestCancelInvitation(unittest.TestCase):

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

        self.ev = _make_event(self.admin.id, None)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_cancel_pending_invitation(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        with self.app.test_request_context('/'):
            result = EventsService.cancel_invitation(inv.id)
        self.assertTrue(result)
        self.assertIsNone(db.session.get(EventInvitation, inv.id))

    def test_cancel_non_pending_raises(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='accepted',
        )
        db.session.add(inv)
        db.session.commit()
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.cancel_invitation(inv.id)

    def test_cancel_not_found_raises(self):
        with self.app.test_request_context('/'):
            with self.assertRaises(ValueError):
                EventsService.cancel_invitation(99999)


class TestGetMyInvitations(unittest.TestCase):

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

        self.ev = _make_event(self.admin.id, None)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_get_my_invitations_returns_only_pending(self):
        pending = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        accepted = EventInvitation(
            event_id=self.ev.id,
            user_id=self.admin.id,  # different user
            invited_by=self.admin.id,
            status='accepted',
        )
        db.session.add_all([pending, accepted])
        db.session.commit()

        result = EventsService.get_my_invitations(self.student.id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['invitation_id'], pending.id)

    def test_get_my_invitations_empty(self):
        result = EventsService.get_my_invitations(self.student.id)
        self.assertEqual(result, [])

    def test_get_event_invitations(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        result = EventsService.get_event_invitations(self.ev.id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['user_id'], self.student.id)

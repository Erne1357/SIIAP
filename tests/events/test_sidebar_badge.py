# tests/events/test_sidebar_badge.py
"""
Tests for the sidebar badge / counter endpoints:

  GET  /api/v1/invitations/my-invitations  — total counts only pending
  POST /api/v1/invitations/<id>/respond    — pending count decreases after respond
  GET  /api/v1/events/new-count            — returns correct count
  POST /api/v1/events/mark-seen           — resets count
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventInvitation, EventAttendance
from app.services.events_service import EventsService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
    make_academic_period, grant_permission, login, inject_csrf,
)


def _future(days=5):
    return datetime.now() + timedelta(days=days)


def _past(days=5):
    return datetime.now() - timedelta(days=days)


class TestSidebarBadge(unittest.TestCase):

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
        self.period = make_academic_period(is_active=True)
        db.session.commit()

        self.ev = Event(
            program_id=None,
            type='conference',
            title='Badge Test Event',
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
            visibility='private',
            academic_period_id=self.period.id,
        )
        db.session.add(self.ev)
        db.session.commit()

        self.client = self.app.test_client()
        self.csrf = login(self.client, self.student)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ------------------------------------------------------------------
    # /my-invitations — only pending counts
    # ------------------------------------------------------------------

    def test_my_invitations_counts_only_pending(self):
        """GET /my-invitations total = only pending invitations."""
        pending = EventInvitation(
            event_id=self.ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        accepted = EventInvitation(
            event_id=self.ev.id, user_id=self.admin.id,
            invited_by=self.admin.id, status='accepted',
        )
        db.session.add_all([pending, accepted])
        db.session.commit()

        resp = self.client.get('/api/v1/invitations/my-invitations')
        data = json.loads(resp.data)
        # student only has 1 pending invitation
        self.assertEqual(data['total'], 1)

    def test_my_invitations_total_zero_when_no_pending(self):
        # Seed accepted invitation only
        inv = EventInvitation(
            event_id=self.ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='accepted',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self.client.get('/api/v1/invitations/my-invitations')
        data = json.loads(resp.data)
        self.assertEqual(data['total'], 0)

    # ------------------------------------------------------------------
    # pending count decreases after respond
    # ------------------------------------------------------------------

    def test_pending_count_decreases_after_accept(self):
        inv = EventInvitation(
            event_id=self.ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        # Before respond
        resp = self.client.get('/api/v1/invitations/my-invitations')
        before = json.loads(resp.data)['total']
        self.assertEqual(before, 1)

        # Respond (accept)
        self.client.post(
            f'/api/v1/invitations/{inv.id}/respond',
            data=json.dumps({'accept': True}),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )

        # After respond
        resp = self.client.get('/api/v1/invitations/my-invitations')
        after = json.loads(resp.data)['total']
        self.assertEqual(after, 0)

    def test_pending_count_decreases_after_reject(self):
        inv = EventInvitation(
            event_id=self.ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        self.client.post(
            f'/api/v1/invitations/{inv.id}/respond',
            data=json.dumps({'accept': False}),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )

        resp = self.client.get('/api/v1/invitations/my-invitations')
        after = json.loads(resp.data)['total']
        self.assertEqual(after, 0)

    def test_multiple_pending_correct_count(self):
        """Add two events, both pending."""
        ev2 = Event(
            program_id=None,
            type='seminar',
            title='Second Event',
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
            visibility='private',
            academic_period_id=self.period.id,
        )
        db.session.add(ev2)
        db.session.flush()

        inv1 = EventInvitation(
            event_id=self.ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        inv2 = EventInvitation(
            event_id=ev2.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        db.session.add_all([inv1, inv2])
        db.session.commit()

        resp = self.client.get('/api/v1/invitations/my-invitations')
        data = json.loads(resp.data)
        self.assertEqual(data['total'], 2)

    # ------------------------------------------------------------------
    # /events/new-count and /events/mark-seen
    # ------------------------------------------------------------------

    def test_new_count_returns_integer(self):
        resp = self.client.get('/api/v1/events/new-count')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIsInstance(data['data']['count'], int)

    def test_new_count_zero_before_any_events(self):
        # Mark seen first to reset threshold
        self.client.post(
            '/api/v1/events/mark-seen',
            data=json.dumps({}),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )
        resp = self.client.get('/api/v1/events/new-count')
        data = json.loads(resp.data)
        self.assertEqual(data['data']['count'], 0)

    def test_mark_seen_returns_ok(self):
        resp = self.client.post(
            '/api/v1/events/mark-seen',
            data=json.dumps({}),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['data']['ok'])

    def test_mark_seen_resets_count(self):
        # Mark seen now
        self.client.post(
            '/api/v1/events/mark-seen',
            data=json.dumps({}),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )
        # Count should be 0 (no new events after mark-seen)
        resp = self.client.get('/api/v1/events/new-count')
        data = json.loads(resp.data)
        self.assertEqual(data['data']['count'], 0)

    def test_mark_seen_unauthenticated_redirects(self):
        anon = self.app.test_client()
        resp = anon.post(
            '/api/v1/events/mark-seen',
            data=json.dumps({}),
            content_type='application/json',
            headers={'X-CSRFToken': 'test'},
        )
        # 400 is also valid: CSRF before_request fires before @login_required
        # when no valid session exists (no _csrf_token in session)
        self.assertIn(resp.status_code, (400, 401, 302, 403))

    def test_new_count_service_direct(self):
        """Direct service test: count_new_events returns correct value after mark_seen."""
        # Create a public multiple event
        ev = Event(
            program_id=None,
            type='conference',
            title='Count Me',
            description='',
            location='',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=100,
            requires_registration=False,
            allows_attendance_tracking=False,
            reminders_enabled=False,
            status='published',
            visibility='public',
            academic_period_id=self.period.id,
        )
        db.session.add(ev)
        db.session.commit()

        # Mark seen after the event exists
        EventsService.mark_events_seen(self.student.id)

        # No new events after mark_seen
        count = EventsService.count_new_events(self.student.id)
        self.assertEqual(count, 0)

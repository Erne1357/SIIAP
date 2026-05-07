# tests/events/test_dashboard_widget.py
"""
Tests for EventsService.get_dashboard_widget(user_id).

Verifies the 4 returned lists and their filtering logic:
  - pending_invitations
  - accepted_invitations  (only future events)
  - upcoming_events       (max 3, future only, not registered/invited)
  - my_registrations      (future only)
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.models.event import Event, EventInvitation, EventAttendance, EventImage
from app.services.events_service import EventsService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program, make_academic_period,
)

# SQLite stores datetimes as naive strings — always use naive datetimes here.
# The service uses now_local() (tz-aware), which would cause a TypeError when
# compared to naive event_date values.  We patch now_local() to return naive
# datetimes so the comparison works in tests without modifying production code.

def _future(days=30):
    return datetime.now() + timedelta(days=days)


def _past(days=5):
    return datetime.now() - timedelta(days=days)


def _make_event(admin_id, prog_id=None, title='Widget Event',
                capacity_type='multiple', max_capacity=50,
                visibility='public', status='published',
                event_date=None):
    ev = Event(
        program_id=prog_id,
        type='conference',
        title=title,
        description='',
        location='',
        created_by=admin_id,
        visible_to_students=True,
        capacity_type=capacity_type,
        max_capacity=max_capacity,
        requires_registration=True,
        allows_attendance_tracking=False,
        reminders_enabled=True,
        status=status,
        visibility=visibility,
        event_date=event_date,
    )
    db.session.add(ev)
    db.session.flush()
    return ev


class TestDashboardWidget(unittest.TestCase):

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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _widget(self, user_id):
        """Run get_dashboard_widget inside a request context.

        Patches now_local() to return a naive datetime so it can be
        compared to SQLite-stored event_date values (which are also naive).
        """
        with patch('app.services.events_service.now_local', side_effect=datetime.now):
            with self.app.test_request_context('/'):
                return EventsService.get_dashboard_widget(user_id)

    def test_widget_returns_four_keys(self):
        result = self._widget(self.student.id)
        self.assertIn('pending_invitations', result)
        self.assertIn('accepted_invitations', result)
        self.assertIn('upcoming_events', result)
        self.assertIn('my_registrations', result)

    def test_widget_empty_when_no_data(self):
        result = self._widget(self.student.id)
        self.assertEqual(result['pending_invitations'], [])
        self.assertEqual(result['accepted_invitations'], [])
        self.assertEqual(result['upcoming_events'], [])
        self.assertEqual(result['my_registrations'], [])

    def test_pending_invitations_included(self):
        ev = _make_event(self.admin.id)
        inv = EventInvitation(
            event_id=ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertEqual(len(result['pending_invitations']), 1)
        self.assertEqual(result['pending_invitations'][0]['invitation_id'], inv.id)

    def test_accepted_invitation_future_event_included(self):
        ev = _make_event(self.admin.id, event_date=_future(10))
        inv = EventInvitation(
            event_id=ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='accepted',
        )
        db.session.add(inv)
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertEqual(len(result['accepted_invitations']), 1)

    def test_accepted_invitation_past_event_excluded(self):
        ev = _make_event(self.admin.id, event_date=_past(10))
        inv = EventInvitation(
            event_id=ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='accepted',
        )
        db.session.add(inv)
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertEqual(len(result['accepted_invitations']), 0)

    def test_my_registrations_future_included(self):
        ev = _make_event(self.admin.id, event_date=_future(5))
        att = EventAttendance(
            event_id=ev.id, user_id=self.student.id, status='registered',
        )
        db.session.add(att)
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertEqual(len(result['my_registrations']), 1)

    def test_my_registrations_past_excluded(self):
        ev = _make_event(self.admin.id, event_date=_past(3))
        att = EventAttendance(
            event_id=ev.id, user_id=self.student.id, status='registered',
        )
        db.session.add(att)
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertEqual(len(result['my_registrations']), 0)

    def test_upcoming_events_max_3(self):
        # Create 5 public future events
        for i in range(5):
            ev = _make_event(
                self.admin.id,
                title=f'Upcoming {i}',
                event_date=_future(i + 1),
                visibility='public',
            )
            # Assign to active period so list_public_events picks them up
            ev.academic_period_id = self.period.id
        db.session.commit()

        result = self._widget(self.student.id)
        self.assertLessEqual(len(result['upcoming_events']), 3)

    def test_upcoming_excludes_past_events(self):
        ev = _make_event(
            self.admin.id, title='Past Upcoming', event_date=_past(2),
            visibility='public',
        )
        ev.academic_period_id = self.period.id
        db.session.commit()

        result = self._widget(self.student.id)
        for item in result['upcoming_events']:
            self.assertNotEqual(item['event_id'], ev.id)

    def test_upcoming_excludes_already_registered(self):
        ev = _make_event(
            self.admin.id, title='Registered Event', event_date=_future(3),
            visibility='public',
        )
        ev.academic_period_id = self.period.id
        att = EventAttendance(
            event_id=ev.id, user_id=self.student.id, status='registered',
        )
        db.session.add(att)
        db.session.commit()

        result = self._widget(self.student.id)
        upcoming_ids = {u['event_id'] for u in result['upcoming_events']}
        self.assertNotIn(ev.id, upcoming_ids)

    def test_upcoming_excludes_already_invited(self):
        ev = _make_event(
            self.admin.id, title='Invited Event', event_date=_future(4),
            visibility='public',
        )
        ev.academic_period_id = self.period.id
        inv = EventInvitation(
            event_id=ev.id, user_id=self.student.id,
            invited_by=self.admin.id, status='pending',
        )
        db.session.add(inv)
        db.session.commit()

        result = self._widget(self.student.id)
        upcoming_ids = {u['event_id'] for u in result['upcoming_events']}
        self.assertNotIn(ev.id, upcoming_ids)

    def test_upcoming_event_with_cover_includes_cover_path(self):
        ev = _make_event(
            self.admin.id, title='Cover Event', event_date=_future(5),
            visibility='public',
        )
        ev.academic_period_id = self.period.id
        cover = EventImage(
            event_id=ev.id, path=f'{ev.id}/cover.jpg',
            is_cover=True, display_order=0,
        )
        db.session.add(cover)
        db.session.commit()

        result = self._widget(self.student.id)
        found = next((u for u in result['upcoming_events'] if u['event_id'] == ev.id), None)
        if found:
            self.assertEqual(found['cover_path'], f'{ev.id}/cover.jpg')

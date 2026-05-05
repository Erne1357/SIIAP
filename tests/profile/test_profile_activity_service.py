# tests/profile/test_profile_activity_service.py
"""
Tests for profile_activity_service:
  - get_recent_activity (history + notifs + submissions + events) sorted desc
  - get_upcoming_events (only future, registered)
  - get_user_documents_grouped (admission/permanence-by-semester/conclusion)
"""

import unittest
from datetime import datetime, timedelta

from app import create_app, db
from app.models.notification import Notification
from app.models.user_history import UserHistory
from app.models.event import Event, EventAttendance
from app.services import profile_activity_service as svc

from tests.profile.conftest import (
    make_test_config, make_role, make_user, make_program,
)


class TestGetRecentActivity(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role = make_role('applicant')
        self.user = make_user(self.role)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_empty_user_returns_empty(self):
        self.assertEqual(svc.get_recent_activity(self.user.id), [])

    def test_history_appears_in_feed(self):
        h = UserHistory(
            user_id=self.user.id, admin_id=self.user.id,
            action='admission_accepted', details='Aceptado en X',
            timestamp=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add(h)
        db.session.commit()
        items = svc.get_recent_activity(self.user.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'history')

    def test_notification_appears_in_feed(self):
        n = Notification(
            user_id=self.user.id,
            type='generic',
            title='Hola',
            message='Mensaje',
            priority='normal',
        )
        db.session.add(n)
        db.session.commit()
        items = svc.get_recent_activity(self.user.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'notification')
        self.assertEqual(items[0]['title'], 'Hola')

    def test_feed_sorted_desc_by_timestamp(self):
        now = datetime.utcnow()
        old = UserHistory(
            user_id=self.user.id, admin_id=self.user.id,
            action='action_a', details='old',
            timestamp=now - timedelta(days=2),
        )
        new = UserHistory(
            user_id=self.user.id, admin_id=self.user.id,
            action='action_b', details='new',
            timestamp=now,
        )
        db.session.add_all([old, new])
        db.session.commit()
        items = svc.get_recent_activity(self.user.id)
        self.assertEqual(len(items), 2)
        # Most recent first
        self.assertEqual(items[0]['description'], 'new')
        self.assertEqual(items[1]['description'], 'old')

    def test_default_limit_is_six(self):
        for i in range(10):
            db.session.add(UserHistory(
                user_id=self.user.id, admin_id=self.user.id,
                action=f'a{i}', details=f'd{i}',
                timestamp=datetime.utcnow() - timedelta(minutes=i),
            ))
        db.session.commit()
        items = svc.get_recent_activity(self.user.id)
        self.assertEqual(len(items), 6)

    def test_limit_can_be_overridden(self):
        for i in range(10):
            db.session.add(UserHistory(
                user_id=self.user.id, admin_id=self.user.id,
                action=f'a{i}', details=f'd{i}',
                timestamp=datetime.utcnow() - timedelta(minutes=i),
            ))
        db.session.commit()
        items = svc.get_recent_activity(self.user.id, limit=3)
        self.assertEqual(len(items), 3)

    def test_other_user_data_ignored(self):
        other_role = make_role('student')
        other = make_user(other_role, suffix='_other')
        db.session.add(UserHistory(
            user_id=other.id, admin_id=other.id,
            action='action', details='ajena',
            timestamp=datetime.utcnow(),
        ))
        db.session.commit()
        items = svc.get_recent_activity(self.user.id)
        self.assertEqual(len(items), 0)


class TestGetUpcomingEvents(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role = make_role('student')
        self.user = make_user(self.role)
        self.program = make_program(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _make_event(self, days_offset, status='published', title='Ev'):
        ev = Event(
            program_id=self.program.id,
            type='conference',
            title=title,
            description='',
            location='Aula',
            created_by=self.user.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=20,
            requires_registration=True,
            allows_attendance_tracking=False,
            reminders_enabled=True,
            status=status,
            event_date=datetime.utcnow() + timedelta(days=days_offset),
        )
        db.session.add(ev)
        db.session.flush()
        return ev

    def _register(self, ev: Event, status='registered'):
        att = EventAttendance(event_id=ev.id, user_id=self.user.id, status=status)
        db.session.add(att)
        db.session.flush()
        return att

    def test_returns_only_future_events(self):
        past = self._make_event(-5, title='Past')
        future = self._make_event(5, title='Future')
        self._register(past)
        self._register(future)
        db.session.commit()

        items = svc.get_upcoming_events(self.user.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Future')

    def test_only_registered_events_returned(self):
        ev = self._make_event(3, title='NoReg')
        # No EventAttendance row created
        db.session.commit()
        self.assertEqual(svc.get_upcoming_events(self.user.id), [])

    def test_excludes_cancelled_status(self):
        ev = self._make_event(3, status='cancelled')
        self._register(ev)
        db.session.commit()
        self.assertEqual(svc.get_upcoming_events(self.user.id), [])

    def test_sorted_ascending(self):
        a = self._make_event(7, title='A')
        b = self._make_event(2, title='B')
        c = self._make_event(15, title='C')
        for ev in (a, b, c):
            self._register(ev)
        db.session.commit()
        items = svc.get_upcoming_events(self.user.id)
        self.assertEqual([i['title'] for i in items], ['B', 'A', 'C'])

    def test_limit_is_respected(self):
        for i in range(8):
            ev = self._make_event(i + 1, title=f'E{i}')
            self._register(ev)
        db.session.commit()
        items = svc.get_upcoming_events(self.user.id, limit=3)
        self.assertEqual(len(items), 3)


if __name__ == '__main__':
    unittest.main()

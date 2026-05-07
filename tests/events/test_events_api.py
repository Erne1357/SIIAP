# tests/events/test_events_api.py
"""
Integration tests for /api/v1/events (admin-facing endpoints):
  POST   /api/v1/events
  GET    /api/v1/events
  GET    /api/v1/events/<id>
  PUT    /api/v1/events/<id>
  DELETE /api/v1/events/<id>
  POST   /api/v1/events/<id>/windows
  POST   /api/v1/events/windows/<wid>/generate-slots
  GET    /api/v1/events/<id>/slots
  GET    /api/v1/events/<id>/windows-list
  DELETE /api/v1/events/windows/<wid>
  DELETE /api/v1/events/slots/<sid>
  POST   /api/v1/events/<id>/conclude
  POST   /api/v1/events/<id>/archive
  POST   /api/v1/events/<id>/unarchive
  GET    /api/v1/events/new-count
  POST   /api/v1/events/mark-seen
"""

import json
import unittest
from unittest.mock import patch

from app import create_app, db
from app.models.event import Event, EventWindow, EventSlot
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
    grant_permission, login, inject_csrf,
)


class TestEventsApiBase(unittest.TestCase):
    """Base class for events API tests with common setUp/tearDown."""

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        for perm in (
            'events.api.create', 'events.api.list', 'events.api.manage',
            'events.api.create_window', 'events.api.generate_slots',
            'events.api.conclude', 'events.api.archive',
            'events.api.manage_hosts', 'events.api.manage_images',
        ):
            grant_permission(self.role_admin, perm)

        self.admin = make_user(self.role_admin)
        self.prog = make_program(self.admin)
        db.session.commit()

        self.client = self.app.test_client()
        self.csrf_token = login(self.client, self.admin)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _post(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf_token},
        )

    def _put(self, url, data):
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf_token},
        )

    def _delete(self, url):
        return self.client.delete(
            url,
            headers={'X-CSRFToken': self.csrf_token},
        )

    def _make_event(self, capacity_type='multiple', max_capacity=50,
                    status='published', visibility='public'):
        ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='API Test Event',
            description='Desc',
            location='Room B',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type=capacity_type,
            max_capacity=max_capacity,
            requires_registration=True,
            allows_attendance_tracking=False,
            reminders_enabled=True,
            status=status,
            visibility=visibility,
        )
        db.session.add(ev)
        db.session.commit()
        return ev


class TestCreateEvent(TestEventsApiBase):

    def test_create_event_success(self):
        resp = self._post('/api/v1/events', {
            'title': 'New Conference',
            'type': 'conference',
            'capacity_type': 'multiple',
            'max_capacity': 30,
            'program_id': self.prog.id,
        })
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertIn('id', data)

    def test_create_event_requires_login(self):
        anon = self.app.test_client()
        resp = anon.post(
            '/api/v1/events',
            data=json.dumps({'title': 'Anon'}),
            content_type='application/json',
            headers={'X-CSRFToken': 'none'},
        )
        # 400 is also valid: CSRF before_request fires before @login_required
        self.assertIn(resp.status_code, (400, 401, 302, 403))

    def test_create_event_requires_permission(self):
        # Create user without permission
        role2 = make_role('applicant')
        u2 = make_user(role2, suffix='_app')
        db.session.commit()
        client2 = self.app.test_client()
        csrf2 = login(client2, u2)
        resp = client2.post(
            '/api/v1/events',
            data=json.dumps({'title': 'No perm'}),
            content_type='application/json',
            headers={'X-CSRFToken': csrf2},
        )
        self.assertEqual(resp.status_code, 403)


class TestListEvents(TestEventsApiBase):

    def test_list_events_returns_items(self):
        self._make_event()
        resp = self.client.get('/api/v1/events')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertIn('items', data)
        self.assertGreater(len(data['items']), 0)

    def test_list_events_empty(self):
        resp = self.client.get('/api/v1/events')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['items'], [])


class TestGetEventDetails(TestEventsApiBase):

    def test_get_event_details_success(self):
        ev = self._make_event()
        resp = self.client.get(f'/api/v1/events/{ev.id}')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['id'], ev.id)

    def test_get_event_not_found(self):
        resp = self.client.get('/api/v1/events/99999')
        self.assertEqual(resp.status_code, 404)


class TestUpdateEvent(TestEventsApiBase):

    def test_update_event_title(self):
        ev = self._make_event()
        resp = self._put(f'/api/v1/events/{ev.id}', {'title': 'Updated Title'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])

    def test_update_event_not_found(self):
        resp = self._put('/api/v1/events/99999', {'title': 'Ghost'})
        self.assertEqual(resp.status_code, 404)


class TestDeleteEvent(TestEventsApiBase):

    def test_delete_event_success(self):
        ev = self._make_event()
        resp = self._delete(f'/api/v1/events/{ev.id}')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertIsNone(db.session.get(Event, ev.id))

    def test_delete_event_not_found(self):
        resp = self._delete('/api/v1/events/99999')
        self.assertEqual(resp.status_code, 404)


class TestWindowsAndSlots(TestEventsApiBase):

    def test_add_window_success(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        resp = self._post(f'/api/v1/events/{ev.id}/windows', {
            'date': '2030-06-15',
            'start_time': '09:00:00',
            'end_time': '12:00:00',
            'slot_minutes': 30,
        })
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])

    def test_generate_slots_success(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        win = EventWindow(
            event_id=ev.id,
            date=__import__('datetime').date(2030, 6, 15),
            start_time=__import__('datetime').time(9, 0),
            end_time=__import__('datetime').time(10, 0),
            slot_minutes=30,
        )
        db.session.add(win)
        db.session.commit()
        resp = self._post(f'/api/v1/events/windows/{win.id}/generate-slots', {})
        self.assertEqual(resp.status_code, 201)

    def test_list_slots_success(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        resp = self.client.get(f'/api/v1/events/{ev.id}/slots')
        self.assertEqual(resp.status_code, 200)

    def test_windows_list_success(self):
        ev = self._make_event()
        resp = self.client.get(f'/api/v1/events/{ev.id}/windows-list')
        self.assertEqual(resp.status_code, 200)

    def test_delete_window_success(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        win = EventWindow(
            event_id=ev.id,
            date=__import__('datetime').date(2030, 7, 1),
            start_time=__import__('datetime').time(9, 0),
            end_time=__import__('datetime').time(10, 0),
            slot_minutes=30,
        )
        db.session.add(win)
        db.session.commit()
        resp = self._delete(f'/api/v1/events/windows/{win.id}')
        self.assertEqual(resp.status_code, 200)

    def test_delete_slot_success(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        from datetime import datetime, timedelta
        win = EventWindow(
            event_id=ev.id,
            date=__import__('datetime').date(2030, 8, 1),
            start_time=__import__('datetime').time(9, 0),
            end_time=__import__('datetime').time(10, 0),
            slot_minutes=30,
        )
        db.session.add(win)
        db.session.flush()
        slot = EventSlot(
            event_window_id=win.id,
            starts_at=datetime(2030, 8, 1, 9, 0),
            ends_at=datetime(2030, 8, 1, 9, 30),
            status='free',
        )
        db.session.add(slot)
        db.session.commit()
        resp = self._delete(f'/api/v1/events/slots/{slot.id}')
        self.assertEqual(resp.status_code, 200)


class TestStatusTransitions(TestEventsApiBase):

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_conclude_event(self, mock_purge):
        mock_purge.return_value = {}
        ev = self._make_event()
        resp = self._post(f'/api/v1/events/{ev.id}/conclude', {})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'completed')

    @patch('app.services.events_service.EventsService.purge_event_media')
    def test_archive_event(self, mock_purge):
        mock_purge.return_value = {}
        ev = self._make_event()
        resp = self._post(f'/api/v1/events/{ev.id}/archive', {})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'archived')

    def test_unarchive_event(self):
        ev = self._make_event(status='archived')
        resp = self._post(f'/api/v1/events/{ev.id}/unarchive', {'new_status': 'published'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'published')


class TestNewCountAndMarkSeen(TestEventsApiBase):

    def test_new_count_returns_count(self):
        resp = self.client.get('/api/v1/events/new-count')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('count', data['data'])

    def test_mark_seen_success(self):
        resp = self._post('/api/v1/events/mark-seen', {})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['data']['ok'])

    def test_new_count_unauthenticated(self):
        anon = self.app.test_client()
        resp = anon.get('/api/v1/events/new-count')
        self.assertIn(resp.status_code, (401, 302, 403))

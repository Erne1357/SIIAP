# tests/events/test_event_model.py
"""
Unit tests for the Event, EventWindow, EventSlot, EventAttendance, EventInvitation,
EventHost, EventImage models.
"""

import unittest
from datetime import date, time, datetime, timedelta

from app import create_app, db
from app.models.event import (
    Event, EventWindow, EventSlot, EventAttendance, EventInvitation,
    EventHost, EventImage,
)
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
)


class TestEventModel(unittest.TestCase):

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

    def _make_event(self, **kwargs):
        defaults = dict(
            program_id=self.prog.id,
            type='conference',
            title='Sample Event',
            description='Desc',
            location='Room A',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=30,
            requires_registration=True,
            allows_attendance_tracking=False,
            reminders_enabled=True,
            status='published',
            visibility='public',
        )
        defaults.update(kwargs)
        ev = Event(**defaults)
        db.session.add(ev)
        db.session.commit()
        return ev

    def test_create_event_persists(self):
        ev = self._make_event()
        self.assertIsNotNone(ev.id)
        loaded = db.session.get(Event, ev.id)
        self.assertEqual(loaded.title, 'Sample Event')

    def test_to_dict_contains_required_keys(self):
        ev = self._make_event()
        d = ev.to_dict()
        for key in ('id', 'title', 'status', 'visibility', 'capacity_type',
                    'created_by', 'visible_to_students', 'reminders_enabled'):
            self.assertIn(key, d)

    def test_event_status_values(self):
        for s in ('draft', 'published', 'ongoing', 'completed', 'cancelled', 'archived'):
            ev = self._make_event(title=f'Event {s}', status=s)
            self.assertEqual(ev.status, s)

    def test_event_visibility_values(self):
        for v in ('public', 'private'):
            ev = self._make_event(title=f'Vis {v}', visibility=v)
            self.assertEqual(ev.visibility, v)

    def test_event_capacity_type_unlimited(self):
        ev = self._make_event(capacity_type='unlimited', max_capacity=None)
        self.assertEqual(ev.capacity_type, 'unlimited')
        self.assertIsNone(ev.max_capacity)

    def test_event_capacity_type_single(self):
        ev = self._make_event(capacity_type='single', max_capacity=None)
        self.assertEqual(ev.capacity_type, 'single')

    def test_event_created_at_set_automatically(self):
        ev = self._make_event()
        self.assertIsNotNone(ev.created_at)

    def test_event_window_cascade_delete(self):
        ev = self._make_event()
        win = EventWindow(
            event_id=ev.id,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_minutes=30,
        )
        db.session.add(win)
        db.session.commit()
        win_id = win.id

        db.session.delete(ev)
        db.session.commit()
        self.assertIsNone(db.session.get(EventWindow, win_id))

    def test_event_slot_cascade_delete_via_window(self):
        ev = self._make_event()
        win = EventWindow(
            event_id=ev.id,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_minutes=30,
        )
        db.session.add(win)
        db.session.flush()
        slot = EventSlot(
            event_window_id=win.id,
            starts_at=datetime.now(),
            ends_at=datetime.now() + timedelta(minutes=30),
            status='free',
        )
        db.session.add(slot)
        db.session.commit()
        slot_id = slot.id

        db.session.delete(win)
        db.session.commit()
        self.assertIsNone(db.session.get(EventSlot, slot_id))

    def test_event_attendance_to_dict(self):
        ev = self._make_event()
        att = EventAttendance(
            event_id=ev.id,
            user_id=self.admin.id,
            status='registered',
        )
        db.session.add(att)
        db.session.commit()
        d = att.to_dict()
        self.assertEqual(d['event_id'], ev.id)
        self.assertEqual(d['status'], 'registered')

    def test_event_invitation_to_dict(self):
        ev = self._make_event()
        inv = EventInvitation(
            event_id=ev.id,
            user_id=self.admin.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        d = inv.to_dict()
        self.assertEqual(d['status'], 'pending')
        self.assertEqual(d['event_id'], ev.id)

    def test_event_no_program_allowed(self):
        ev = self._make_event(program_id=None)
        self.assertIsNone(ev.program_id)


class TestEventHostModel(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('program_admin')
        self.admin = make_user(role)
        self.prog = make_program(self.admin)
        self.ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='Host Test',
            description='',
            location='',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=10,
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

    def test_internal_host_created(self):
        host = EventHost(
            event_id=self.ev.id,
            user_id=self.admin.id,
            role_label='Ponente',
            display_order=0,
        )
        db.session.add(host)
        db.session.commit()
        self.assertIsNotNone(host.id)
        self.assertEqual(host.user_id, self.admin.id)

    def test_external_host_created(self):
        host = EventHost(
            event_id=self.ev.id,
            external_name='Dr. Externo',
            external_bio='Bio externa',
            role_label='Invitado',
            display_order=1,
        )
        db.session.add(host)
        db.session.commit()
        self.assertIsNotNone(host.id)
        self.assertIsNone(host.user_id)
        self.assertEqual(host.external_name, 'Dr. Externo')

    def test_host_to_dict(self):
        host = EventHost(
            event_id=self.ev.id,
            user_id=self.admin.id,
            role_label='Moderador',
            display_order=0,
        )
        db.session.add(host)
        db.session.commit()
        d = host.to_dict()
        self.assertIn('id', d)
        self.assertIn('role_label', d)
        self.assertEqual(d['role_label'], 'Moderador')

    def test_host_cascade_delete_with_event(self):
        host = EventHost(
            event_id=self.ev.id,
            user_id=self.admin.id,
            role_label='Ponente',
            display_order=0,
        )
        db.session.add(host)
        db.session.commit()
        hid = host.id
        db.session.delete(self.ev)
        db.session.commit()
        self.assertIsNone(db.session.get(EventHost, hid))


class TestEventImageModel(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        role = make_role('program_admin')
        self.admin = make_user(role)
        self.prog = make_program(self.admin)
        self.ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='Image Test',
            description='',
            location='',
            created_by=self.admin.id,
            visible_to_students=True,
            capacity_type='multiple',
            max_capacity=10,
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

    def test_cover_image_created(self):
        img = EventImage(
            event_id=self.ev.id,
            path='1/cover.jpg',
            is_cover=True,
            display_order=0,
        )
        db.session.add(img)
        db.session.commit()
        self.assertTrue(img.is_cover)

    def test_gallery_image_created(self):
        img = EventImage(
            event_id=self.ev.id,
            path='1/gallery/abc.jpg',
            is_cover=False,
            display_order=1,
        )
        db.session.add(img)
        db.session.commit()
        self.assertFalse(img.is_cover)

    def test_image_to_dict(self):
        img = EventImage(
            event_id=self.ev.id,
            path='1/cover.png',
            is_cover=True,
            display_order=0,
        )
        db.session.add(img)
        db.session.commit()
        d = img.to_dict()
        self.assertIn('path', d)
        self.assertIn('is_cover', d)
        self.assertTrue(d['is_cover'])

    def test_image_cascade_delete_with_event(self):
        img = EventImage(
            event_id=self.ev.id,
            path='1/cover.jpg',
            is_cover=True,
            display_order=0,
        )
        db.session.add(img)
        db.session.commit()
        iid = img.id
        db.session.delete(self.ev)
        db.session.commit()
        self.assertIsNone(db.session.get(EventImage, iid))

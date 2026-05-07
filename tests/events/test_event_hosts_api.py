# tests/events/test_event_hosts_api.py
"""
Integration tests for event host endpoints:
  GET  /api/v1/events/<id>/hosts
  PUT  /api/v1/events/<id>/hosts
  POST /api/v1/events/<id>/hosts/photo
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
    grant_permission, login, inject_csrf,
)


class TestEventHostsApi(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        grant_permission(self.role_admin, 'events.api.manage_hosts')

        self.admin = make_user(self.role_admin, suffix='_adm')
        self.prog = make_program(self.admin)
        db.session.commit()

        self.ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='Hosts API Test',
            description='',
            location='',
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
        db.session.add(self.ev)
        db.session.commit()

        self.client = self.app.test_client()
        self.csrf = login(self.client, self.admin)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _put(self, url, data):
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json',
            headers={'X-CSRFToken': self.csrf},
        )

    def test_list_hosts_empty(self):
        resp = self.client.get(f'/api/v1/events/{self.ev.id}/hosts')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['hosts'], [])

    def test_set_hosts_internal(self):
        resp = self._put(f'/api/v1/events/{self.ev.id}/hosts', {
            'hosts': [{'user_id': self.admin.id, 'role_label': 'Ponente'}]
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['count'], 1)

    def test_set_hosts_external(self):
        resp = self._put(f'/api/v1/events/{self.ev.id}/hosts', {
            'hosts': [{'external_name': 'Dr. Guest', 'role_label': 'Invitado'}]
        })
        self.assertEqual(resp.status_code, 200)

    def test_set_hosts_empty_clears_hosts(self):
        self._put(f'/api/v1/events/{self.ev.id}/hosts', {
            'hosts': [{'user_id': self.admin.id, 'role_label': 'Ponente'}]
        })
        resp = self._put(f'/api/v1/events/{self.ev.id}/hosts', {'hosts': []})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['count'], 0)

    def test_set_hosts_invalid_data_returns_400(self):
        resp = self._put(f'/api/v1/events/{self.ev.id}/hosts', {
            'hosts': [{'role_label': 'Ponente'}]  # no user_id or external_name
        })
        self.assertEqual(resp.status_code, 400)

    def test_set_hosts_not_a_list_returns_400(self):
        resp = self._put(f'/api/v1/events/{self.ev.id}/hosts', {
            'hosts': 'not-a-list'
        })
        self.assertEqual(resp.status_code, 400)

    def test_set_hosts_event_not_found(self):
        resp = self._put('/api/v1/events/99999/hosts', {
            'hosts': [{'user_id': self.admin.id, 'role_label': 'Ponente'}]
        })
        self.assertEqual(resp.status_code, 404)

    def test_list_hosts_requires_login(self):
        anon = self.app.test_client()
        resp = anon.get(f'/api/v1/events/{self.ev.id}/hosts')
        self.assertIn(resp.status_code, (401, 302, 403))

    @patch('app.utils.files.save_event_image')
    def test_upload_host_photo_success(self, mock_save):
        mock_save.return_value = f'{self.ev.id}/hosts/abc.jpg'
        import io
        data = {'file': (io.BytesIO(b'fake-image-data'), 'photo.jpg')}
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/hosts/photo',
            data=data,
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 201)
        result = json.loads(resp.data)
        self.assertTrue(result['ok'])

    def test_upload_host_photo_no_file_returns_400(self):
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/hosts/photo',
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 400)

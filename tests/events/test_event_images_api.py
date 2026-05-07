# tests/events/test_event_images_api.py
"""
Integration tests for event image endpoints:
  GET    /api/v1/events/<id>/images
  POST   /api/v1/events/<id>/cover
  POST   /api/v1/events/<id>/images  (gallery)
  DELETE /api/v1/events/images/<image_id>
"""

import io
import json
import unittest
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventImage
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
    grant_permission, login, inject_csrf,
)


class TestEventImagesApi(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        grant_permission(self.role_admin, 'events.api.manage_images')

        self.admin = make_user(self.role_admin, suffix='_adm')
        self.prog = make_program(self.admin)
        db.session.commit()

        self.ev = Event(
            program_id=self.prog.id,
            type='conference',
            title='Images API Test',
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

    def _delete(self, url):
        return self.client.delete(url, headers={'X-CSRFToken': self.csrf})

    def test_list_images_empty(self):
        resp = self.client.get(f'/api/v1/events/{self.ev.id}/images')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertIsNone(data['cover'])
        self.assertEqual(data['gallery'], [])

    def test_list_images_event_not_found(self):
        resp = self.client.get('/api/v1/events/99999/images')
        self.assertEqual(resp.status_code, 404)

    @patch('app.utils.files.save_event_image')
    @patch('app.utils.files.delete_event_image_file')
    def test_upload_cover_success(self, mock_delete, mock_save):
        mock_save.return_value = f'{self.ev.id}/cover.jpg'
        data = {'file': (io.BytesIO(b'fake-image'), 'cover.jpg')}
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/cover',
            data=data,
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 201)
        result = json.loads(resp.data)
        self.assertTrue(result['ok'])
        self.assertIn('image', result)

    def test_upload_cover_no_file_returns_400(self):
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/cover',
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_cover_event_not_found(self):
        data = {'file': (io.BytesIO(b'fake'), 'cover.jpg')}
        resp = self.client.post(
            '/api/v1/events/99999/cover',
            data=data,
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 404)

    @patch('app.utils.files.save_event_image')
    def test_upload_gallery_image_success(self, mock_save):
        mock_save.return_value = f'{self.ev.id}/gallery/img.jpg'
        data = {
            'file': (io.BytesIO(b'fake-image'), 'gallery.jpg'),
            'caption': 'Caption text',
        }
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/images',
            data=data,
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 201)
        result = json.loads(resp.data)
        self.assertFalse(result['image']['is_cover'])

    def test_upload_gallery_no_file_returns_400(self):
        resp = self.client.post(
            f'/api/v1/events/{self.ev.id}/images',
            content_type='multipart/form-data',
            headers={'X-CSRFToken': self.csrf},
        )
        self.assertEqual(resp.status_code, 400)

    @patch('app.utils.files.delete_event_image_file')
    def test_delete_image_success(self, mock_delete):
        mock_delete.return_value = True
        img = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/gallery/img.jpg',
            is_cover=False,
            display_order=1,
        )
        db.session.add(img)
        db.session.commit()
        resp = self._delete(f'/api/v1/events/images/{img.id}')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertIsNone(db.session.get(EventImage, img.id))

    def test_delete_image_not_found(self):
        resp = self._delete('/api/v1/events/images/99999')
        self.assertEqual(resp.status_code, 404)

    def test_list_images_requires_login(self):
        anon = self.app.test_client()
        resp = anon.get(f'/api/v1/events/{self.ev.id}/images')
        self.assertIn(resp.status_code, (401, 302, 403))

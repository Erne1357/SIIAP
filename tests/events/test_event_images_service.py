# tests/events/test_event_images_service.py
"""
Unit tests for EventsService image-related methods:
  - upload_event_cover (mocked file I/O)
  - upload_event_gallery_image (mocked file I/O)
  - delete_event_image
  - get_event_images
  - purge_event_media
"""

import io
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import create_app, db
from app.models.event import Event, EventImage
from app.services.events_service import EventsService
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
)


def _make_app_with_upload():
    """Create app with a real temp upload folder."""
    tmpdir = tempfile.mkdtemp()
    cfg = make_test_config(upload_folder=tmpdir)
    return create_app(cfg), tmpdir


class TestGetEventImages(unittest.TestCase):

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
            title='Img Test',
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

    def test_get_images_empty(self):
        data = EventsService.get_event_images(self.ev.id)
        self.assertIsNone(data['cover'])
        self.assertEqual(data['gallery'], [])

    def test_get_images_with_cover(self):
        img = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/cover.jpg',
            is_cover=True,
            display_order=0,
        )
        db.session.add(img)
        db.session.commit()
        data = EventsService.get_event_images(self.ev.id)
        self.assertIsNotNone(data['cover'])
        self.assertEqual(data['cover']['path'], f'{self.ev.id}/cover.jpg')
        self.assertEqual(data['gallery'], [])

    def test_get_images_with_gallery(self):
        for i in range(3):
            img = EventImage(
                event_id=self.ev.id,
                path=f'{self.ev.id}/gallery/img{i}.jpg',
                is_cover=False,
                display_order=i + 1,
            )
            db.session.add(img)
        db.session.commit()
        data = EventsService.get_event_images(self.ev.id)
        self.assertIsNone(data['cover'])
        self.assertEqual(len(data['gallery']), 3)

    def test_get_images_cover_and_gallery(self):
        cover = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/cover.jpg',
            is_cover=True,
            display_order=0,
        )
        gal = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/gallery/g1.jpg',
            is_cover=False,
            display_order=1,
        )
        db.session.add_all([cover, gal])
        db.session.commit()
        data = EventsService.get_event_images(self.ev.id)
        self.assertIsNotNone(data['cover'])
        self.assertEqual(len(data['gallery']), 1)


class TestUploadEventCoverMocked(unittest.TestCase):
    """Tests upload_event_cover with mocked filesystem calls."""

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
            title='Cover Upload Test',
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

    @patch('app.utils.files.save_event_image')
    @patch('app.utils.files.delete_event_image_file')
    def test_upload_cover_creates_image_record(self, mock_delete, mock_save):
        mock_save.return_value = f'{self.ev.id}/cover.jpg'
        fake_file = MagicMock()
        image = EventsService.upload_event_cover(self.ev.id, fake_file)
        self.assertTrue(image.is_cover)
        self.assertEqual(image.path, f'{self.ev.id}/cover.jpg')

    @patch('app.utils.files.save_event_image')
    @patch('app.utils.files.delete_event_image_file')
    def test_upload_cover_replaces_previous(self, mock_delete, mock_save):
        # Seed an existing cover
        old = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/cover.png',
            is_cover=True,
            display_order=0,
        )
        db.session.add(old)
        db.session.commit()
        old_id = old.id

        mock_save.return_value = f'{self.ev.id}/cover.jpg'
        fake_file = MagicMock()
        new_image = EventsService.upload_event_cover(self.ev.id, fake_file)

        # The service deletes the old cover and creates a new one.
        # SQLite may reuse the same id — verify by checking that only one
        # cover exists and its path is the new one.
        db.session.expire_all()
        covers = EventImage.query.filter_by(event_id=self.ev.id, is_cover=True).all()
        self.assertEqual(len(covers), 1)
        self.assertEqual(covers[0].path, f'{self.ev.id}/cover.jpg')
        self.assertTrue(new_image.is_cover)
        # Old path must no longer exist
        old_cover = EventImage.query.filter_by(
            event_id=self.ev.id, path=f'{self.ev.id}/cover.png'
        ).first()
        self.assertIsNone(old_cover)

    @patch('app.utils.files.save_event_image')
    @patch('app.utils.files.delete_event_image_file')
    def test_upload_gallery_image_creates_record(self, mock_delete, mock_save):
        mock_save.return_value = f'{self.ev.id}/gallery/abc.jpg'
        fake_file = MagicMock()
        image = EventsService.upload_event_gallery_image(self.ev.id, fake_file, caption='Test')
        self.assertFalse(image.is_cover)
        self.assertEqual(image.caption, 'Test')

    def test_upload_cover_event_not_found_raises(self):
        with self.assertRaises(ValueError):
            EventsService.upload_event_cover(99999, MagicMock())

    def test_upload_gallery_event_not_found_raises(self):
        with self.assertRaises(ValueError):
            EventsService.upload_event_gallery_image(99999, MagicMock())


class TestDeleteEventImage(unittest.TestCase):

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
            title='Delete Img',
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

    @patch('app.utils.files.delete_event_image_file')
    def test_delete_image_removes_db_row(self, mock_delete):
        mock_delete.return_value = True
        img = EventImage(
            event_id=self.ev.id,
            path=f'{self.ev.id}/gallery/g1.jpg',
            is_cover=False,
            display_order=1,
        )
        db.session.add(img)
        db.session.commit()
        img_id = img.id
        result = EventsService.delete_event_image(img_id)
        self.assertTrue(result)
        self.assertIsNone(db.session.get(EventImage, img_id))

    def test_delete_image_not_found_raises(self):
        with self.assertRaises(ValueError):
            EventsService.delete_event_image(99999)


class TestPurgeEventMedia(unittest.TestCase):

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
            title='Purge Test',
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

    @patch('app.utils.files.delete_all_event_files')
    def test_purge_removes_all_images(self, mock_delete_files):
        mock_delete_files.return_value = 2
        for i in range(2):
            img = EventImage(
                event_id=self.ev.id,
                path=f'{self.ev.id}/gallery/img{i}.jpg',
                is_cover=False,
                display_order=i,
            )
            db.session.add(img)
        db.session.commit()
        result = EventsService.purge_event_media(self.ev.id)
        self.assertEqual(result['db_rows_deleted'], 2)
        self.assertEqual(EventImage.query.filter_by(event_id=self.ev.id).count(), 0)

# tests/events/test_invitations_api.py
"""
Integration tests for /api/v1/invitations endpoints:
  POST   /event/<id>/invite
  GET    /event/<id>/list
  POST   /<inv_id>/respond
  GET    /my-invitations
  DELETE /<inv_id>
  PUT    /event/<id>/dates
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app import create_app, db
from app.models.event import Event, EventInvitation, EventAttendance
from tests.events.conftest import (
    make_test_config, make_role, make_user, make_program,
    grant_permission, login, inject_csrf,
)


class TestInvitationsApiBase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(make_test_config())
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.role_admin = make_role('program_admin')
        grant_permission(self.role_admin, 'invitations.api.send')
        grant_permission(self.role_admin, 'invitations.api.list')
        grant_permission(self.role_admin, 'invitations.api.manage')

        self.admin = make_user(self.role_admin, suffix='_adm')
        self.prog = make_program(self.admin)

        self.role_student = make_role('student')
        self.student = make_user(self.role_student, suffix='_stu')
        db.session.commit()

        self.ev = Event(
            program_id=None,
            type='conference',
            title='Invite Test Event',
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
        )
        db.session.add(self.ev)
        db.session.commit()

        self.admin_client = self.app.test_client()
        self.admin_csrf = login(self.admin_client, self.admin)

        self.student_client = self.app.test_client()
        self.student_csrf = login(self.student_client, self.student)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _admin_post(self, url, data):
        return self.admin_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            headers={'X-CSRFToken': self.admin_csrf},
        )

    def _student_post(self, url, data):
        return self.student_client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            headers={'X-CSRFToken': self.student_csrf},
        )

    def _admin_delete(self, url):
        return self.admin_client.delete(url, headers={'X-CSRFToken': self.admin_csrf})


class TestInviteStudents(TestInvitationsApiBase):

    @patch('app.services.user_history_service.UserHistoryService.log_event_invitation')
    @patch('app.services.notification_service.NotificationService.notify_event_invitation')
    def test_invite_students_success(self, mock_notif, mock_log):
        mock_notif.return_value = MagicMock(id=1)
        resp = self._admin_post(
            f'/api/v1/invitations/event/{self.ev.id}/invite',
            {'user_ids': [self.student.id]},
        )
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertGreater(data['invited'], 0)

    def test_invite_empty_user_ids_returns_400(self):
        resp = self._admin_post(
            f'/api/v1/invitations/event/{self.ev.id}/invite',
            {'user_ids': []},
        )
        self.assertEqual(resp.status_code, 400)

    def test_invite_event_not_found_returns_404(self):
        resp = self._admin_post(
            '/api/v1/invitations/event/99999/invite',
            {'user_ids': [self.student.id]},
        )
        self.assertEqual(resp.status_code, 404)

    def test_invite_requires_permission(self):
        role2 = make_role('applicant')
        u2 = make_user(role2, suffix='_app')
        db.session.commit()
        client2 = self.app.test_client()
        login(client2, u2)
        inject_csrf(client2)
        resp = client2.post(
            f'/api/v1/invitations/event/{self.ev.id}/invite',
            data=json.dumps({'user_ids': [self.student.id]}),
            content_type='application/json',
            headers={'X-CSRFToken': 'test-csrf-token'},
        )
        self.assertEqual(resp.status_code, 403)


class TestListEventInvitations(TestInvitationsApiBase):

    def test_list_invitations_success(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self.admin_client.get(f'/api/v1/invitations/event/{self.ev.id}/list')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertGreater(data['total'], 0)

    def test_list_invitations_not_found_event(self):
        resp = self.admin_client.get('/api/v1/invitations/event/99999/list')
        self.assertEqual(resp.status_code, 404)


class TestRespondToInvitation(TestInvitationsApiBase):

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

    def test_accept_invitation(self):
        inv = self._make_invitation()
        resp = self._student_post(
            f'/api/v1/invitations/{inv.id}/respond',
            {'accept': True},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'accepted')

    def test_reject_invitation(self):
        inv = self._make_invitation()
        resp = self._student_post(
            f'/api/v1/invitations/{inv.id}/respond',
            {'accept': False},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'rejected')

    def test_respond_wrong_user_returns_400(self):
        inv = self._make_invitation()
        # Admin tries to respond to student's invitation
        resp = self._admin_post(
            f'/api/v1/invitations/{inv.id}/respond',
            {'accept': True},
        )
        self.assertEqual(resp.status_code, 400)

    def test_respond_cancelled_invitation_returns_400(self):
        inv = self._make_invitation(status='cancelled')
        resp = self._student_post(
            f'/api/v1/invitations/{inv.id}/respond',
            {'accept': True},
        )
        self.assertEqual(resp.status_code, 400)

    def test_respond_not_found_returns_400(self):
        resp = self._student_post(
            '/api/v1/invitations/99999/respond',
            {'accept': True},
        )
        self.assertEqual(resp.status_code, 400)


class TestMyInvitations(TestInvitationsApiBase):

    def test_my_invitations_returns_pending(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self.student_client.get('/api/v1/invitations/my-invitations')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)

    def test_my_invitations_does_not_include_non_pending(self):
        """GET /my-invitations only returns pending invitations."""
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='accepted',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self.student_client.get('/api/v1/invitations/my-invitations')
        data = json.loads(resp.data)
        self.assertEqual(data['total'], 0)

    def test_my_invitations_empty(self):
        resp = self.student_client.get('/api/v1/invitations/my-invitations')
        data = json.loads(resp.data)
        self.assertEqual(data['total'], 0)

    def test_my_invitations_requires_auth(self):
        anon = self.app.test_client()
        resp = anon.get('/api/v1/invitations/my-invitations')
        self.assertIn(resp.status_code, (401, 302, 403))


class TestCancelInvitation(TestInvitationsApiBase):

    def test_cancel_pending_invitation(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='pending',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self._admin_delete(f'/api/v1/invitations/{inv.id}')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])

    def test_cancel_accepted_invitation_returns_400(self):
        inv = EventInvitation(
            event_id=self.ev.id,
            user_id=self.student.id,
            invited_by=self.admin.id,
            status='accepted',
        )
        db.session.add(inv)
        db.session.commit()
        resp = self._admin_delete(f'/api/v1/invitations/{inv.id}')
        self.assertEqual(resp.status_code, 400)


class TestUpdateEventDates(TestInvitationsApiBase):

    def test_update_event_dates_success(self):
        future = (datetime.now() + timedelta(days=7)).isoformat()
        resp = self.admin_client.put(
            f'/api/v1/invitations/event/{self.ev.id}/dates',
            data=json.dumps({'event_date': future}),
            content_type='application/json',
            headers={'X-CSRFToken': self.admin_csrf},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])

    def test_update_dates_event_not_found(self):
        resp = self.admin_client.put(
            '/api/v1/invitations/event/99999/dates',
            data=json.dumps({'event_date': '2030-01-01T00:00:00'}),
            content_type='application/json',
            headers={'X-CSRFToken': self.admin_csrf},
        )
        self.assertEqual(resp.status_code, 404)

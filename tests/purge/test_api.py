# tests/purge/test_api.py
"""
HTTP-level tests for the purge API endpoints.

Endpoint map (all under /api/v1/admin/purge):
  GET  /candidates?category=<cat>      → list_candidates
  POST /start                           → start_purge_run
  GET  /<run_id>/archive.zip            → download_archive
  POST /<run_id>/confirm                → confirm_purge
  POST /<run_id>/cancel                 → cancel_run
  GET  /runs                            → list_runs
"""

from pathlib import Path

import pytest

from app import db
from app.models.purge_run import PurgeRun
from app.models.submission import Submission
from app.models.user_program import UserProgram
import app.services.applicant_archive_service as svc

from tests.purge.conftest import login, csrf


BASE = '/api/v1/admin/purge'


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _login_postgrad(client, postgrad_admin):
    return login(client, postgrad_admin)


def _login_applicant(client, applicant_user_factory):
    """Login as a plain applicant (no purge perms)."""
    user = applicant_user_factory(suffix='apiappl')
    db.session.commit()
    return user, login(client, user)


# ---------------------------------------------------------------------------
# GET /candidates — permission checks
# ---------------------------------------------------------------------------

class TestCandidatesPermissions:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get(f'{BASE}/candidates?category=admission_expired_with_files')
        assert resp.status_code == 401

    def test_applicant_role_gets_403(
        self, client, roles, permissions, applicant_user_factory
    ):
        user, _ = _login_applicant(client, applicant_user_factory)
        resp = client.get(f'{BASE}/candidates?category=admission_expired_with_files')
        assert resp.status_code == 403

    def test_postgrad_admin_gets_200(
        self, client, roles, permissions, postgrad_admin, periods
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=admission_expired_with_files')
        assert resp.status_code == 200

    def test_missing_category_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'MISSING_FIELD'

    def test_invalid_category_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=not_a_real_category')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'INVALID_CATEGORY'


class TestCandidatesResponseShape:
    def test_returns_data_error_meta(
        self, client, roles, permissions, postgrad_admin, periods
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=admission_expired_with_files')
        body = resp.get_json()
        assert 'data' in body
        assert 'error' in body
        assert 'meta' in body
        assert body['error'] is None
        assert 'count' in body['meta']
        assert 'category' in body['meta']

    def test_returns_list_for_valid_category(
        self, client, roles, permissions, postgrad_admin, periods,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='api_exp')
        make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=admission_expired_with_files')
        body = resp.get_json()
        assert isinstance(body['data'], list)
        assert body['meta']['count'] == len(body['data'])

    def test_delta3_plus_category_accepted(
        self, client, roles, permissions, postgrad_admin, periods
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=admission_delta3_plus')
        assert resp.status_code == 200

    def test_retention_policy_category_accepted(
        self, client, roles, permissions, postgrad_admin, periods
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/candidates?category=retention_policy')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /start
# ---------------------------------------------------------------------------

class TestStartPurgeRun:
    def test_unauthenticated_blocked(self, client, roles, permissions):
        """
        Without a session, CSRF guard fires first (400) before @login_required
        (401). Either status code means the request is correctly blocked.
        """
        resp = client.post(f'{BASE}/start', json={
            'user_program_ids': [1],
            'purge_type': 'admission_expired_with_files',
        })
        assert resp.status_code in (400, 401)

    def test_applicant_role_gets_403(
        self, client, roles, permissions, applicant_user_factory
    ):
        user, token = _login_applicant(client, applicant_user_factory)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [1], 'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        assert resp.status_code == 403

    def test_missing_user_program_ids_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'MISSING_FIELD'

    def test_empty_user_program_ids_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [], 'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        assert resp.status_code == 400

    def test_missing_purge_type_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [1]},
            headers=csrf(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'MISSING_FIELD'

    def test_invalid_purge_type_returns_400(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='startinv')
        up, _ = make_applicant(user, status='expired', with_file=False)
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [up.id], 'purge_type': 'bad_type'},
            headers=csrf(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'INVALID_PURGE_TYPE'

    def test_nonexistent_up_ids_returns_400(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [99999], 'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        assert resp.status_code == 400

    def test_valid_request_returns_201_with_run(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='startok')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [up.id],
                  'purge_type': 'admission_expired_with_files',
                  'notes': 'test run'},
            headers=csrf(token),
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['error'] is None
        assert 'run' in body['data']
        assert 'archive_url' in body['data']
        assert 'confirm_url' in body['data']
        assert 'cancel_url' in body['data']
        run_dict = body['data']['run']
        assert run_dict['status'] == 'pending_download'
        assert run_dict['notes'] == 'test run'

    def test_flash_message_present_on_success(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='startflash')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [up.id],
                  'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        body = resp.get_json()
        assert body.get('flash')
        assert body['flash'][0]['level'] == 'success'


# ---------------------------------------------------------------------------
# GET /<run_id>/archive.zip
# ---------------------------------------------------------------------------

class TestDownloadArchive:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get(f'{BASE}/fake-run-id/archive.zip')
        assert resp.status_code == 401

    def test_applicant_role_gets_403(
        self, client, roles, permissions, applicant_user_factory,
        postgrad_admin, make_applicant
    ):
        user_admin = postgrad_admin
        user_appl = applicant_user_factory(suffix='dlperm')
        up, sub = make_applicant(user_appl, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=user_admin.id,
        )
        db.session.commit()

        user_applicant, token = _login_applicant(client, applicant_user_factory)
        resp = client.get(f'{BASE}/{run.run_id}/archive.zip')
        assert resp.status_code == 403

    def test_nonexistent_run_returns_404(
        self, client, roles, permissions, postgrad_admin
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/no-such-run/archive.zip')
        assert resp.status_code == 404

    def test_download_returns_zip_content_type(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='dlct')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/{run.run_id}/archive.zip')
        assert resp.status_code == 200
        assert 'zip' in resp.content_type

    def test_download_purged_run_returns_409(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='dl409')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'purged'
        db.session.commit()

        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/{run.run_id}/archive.zip')
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /<run_id>/confirm
# ---------------------------------------------------------------------------

class TestConfirmEndpoint:
    def test_unauthenticated_blocked(self, client):
        """CSRF guard (400) or login_required (401) both correctly block access."""
        resp = client.post(f'{BASE}/fake-run/confirm', json={})
        assert resp.status_code in (400, 401)

    def test_applicant_gets_403(
        self, client, roles, permissions, applicant_user_factory
    ):
        user, token = _login_applicant(client, applicant_user_factory)
        resp = client.post(
            f'{BASE}/fake-run/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 403

    def test_nonexistent_run_returns_404(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/no-such-run/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 404

    def test_confirm_pending_run_returns_409(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        """pending_download → cannot confirm yet → 409."""
        user = applicant_user_factory(suffix='conf409')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 409

    def test_confirm_transition_snapshot_returns_409(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='confsnap')
        up, sub = make_applicant(user, status='enrolled', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='transition_snapshot',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 409

    def test_confirm_downloaded_run_returns_200(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='conf200')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['error'] is None
        assert body['data']['run_id'] == run.run_id

    def test_confirm_response_has_flash_success(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='confflash')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/confirm', json={}, headers=csrf(token)
        )
        body = resp.get_json()
        assert body.get('flash')
        assert body['flash'][0]['level'] == 'success'


# ---------------------------------------------------------------------------
# POST /<run_id>/cancel
# ---------------------------------------------------------------------------

class TestCancelEndpoint:
    def test_unauthenticated_blocked(self, client):
        """CSRF guard (400) or login_required (401) both correctly block access."""
        resp = client.post(f'{BASE}/fake-run/cancel', json={})
        assert resp.status_code in (400, 401)

    def test_applicant_gets_403(
        self, client, roles, permissions, applicant_user_factory
    ):
        user, token = _login_applicant(client, applicant_user_factory)
        resp = client.post(
            f'{BASE}/fake-run/cancel', json={}, headers=csrf(token)
        )
        assert resp.status_code == 403

    def test_nonexistent_run_returns_404(
        self, client, roles, permissions, postgrad_admin
    ):
        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/no-such-run/cancel', json={}, headers=csrf(token)
        )
        assert resp.status_code == 404

    def test_cancel_pending_run_returns_200(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='cancel200')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/cancel', json={}, headers=csrf(token)
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['data']['status'] == 'cancelled'

    def test_cancel_purged_run_returns_409(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='cancel409')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'purged'
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/cancel', json={}, headers=csrf(token)
        )
        assert resp.status_code == 409

    def test_cancel_response_has_flash_info(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='cancelflash')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)
        resp = client.post(
            f'{BASE}/{run.run_id}/cancel', json={}, headers=csrf(token)
        )
        body = resp.get_json()
        assert body.get('flash')
        assert body['flash'][0]['level'] == 'info'


# ---------------------------------------------------------------------------
# GET /runs
# ---------------------------------------------------------------------------

class TestListRunsEndpoint:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get(f'{BASE}/runs')
        assert resp.status_code == 401

    def test_applicant_gets_403(
        self, client, roles, permissions, applicant_user_factory
    ):
        user, _ = _login_applicant(client, applicant_user_factory)
        resp = client.get(f'{BASE}/runs')
        assert resp.status_code == 403

    def test_postgrad_admin_gets_200(
        self, client, roles, permissions, postgrad_admin
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/runs')
        assert resp.status_code == 200

    def test_returns_data_error_meta_count(
        self, client, roles, permissions, postgrad_admin
    ):
        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/runs')
        body = resp.get_json()
        assert body['error'] is None
        assert isinstance(body['data'], list)
        assert body['meta']['count'] == len(body['data'])

    def test_newly_created_run_appears_in_list(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='listrun')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/runs')
        body = resp.get_json()
        run_ids = [r['run_id'] for r in body['data']]
        assert run.run_id in run_ids

    def test_run_dict_has_required_keys(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='listkeys')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        db.session.commit()

        _login_postgrad(client, postgrad_admin)
        resp = client.get(f'{BASE}/runs')
        items = resp.get_json()['data']
        assert len(items) >= 1
        item = items[0]
        for key in ('run_id', 'status', 'purge_type', 'initiated_by',
                    'initiated_at', 'expires_at', 'item_count'):
            assert key in item, f'Missing key in run dict: {key}'


# ---------------------------------------------------------------------------
# Full workflow: start → download → confirm
# ---------------------------------------------------------------------------

class TestFullPurgeWorkflow:
    def test_full_workflow_via_api(
        self, client, roles, permissions, postgrad_admin,
        applicant_user_factory, make_applicant, upload_root
    ):
        """
        Smoke test: POST /start → GET /<run_id>/archive.zip → POST /<run_id>/confirm.
        Verifies the run ends up in 'purged' state and the user file is gone.
        """
        user = applicant_user_factory(suffix='fullwf')
        up, sub = make_applicant(user, status='expired', with_file=True)
        user_file = upload_root / sub.file_path
        assert user_file.exists()
        db.session.commit()

        token = _login_postgrad(client, postgrad_admin)

        # 1. Start
        resp = client.post(
            f'{BASE}/start',
            json={'user_program_ids': [up.id],
                  'purge_type': 'admission_expired_with_files'},
            headers=csrf(token),
        )
        assert resp.status_code == 201
        run_id = resp.get_json()['data']['run']['run_id']

        # 2. Download (triggers on_complete via call_on_close in test client)
        resp = client.get(f'{BASE}/{run_id}/archive.zip')
        assert resp.status_code == 200
        # Manually mark as downloaded because call_on_close may not fire in tests
        db.session.expire_all()
        run = PurgeRun.query.filter_by(run_id=run_id).first()
        run.status = 'downloaded'
        db.session.commit()

        # 3. Confirm
        resp = client.post(
            f'{BASE}/{run_id}/confirm', json={}, headers=csrf(token)
        )
        assert resp.status_code == 200

        # Verify final state
        db.session.expire_all()
        run = PurgeRun.query.filter_by(run_id=run_id).first()
        assert run.status == 'purged'
        assert run.purged_at is not None

        # Submission completa borrada (sin rastro auditable en DB; solo en ZIP)
        assert Submission.query.get(sub.id) is None
        assert not user_file.exists()

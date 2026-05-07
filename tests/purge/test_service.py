# tests/purge/test_service.py
"""
Pure service-layer tests for app.services.applicant_archive_service.

Each test function is independent: it creates its own DB records and does
not rely on shared mutable state.
"""

import json
import os
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.purge_run import PurgeRun
from app.models.submission import Submission
from app.models.user_program import UserProgram
from app.models.retention_policy import RetentionPolicy
import app.services.applicant_archive_service as svc

from tests.purge.conftest import _write_fake_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _commit():
    db.session.commit()


# ---------------------------------------------------------------------------
# PurgeRun model methods
# ---------------------------------------------------------------------------

class TestPurgeRunModel:
    def test_is_terminal_statuses(self, app):
        for status in ('purged', 'cancelled', 'expired'):
            run = PurgeRun(
                run_id=f'run-{status}', initiated_by=1, purge_type='admission_expired_with_files',
                target_user_program_ids=[], status=status,
            )
            assert run.is_terminal() is True

    def test_is_not_terminal_for_pending_and_downloaded(self, app):
        for status in ('pending_download', 'downloaded'):
            run = PurgeRun(
                run_id=f'run-nt-{status}', initiated_by=1,
                purge_type='admission_expired_with_files',
                target_user_program_ids=[], status=status,
            )
            assert run.is_terminal() is False

    def test_can_download_returns_true_for_correct_statuses(self, app):
        for status in ('pending_download', 'downloaded'):
            run = PurgeRun(
                run_id=f'dl-{status}', initiated_by=1,
                purge_type='admission_expired_with_files',
                target_user_program_ids=[], status=status,
            )
            assert run.can_download() is True

    def test_can_download_returns_false_for_terminal(self, app):
        for status in ('purged', 'cancelled', 'expired'):
            run = PurgeRun(
                run_id=f'nodl-{status}', initiated_by=1,
                purge_type='admission_expired_with_files',
                target_user_program_ids=[], status=status,
            )
            assert run.can_download() is False

    def test_can_confirm_purge_requires_downloaded_status(self, app):
        run_dl = PurgeRun(
            run_id='confirm-ok', initiated_by=1,
            purge_type='admission_expired_with_files',
            target_user_program_ids=[], status='downloaded',
        )
        run_pending = PurgeRun(
            run_id='confirm-nok', initiated_by=1,
            purge_type='admission_expired_with_files',
            target_user_program_ids=[], status='pending_download',
        )
        assert run_dl.can_confirm_purge() is True
        assert run_pending.can_confirm_purge() is False

    def test_can_confirm_purge_always_false_for_transition_snapshot(self, app):
        for status in ('downloaded', 'pending_download'):
            run = PurgeRun(
                run_id=f'snap-{status}', initiated_by=1,
                purge_type='transition_snapshot',
                target_user_program_ids=[], status=status,
            )
            assert run.can_confirm_purge() is False


# ---------------------------------------------------------------------------
# list_candidates — InvalidPurgeType
# ---------------------------------------------------------------------------

class TestListCandidatesInvalidType:
    def test_unknown_category_raises(self, app):
        with pytest.raises(svc.InvalidPurgeType):
            svc.list_candidates('unknown_category')

    def test_empty_string_raises(self, app):
        with pytest.raises(svc.InvalidPurgeType):
            svc.list_candidates('')

    def test_transition_snapshot_not_a_candidate_category(self, app):
        # transition_snapshot is a valid purge_type but NOT a list_candidates category
        with pytest.raises(svc.InvalidPurgeType):
            svc.list_candidates('transition_snapshot')


# ---------------------------------------------------------------------------
# list_candidates — admission_expired_with_files
# ---------------------------------------------------------------------------

class TestListCandidatesExpiredWithFiles:
    def test_returns_expired_ups_with_files(
        self, app, applicant_user_factory, make_applicant, upload_root
    ):
        user = applicant_user_factory(suffix='exp1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        results = svc.list_candidates('admission_expired_with_files')
        ids = [r['user_program_id'] for r in results]
        assert up.id in ids

    def test_excludes_expired_ups_without_files(
        self, app, applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='expnofile')
        up, _ = make_applicant(user, status='expired', with_file=False)
        _commit()

        results = svc.list_candidates('admission_expired_with_files')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids

    def test_excludes_non_expired_ups(
        self, app, applicant_user_factory, make_applicant
    ):
        user = applicant_user_factory(suffix='inprog')
        up, _ = make_applicant(user, status='in_progress', with_file=True)
        _commit()

        results = svc.list_candidates('admission_expired_with_files')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids

    def test_result_shape(
        self, app, applicant_user_factory, make_applicant, upload_root
    ):
        user = applicant_user_factory(suffix='shape1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        results = svc.list_candidates('admission_expired_with_files')
        match = next((r for r in results if r['user_program_id'] == up.id), None)
        assert match is not None
        for key in ('user_program_id', 'user_id', 'name', 'email', 'program_name',
                    'admission_status', 'admission_period', 'files_count',
                    'total_size_bytes'):
            assert key in match, f'Missing key: {key}'
        assert match['files_count'] >= 1
        assert match['total_size_bytes'] > 0

    def test_excluded_file_not_on_disk(
        self, app, applicant_user_factory, make_applicant, upload_root
    ):
        """File recorded in Submission but deleted from disk → not counted."""
        user = applicant_user_factory(suffix='nodisk')
        up, sub = make_applicant(user, status='expired', with_file=True)
        # Remove the file from disk after creating the submission
        full = upload_root / sub.file_path
        full.unlink()
        _commit()

        results = svc.list_candidates('admission_expired_with_files')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids


# ---------------------------------------------------------------------------
# list_candidates — admission_delta3_plus
# ---------------------------------------------------------------------------

class TestListCandidatesDelta3Plus:
    def test_returns_ups_with_two_or_more_elapsed_periods(
        self, app, applicant_user_factory, make_applicant, periods
    ):
        """
        P0 (20251) is old enough that two periods (20253, 20263) have passed
        with admission_end_date in the past.
        """
        user = applicant_user_factory(suffix='delta2')
        up, sub = make_applicant(user, status='in_progress',
                                 period_code='20251', with_file=True)
        _commit()

        results = svc.list_candidates('admission_delta3_plus')
        ids = [r['user_program_id'] for r in results]
        assert up.id in ids
        match = next(r for r in results if r['user_program_id'] == up.id)
        assert match['periods_elapsed'] >= 2

    def test_excludes_recent_ups(
        self, app, applicant_user_factory, make_applicant, periods
    ):
        """P3 (20271 — upcoming, admission window in 2030) has 0 closed periods after it."""
        user = applicant_user_factory(suffix='recent')
        up, _ = make_applicant(user, status='in_progress',
                                period_code='20271', with_file=True)
        _commit()

        results = svc.list_candidates('admission_delta3_plus')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids

    def test_excludes_enrolled_status(
        self, app, applicant_user_factory, make_applicant, periods
    ):
        """enrolled is not in the watched statuses for delta3_plus."""
        user = applicant_user_factory(suffix='enrolled')
        up, _ = make_applicant(user, status='enrolled',
                                period_code='20251', with_file=True)
        _commit()

        results = svc.list_candidates('admission_delta3_plus')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids


# ---------------------------------------------------------------------------
# list_candidates — retention_policy
# ---------------------------------------------------------------------------

class TestListCandidatesRetentionPolicy:
    def test_returns_up_matching_policy_with_old_updated_at(
        self, app, applicant_user_factory, make_applicant,
        program_structure, upload_root
    ):
        """Happy path: policy with keep_years=1, UP updated 2 years ago."""
        archive = program_structure['archive']
        policy = RetentionPolicy(
            archive_id=archive.id,
            keep_years=1,
            keep_forever=False,
            apply_after='rejected',
        )
        db.session.add(policy)
        db.session.flush()

        user = applicant_user_factory(suffix='ret1')
        up, sub = make_applicant(user, status='rejected', with_file=True)
        # Push updated_at back 2+ years
        from app.utils.datetime_utils import now_local
        up.updated_at = now_local() - timedelta(days=800)
        db.session.flush()
        _commit()

        results = svc.list_candidates('retention_policy')
        ids = [r['user_program_id'] for r in results]
        assert up.id in ids

    def test_excludes_keep_forever_policies(
        self, app, applicant_user_factory, make_applicant, program_structure
    ):
        archive = program_structure['archive']
        policy = RetentionPolicy(
            archive_id=archive.id,
            keep_years=1,
            keep_forever=True,   # <-- must be excluded
            apply_after='rejected',
        )
        db.session.add(policy)
        db.session.flush()

        user = applicant_user_factory(suffix='keepfv')
        up, _ = make_applicant(user, status='rejected', with_file=True)
        from app.utils.datetime_utils import now_local
        up.updated_at = now_local() - timedelta(days=800)
        db.session.flush()
        _commit()

        results = svc.list_candidates('retention_policy')
        ids = [r['user_program_id'] for r in results]
        assert up.id not in ids


# ---------------------------------------------------------------------------
# create_purge_run
# ---------------------------------------------------------------------------

class TestCreatePurgeRun:
    def test_creates_run_with_pending_download_status(
        self, app, applicant_user_factory, make_applicant, postgrad_admin,
        backups_dir
    ):
        user = applicant_user_factory(suffix='cr1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        assert run.status == 'pending_download'
        assert run.run_id is not None
        assert run.archive_path is not None

    def test_zip_is_created_on_disk(
        self, app, applicant_user_factory, make_applicant, postgrad_admin,
        backups_dir
    ):
        user = applicant_user_factory(suffix='cr2')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        assert Path(run.archive_path).exists()

    def test_zip_contains_manifest_summary_and_documents(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cr3')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with zipfile.ZipFile(run.archive_path, 'r') as zf:
            names = zf.namelist()
        assert 'manifest.json' in names
        assert 'summary.csv' in names
        # At least one document entry
        docs = [n for n in names if n.startswith('documents/')]
        assert len(docs) >= 1

    def test_manifest_has_correct_run_id_and_type(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cr4')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with zipfile.ZipFile(run.archive_path, 'r') as zf:
            manifest = json.loads(zf.read('manifest.json'))

        assert manifest['run_id'] == run.run_id
        assert manifest['purge_type'] == 'admission_expired_with_files'
        assert manifest['initiated_by_id'] == postgrad_admin.id
        assert len(manifest['items']) == 1
        assert manifest['item_count'] == 1

    def test_manifest_item_has_user_and_submissions(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cr5')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with zipfile.ZipFile(run.archive_path, 'r') as zf:
            manifest = json.loads(zf.read('manifest.json'))

        item = manifest['items'][0]
        assert item['user_program_id'] == up.id
        assert 'user' in item
        assert item['user']['email'] == user.email
        assert 'submissions' in item
        # No created_at key should appear (it doesn't exist on UserProgram)
        assert 'created_at' not in item.get('user_program', {})

    def test_raises_invalid_purge_type(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='invtype')
        up, _ = make_applicant(user, status='expired', with_file=False)
        _commit()

        with pytest.raises(svc.InvalidPurgeType):
            svc.create_purge_run(
                user_program_ids=[up.id],
                purge_type='nonexistent_type',
                initiated_by_id=postgrad_admin.id,
            )

    def test_raises_purge_error_when_no_ups_found(
        self, app, postgrad_admin
    ):
        _commit()
        with pytest.raises(svc.PurgeError):
            svc.create_purge_run(
                user_program_ids=[99999],
                purge_type='admission_expired_with_files',
                initiated_by_id=postgrad_admin.id,
            )

    def test_logs_purge_run_created_action_in_history(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.models.user_history import UserHistory
        user = applicant_user_factory(suffix='histcr')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        # purge_run_created is logged on the target user
        history = UserHistory.query.filter_by(
            user_id=user.id, action='purge_run_created'
        ).first()
        assert history is not None
        assert run.run_id in history.details

    def test_sha256_and_size_are_populated(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='shasize')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        assert run.archive_sha256 is not None
        assert len(run.archive_sha256) == 64
        assert run.archive_size_bytes > 0

    def test_notes_stored_on_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='notes')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
            notes='Test notes content',
        )

        assert run.notes == 'Test notes content'


# ---------------------------------------------------------------------------
# stream_archive
# ---------------------------------------------------------------------------

class TestStreamArchive:
    def test_returns_path_size_callback(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='sa1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        path, size, on_complete = svc.stream_archive(
            run_id=run.run_id, downloader_user_id=postgrad_admin.id
        )
        assert path.exists()
        assert size > 0
        assert callable(on_complete)

    def test_on_complete_marks_downloaded(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='sa2')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        _, _, on_complete = svc.stream_archive(
            run_id=run.run_id, downloader_user_id=postgrad_admin.id
        )
        on_complete()

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        assert refreshed.status == 'downloaded'
        assert refreshed.archive_downloaded_at is not None

    def test_on_complete_logs_purge_run_downloaded(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.models.user_history import UserHistory
        user = applicant_user_factory(suffix='sa3')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        _, _, on_complete = svc.stream_archive(
            run_id=run.run_id, downloader_user_id=postgrad_admin.id
        )
        on_complete()

        h = UserHistory.query.filter_by(
            user_id=postgrad_admin.id, action='purge_run_downloaded'
        ).first()
        assert h is not None

    def test_raises_invalid_purge_state_when_already_purged(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='sa4')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'purged'
        db.session.commit()

        with pytest.raises(svc.InvalidPurgeState):
            svc.stream_archive(run_id=run.run_id, downloader_user_id=postgrad_admin.id)

    def test_raises_purge_run_not_found(self, app):
        with pytest.raises(svc.PurgeRunNotFound):
            svc.stream_archive(run_id='nonexistent-run-id', downloader_user_id=1)


# ---------------------------------------------------------------------------
# confirm_purge — state machine
# ---------------------------------------------------------------------------

class TestConfirmPurgeStateMachine:
    def test_cannot_confirm_when_pending_download(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cpnd')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        # Status is still 'pending_download' — not downloaded yet

        with pytest.raises(svc.InvalidPurgeState):
            svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

    def test_cannot_confirm_transition_snapshot(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cpsnap')
        up, sub = make_applicant(user, status='enrolled', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='transition_snapshot',
            initiated_by_id=postgrad_admin.id,
        )
        # Manually mark as downloaded
        run.status = 'downloaded'
        db.session.commit()

        with pytest.raises(svc.InvalidPurgeState):
            svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

    def test_confirm_after_download_succeeds(
        self, app, applicant_user_factory, make_applicant, postgrad_admin,
        upload_root
    ):
        user = applicant_user_factory(suffix='cpok')
        up, sub = make_applicant(user, status='expired', with_file=True)
        file_on_disk = upload_root / sub.file_path
        assert file_on_disk.exists()
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        result = svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        assert result['deleted_files'] >= 1
        assert result['purged_submissions'] >= 1
        assert result['user_programs_affected'] == 1

    def test_confirm_sets_run_status_to_purged(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cpstatus')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        assert refreshed.status == 'purged'
        assert refreshed.purged_at is not None

    def test_confirm_deletes_zip_from_disk(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cpzip')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        zip_path = Path(run.archive_path)
        assert zip_path.exists()

        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        assert not zip_path.exists()

    def test_confirm_removes_submission_files_from_disk(
        self, app, applicant_user_factory, make_applicant, postgrad_admin,
        upload_root
    ):
        user = applicant_user_factory(suffix='cpdisk')
        up, sub = make_applicant(user, status='expired', with_file=True)
        file_path = upload_root / sub.file_path
        assert file_path.exists()
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        assert not file_path.exists()

    def test_confirm_deletes_submission_row(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        """Submissions completas se borran del DB para que no queden con
        status='approved' que confunda un re-intento del aspirante."""
        user = applicant_user_factory(suffix='cpnone')
        up, sub = make_applicant(user, status='expired', with_file=True)
        sub_id = sub.id
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        db.session.expire_all()
        assert Submission.query.get(sub_id) is None

    def test_confirm_marks_admission_status_expired(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='cpexpstatus')
        up, sub = make_applicant(user, status='in_progress', with_file=True)
        up_id = up.id
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_delta3_plus',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        db.session.expire_all()
        refreshed_up = UserProgram.query.get(up_id)
        assert refreshed_up.admission_status == 'expired'

    def test_confirm_does_not_touch_already_expired_admission_status(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='alreadyexp')
        up, sub = make_applicant(user, status='expired', with_file=True)
        up_id = up.id
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        db.session.expire_all()
        refreshed = UserProgram.query.get(up_id)
        assert refreshed.admission_status == 'expired'

    def test_confirm_logs_purge_run_confirmed_action(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.models.user_history import UserHistory
        user = applicant_user_factory(suffix='cplog')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.confirm_purge(run.run_id, confirmer_user_id=postgrad_admin.id)

        h = UserHistory.query.filter_by(
            user_id=user.id, action='purge_run_confirmed'
        ).first()
        assert h is not None

    def test_confirm_raises_for_nonexistent_run(self, app, postgrad_admin):
        _commit()
        with pytest.raises(svc.PurgeRunNotFound):
            svc.confirm_purge('no-such-run', confirmer_user_id=postgrad_admin.id)


# ---------------------------------------------------------------------------
# cancel_purge_run
# ---------------------------------------------------------------------------

class TestCancelPurgeRun:
    def test_cancel_pending_download_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='can1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        assert run.status == 'pending_download'

        svc.cancel_purge_run(run.run_id, canceller_user_id=postgrad_admin.id)

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        assert refreshed.status == 'cancelled'

    def test_cancel_downloaded_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='can2')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'downloaded'
        db.session.commit()

        svc.cancel_purge_run(run.run_id, canceller_user_id=postgrad_admin.id)

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        assert refreshed.status == 'cancelled'

    def test_cancel_deletes_zip(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='can3')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        zip_path = Path(run.archive_path)
        assert zip_path.exists()

        svc.cancel_purge_run(run.run_id, canceller_user_id=postgrad_admin.id)

        assert not zip_path.exists()

    def test_cancel_raises_for_terminal_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='canterminal')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'purged'
        db.session.commit()

        with pytest.raises(svc.InvalidPurgeState):
            svc.cancel_purge_run(run.run_id, canceller_user_id=postgrad_admin.id)

    def test_cancel_logs_purge_run_cancelled_action(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.models.user_history import UserHistory
        user = applicant_user_factory(suffix='canlog')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        svc.cancel_purge_run(run.run_id, canceller_user_id=postgrad_admin.id)

        h = UserHistory.query.filter_by(
            user_id=user.id, action='purge_run_cancelled'
        ).first()
        assert h is not None

    def test_cancel_raises_for_nonexistent_run(self, app, postgrad_admin):
        _commit()
        with pytest.raises(svc.PurgeRunNotFound):
            svc.cancel_purge_run('no-run', canceller_user_id=postgrad_admin.id)


# ---------------------------------------------------------------------------
# sweep_expired_runs
# ---------------------------------------------------------------------------

class TestSweepExpiredRuns:
    def test_sweep_marks_old_runs_expired(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.utils.datetime_utils import now_local
        user = applicant_user_factory(suffix='sweep1')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        # Force expires_at into the past
        run.expires_at = now_local() - timedelta(days=1)
        db.session.commit()

        count = svc.sweep_expired_runs()
        assert count >= 1

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        assert refreshed.status == 'expired'

    def test_sweep_does_not_touch_terminal_runs(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.utils.datetime_utils import now_local
        user = applicant_user_factory(suffix='sweepterm')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        run.status = 'purged'
        run.expires_at = now_local() - timedelta(days=1)
        db.session.commit()

        svc.sweep_expired_runs()

        db.session.expire_all()
        refreshed = PurgeRun.query.filter_by(run_id=run.run_id).first()
        # Must remain 'purged', not reset to 'expired'
        assert refreshed.status == 'purged'

    def test_sweep_returns_zero_when_nothing_to_expire(
        self, app
    ):
        _commit()
        count = svc.sweep_expired_runs()
        assert count == 0

    def test_sweep_deletes_zip_for_expired_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        from app.utils.datetime_utils import now_local
        user = applicant_user_factory(suffix='sweepzip')
        up, sub = make_applicant(user, status='expired', with_file=True)
        _commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )
        zip_path = Path(run.archive_path)
        assert zip_path.exists()

        run.expires_at = now_local() - timedelta(days=1)
        db.session.commit()

        svc.sweep_expired_runs()

        assert not zip_path.exists()


# ---------------------------------------------------------------------------
# UserHistoryService ACTIONS validation (regression for purge_run_* entries)
# ---------------------------------------------------------------------------

class TestPurgeActionsInUserHistory:
    """Verify the four purge action codenames are registered in ACTIONS."""

    def test_purge_run_created_is_valid_action(self, app):
        from app.services.user_history_service import UserHistoryService
        assert 'purge_run_created' in UserHistoryService.ACTIONS

    def test_purge_run_downloaded_is_valid_action(self, app):
        from app.services.user_history_service import UserHistoryService
        assert 'purge_run_downloaded' in UserHistoryService.ACTIONS

    def test_purge_run_confirmed_is_valid_action(self, app):
        from app.services.user_history_service import UserHistoryService
        assert 'purge_run_confirmed' in UserHistoryService.ACTIONS

    def test_purge_run_cancelled_is_valid_action(self, app):
        from app.services.user_history_service import UserHistoryService
        assert 'purge_run_cancelled' in UserHistoryService.ACTIONS

    def test_user_program_has_no_created_at_attribute(self, app):
        """Regression: UserProgram must not have created_at (only updated_at)."""
        import inspect
        cols = {c.key for c in UserProgram.__table__.columns}
        assert 'created_at' not in cols
        assert 'updated_at' in cols

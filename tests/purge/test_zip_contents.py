# tests/purge/test_zip_contents.py
"""
Tests that verify the internal structure of the ZIP produced by create_purge_run.

Checks:
  - manifest.json: required keys, correct values, no deprecated fields.
  - summary.csv: header row exactly matches spec, one data row per UP.
  - documents/: each Submission with a file on disk gets included.
  - Multiple UPs: each gets its own documents/ subdirectory.
"""

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from app import db
from app.models.user_program import UserProgram
import app.services.applicant_archive_service as svc

from tests.purge.conftest import _write_fake_file


EXPECTED_CSV_HEADER = [
    'user_program_id', 'user_id', 'full_name', 'email',
    'program', 'admission_status', 'admission_period',
    'files_count', 'total_size_bytes',
]


def _open_zip(run) -> zipfile.ZipFile:
    return zipfile.ZipFile(run.archive_path, 'r')


# ---------------------------------------------------------------------------
# manifest.json
# ---------------------------------------------------------------------------

class TestManifestJson:
    def test_manifest_top_level_keys(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_keys')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
            notes='manifest keys test',
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        for key in ('run_id', 'purge_type', 'initiated_at', 'initiated_by_id',
                    'item_count', 'items'):
            assert key in manifest, f'Missing top-level key in manifest: {key}'

    def test_manifest_run_id_matches_run(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_rid')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        assert manifest['run_id'] == run.run_id

    def test_manifest_item_count_matches_ups(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_cnt')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        assert manifest['item_count'] == 1
        assert len(manifest['items']) == 1

    def test_manifest_item_has_user_block(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_user')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        item = manifest['items'][0]
        assert 'user' in item
        user_block = item['user']
        for key in ('id', 'first_name', 'last_name', 'email'):
            assert key in user_block, f'Missing key in user block: {key}'
        assert user_block['email'] == user.email

    def test_manifest_item_has_user_program_block(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_up')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        up_block = manifest['items'][0]['user_program']
        assert 'admission_status' in up_block
        assert 'updated_at' in up_block
        # Regression: created_at must NOT appear (UserProgram has no created_at)
        assert 'created_at' not in up_block

    def test_manifest_item_has_submissions_list(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_subs')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        submissions = manifest['items'][0]['submissions']
        assert isinstance(submissions, list)
        assert len(submissions) >= 1
        s = submissions[0]
        for key in ('id', 'archive_id', 'program_step_id', 'file_path', 'status'):
            assert key in s, f'Missing key in submission block: {key}'

    def test_manifest_item_has_history_list(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        """
        The manifest is built before logging purge_run_created, so history in
        the ZIP captures the user's pre-existing actions only. The field must
        exist and be a list (possibly empty for a brand-new applicant).
        """
        user = applicant_user_factory(suffix='mf_hist')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        history = manifest['items'][0]['history']
        assert isinstance(history, list)

    def test_manifest_initiated_by_id_correct(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='mf_iby')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            manifest = json.loads(zf.read('manifest.json'))

        assert manifest['initiated_by_id'] == postgrad_admin.id


# ---------------------------------------------------------------------------
# summary.csv
# ---------------------------------------------------------------------------

class TestSummaryCsv:
    def _read_csv(self, run) -> list:
        with _open_zip(run) as zf:
            content = zf.read('summary.csv').decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        return list(reader)

    def test_csv_header_row_exact_match(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='csv_hdr')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        rows = self._read_csv(run)
        assert rows[0] == EXPECTED_CSV_HEADER

    def test_csv_has_one_data_row_per_up(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='csv_row')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        rows = self._read_csv(run)
        # Header + 1 data row
        assert len(rows) == 2

    def test_csv_data_row_values(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='csv_vals')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        rows = self._read_csv(run)
        row = rows[1]
        assert row[0] == str(up.id)            # user_program_id
        assert row[1] == str(user.id)          # user_id
        assert user.email in row               # email somewhere in row
        assert 'expired' in row               # admission_status

    def test_csv_two_ups_produce_two_data_rows(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        u1 = applicant_user_factory(suffix='csv_2a')
        u2 = applicant_user_factory(suffix='csv_2b')
        up1, _ = make_applicant(u1, status='expired', with_file=True)
        up2, _ = make_applicant(u2, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up1.id, up2.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        rows = self._read_csv(run)
        # Header + 2 data rows
        assert len(rows) == 3

    def test_csv_files_count_and_size_present(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='csv_size')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        rows = self._read_csv(run)
        row = rows[1]
        # files_count (index 7) and total_size_bytes (index 8) must be numeric
        assert int(row[7]) >= 1
        assert int(row[8]) > 0


# ---------------------------------------------------------------------------
# documents/ entries
# ---------------------------------------------------------------------------

class TestDocumentsInZip:
    def test_documents_subdirectory_exists(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='doc_sub')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            names = zf.namelist()
        doc_entries = [n for n in names if n.startswith('documents/')]
        assert len(doc_entries) >= 1

    def test_document_path_contains_user_id(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='doc_uid')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            names = zf.namelist()
        doc_entries = [n for n in names if n.startswith('documents/')]
        assert any(f'user_{user.id}' in n for n in doc_entries)

    def test_no_document_entry_when_file_not_on_disk(
        self, app, applicant_user_factory, make_applicant, postgrad_admin,
        upload_root
    ):
        user = applicant_user_factory(suffix='doc_nodisk')
        up, sub = make_applicant(user, status='expired', with_file=True)
        # Delete the file before creating the run
        (upload_root / sub.file_path).unlink()
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            names = zf.namelist()
        doc_entries = [n for n in names if n.startswith('documents/')]
        assert len(doc_entries) == 0

    def test_multiple_ups_each_have_own_doc_folder(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        u1 = applicant_user_factory(suffix='doc_mu1')
        u2 = applicant_user_factory(suffix='doc_mu2')
        up1, _ = make_applicant(u1, status='expired', with_file=True)
        up2, _ = make_applicant(u2, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up1.id, up2.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            names = zf.namelist()
        u1_docs = [n for n in names if f'user_{u1.id}' in n]
        u2_docs = [n for n in names if f'user_{u2.id}' in n]
        assert len(u1_docs) >= 1
        assert len(u2_docs) >= 1

    def test_document_content_is_readable(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        """Ensures ZIP entries are not corrupt (readable bytes match disk bytes)."""
        user = applicant_user_factory(suffix='doc_bytes')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        from app.config import Config
        disk_path = Path(str(app.config['UPLOAD_FOLDER'])) / sub.file_path
        original_bytes = disk_path.read_bytes()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        with _open_zip(run) as zf:
            names = zf.namelist()
            doc_entries = [n for n in names if n.startswith('documents/')]
            assert len(doc_entries) >= 1
            zipped_bytes = zf.read(doc_entries[0])

        assert zipped_bytes == original_bytes


# ---------------------------------------------------------------------------
# ZIP integrity
# ---------------------------------------------------------------------------

class TestZipIntegrity:
    def test_zip_is_valid_and_not_corrupt(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='zip_ok')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        # zipfile.testzip() returns None if no errors
        with zipfile.ZipFile(run.archive_path, 'r') as zf:
            bad = zf.testzip()
        assert bad is None

    def test_sha256_on_run_matches_actual_file(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        import hashlib
        user = applicant_user_factory(suffix='zip_sha')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        h = hashlib.sha256()
        with open(run.archive_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        assert h.hexdigest() == run.archive_sha256

    def test_archive_size_bytes_matches_actual_file(
        self, app, applicant_user_factory, make_applicant, postgrad_admin
    ):
        user = applicant_user_factory(suffix='zip_size')
        up, sub = make_applicant(user, status='expired', with_file=True)
        db.session.commit()

        run = svc.create_purge_run(
            user_program_ids=[up.id],
            purge_type='admission_expired_with_files',
            initiated_by_id=postgrad_admin.id,
        )

        actual_size = Path(run.archive_path).stat().st_size
        assert run.archive_size_bytes == actual_size
